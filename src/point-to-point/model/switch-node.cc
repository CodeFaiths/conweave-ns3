#include "switch-node.h"

#include "assert.h"
#include "ns3/boolean.h"
#include "ns3/conweave-routing.h"
#include "ns3/custom-header.h"
#include "ns3/double.h"
#include "ns3/flow-id-tag.h"
#include "ns3/int-header.h"
#include "ns3/ipv4-header.h"
#include "ns3/ipv4.h"
#include "ns3/letflow-routing.h"
#include "ns3/packet.h"
#include "ns3/pause-header.h"
#include "ns3/settings.h"
#include "ns3/simulator.h"
#include "ns3/uinteger.h"
#include "ns3/credit-feedback-header.h"
#include "ppp-header.h"
#include "qbb-net-device.h"

namespace ns3 {

TypeId SwitchNode::GetTypeId(void) {
    static TypeId tid =
        TypeId("ns3::SwitchNode")
            .SetParent<Node>()
            .AddConstructor<SwitchNode>()
            .AddAttribute("EcnEnabled", "Enable ECN marking.", BooleanValue(false),
                          MakeBooleanAccessor(&SwitchNode::m_ecnEnabled), MakeBooleanChecker())
            .AddAttribute("CcMode", "CC mode.", UintegerValue(0),
                          MakeUintegerAccessor(&SwitchNode::m_ccMode),
                          MakeUintegerChecker<uint32_t>())
            .AddAttribute("AckHighPrio", "Set high priority for ACK/NACK or not", UintegerValue(0),
                          MakeUintegerAccessor(&SwitchNode::m_ackHighPrio),
                          MakeUintegerChecker<uint32_t>());
    return tid;
}

SwitchNode::SwitchNode() {
    m_ecmpSeed = m_id;
    m_isToR = false;
    m_node_type = 1;
    m_isToR = false;
    m_drill_candidate = 2;
    m_mmu = CreateObject<SwitchMmu>();
    // Conga's Callback for switch functions
    m_mmu->m_congaRouting.SetSwitchSendCallback(MakeCallback(&SwitchNode::DoSwitchSend, this));
    m_mmu->m_congaRouting.SetSwitchSendToDevCallback(
        MakeCallback(&SwitchNode::SendToDevContinue, this));
    // ConWeave's Callback for switch functions
    m_mmu->m_conweaveRouting.SetSwitchSendCallback(MakeCallback(&SwitchNode::DoSwitchSend, this));
    m_mmu->m_conweaveRouting.SetSwitchSendToDevCallback(
        MakeCallback(&SwitchNode::SendToDevContinue, this));

    for (uint32_t i = 0; i < pCnt; i++) {
        m_txBytes[i] = 0;
        m_rxBytes[i] = 0;
        m_txBytesSample[i] = 0;
        m_rxBytesSample[i] = 0;
    }
}

/**
 * @brief Load Balancing
 */
uint32_t SwitchNode::DoLbFlowECMP(Ptr<const Packet> p, const CustomHeader &ch,
                                  const std::vector<int> &nexthops) {
    // pick one next hop based on hash
    union {
        uint8_t u8[4 + 4 + 2 + 2];
        uint32_t u32[3];
    } buf;
    buf.u32[0] = ch.sip;
    buf.u32[1] = ch.dip;
    if (ch.l3Prot == 0x6)
        buf.u32[2] = ch.tcp.sport | ((uint32_t)ch.tcp.dport << 16);
    else if (ch.l3Prot == 0x11)  // XXX RDMA traffic on UDP
        buf.u32[2] = ch.udp.sport | ((uint32_t)ch.udp.dport << 16);
    else if (ch.l3Prot == 0xFC || ch.l3Prot == 0xFD)  // ACK or NACK
        buf.u32[2] = ch.ack.sport | ((uint32_t)ch.ack.dport << 16);
    else {
        std::cout << "[ERROR] Sw(" << m_id << ")," << PARSE_FIVE_TUPLE(ch)
                  << "Cannot support other protoocls than TCP/UDP (l3Prot:" << ch.l3Prot << ")"
                  << std::endl;
        assert(false && "Cannot support other protoocls than TCP/UDP");
    }

    uint32_t hashVal = EcmpHash(buf.u8, 12, m_ecmpSeed);
    uint32_t idx = hashVal % nexthops.size();
    return nexthops[idx];
}

/*-----------------CONGA-----------------*/
uint32_t SwitchNode::DoLbConga(Ptr<Packet> p, CustomHeader &ch, const std::vector<int> &nexthops) {
    return DoLbFlowECMP(p, ch, nexthops);  // flow ECMP (dummy)
}

/*-----------------Letflow-----------------*/
uint32_t SwitchNode::DoLbLetflow(Ptr<Packet> p, CustomHeader &ch,
                                 const std::vector<int> &nexthops) {
    if (m_isToR && nexthops.size() == 1) {
        if (m_isToR_hostIP.find(ch.sip) != m_isToR_hostIP.end() &&
            m_isToR_hostIP.find(ch.dip) != m_isToR_hostIP.end()) {
            return nexthops[0];  // intra-pod traffic
        }
    }

    /* ONLY called for inter-Pod traffic */
    uint32_t outPort = m_mmu->m_letflowRouting.RouteInput(p, ch);
    if (outPort == LETFLOW_NULL) {
        assert(nexthops.size() == 1);  // Receiver's TOR has only one interface to receiver-server
        outPort = nexthops[0];         // has only one option
    }
    assert(std::find(nexthops.begin(), nexthops.end(), outPort) !=
           nexthops.end());  // Result of Letflow cannot be found in nexthops
    return outPort;
}

/*-----------------DRILL-----------------*/
uint32_t SwitchNode::CalculateInterfaceLoad(uint32_t interface) {
    Ptr<QbbNetDevice> device = DynamicCast<QbbNetDevice>(m_devices[interface]);
    NS_ASSERT_MSG(!!device && !!device->GetQueue(),
                  "Error of getting a egress queue for calculating interface load");
    return device->GetQueue()->GetNBytesTotal();  // also used in HPCC
}

uint32_t SwitchNode::DoLbDrill(Ptr<const Packet> p, const CustomHeader &ch,
                               const std::vector<int> &nexthops) {
    // find the Egress (output) link with the smallest local Egress Queue length
    uint32_t leastLoadInterface = 0;
    uint32_t leastLoad = std::numeric_limits<uint32_t>::max();
    auto rand_nexthops = nexthops;
    std::random_shuffle(rand_nexthops.begin(), rand_nexthops.end());

    std::map<uint32_t, uint32_t>::iterator itr = m_previousBestInterfaceMap.find(ch.dip);
    if (itr != m_previousBestInterfaceMap.end()) {
        leastLoadInterface = itr->second;
        leastLoad = CalculateInterfaceLoad(itr->second);
    }

    uint32_t sampleNum =
        m_drill_candidate < rand_nexthops.size() ? m_drill_candidate : rand_nexthops.size();
    for (uint32_t samplePort = 0; samplePort < sampleNum; samplePort++) {
        uint32_t sampleLoad = CalculateInterfaceLoad(rand_nexthops[samplePort]);
        if (sampleLoad < leastLoad) {
            leastLoad = sampleLoad;
            leastLoadInterface = rand_nexthops[samplePort];
        }
    }
    m_previousBestInterfaceMap[ch.dip] = leastLoadInterface;
    return leastLoadInterface;
}

/*------------------ConWeave Dummy ----------------*/
uint32_t SwitchNode::DoLbConWeave(Ptr<const Packet> p, const CustomHeader &ch,
                                  const std::vector<int> &nexthops) {
    return DoLbFlowECMP(p, ch, nexthops);  // flow ECMP (dummy)
}
/*----------------------------------*/

void SwitchNode::CheckAndSendPfc(uint32_t inDev, uint32_t qIndex) {
    Ptr<QbbNetDevice> device = DynamicCast<QbbNetDevice>(m_devices[inDev]);
    bool pClasses[qCnt] = {0};
    m_mmu->GetPauseClasses(inDev, qIndex, pClasses);
    for (int j = 0; j < qCnt; j++) {
        if (pClasses[j]) {
            uint32_t paused_time = device->SendPfc(j, 0);
            m_mmu->SetPause(inDev, j, paused_time);
            m_mmu->m_pause_remote[inDev][j] = true;
            /** PAUSE SEND COUNT ++ */
        }
    }

    for (int j = 0; j < qCnt; j++) {
        if (!m_mmu->m_pause_remote[inDev][j]) continue;

        if (m_mmu->GetResumeClasses(inDev, j)) {
            device->SendPfc(j, 1);
            m_mmu->SetResume(inDev, j);
            m_mmu->m_pause_remote[inDev][j] = false;
        }
    }
}
void SwitchNode::CheckAndSendResume(uint32_t inDev, uint32_t qIndex) {
    Ptr<QbbNetDevice> device = DynamicCast<QbbNetDevice>(m_devices[inDev]);
    if (m_mmu->GetResumeClasses(inDev, qIndex)) {
        device->SendPfc(qIndex, 1);
        m_mmu->SetResume(inDev, qIndex);
    }
}

/********************************************
 *              MAIN LOGICS                 *
 *******************************************/

// This function can only be called in switch mode
bool SwitchNode::SwitchReceiveFromDevice(Ptr<NetDevice> device, Ptr<Packet> packet,
                                         CustomHeader &ch) {
    // Update RX bytes counter for throughput monitoring
    uint32_t ifIndex = device->GetIfIndex();
    if (ifIndex < pCnt) {
        m_rxBytes[ifIndex] += packet->GetSize();
    }
    
    SendToDev(packet, ch);
    return true;
}

void SwitchNode::SendToDev(Ptr<Packet> p, CustomHeader &ch) {
    /** HIJACK: hijack the packet and run DoSwitchSend internally for Conga and ConWeave.
     * Note that DoLbConWeave() and DoLbConga() are flow-ECMP function for control packets
     * or intra-ToR traffic.
     */

    // CPEM: Credit feedback packets should bypass load balancer routing
    // and be handled directly in SendToDevContinue()
    if (Settings::cpem_enabled && ch.l3Prot == 0xFB) {
        SendToDevContinue(p, ch);
        return;
    }

    // Conga
    if (Settings::lb_mode == 3) {
        m_mmu->m_congaRouting.RouteInput(p, ch);
        return;
    }

    // ConWeave
    if (Settings::lb_mode == 9) {
        m_mmu->m_conweaveRouting.RouteInput(p, ch);
        return;
    }

    // Others
    SendToDevContinue(p, ch);
}

void SwitchNode::SendToDevContinue(Ptr<Packet> p, CustomHeader &ch) {
    // CPEM: Handle credit feedback packets
    if (Settings::cpem_enabled && ch.l3Prot == 0xFB) {
        CpemHandleFeedback(p, ch);
        return;  // Feedback packets are consumed locally, not forwarded
    }
    
    int idx = GetOutDev(p, ch);
    if (idx >= 0) {
        NS_ASSERT_MSG(m_devices[idx]->IsLinkUp(),
                      "The routing table look up should return link that is up");

        // determine the qIndex
        uint32_t qIndex;
        if (ch.l3Prot == 0xFF || ch.l3Prot == 0xFE || ch.l3Prot == 0xFB ||
            (m_ackHighPrio &&
             (ch.l3Prot == 0xFD ||
              ch.l3Prot == 0xFC))) {  // QCN or PFC or CPEM or ACK/NACK, go highest priority
            qIndex = 0;               // high priority
        } else {
            qIndex = (ch.l3Prot == 0x06 ? 1 : ch.udp.pg);  // if TCP, put to queue 1. Otherwise, it
                                                           // would be 3 (refer to trafficgen)
        }

        DoSwitchSend(p, ch, idx, qIndex);  // m_devices[idx]->SwitchSend(qIndex, p, ch);
        return;
    }
    std::cout << "WARNING - Drop occurs in SendToDevContinue()" << std::endl;
    return;  // Drop otherwise
}

int SwitchNode::GetOutDev(Ptr<Packet> p, CustomHeader &ch) {
    // look up entries
    auto entry = m_rtTable.find(ch.dip);

    // no matching entry
    if (entry == m_rtTable.end()) {
        std::cout << "[ERROR] Sw(" << m_id << ")," << PARSE_FIVE_TUPLE(ch)
                  << "No matching entry, so drop this packet at SwitchNode (l3Prot:" << ch.l3Prot
                  << ")" << std::endl;
        assert(false);
    }

    // entry found
    const auto &nexthops = entry->second;
    bool control_pkt =
        (ch.l3Prot == 0xFF || ch.l3Prot == 0xFE || ch.l3Prot == 0xFD || ch.l3Prot == 0xFC || ch.l3Prot == 0xFB);

    if (Settings::lb_mode == 0 || control_pkt) {  // control packet (ACK, NACK, PFC, QCN, CPEM)
        return DoLbFlowECMP(p, ch, nexthops);     // ECMP routing path decision (4-tuple)
    }

    switch (Settings::lb_mode) {
        case 2:
            return DoLbDrill(p, ch, nexthops);
        case 3:
            return DoLbConga(p, ch, nexthops); /** DUMMY: Do ECMP */
        case 6:
            return DoLbLetflow(p, ch, nexthops);
        case 9:
            return DoLbConWeave(p, ch, nexthops); /** DUMMY: Do ECMP */
        default:
            std::cout << "Unknown lb_mode(" << Settings::lb_mode << ")" << std::endl;
            assert(false);
    }
}

/*
 * The (possible) callback point when conweave dequeues packets from buffer
 */
void SwitchNode::DoSwitchSend(Ptr<Packet> p, CustomHeader &ch, uint32_t outDev, uint32_t qIndex) {
    // admission control
    FlowIdTag t;
    p->PeekPacketTag(t);
    uint32_t inDev = t.GetFlowId();

    /** NOTE:
     * ConWeave control packets have the high priority as ACK/NACK/PFC/etc with qIndex = 0.
     */
    if (inDev == Settings::CONWEAVE_CTRL_DUMMY_INDEV) { // sanity check
        // ConWeave reply is on ACK protocol with high priority, so qIndex should be 0
        assert(qIndex == 0 && m_ackHighPrio == 1 && "ConWeave's reply packet follows ACK, so its qIndex should be 0");
    }

    if (qIndex != 0) {  // not highest priority
        if (m_mmu->CheckEgressAdmission(outDev, qIndex,
                                        p->GetSize())) {  // Egress Admission control
            if (m_mmu->CheckIngressAdmission(inDev, qIndex,
                                             p->GetSize())) {  // Ingress Admission control
                m_mmu->UpdateIngressAdmission(inDev, qIndex, p->GetSize());
                m_mmu->UpdateEgressAdmission(outDev, qIndex, p->GetSize());
            } else { /** DROP: At Ingress */
#if (0)
                // /** NOTE: logging dropped pkts */
                // std::cout << "LostPkt ingress - Sw(" << m_id << ")," << PARSE_FIVE_TUPLE(ch)
                //           << "L3Prot:" << ch.l3Prot
                //           << ",Size:" << p->GetSize()
                //           << ",At " << Simulator::Now() << std::endl;
#endif
                Settings::dropped_pkt_sw_ingress++;
                return;  // drop
            }
        } else { /** DROP: At Egress */
#if (0)
            // /** NOTE: logging dropped pkts */
            // std::cout << "LostPkt egress - Sw(" << m_id << ")," << PARSE_FIVE_TUPLE(ch)
            //           << "L3Prot:" << ch.l3Prot << ",Size:" << p->GetSize() << ",At "
            //           << Simulator::Now() << std::endl;
#endif
            Settings::dropped_pkt_sw_egress++;
            return;  // drop
        }

        CheckAndSendPfc(inDev, qIndex);
        
        // CPEM: Update in-flight bytes for the egress port
        if (Settings::cpem_enabled) {
            m_mmu->CpemUpdateInflightOnSend(outDev, p->GetSize());
        }
    }

    m_devices[outDev]->SwitchSend(qIndex, p, ch);
}

void SwitchNode::SwitchNotifyDequeue(uint32_t ifIndex, uint32_t qIndex, Ptr<Packet> p) {
    FlowIdTag t;
    p->PeekPacketTag(t);
    if (qIndex != 0) {
        uint32_t inDev = t.GetFlowId();
        if (inDev != Settings::CONWEAVE_CTRL_DUMMY_INDEV) {
            // NOTE: ConWeave's probe/reply does not need to pass inDev interface,
            // so skip for conweave's queued packets
            m_mmu->RemoveFromIngressAdmission(inDev, qIndex, p->GetSize());
        }
        m_mmu->RemoveFromEgressAdmission(ifIndex, qIndex, p->GetSize());
        if (m_ecnEnabled) {
            bool egressCongested = m_mmu->ShouldSendCN(ifIndex, qIndex);
            if (egressCongested) {
                PppHeader ppp;
                Ipv4Header h;
                p->RemoveHeader(ppp);
                p->RemoveHeader(h);
                h.SetEcn((Ipv4Header::EcnType)0x03);
                p->AddHeader(h);
                p->AddHeader(ppp);
            }
        }
        // NOTE: ConWeave's probe/reply does not need to pass inDev interface
        if (inDev != Settings::CONWEAVE_CTRL_DUMMY_INDEV) {
            CheckAndSendResume(inDev, qIndex);
        }
    }

    // HPCC's INT
    if (1) {
        uint8_t *buf = p->GetBuffer();
        if (buf[PppHeader::GetStaticSize() + 9] == 0x11) {  // udp packet
            IntHeader *ih = (IntHeader *)&buf[PppHeader::GetStaticSize() + 20 + 8 +
                                              6];  // ppp, ip, udp, SeqTs, INT
            Ptr<QbbNetDevice> dev = DynamicCast<QbbNetDevice>(m_devices[ifIndex]);
            if (m_ccMode == 3) {  // HPCC
                ih->PushHop(Simulator::Now().GetTimeStep(), m_txBytes[ifIndex],
                            dev->GetQueue()->GetNBytesTotal(), dev->GetDataRate().GetBitRate());
            }
        }
    }
    m_txBytes[ifIndex] += p->GetSize();
}

uint32_t SwitchNode::EcmpHash(const uint8_t *key, size_t len, uint32_t seed) {
    uint32_t h = seed;
    if (len > 3) {
        const uint32_t *key_x4 = (const uint32_t *)key;
        size_t i = len >> 2;
        do {
            uint32_t k = *key_x4++;
            k *= 0xcc9e2d51;
            k = (k << 15) | (k >> 17);
            k *= 0x1b873593;
            h ^= k;
            h = (h << 13) | (h >> 19);
            h += (h << 2) + 0xe6546b64;
        } while (--i);
        key = (const uint8_t *)key_x4;
    }
    if (len & 3) {
        size_t i = len & 3;
        uint32_t k = 0;
        key = &key[i - 1];
        do {
            k <<= 8;
            k |= *key--;
        } while (--i);
        k *= 0xcc9e2d51;
        k = (k << 15) | (k >> 17);
        k *= 0x1b873593;
        h ^= k;
    }
    h ^= len;
    h ^= h >> 16;
    h *= 0x85ebca6b;
    h ^= h >> 13;
    h *= 0xc2b2ae35;
    h ^= h >> 16;
    return h;
}

void SwitchNode::SetEcmpSeed(uint32_t seed) { m_ecmpSeed = seed; }

void SwitchNode::AddTableEntry(Ipv4Address &dstAddr, uint32_t intf_idx) {
    uint32_t dip = dstAddr.Get();
    m_rtTable[dip].push_back(intf_idx);
}

void SwitchNode::ClearTable() { m_rtTable.clear(); }

uint64_t SwitchNode::GetTxBytesOutDev(uint32_t outdev) {
    assert(outdev < pCnt);
    return m_txBytes[outdev];
}

uint64_t SwitchNode::GetRxBytesInDev(uint32_t indev) {
    assert(indev < pCnt);
    return m_rxBytes[indev];
}

void SwitchNode::ResetThroughputCounters() {
    for (uint32_t i = 0; i < pCnt; i++) {
        m_txBytesSample[i] = m_txBytes[i];
        m_rxBytesSample[i] = m_rxBytes[i];
    }
}

uint64_t SwitchNode::GetTxBytesDelta(uint32_t outdev) {
    assert(outdev < pCnt);
    return m_txBytes[outdev] - m_txBytesSample[outdev];
}

uint64_t SwitchNode::GetRxBytesDelta(uint32_t indev) {
    assert(indev < pCnt);
    return m_rxBytes[indev] - m_rxBytesSample[indev];
}

void SwitchNode::UpdateSampleCounters() {
    for (uint32_t i = 0; i < pCnt; i++) {
        m_txBytesSample[i] = m_txBytes[i];
        m_rxBytesSample[i] = m_rxBytes[i];
    }
}

/*========== CPEM: Credit-based PFC Enhancement Module Implementation ==========*/

void SwitchNode::CpemInit() {
    if (!Settings::cpem_enabled) return;
    
    // Initialize CPEM state for all ports
    for (uint32_t i = 1; i < GetNDevices(); i++) {
        Ptr<QbbNetDevice> dev = DynamicCast<QbbNetDevice>(m_devices[i]);
        if (dev && dev->IsLinkUp()) {
            m_mmu->CpemInitPort(i, dev->GetDataRate());
        }
    }
    
    // Start periodic feedback generation
    CpemStartFeedbackGeneration();
}

void SwitchNode::CpemStartFeedbackGeneration() {
    if (!Settings::cpem_enabled) return;
    
    // Schedule periodic feedback check for each port
    for (uint32_t i = 1; i < GetNDevices(); i++) {
        Ptr<QbbNetDevice> dev = DynamicCast<QbbNetDevice>(m_devices[i]);
        if (dev && dev->IsLinkUp()) {
            // Stagger the start times to avoid burst
            Time startDelay = NanoSeconds(Settings::cpem_feedback_interval_ns * i / GetNDevices());
            Simulator::Schedule(startDelay, &SwitchNode::CpemPeriodicFeedbackCheck, this, i);
        }
    }
}

void SwitchNode::CpemPeriodicFeedbackCheck(uint32_t port) {
    if (!Settings::cpem_enabled) return;
    if (port >= GetNDevices()) return;
    
    Ptr<QbbNetDevice> dev = DynamicCast<QbbNetDevice>(m_devices[port]);
    if (!dev || !dev->IsLinkUp()) return;
    
    // Check if we should generate feedback for this ingress port
    uint32_t ingressQueueLen = m_mmu->GetIngressPortBytes(port);
    
    if (ingressQueueLen >= Settings::cpem_queue_threshold_low) {
        // Find the upstream port (source of traffic) and send feedback
        // For simplicity, we send feedback back through the same port
        CpemSendFeedback(port, port);
    }
    
    // Schedule next check
    Simulator::Schedule(NanoSeconds(Settings::cpem_feedback_interval_ns),
                        &SwitchNode::CpemPeriodicFeedbackCheck, this, port);
}

void SwitchNode::CpemSendFeedback(uint32_t inPort, uint32_t outPort) {
    if (!Settings::cpem_enabled) return;
    if (inPort >= pCnt || outPort >= GetNDevices()) return;
    
    Ptr<QbbNetDevice> dev = DynamicCast<QbbNetDevice>(m_devices[outPort]);
    if (!dev || !dev->IsLinkUp()) return;
    
    // Get current queue state
    uint32_t queueLen = m_mmu->GetIngressPortBytes(inPort);
    int16_t gradient = (int16_t)(queueLen - m_mmu->m_cpemState[inPort].lastQueueLen);
    m_mmu->m_cpemState[inPort].lastQueueLen = queueLen;
    
    // Get dynamic or fixed thresholds
    uint32_t threshold_low, threshold_high;
    m_mmu->CpemGetDynamicThresholds(inPort, threshold_low, threshold_high);
    
    // Calculate credit value
    uint16_t creditValue = m_mmu->CpemCalculateCreditValue(queueLen, gradient, threshold_low, threshold_high);
    
    // Only send feedback when credit is non-zero (queue exceeds threshold)
    if (creditValue == 0) {
        return;  // No need to send feedback when queue is below threshold
    }
    
    // DEBUG: Print queue state
    static uint64_t debugCount = 0;
    if (debugCount++ % 100 == 0) {
        // std::cerr << "[CPEM-SW] Node " << m_id << " Port " << inPort 
        //           << " queueLen=" << queueLen << " threshold_low=" << threshold_low 
        //           << " threshold_high=" << threshold_high << " creditValue=" << creditValue << std::endl;
    }
    
    // Create feedback packet
    Ptr<Packet> p = Create<Packet>(0);
    
    // Add Credit Feedback header
    CreditFeedbackHeader cfh(queueLen, gradient, creditValue, (uint8_t)inPort);
    p->AddHeader(cfh);
    
    // Add IPv4 header with protocol 0xFB (Credit Feedback)
    Ipv4Header ipv4h;
    ipv4h.SetProtocol(CreditFeedbackHeader::PROT_NUMBER);  // 0xFB
    ipv4h.SetSource(GetObject<Ipv4>() ? 
                    GetObject<Ipv4>()->GetAddress(outPort, 0).GetLocal() :
                    Ipv4Address("0.0.0.0"));
    ipv4h.SetDestination(Ipv4Address("255.255.255.255"));  // Broadcast to upstream
    ipv4h.SetPayloadSize(p->GetSize());
    ipv4h.SetTtl(1);  // Single hop
    ipv4h.SetIdentification(Simulator::Now().GetMicroSeconds() & 0xFFFF);
    p->AddHeader(ipv4h);
    
    // Add PPP header
    PppHeader ppp;
    ppp.SetProtocol(0x0021);  // IPv4
    p->AddHeader(ppp);
    
    // Send with highest priority
    CustomHeader ch(CustomHeader::L2_Header | CustomHeader::L3_Header | CustomHeader::L4_Header);
    p->PeekHeader(ch);
    
    // Use SwitchSend with queue index 0 (highest priority)
    dev->SwitchSend(0, p, ch);
    
    SwitchMmu::m_cpemFeedbackSent++;
}

void SwitchNode::CpemHandleFeedback(Ptr<Packet> p, CustomHeader &ch) {
    if (!Settings::cpem_enabled) return;
    
    // Extract feedback information from the packet
    // The credit feedback info is in ch.pfc (reusing the union structure)
    // Or we can parse it directly
    
    // Get the port that received this feedback (it came from downstream)
    FlowIdTag t;
    if (!p->PeekPacketTag(t)) return;
    uint32_t inPort = t.GetFlowId();
    
    // Parse the credit feedback header
    Ptr<Packet> pCopy = p->Copy();
    PppHeader ppp;
    Ipv4Header ipv4;
    CreditFeedbackHeader cfh;
    
    pCopy->RemoveHeader(ppp);
    pCopy->RemoveHeader(ipv4);
    pCopy->RemoveHeader(cfh);
    
    uint32_t queueLen = cfh.GetQueueLen();
    int16_t gradient = cfh.GetGradient();
    uint16_t creditValue = cfh.GetCreditValue();
    uint8_t portIndex = cfh.GetPortIndex();
    
    // Update credit state for the port that sends to this downstream
    // In this case, the feedback arrived on inPort, so we update the outbound port state
    // The portIndex tells us which downstream port is congested
    
    // For now, we update the port state where this feedback was received
    // This means: the device connected to inPort is the upstream, we need to slow down
    // traffic going OUT of inPort
    m_mmu->CpemUpdateCreditOnFeedback(inPort, creditValue, queueLen, gradient);
    
    // Apply rate adjustment to the device
    Ptr<QbbNetDevice> dev = DynamicCast<QbbNetDevice>(m_devices[inPort]);
    if (dev) {
        DataRate linkRate = dev->GetDataRate();
        DataRate adjustedRate = m_mmu->CpemGetAdjustedRate(inPort, linkRate);
        dev->CpemSetEffectiveRate(adjustedRate);
    }
    
    SwitchMmu::m_cpemFeedbackRecv++;
}

} /* namespace ns3 */
