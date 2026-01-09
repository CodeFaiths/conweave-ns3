#ifndef SWITCH_MMU_H
#define SWITCH_MMU_H

#include <ns3/node.h>
#include <ns3/random-variable-stream.h>

#include <list>
#include <unordered_map>
#include <deque>

#include "ns3/conga-routing.h"
#include "ns3/conweave-routing.h"
#include "ns3/letflow-routing.h"
#include "ns3/settings.h"
#include "ns3/data-rate.h"


namespace ns3 {

class Packet;

class SwitchMmu : public Object {
   public:
    static const unsigned qCnt = 8;    // Number of queues/priorities used
    static const unsigned pCnt = 128;  // port 0 is not used so + 1	// Number of ports used
    static const unsigned MTU = 1048;  // 1000 + headers

    static TypeId GetTypeId(void);

    SwitchMmu(void);
    void InitSwitch(void);

    bool CheckIngressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize);
    bool CheckEgressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize);
    void UpdateIngressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize);
    void UpdateEgressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize);
    void RemoveFromIngressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize);
    void RemoveFromEgressAdmission(uint32_t port, uint32_t qIndex, uint32_t psize);

    void SetPause(uint32_t port, uint32_t qIndex, uint32_t pause_time);
    void SetResume(uint32_t port, uint32_t qIndex);
    void GetPauseClasses(uint32_t port, uint32_t qIndex, bool pClasses[]);
    bool GetResumeClasses(uint32_t port, uint32_t qIndex);

    void SetBroadcomParams(uint32_t buffer_cell_limit_sp,  // ingress sp buffer threshold p.120
                           uint32_t buffer_cell_limit_sp_shared,  // ingress sp buffer shared
                                                                  // threshold, nonshare -> share
                           uint32_t pg_min_cell,                  // ingress pg guarantee
                           uint32_t port_min_cell,                // ingress port guarantee
                           uint32_t pg_shared_limit_cell,         // max buffer for an ingress pg
                           uint32_t port_max_shared_cell,         // max buffer for an ingress port
                           uint32_t pg_hdrm_limit,                // ingress pg headroom
                           uint32_t port_max_pkt_size,            // ingress global headroom
                           uint32_t q_min_cell,                   // egress queue guaranteed buffer
                           uint32_t op_uc_port_config1_cell,      // egress queue threshold
                           uint32_t op_uc_port_config_cell,       // egress port threshold
                           uint32_t op_buffer_shared_limit_cell,  // egress sp threshold
                           uint32_t q_shared_alpha_cell, uint32_t port_share_alpha_cell,
                           uint32_t pg_qcn_threshold);

    void SetMarkingThreshold(uint32_t kmin, uint32_t kmax, double pmax);

    bool ShouldSendCN(uint32_t ifindex, uint32_t qIndex);

    uint32_t GetUsedBufferTotal();

    void SetDynamicThreshold(bool value);
    bool GetDynamicThreshold(void) const { return m_dynamicth; }

    // void printQueueStat(std::ostream& os, uint32_t port);

    void ConfigEcn(uint32_t port, uint32_t _kmin, uint32_t _kmax, double _pmax);
    void ConfigBufferSize(uint32_t size);

    void ConfigHdrm(uint32_t port, uint32_t size);
    void ConfigNPort(uint32_t n_port);

    uint32_t GetIngressSP(uint32_t port, uint32_t pgIndex);
    uint32_t GetEgressSP(uint32_t port, uint32_t qIndex);

    // config
    uint32_t node_id;

    uint32_t kmin[pCnt], kmax[pCnt];
    double pmax[pCnt];
    uint32_t paused[pCnt][qCnt];
    EventId resumeEvt[pCnt][qCnt];
    bool m_pause_remote[pCnt][qCnt];

    uint32_t pfc_a_shift[pCnt];         // legacy: not used anymore
    uint32_t egress_bytes[pCnt][qCnt];  // legacy: not used anymore

    uint32_t GetActivePortCnt(void) const { return m_activePortCnt; }
    void SetActivePortCnt(uint32_t v) {
        m_activePortCnt = v;
        InitSwitch();
    }

    uint32_t GetMmuBufferBytes(void) const { return m_maxBufferBytes; }
    uint32_t GetMaxBufferBytesPerPort(void) const { return m_maxBufferBytesPerPort; }
    void SetMaxBufferBytesPerPort(uint32_t v) {
        m_maxBufferBytesPerPort = v;
        InitSwitch();
    }

    uint32_t GetPgHdrmLimit(void) const { return m_pg_hdrm_limit[0]; }
    void SetPgHdrmLimit(uint32_t v) {
        for (int i = 0; i < pCnt; i++) m_pg_hdrm_limit[i] = v;
        InitSwitch();
    }

    /*------------ Conga Objects-------------*/
    CongaRouting m_congaRouting;

    /*------------ Letflow Objects-------------*/
    LetflowRouting m_letflowRouting;

    /*------------ ConWeave Objects-------------*/
    ConWeaveRouting m_conweaveRouting;

    /*========== Credit-based PFC Enhancement Module (CPEM) ==========*/
    /**
     * @brief Get ingress port buffer usage
     */
    uint32_t GetIngressPortBytes(uint32_t port) const {
        if (port < pCnt) return m_usedIngressPortBytes[port];
        return 0;
    }

    /**
     * @brief Get egress port buffer usage
     */
    uint32_t GetEgressPortBytes(uint32_t port) const {
        if (port < pCnt) return m_usedEgressPortBytes[port];
        return 0;
    }

    /**
     * @brief Get ingress queue (PG) buffer usage
     */
    uint32_t GetIngressQueueBytes(uint32_t port, uint32_t qIndex) const {
        if (port < pCnt && qIndex < qCnt) return m_usedIngressPGBytes[port][qIndex];
        return 0;
    }

    /**
     * @brief Get egress queue buffer usage (min + shared)
     */
    uint32_t GetEgressQueueBytes(uint32_t port, uint32_t qIndex) const {
        if (port < pCnt && qIndex < qCnt)
            return m_usedEgressQMinBytes[port][qIndex] + m_usedEgressQSharedBytes[port][qIndex];
        return 0;
    }
    
    /**
     * @brief Port credit state for rate control
     */
    struct PortCreditState {
        double feedbackCredit;      // Credit from downstream feedback (0-MAX_CREDIT)
        double inflightCredit;      // Credit based on in-flight bytes
        uint64_t inflightBytes;     // Estimated in-flight bytes
        uint32_t lastQueueLen;      // Last observed queue length (for gradient calc)
        Time lastFeedbackTime;      // Time of last received feedback
        Time lastSendTime;          // Time of last packet sent
        DataRate effectiveRate;     // Current effective sending rate
        bool initialized;           // Whether state has been initialized
        
        PortCreditState() : feedbackCredit(0), inflightCredit(0), inflightBytes(0),
                           lastQueueLen(0), lastFeedbackTime(Time(0)), lastSendTime(Time(0)),
                           effectiveRate(DataRate(0)), initialized(false) {}
    };
    
    PortCreditState m_cpemState[pCnt];  // Credit state per port
    EventId m_cpemFeedbackEvent[pCnt];  // Feedback generation events
    
    // CPEM Methods - Downstream (feedback generation)
    void CpemInitPort(uint32_t port, DataRate linkRate);
    void CpemScheduleFeedback(uint32_t port);
    void CpemGenerateFeedback(uint32_t inPort);
    void CpemGetDynamicThresholds(uint32_t port, uint32_t& threshold_low, uint32_t& threshold_high);
    uint16_t CpemCalculateCreditValue(uint32_t queueLen, int16_t gradient, 
                                      uint32_t threshold_low, uint32_t threshold_high);
    
    // CPEM Methods - Upstream (credit processing and rate adjustment)
    void CpemUpdateInflightOnSend(uint32_t port, uint64_t bytes);
    void CpemUpdateCreditOnFeedback(uint32_t port, uint16_t creditValue, 
                                     uint32_t queueLen, int16_t gradient);
    double CpemGetEffectiveCredit(uint32_t port);
    DataRate CpemGetAdjustedRate(uint32_t port, DataRate linkRate);
    
    // CPEM Statistics
    static uint64_t m_cpemFeedbackSent;
    static uint64_t m_cpemFeedbackRecv;
    static uint64_t m_cpemRateAdjustments;

   private:
    bool m_PFCenabled;

    uint32_t m_maxBufferBytes{0};
    uint32_t m_usedTotalBytes{0};

    unsigned m_activePortCnt{0};
    uint32_t m_maxBufferBytesPerPort{0};  // use this to calculate m_maxBufferBytes
    uint32_t m_staticMaxBufferBytes{0};   // use this to calculate m_maxBufferBytes

    uint32_t m_usedIngressPGBytes[pCnt][qCnt];
    uint32_t m_usedIngressPortBytes[pCnt];
    uint32_t m_usedIngressSPBytes[4];
    uint32_t m_usedIngressPGHeadroomBytes[pCnt][qCnt];

    uint32_t m_usedEgressQMinBytes[pCnt][qCnt];
    uint32_t m_usedEgressQSharedBytes[pCnt][qCnt];
    uint32_t m_usedEgressPortBytes[pCnt];
    uint32_t m_usedEgressSPBytes[4];

    // ingress params
    uint32_t m_buffer_cell_limit_sp;  // ingress sp buffer threshold p.120
    uint32_t
        m_buffer_cell_limit_sp_shared;  // ingress sp buffer shared threshold, nonshare -> share
    uint32_t m_pg_min_cell;             // ingress pg guarantee
    uint32_t m_port_min_cell;           // ingress port guarantee
    uint32_t m_pg_shared_limit_cell;    // max buffer for an ingress pg
    uint32_t m_port_max_shared_cell;    // max buffer for an ingress port
    uint32_t m_pg_hdrm_limit[pCnt];     // ingress pg headroom
    uint32_t m_port_max_pkt_size;       // ingress global headroom
    // still needs reset limits..
    uint32_t m_port_min_cell_off;  // PAUSE off threshold
    uint32_t m_pg_shared_limit_cell_off;
    uint32_t m_global_hdrm_limit;

    // egress params
    uint32_t m_q_min_cell;                   // egress queue guaranteed buffer
    uint32_t m_op_uc_port_config1_cell;      // egress queue threshold
    uint32_t m_op_uc_port_config_cell;       // egress port threshold
    uint32_t m_op_buffer_shared_limit_cell;  // egress sp threshold

    // dynamic threshold
    double m_pg_shared_alpha_cell{0};
    double m_pg_shared_alpha_cell_egress{0};
    double m_pg_shared_alpha_cell_off_diff;
    double m_port_shared_alpha_cell;
    double m_port_shared_alpha_cell_off_diff;
    bool m_dynamicth;

    double m_log_start;
    double m_log_end;
    double m_log_step;

    UniformRandomVariable m_uniform_random_var;
};

} /* namespace ns3 */

#endif /* SWITCH_MMU_H */
