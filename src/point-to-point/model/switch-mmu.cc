#include "switch-mmu.h"

#include <fstream>
#include <iostream>
#include <cmath>

#include "ns3/assert.h"
#include "ns3/boolean.h"
#include "ns3/broadcom-node.h"
#include "ns3/double.h"
#include "ns3/global-value.h"
#include "ns3/log.h"
#include "ns3/object-vector.h"
#include "ns3/packet.h"
#include "ns3/random-variable.h"
#include "ns3/simulator.h"
#include "ns3/uinteger.h"

NS_LOG_COMPONENT_DEFINE("SwitchMmu");
namespace ns3 {

// CPEM Static counters
uint64_t SwitchMmu::m_cpemFeedbackSent = 0;
uint64_t SwitchMmu::m_cpemFeedbackRecv = 0;
uint64_t SwitchMmu::m_cpemRateAdjustments = 0;

TypeId SwitchMmu::GetTypeId(void) {
    static TypeId tid =
        TypeId("ns3::SwitchMmu")
            .SetParent<Object>()
            .AddConstructor<SwitchMmu>()
            .AddAttribute("IngressAlpha", "Broadcom Ingress alpha", DoubleValue(0.0625),
                          MakeDoubleAccessor(&SwitchMmu::m_pg_shared_alpha_cell),
                          MakeDoubleChecker<double>())
            .AddAttribute("EgressAlpha", "Broadcom Egress alpha", DoubleValue(1.),
                          MakeDoubleAccessor(&SwitchMmu::m_pg_shared_alpha_cell_egress),
                          MakeDoubleChecker<double>())
            .AddAttribute("DynamicThreshold", "Broadcom Egress alpha", BooleanValue(true),
                          MakeBooleanAccessor(&SwitchMmu::SetDynamicThreshold,
                                              &SwitchMmu::GetDynamicThreshold),
                          MakeBooleanChecker())
            .AddAttribute(
                "MaxTotalBufferPerPort",
                "Maximum buffer size of MMU per port in bytes (12-port switch: 12 * 375kB = 4.5MB)",
                UintegerValue(375 * 1000),
                MakeUintegerAccessor(&SwitchMmu::SetMaxBufferBytesPerPort,
                                     &SwitchMmu::GetMaxBufferBytesPerPort),
                MakeUintegerChecker<uint32_t>())
            .AddAttribute(
                "ActivePortCnt", "Number of active switch ports", UintegerValue(12),
                MakeUintegerAccessor(&SwitchMmu::SetActivePortCnt, &SwitchMmu::GetActivePortCnt),
                MakeUintegerChecker<uint32_t>())
            .AddAttribute(
                "PGHeadroomLimit", "Headroom Limit per PG",
                UintegerValue(12500 + 2 * MTU),  // 2*(LinkDelay*Bandwidth+MTU) 2*1us*450Gbps+2*MTU
                MakeUintegerAccessor(&SwitchMmu::SetPgHdrmLimit, &SwitchMmu::GetPgHdrmLimit),
                MakeUintegerChecker<uint32_t>());
    return tid;
}
SwitchMmu::SwitchMmu(void) {
    // Default buffer size: 375kB per active ports
    // 12-port switch: 12 * 375kB = 4.5MB
    // 32-port switch: 32 * 375kB = 12MB
    // m_maxBufferBytes = 4500 * 1000; //Originally: 9MB Current:4.5MB
    m_uniform_random_var.SetStream(0);

    // dynamic threshold
    m_dynamicth = false;

    InitSwitch();
}

void SwitchMmu::InitSwitch(void) {
    m_maxBufferBytes = m_staticMaxBufferBytes ? m_staticMaxBufferBytes
                                              : (m_maxBufferBytesPerPort * m_activePortCnt);
    m_usedTotalBytes = 0;

    if (m_dynamicth) {
        m_pg_shared_limit_cell = m_maxBufferBytes;  // using dynamic threshold, we don't respect the
                                                    // static thresholds anymore
        m_port_max_shared_cell = m_maxBufferBytes;
    } else {
        m_pg_shared_limit_cell = 20 * MTU;    // max buffer for an ingress pg
        m_port_max_shared_cell = 4800 * MTU;  // max buffer for an ingress port
    }

    for (uint32_t i = 0; i < pCnt; i++)  // port 0 is not used
    {
        m_usedIngressPortBytes[i] = 0;
        m_usedEgressPortBytes[i] = 0;
        for (uint32_t j = 0; j < qCnt; j++) {
            m_usedIngressPGBytes[i][j] = 0;
            m_usedIngressPGHeadroomBytes[i][j] = 0;
            m_usedEgressQMinBytes[i][j] = 0;
            m_usedEgressQSharedBytes[i][j] = 0;
        }
    }
    for (int i = 0; i < 4; i++) {
        m_usedIngressSPBytes[i] = 0;
        m_usedEgressSPBytes[i] = 0;
    }
    // ingress params
    m_buffer_cell_limit_sp = 4000 * MTU;  // ingress sp buffer threshold
    // m_buffer_cell_limit_sp_shared=4000*MTU; //ingress sp buffer shared threshold, nonshare ->
    // share
    m_pg_min_cell = MTU;    // ingress pg guarantee
    m_port_min_cell = MTU;  // ingress port guarantee
    // m_pg_hdrm_limit = 103000; //2*10us*40Gbps+2*1.5kB //106 * MTU; //ingress pg headroom // set
    // dynamically
    m_port_max_pkt_size = 100 * MTU;  // ingress global headroom
    uint32_t total_m_pg_hdrm_limit = 0;
    for (int i = 0; i < m_activePortCnt; i++) total_m_pg_hdrm_limit += m_pg_hdrm_limit[i];
    m_buffer_cell_limit_sp =
        m_maxBufferBytes - total_m_pg_hdrm_limit -
        (m_activePortCnt)*std::max(qCnt * m_pg_min_cell,
                                   m_port_min_cell);  // 12000 * MTU; //ingress sp buffer threshold
    // still needs reset limits..
    m_port_min_cell_off = 4700 * MTU;
    m_pg_shared_limit_cell_off = m_pg_shared_limit_cell - 2 * MTU;

    // egress params
    m_op_buffer_shared_limit_cell =
        m_maxBufferBytes -
        (m_activePortCnt)*std::max(
            qCnt * m_pg_min_cell,
            m_port_min_cell);  // m_maxBufferBytes; //per egress sp limit, //maxBufferBytes(375KB *
                               // activePortNumber) - activePortNumber * (MTU * 8) ~ 367KB *
                               // activePortNumber
    m_op_uc_port_config_cell = m_maxBufferBytes;  // per egress port limit
    m_q_min_cell = 1 + MTU;
    m_op_uc_port_config1_cell = m_maxBufferBytes;

    m_port_shared_alpha_cell = 128;  // not used for now. not sure whether this is used on switches
    m_pg_shared_alpha_cell_off_diff = 16;
    m_port_shared_alpha_cell_off_diff = 16;
    m_log_start = 2.1;
    m_log_end = 2.2;
    m_log_step = 0.00001;
}

bool SwitchMmu::CheckIngressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize) {
    NS_ASSERT(m_pg_shared_alpha_cell > 0);

    if (m_usedTotalBytes + psize > m_maxBufferBytes)  // buffer full, usually should not reach here.
    {
        std::cerr << "WARNING: Drop because ingress buffer full\n";
        return false;
    }
    if (m_usedIngressPGBytes[port][qIndex] + psize > m_pg_min_cell &&
        m_usedIngressPortBytes[port] + psize >
            m_port_min_cell)  // exceed guaranteed, use share buffer
    {
        if (m_usedIngressSPBytes[GetIngressSP(port, qIndex)] >
            m_buffer_cell_limit_sp)  // check if headroom is already being used
        {
            if (m_usedIngressPGHeadroomBytes[port][qIndex] + psize >
                m_pg_hdrm_limit[port])  // exceed headroom space
            {
                if (m_PFCenabled) {
                    std::cerr << "WARNING: Drop because ingress headroom full:"
                              << m_usedIngressPGHeadroomBytes[port][qIndex] << "\t"
                              << m_pg_hdrm_limit << "\n";
                }
                return false;
            }
        }
    }
    return true;
}

bool SwitchMmu::CheckEgressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize) {
    NS_ASSERT(m_pg_shared_alpha_cell_egress > 0);

    // PFC OFF Nothing
    bool threshold = true;
    if (m_usedEgressSPBytes[GetEgressSP(port, qIndex)] + psize >
        m_op_buffer_shared_limit_cell)  // exceed the sp limit
    {
        std::cerr << "WARNING: Drop because egress SP buffer full (exceed the sp limit), "
                  << Simulator::Now() << std::endl;
        return false;
    }
    if (m_usedEgressPortBytes[port] + psize > m_op_uc_port_config_cell)  // exceed the port limit
    {
        std::cerr << "WARNING: Drop because egress Port buffer full (exceed the port limit), "
                  << Simulator::Now() << std::endl;
        return false;
    }
    if (m_usedEgressQSharedBytes[port][qIndex] + psize >
        m_op_uc_port_config1_cell)  // exceed the queue limit
    {
        std::cerr << "WARNING: Drop because egress Q buffer full (exceed the queue limit), "
                  << Simulator::Now() << std::endl;
        return false;
    }

    if ((double)m_usedEgressQSharedBytes[port][qIndex] + psize >
        m_pg_shared_alpha_cell_egress * ((double)m_op_buffer_shared_limit_cell -
                                         m_usedEgressSPBytes[GetEgressSP(port, qIndex)])) {
#if (SLB_DEBUG == true)
        // std::cerr << "WARNING: Drop because egress DT threshold exceed, Port:" << port
        //           << ", Queue:" << qIndex
        //           << ", QlenInfo:"
        //           << ((double)m_usedEgressQSharedBytes[port][qIndex] + psize) << " > "
        //           << (m_pg_shared_alpha_cell_egress * ((double)m_op_buffer_shared_limit_cell -
        //           m_usedEgressSPBytes[GetEgressSP(port, qIndex)]))
        //           << ". Natural if not using PFC"
        //           << std::endl;
#endif
        threshold = false;
        // drop because it exceeds threshold
    }
    return threshold;
}
void SwitchMmu::UpdateIngressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize) {
    m_usedTotalBytes += psize;  // count total buffer usage
    m_usedIngressSPBytes[GetIngressSP(port, qIndex)] += psize;
    m_usedIngressPortBytes[port] += psize;
    m_usedIngressPGBytes[port][qIndex] += psize;
    if (m_usedIngressSPBytes[GetIngressSP(port, qIndex)] >
        m_buffer_cell_limit_sp)  // begin to use headroom buffer
    {
        m_usedIngressPGHeadroomBytes[port][qIndex] += psize;
    }
}

void SwitchMmu::UpdateEgressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize) {
    if (m_usedEgressQMinBytes[port][qIndex] + psize < m_q_min_cell)  // guaranteed
    {
        m_usedEgressQMinBytes[port][qIndex] += psize;
        m_usedEgressPortBytes[port] = m_usedEgressPortBytes[port] + psize;
        return;
    } else {
        /*
        2 case
        First, when there is left space in q_min_cell, and we should use remaining space in
        q_min_cell and add rest to the shared_pool Second, just adding to shared pool
        */
        if (m_usedEgressQMinBytes[port][qIndex] != m_q_min_cell) {
            m_usedEgressQSharedBytes[port][qIndex] = m_usedEgressQSharedBytes[port][qIndex] +
                                                     psize + m_usedEgressQMinBytes[port][qIndex] -
                                                     m_q_min_cell;
            m_usedEgressPortBytes[port] =
                m_usedEgressPortBytes[port] +
                psize;  //+ m_usedEgressQMinBytes[port][qIndex] - m_q_min_cell ;
            m_usedEgressSPBytes[GetEgressSP(port, qIndex)] =
                m_usedEgressSPBytes[GetEgressSP(port, qIndex)] + psize +
                m_usedEgressQMinBytes[port][qIndex] - m_q_min_cell;
            m_usedEgressQMinBytes[port][qIndex] = m_q_min_cell;

        } else {
            m_usedEgressQSharedBytes[port][qIndex] += psize;
            m_usedEgressPortBytes[port] += psize;
            m_usedEgressSPBytes[GetEgressSP(port, qIndex)] += psize;
        }
    }
}
void SwitchMmu::RemoveFromIngressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize) {
    if (m_usedTotalBytes < psize) {
        m_usedTotalBytes = psize;
        std::cerr << "Warning : Illegal Remove" << std::endl;
    }
    if (m_usedIngressSPBytes[GetIngressSP(port, qIndex)] < psize) {
        m_usedIngressSPBytes[GetIngressSP(port, qIndex)] = psize;
        std::cerr << "Warning : Illegal Remove" << std::endl;
    }
    if (m_usedIngressSPBytes[GetIngressSP(port, qIndex)] < psize) {
        m_usedIngressSPBytes[GetIngressSP(port, qIndex)] = psize;
        std::cerr << "Warning : Illegal Remove" << std::endl;
    }
    if (m_usedIngressPortBytes[port] < psize) {
        m_usedIngressPortBytes[port] = psize;
        std::cerr << "Warning : Illegal Remove" << std::endl;
    }
    if (m_usedIngressPGBytes[port][qIndex] < psize) {
        m_usedIngressPGBytes[port][qIndex] = psize;
        std::cerr << "Warning : Illegal Remove" << std::endl;
    }
    m_usedTotalBytes -= psize;
    m_usedIngressSPBytes[GetIngressSP(port, qIndex)] -= psize;
    m_usedIngressPortBytes[port] -= psize;
    m_usedIngressPGBytes[port][qIndex] -= psize;
    if ((double)m_usedIngressPGHeadroomBytes[port][qIndex] - psize > 0)
        m_usedIngressPGHeadroomBytes[port][qIndex] -= psize;
    else
        m_usedIngressPGHeadroomBytes[port][qIndex] = 0;
}
void SwitchMmu::RemoveFromEgressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize) {
    if (m_usedEgressQMinBytes[port][qIndex] < m_q_min_cell)  // guaranteed
    {
        if (m_usedEgressQMinBytes[port][qIndex] < psize) {
            std::cerr << "STOP overflow\n";
        }
        m_usedEgressQMinBytes[port][qIndex] -= psize;
        m_usedEgressPortBytes[port] -= psize;
        return;
    } else {
        /*
        2 case
        First, when packet was using both qminbytes and qsharedbytes we should substract from each
        one Second, just subtracting shared pool
        */

        // first case
        if (m_usedEgressQMinBytes[port][qIndex] == m_q_min_cell &&
            m_usedEgressQSharedBytes[port][qIndex] < psize) {
            m_usedEgressQMinBytes[port][qIndex] = m_usedEgressQMinBytes[port][qIndex] +
                                                  m_usedEgressQSharedBytes[port][qIndex] - psize;
            m_usedEgressSPBytes[GetEgressSP(port, qIndex)] =
                m_usedEgressSPBytes[GetEgressSP(port, qIndex)] -
                m_usedEgressQSharedBytes[port][qIndex];
            m_usedEgressQSharedBytes[port][qIndex] = 0;
            if (m_usedEgressPortBytes[port] < psize) {
                std::cerr << "STOP overflow\n";
            }
            m_usedEgressPortBytes[port] -= psize;

        } else {
            if (m_usedEgressQSharedBytes[port][qIndex] < psize ||
                m_usedEgressPortBytes[port] < psize ||
                m_usedEgressSPBytes[GetEgressSP(port, qIndex)] < psize) {
                std::cerr << "STOP overflow\n";
            }
            m_usedEgressQSharedBytes[port][qIndex] -= psize;
            m_usedEgressPortBytes[port] -= psize;
            m_usedEgressSPBytes[GetEgressSP(port, qIndex)] -= psize;
        }
        return;
    }
}

void SwitchMmu::GetPauseClasses(uint32_t port, uint32_t qIndex, bool pClasses[]) {
    if (port > m_activePortCnt) {
        std::cerr << "ERROR: port is " << port << std::endl;
    }
    if (m_dynamicth) {
        for (uint32_t i = 0; i < qCnt; i++) {
            pClasses[i] = false;
            if (m_usedIngressPGBytes[port][i] <= m_pg_min_cell + m_port_min_cell) continue;

            // std::cerr << "BCM : Used=" << m_usedIngressPGBytes[port][i] << ", thresh=" <<
            // m_pg_shared_alpha_cell*((double)m_buffer_cell_limit_sp -
            // m_usedIngressSPBytes[GetIngressSP(port, qIndex)]) + m_pg_min_cell+m_port_min_cell <<
            // std::endl;

            if ((double)m_usedIngressPGBytes[port][i] - m_pg_min_cell - m_port_min_cell >
                    m_pg_shared_alpha_cell * ((double)m_buffer_cell_limit_sp -
                                              m_usedIngressSPBytes[GetIngressSP(port, qIndex)]) ||
                m_usedIngressPGHeadroomBytes[port][qIndex] != 0) {
                pClasses[i] = true;
            }
        }
    } else {
        if (m_usedIngressPortBytes[port] > m_port_max_shared_cell)  // pause the whole port
        {
            for (uint32_t i = 0; i < qCnt; i++) {
                pClasses[i] = true;
            }
            return;
        } else {
            for (uint32_t i = 0; i < qCnt; i++) {
                pClasses[i] = false;
            }
        }
        if (m_usedIngressPGBytes[port][qIndex] > m_pg_shared_limit_cell) {
            pClasses[qIndex] = true;
        }
    }
    return;
}

bool SwitchMmu::GetResumeClasses(uint32_t port, uint32_t qIndex) {
    if (!paused[port][qIndex]) return false;
    if (m_dynamicth) {
        if ((double)m_usedIngressPGBytes[port][qIndex] - m_pg_min_cell - m_port_min_cell <
                m_pg_shared_alpha_cell * ((double)m_buffer_cell_limit_sp -
                                          m_usedIngressSPBytes[GetIngressSP(port, qIndex)] -
                                          m_pg_shared_alpha_cell_off_diff) &&
            m_usedIngressPGHeadroomBytes[port][qIndex] == 0) {
            return true;
        }
    } else {
        if (m_usedIngressPGBytes[port][qIndex] < m_pg_shared_limit_cell_off &&
            m_usedIngressPortBytes[port] < m_port_min_cell_off) {
            return true;
        }
    }
    return false;
}

uint32_t SwitchMmu::GetIngressSP(uint32_t port, uint32_t pgIndex) {
    if (pgIndex == 1)
        return 1;
    else
        return 0;
}

uint32_t SwitchMmu::GetEgressSP(uint32_t port, uint32_t qIndex) {
    if (qIndex == 0)
        return 0;
    else
        return 1;
}

bool SwitchMmu::ShouldSendCN(uint32_t ifindex, uint32_t qIndex) {
    if (qIndex == 0)  // qidx=0 as highest priority
        return false;

    if (m_usedEgressQSharedBytes[ifindex][qIndex] > kmax[ifindex]) {
        return true;
    } else if (m_usedEgressQSharedBytes[ifindex][qIndex] > kmin[ifindex] &&
               kmin[ifindex] != kmax[ifindex]) {
        double p = 1.0 * (m_usedEgressQSharedBytes[ifindex][qIndex] - kmin[ifindex]) /
                   (kmax[ifindex] - kmin[ifindex]) * pmax[ifindex];
        if (m_uniform_random_var.GetValue(0, 1) < p) return true;
    }
    return false;
}

void SwitchMmu::SetBroadcomParams(
    uint32_t buffer_cell_limit_sp,  // ingress sp buffer threshold p.120
    uint32_t
        buffer_cell_limit_sp_shared,  // ingress sp buffer shared threshold p.120, nonshare -> share
    uint32_t pg_min_cell,             // ingress pg guarantee p.121					---1
    uint32_t port_min_cell,           // ingress port guarantee						---2
    uint32_t pg_shared_limit_cell,    // max buffer for an ingress pg			---3	PAUSE
    uint32_t port_max_shared_cell,    // max buffer for an ingress port		---4	PAUSE
    uint32_t pg_hdrm_limit,           // ingress pg headroom
    uint32_t port_max_pkt_size,       // ingress global headroom
    uint32_t q_min_cell,              // egress queue guaranteed buffer
    uint32_t op_uc_port_config1_cell,      // egress queue threshold
    uint32_t op_uc_port_config_cell,       // egress port threshold
    uint32_t op_buffer_shared_limit_cell,  // egress sp threshold
    uint32_t q_shared_alpha_cell, uint32_t port_share_alpha_cell, uint32_t pg_qcn_threshold) {
    m_buffer_cell_limit_sp = buffer_cell_limit_sp;
    m_buffer_cell_limit_sp_shared = buffer_cell_limit_sp_shared;
    m_pg_min_cell = pg_min_cell;
    m_port_min_cell = port_min_cell;
    m_pg_shared_limit_cell = pg_shared_limit_cell;
    m_port_max_shared_cell = port_max_shared_cell;
    for (int i = 0; i < pCnt; i++) m_pg_hdrm_limit[i] = pg_hdrm_limit;
    m_port_max_pkt_size = port_max_pkt_size;
    m_q_min_cell = q_min_cell;
    m_op_uc_port_config1_cell = op_uc_port_config1_cell;
    m_op_uc_port_config_cell = op_uc_port_config_cell;
    m_op_buffer_shared_limit_cell = op_buffer_shared_limit_cell;
    m_pg_shared_alpha_cell = q_shared_alpha_cell;
    m_port_shared_alpha_cell = port_share_alpha_cell;
}

uint32_t SwitchMmu::GetUsedBufferTotal() { return m_usedTotalBytes; }

void SwitchMmu::SetDynamicThreshold(bool v) {
    m_dynamicth = v;
    InitSwitch();
    return;
}

void SwitchMmu::ConfigEcn(uint32_t port, uint32_t _kmin, uint32_t _kmax, double _pmax) {
    kmin[port] = _kmin * 1000;
    kmax[port] = _kmax * 1000;
    pmax[port] = _pmax;
}

void SwitchMmu::SetPause(uint32_t port, uint32_t qIndex, uint32_t pause_time) {
    paused[port][qIndex] = true;
    Simulator::Cancel(resumeEvt[port][qIndex]);
    resumeEvt[port][qIndex] =
        Simulator::Schedule(MicroSeconds(pause_time), &SwitchMmu::SetResume, this, port, qIndex);
}
void SwitchMmu::SetResume(uint32_t port, uint32_t qIndex) {
    paused[port][qIndex] = false;
    Simulator::Cancel(resumeEvt[port][qIndex]);
}

void SwitchMmu::ConfigHdrm(uint32_t port, uint32_t size) {
    m_pg_hdrm_limit[port] = size;
    InitSwitch();
}
void SwitchMmu::ConfigNPort(uint32_t n_port) {
    m_activePortCnt = n_port;
    InitSwitch();
}
void SwitchMmu::ConfigBufferSize(uint32_t size) {
    // if size == 0, buffer size will be automatically decided
    m_staticMaxBufferBytes = size;
    InitSwitch();
}

/*========== Credit-based PFC Enhancement Module (CPEM) Implementation ==========*/

void SwitchMmu::CpemInitPort(uint32_t port, DataRate linkRate) {
    if (!Settings::cpem_enabled || port >= pCnt) return;
    
    m_cpemState[port].feedbackCredit = 0;
    m_cpemState[port].inflightCredit = 0;
    m_cpemState[port].inflightBytes = 0;
    m_cpemState[port].lastQueueLen = 0;
    m_cpemState[port].lastFeedbackTime = Time(0);
    m_cpemState[port].lastSendTime = Time(0);
    m_cpemState[port].effectiveRate = linkRate;
    m_cpemState[port].initialized = true;
    
    NS_LOG_DEBUG("CPEM: Initialized port " << port << " with link rate " << linkRate);
}

void SwitchMmu::CpemScheduleFeedback(uint32_t port) {
    if (!Settings::cpem_enabled || port >= pCnt) return;
    
    // Cancel any existing scheduled feedback
    if (m_cpemFeedbackEvent[port].IsRunning()) {
        Simulator::Cancel(m_cpemFeedbackEvent[port]);
    }
    
    // Schedule next feedback generation
    m_cpemFeedbackEvent[port] = Simulator::Schedule(
        NanoSeconds(Settings::cpem_feedback_interval_ns),
        &SwitchMmu::CpemGenerateFeedback, this, port);
}

void SwitchMmu::CpemGetDynamicThresholds(uint32_t port, uint32_t& threshold_low, uint32_t& threshold_high) {
    if (Settings::cpem_use_dynamic_threshold && m_dynamicth) {
        // Dynamic mode: Calculate CPEM thresholds based on PFC dynamic threshold
        // PFC threshold = m_pg_shared_alpha_cell * (m_buffer_cell_limit_sp - m_usedIngressSPBytes[SP]) + m_pg_min_cell + m_port_min_cell
        double pfcThreshold = m_pg_shared_alpha_cell * 
                             ((double)m_buffer_cell_limit_sp - m_usedIngressSPBytes[GetIngressSP(port, 0)]) + 
                             m_pg_min_cell + m_port_min_cell;
        
        threshold_low = (uint32_t)(pfcThreshold * Settings::cpem_threshold_low_ratio);
        threshold_high = (uint32_t)(pfcThreshold * Settings::cpem_threshold_high_ratio);
        
        // Ensure thresholds are reasonable
        threshold_low = std::max(threshold_low, (uint32_t)(10 * MTU));  // At least 10 MTU
        threshold_high = std::max(threshold_high, threshold_low + (uint32_t)(5 * MTU));  // High > Low + 5 MTU
    } else {
        // Fixed mode: Use configured fixed thresholds
        threshold_low = Settings::cpem_queue_threshold_low;
        threshold_high = Settings::cpem_queue_threshold_high;
    }
}

void SwitchMmu::CpemGenerateFeedback(uint32_t inPort) {
    if (!Settings::cpem_enabled || inPort >= pCnt) return;
    
    // Get current ingress queue length for this port
    uint32_t currentQueueLen = m_usedIngressPortBytes[inPort];
    
    // Calculate dynamic or fixed thresholds
    uint32_t threshold_low, threshold_high;
    CpemGetDynamicThresholds(inPort, threshold_low, threshold_high);
    
    // Only generate feedback if queue exceeds low threshold
    if (currentQueueLen < threshold_low) {
        // Queue is low, schedule next check and return
        CpemScheduleFeedback(inPort);
        return;
    }
    
    // Calculate queue gradient (change since last observation)
    int16_t gradient = (int16_t)(currentQueueLen - m_cpemState[inPort].lastQueueLen);
    m_cpemState[inPort].lastQueueLen = currentQueueLen;
    
    // Calculate credit value based on queue length and gradient (pass thresholds)
    uint16_t creditValue = CpemCalculateCreditValue(currentQueueLen, gradient, threshold_low, threshold_high);
    
    // The actual packet sending will be done by SwitchNode
    // Here we just update statistics and store the values
    m_cpemFeedbackSent++;
    
    NS_LOG_DEBUG("CPEM: Port " << inPort << " generating feedback - qlen=" << currentQueueLen 
                 << ", gradient=" << gradient << ", credit=" << creditValue);
    
    // Schedule next feedback
    CpemScheduleFeedback(inPort);
}

uint16_t SwitchMmu::CpemCalculateCreditValue(uint32_t queueLen, int16_t gradient, 
                                             uint32_t threshold_low, uint32_t threshold_high) {
    // Normalize queue length to [0, 1] based on thresholds
    double qRatio = 0.0;
    if (queueLen >= threshold_high) {
        qRatio = 1.0;
    } else if (queueLen > threshold_low) {
        qRatio = (double)(queueLen - threshold_low) / 
                 (double)(threshold_high - threshold_low);
    }
    
    // Gradient factor: positive gradient (queue growing) increases urgency
    double gradientFactor = 1.0;
    if (gradient > 0) {
        // Queue is growing, increase the credit value
        double gradientRatio = std::min((double)gradient / 
                                         (double)threshold_low, 1.0);
        gradientFactor = 1.0 + gradientRatio * 0.5;  // Max 50% increase from gradient
    } else if (gradient < 0) {
        // Queue is shrinking, slightly decrease the credit value
        double gradientRatio = std::min((double)(-gradient) / 
                                         (double)threshold_low, 1.0);
        gradientFactor = 1.0 - gradientRatio * 0.3;  // Max 30% decrease from negative gradient
    }
    
    // Calculate final credit value
    uint16_t creditValue = (uint16_t)(qRatio * gradientFactor * Settings::cpem_max_credit);
    return std::min(creditValue, (uint16_t)Settings::cpem_max_credit);
}

void SwitchMmu::CpemUpdateInflightOnSend(uint32_t port, uint64_t bytes) {
    if (!Settings::cpem_enabled || port >= pCnt) return;
    if (!m_cpemState[port].initialized) return;
    
    Time now = Simulator::Now();
    auto& state = m_cpemState[port];
    
    // Time-based decay: simulate packets "arriving" at downstream
    Time dt = now - state.lastSendTime;
    if (dt.GetNanoSeconds() > 0 && state.lastSendTime.GetNanoSeconds() > 0) {
        // Decay factor based on estimated RTT (use feedback interval as proxy)
        double decayTime = Settings::cpem_feedback_interval_ns * 2.0;  // ~2x feedback interval
        double decay = std::exp(-(double)dt.GetNanoSeconds() / decayTime);
        state.inflightBytes = (uint64_t)(decay * state.inflightBytes);
    }
    
    // Add newly sent bytes
    state.inflightBytes += bytes;
    state.lastSendTime = now;
    
    // Convert to credit value using dynamic thresholds
    uint32_t threshold_low, threshold_high;
    CpemGetDynamicThresholds(port, threshold_low, threshold_high);
    double maxInflightBytes = threshold_high * 2.0;  // Max expected in-flight
    state.inflightCredit = (double)state.inflightBytes / maxInflightBytes * Settings::cpem_max_credit;
    state.inflightCredit = std::min(state.inflightCredit, (double)Settings::cpem_max_credit);
}

void SwitchMmu::CpemUpdateCreditOnFeedback(uint32_t port, uint16_t creditValue, 
                                            uint32_t queueLen, int16_t gradient) {
    if (!Settings::cpem_enabled || port >= pCnt) return;
    if (!m_cpemState[port].initialized) return;
    
    Time now = Simulator::Now();
    auto& state = m_cpemState[port];
    
    // EWMA update for feedback credit
    double alpha = Settings::cpem_credit_decay_alpha;
    double newCredit = (double)creditValue;
    
    // Add gradient bonus/penalty using dynamic thresholds
    if (gradient > 0) {
        // Queue is growing at downstream - increase urgency
        uint32_t threshold_low, threshold_high;
        CpemGetDynamicThresholds(port, threshold_low, threshold_high);
        double gradientBonus = std::min((double)gradient / 
                                        (double)threshold_low * 
                                        Settings::cpem_max_credit * 0.2,
                                        (double)Settings::cpem_max_credit * 0.3);
        newCredit += gradientBonus;
    }
    
    state.feedbackCredit = alpha * state.feedbackCredit + (1 - alpha) * newCredit;
    state.feedbackCredit = std::min(state.feedbackCredit, (double)Settings::cpem_max_credit);
    state.lastFeedbackTime = now;
    
    // When feedback arrives, reduce in-flight estimate (data has arrived)
    state.inflightBytes = (uint64_t)(state.inflightBytes * 0.5);
    
    m_cpemFeedbackRecv++;
    
    NS_LOG_DEBUG("CPEM: Port " << port << " received feedback - credit=" << creditValue 
                 << ", newFeedbackCredit=" << state.feedbackCredit);
}

double SwitchMmu::CpemGetEffectiveCredit(uint32_t port) {
    if (!Settings::cpem_enabled || port >= pCnt) return 0.0;
    if (!m_cpemState[port].initialized) return 0.0;
    
    Time now = Simulator::Now();
    auto& state = m_cpemState[port];
    
    // Calculate feedback age - older feedback is less reliable
    Time feedbackAge = now - state.lastFeedbackTime;
    double feedbackAgeNs = feedbackAge.GetNanoSeconds();
    double decayTime = Settings::cpem_feedback_interval_ns * 3.0;  // ~3x feedback interval
    double feedbackWeight = std::exp(-feedbackAgeNs / decayTime);
    
    // If feedback is very old (no recent feedback), rely more on in-flight estimate
    if (feedbackAgeNs > Settings::cpem_feedback_interval_ns * 10) {
        feedbackWeight = 0.2;  // Minimal weight for very old feedback
    }
    
    // Combine feedback credit and in-flight credit
    double effectiveCredit = feedbackWeight * state.feedbackCredit + 
                             Settings::cpem_inflight_discount * state.inflightCredit;
    
    return std::min(effectiveCredit, (double)Settings::cpem_max_credit);
}

DataRate SwitchMmu::CpemGetAdjustedRate(uint32_t port, DataRate linkRate) {
    if (!Settings::cpem_enabled || port >= pCnt) return linkRate;
    if (!m_cpemState[port].initialized) return linkRate;
    
    double credit = CpemGetEffectiveCredit(port);
    double creditRatio = credit / Settings::cpem_max_credit;
    
    // Calculate rate ratio: higher credit = lower rate
    double rateRatio = 1.0 - creditRatio * Settings::cpem_credit_to_rate_gain;
    rateRatio = std::max(rateRatio, Settings::cpem_min_rate_ratio);
    
    DataRate adjustedRate = DataRate((uint64_t)(linkRate.GetBitRate() * rateRatio));
    
    // Update state
    if (m_cpemState[port].effectiveRate != adjustedRate) {
        m_cpemState[port].effectiveRate = adjustedRate;
        m_cpemRateAdjustments++;
        NS_LOG_DEBUG("CPEM: Port " << port << " rate adjusted to " << adjustedRate 
                     << " (credit=" << credit << ", ratio=" << rateRatio << ")");
    }
    
    return adjustedRate;
}

NS_OBJECT_ENSURE_REGISTERED(SwitchMmu);

}  // namespace ns3
