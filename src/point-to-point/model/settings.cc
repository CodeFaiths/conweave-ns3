#include "ns3/settings.h"

namespace ns3 {
/* helper function */
Ipv4Address Settings::node_id_to_ip(uint32_t id) {
    return Ipv4Address(0x0b000001 + ((id / 256) * 0x00010000) + ((id % 256) * 0x00000100));
}
uint32_t Settings::ip_to_node_id(Ipv4Address ip) {
    return (ip.Get() >> 8) & 0xffff;
}

/* others */
uint32_t Settings::lb_mode = 0;

std::map<uint32_t, uint32_t> Settings::hostIp2IdMap;
std::map<uint32_t, uint32_t> Settings::hostId2IpMap;

/* statistics */
uint32_t Settings::node_num = 0;
uint32_t Settings::host_num = 0;
uint32_t Settings::switch_num = 0;
uint64_t Settings::cnt_finished_flows = 0;
uint32_t Settings::packet_payload = 1000;

uint32_t Settings::dropped_pkt_sw_ingress = 0;
uint32_t Settings::dropped_pkt_sw_egress = 0;

/* for load balancer */
std::map<uint32_t, uint32_t> Settings::hostIp2SwitchId;

/* Credit-based PFC Enhancement Module (CPEM) */
bool Settings::cpem_enabled = false;                    // Module enable switch
uint32_t Settings::cpem_feedback_interval_ns = 10000;   // Feedback interval (10us default)
double Settings::cpem_credit_decay_alpha = 0.8;         // EWMA decay factor
double Settings::cpem_inflight_discount = 0.4;          // In-flight credit discount
double Settings::cpem_credit_to_rate_gain = 0.8;        // Credit to rate conversion gain
double Settings::cpem_min_rate_ratio = 0.1;             // Minimum rate ratio (10%)
uint32_t Settings::cpem_max_credit = 1000;              // Maximum credit value
uint32_t Settings::cpem_queue_threshold_low = 50000;    // Low queue threshold (50KB) - used in fixed mode
uint32_t Settings::cpem_queue_threshold_high = 200000;  // High queue threshold (200KB) - used in fixed mode

// Dynamic threshold mode settings
bool Settings::cpem_use_dynamic_threshold = true;       // Enable dynamic threshold by default
double Settings::cpem_threshold_low_ratio = 0.5;        // Low threshold = 50% of PFC threshold
double Settings::cpem_threshold_high_ratio = 0.8;       // High threshold = 80% of PFC threshold

}  // namespace ns3
