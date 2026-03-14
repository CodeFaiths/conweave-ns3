#!/bin/bash

# ==============================================================================
# MeCP Experiment Script (Upgraded from autorunMedu.sh)
# MEDU On/Off comparison + CPEM switch/params + CC_MODE selection
# ==============================================================================

cecho(){
    case "$1" in
        RED) color="\033[0;31m" ;;
        GREEN) color="\033[0;32m" ;;
        YELLOW) color="\033[0;33m" ;;
        CYAN) color="\033[0;36m" ;;
        *) color="\033[0m" ;;
    esac
    NC="\033[0m"
    echo -e "${color}${2}${NC}"
}

# Experiment Parameters
<<<<<<< HEAD
TOPOLOGY="leaf_spine_32_100G_OS2"
LOADS=("30" "50" "70" "80" "90")  # List of loads to test
#LOADS=("50" "80")
CDF="AliStorage2019"           # CDF file name: AliStorage2019 webserver search Solar2022 FbHdp2015
RUNTIME="0.1"                  # 0.1 second (traffic generation)
BUFFER_SIZE="9"                # 交换机缓存大小 (MB)，默认: 9
FLOW_THRESHOLD_KB="100"        # MEDU长短流分界阈值 (KB)，默认: 100
CC_MODE=0                      # 0=none, 1=dcqcn, 3=hpcc, 7=timely, 8=dctcp
SW_MONITORING_INTERVAL="10000" # 采样间隔 (ns)，默认: 10000

# ===== CPEM 参数 =====
CPEM_ENABLED=1                     # 是否启用CPEM，0=关闭, 1=开启
CPEM_FEEDBACK_INTERVAL="5000"
=======
TOPOLOGY="leaf_spine_128_100G_OS2"
#LOADS=("30" "50" "70" "80" "90")  # List of loads to test
LOADS=("50" "80")
CDF="search"           # CDF file name: AliStorage2019 webserver search Solar2022 FbHdp2015
RUNTIME="0.1"                  # 0.1 second (traffic generation)
BUFFER_SIZE="9"                # 交换机缓存大小 (MB)，默认: 9
FLOW_THRESHOLD_KB="100"        # MEDU长短流分界阈值 (KB)，默认: 100
CC_MODE=0                       # 1=dcqcn, 0=none(不采用拥塞控制)
SW_MONITORING_INTERVAL="10000" # 采样间隔 (ns)，默认: 10000

# ===== CPEM 参数 =====
CPEM_FEEDBACK_INTERVAL="2000"
>>>>>>> 176a7bd65d806d2ebf5b393dbc3e4c05384ea354
CPEM_CREDIT_DECAY_ALPHA="0.8"
CPEM_INFLIGHT_DISCOUNT="0.4"
CPEM_CREDIT_TO_RATE_GAIN="1.0"
CPEM_MIN_RATE_RATIO="0.05"
CPEM_MAX_CREDIT="1000"
# CPEM threshold mode: 1=dynamic threshold, 0=static threshold
CPEM_USE_DYNAMIC_THRESHOLD="1"
CPEM_THRESHOLD_LOW_RATIO="0.6"
CPEM_THRESHOLD_HIGH_RATIO="0.9"
# Static thresholds (used only when CPEM_USE_DYNAMIC_THRESHOLD=0)
<<<<<<< HEAD
CPEM_QUEUE_THRESHOLD_LOW="200000"
CPEM_QUEUE_THRESHOLD_HIGH="300000"
=======
CPEM_QUEUE_THRESHOLD_LOW="10000"
CPEM_QUEUE_THRESHOLD_HIGH="100000"
>>>>>>> 176a7bd65d806d2ebf5b393dbc3e4c05384ea354

# ===== 差异化拥塞控制参数 (MEDU开启时生效) =====
DIFF_CC=0                       # 是否启用长短流差异化CC参数，0=关闭, 1=开启
SHORT_AI_FACTOR="2.0"          # 短流 RATE_AI 倍数 (相对全局值)
SHORT_HAI_FACTOR="2.0"         # 短流 RATE_HAI 倍数 (相对全局值)
SHORT_EWMA_GAIN="0.00390625"   # 短流 EWMA_GAIN (-1表示使用全局值)
SHORT_ALPHA_RESUME="1"         # 短流 ALPHA_RESUME_INTERVAL (us)
SHORT_RATE_DECREASE="4"        # 短流 RATE_DECREASE_INTERVAL (us)
SHORT_RP_TIMER="300"           # 短流 RP_TIMER (us)
SHORT_FAST_RECOVERY="1"        # 短流 FAST_RECOVERY_TIMES
LONG_AI_FACTOR="1.0"           # 长流 RATE_AI 倍数 (相对全局值)
LONG_HAI_FACTOR="1.0"          # 长流 RATE_HAI 倍数 (相对全局值)
LONG_EWMA_GAIN="0.00390625"    # 长流 EWMA_GAIN (-1表示使用全局值)
LONG_ALPHA_RESUME="1"          # 长流 ALPHA_RESUME_INTERVAL (us)
LONG_RATE_DECREASE="4"         # 长流 RATE_DECREASE_INTERVAL (us)
LONG_RP_TIMER="20"             # 长流 RP_TIMER (us)
LONG_FAST_RECOVERY="1"         # 长流 FAST_RECOVERY_TIMES

# Load Balancing algorithms to test
LB_ALGORITHMS=("fecmp" "letflow" "conga" "conweave")

# ==============================================================================
# Parse command line arguments
# Usage:
<<<<<<< HEAD
#   ./autorunMeCp.sh --cc-mode 3 --para 8H HPCC
#   ./autorunMeCp.sh --cc hpcc --para 8H HPCC
=======
#   ./autorunMeCp.sh --cc-mode 1 --para CPEM1
>>>>>>> 176a7bd65d806d2ebf5b393dbc3e4c05384ea354
# ==============================================================================
PARA_SUFFIX=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --cc-mode)
            CC_MODE="$2"
            shift 2
            ;;
<<<<<<< HEAD
        --cc)
            case "${2}" in
                none) CC_MODE="0" ;;
                dcqcn) CC_MODE="1" ;;
                hpcc) CC_MODE="3" ;;
                timely) CC_MODE="7" ;;
                dctcp) CC_MODE="8" ;;
                *)
                    cecho "RED" "Invalid --cc value: ${2}. Supported: none/dcqcn/hpcc/timely/dctcp"
                    exit 1
                    ;;
            esac
            shift 2
            ;;
=======
>>>>>>> 176a7bd65d806d2ebf5b393dbc3e4c05384ea354
        --para)
            shift
            while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                PARA_SUFFIX="${PARA_SUFFIX}_${1}"
                shift
            done
            ;;
        *)
            shift
            ;;
    esac
done

<<<<<<< HEAD
if [[ "${CC_MODE}" != "0" && "${CC_MODE}" != "1" && "${CC_MODE}" != "3" && "${CC_MODE}" != "7" && "${CC_MODE}" != "8" ]]; then
    cecho "RED" "Invalid --cc-mode value: ${CC_MODE}. Supported: 0/1/3/7/8"
    exit 1
fi

case "${CC_MODE}" in
    0) CC_ALGO="none" ;;
    1) CC_ALGO="dcqcn" ;;
    3) CC_ALGO="hpcc" ;;
    7) CC_ALGO="timely" ;;
    8) CC_ALGO="dctcp" ;;
esac

# ConWeave在当前实现下不支持RTT类协议（HPCC/Timely），none模式也跳过以避免不兼容问题。
EFFECTIVE_LB_ALGORITHMS=()
for lb in "${LB_ALGORITHMS[@]}"; do
    if [[ "${lb}" == "conweave" && ( "${CC_ALGO}" == "hpcc" || "${CC_ALGO}" == "timely" || "${CC_ALGO}" == "none" ) ]]; then
        cecho "YELLOW" "Skip LB=conweave: incompatible with CC=${CC_ALGO}."
=======
if [[ "${CC_MODE}" != "0" && "${CC_MODE}" != "1" ]]; then
    cecho "RED" "Invalid --cc-mode value: ${CC_MODE}. Supported: 0/1"
    exit 1
fi

if [[ "${CC_MODE}" == "1" ]]; then
    CC_ALGO="dcqcn"
else
    CC_ALGO="none"
fi

# ConWeave currently requires DCQCN in simulator implementation.
# When CC_MODE=0 (none), skip conweave to avoid guaranteed simulation failure.
EFFECTIVE_LB_ALGORITHMS=()
for lb in "${LB_ALGORITHMS[@]}"; do
    if [[ "${lb}" == "conweave" && "${CC_MODE}" != "1" ]]; then
        cecho "YELLOW" "Skip LB=conweave: only supported with --cc-mode 1 (dcqcn)."
>>>>>>> 176a7bd65d806d2ebf5b393dbc3e4c05384ea354
        continue
    fi
    EFFECTIVE_LB_ALGORITHMS+=("${lb}")
done

if [[ ${#EFFECTIVE_LB_ALGORITHMS[@]} -eq 0 ]]; then
    cecho "RED" "No valid load balancer left after CC compatibility filtering."
    exit 1
fi

# Global Output Setup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ROOT_EXP_NAME="${TIMESTAMP}_${CDF}_CC${CC_MODE}${PARA_SUFFIX}"
ROOT_EXPERIMENT_DIR="mix/output/${ROOT_EXP_NAME}"

cecho "GREEN" "============================================================"
cecho "GREEN" "       MeCP Multi-Load Experiment Loop"
cecho "GREEN" "       (MEDU On/Off + CPEM + CC Mode)"
cecho "GREEN" "============================================================"
cecho "YELLOW" "TOPOLOGY: ${TOPOLOGY}"
cecho "YELLOW" "LOADS TO TEST: ${LOADS[*]}"
cecho "YELLOW" "CDF: ${CDF}"
cecho "YELLOW" "SIMULATION TIME: ${RUNTIME}s"
cecho "YELLOW" "FLOW THRESHOLD: ${FLOW_THRESHOLD_KB}KB"
cecho "YELLOW" "CC MODE: ${CC_MODE} (algo=${CC_ALGO})"
<<<<<<< HEAD
cecho "YELLOW" "CPEM ENABLED: ${CPEM_ENABLED}"
=======
cecho "YELLOW" "CPEM ENABLED: 1 (fixed)"
>>>>>>> 176a7bd65d806d2ebf5b393dbc3e4c05384ea354
cecho "YELLOW" "SW_MONITORING_INTERVAL: ${SW_MONITORING_INTERVAL}ns"
cecho "YELLOW" "DIFF CC: ${DIFF_CC} (short AI×${SHORT_AI_FACTOR} HAI×${SHORT_HAI_FACTOR}, long AI×${LONG_AI_FACTOR} HAI×${LONG_HAI_FACTOR})"
cecho "YELLOW" "  Short: EWMA=${SHORT_EWMA_GAIN} α_resume=${SHORT_ALPHA_RESUME} rate_dec=${SHORT_RATE_DECREASE} rp_timer=${SHORT_RP_TIMER} fast_rec=${SHORT_FAST_RECOVERY}"
cecho "YELLOW" "  Long:  EWMA=${LONG_EWMA_GAIN} α_resume=${LONG_ALPHA_RESUME} rate_dec=${LONG_RATE_DECREASE} rp_timer=${LONG_RP_TIMER} fast_rec=${LONG_FAST_RECOVERY}"
cecho "YELLOW" "CPEM params: feedback=${CPEM_FEEDBACK_INTERVAL}, alpha=${CPEM_CREDIT_DECAY_ALPHA}, inflight_discount=${CPEM_INFLIGHT_DISCOUNT}, gain=${CPEM_CREDIT_TO_RATE_GAIN}, min_rate_ratio=${CPEM_MIN_RATE_RATIO}, max_credit=${CPEM_MAX_CREDIT}"
cecho "YELLOW" "CPEM threshold: dynamic=${CPEM_USE_DYNAMIC_THRESHOLD}, low_ratio=${CPEM_THRESHOLD_LOW_RATIO}, high_ratio=${CPEM_THRESHOLD_HIGH_RATIO}, static_low=${CPEM_QUEUE_THRESHOLD_LOW}, static_high=${CPEM_QUEUE_THRESHOLD_HIGH}"
cecho "YELLOW" "Load Balancers (effective): ${EFFECTIVE_LB_ALGORITHMS[*]}"
cecho "GREEN" "============================================================"
echo ""

mkdir -p ${ROOT_EXPERIMENT_DIR}
cecho "CYAN" "Root Output directory: ${ROOT_EXPERIMENT_DIR}"
echo ""

# ==============================================================================
# IMPORTANT: Pre-compile to avoid parallel build conflicts
# ==============================================================================
cecho "GREEN" "============================================================"
cecho "GREEN" "  Pre-compiling ns-3 to avoid parallel build conflicts..."
cecho "GREEN" "============================================================"
./waf build
if [ $? -ne 0 ]; then
    cecho "RED" "Build failed! Please fix compilation errors first."
    exit 1
fi
cecho "GREEN" "Build completed successfully!"
echo ""

# Loop through each network load
for NETLOAD in "${LOADS[@]}"; do
    # Create load-specific subdirectories for logs
    LOAD_LOG_DIR="${ROOT_EXPERIMENT_DIR}/load${NETLOAD}"
    mkdir -p ${LOAD_LOG_DIR}

    cecho "CYAN" "------------------------------------------------------------"
    cecho "CYAN" "  Processing Network Load: ${NETLOAD}%"
    cecho "CYAN" "------------------------------------------------------------"

    # Group 1: WITHOUT MEDU (MEDU=0)
    for lb in "${EFFECTIVE_LB_ALGORITHMS[@]}"; do
<<<<<<< HEAD
        cecho "YELLOW" "  Starting: LB=${lb}, MEDU=OFF, CPEM=${CPEM_ENABLED}, CC_MODE=${CC_MODE}(${CC_ALGO}), LOAD=${NETLOAD}%"
=======
        cecho "YELLOW" "  Starting: LB=${lb}, MEDU=OFF, CPEM=1, CC_MODE=${CC_MODE}(${CC_ALGO}), LOAD=${NETLOAD}%"
>>>>>>> 176a7bd65d806d2ebf5b393dbc3e4c05384ea354
        python3 run.py --lb ${lb} --cc ${CC_ALGO} --pfc 1 --irn 0 \
            --simul_time ${RUNTIME} \
            --netload ${NETLOAD} \
            --topo ${TOPOLOGY} \
            --cdf ${CDF} \
            --buffer ${BUFFER_SIZE} \
            --sw_monitoring_interval ${SW_MONITORING_INTERVAL} \
            --flow-threshold-kb ${FLOW_THRESHOLD_KB} \
            --medu 0 \
<<<<<<< HEAD
            --cpem ${CPEM_ENABLED} \
=======
            --cpem 1 \
>>>>>>> 176a7bd65d806d2ebf5b393dbc3e4c05384ea354
            --cpem-feedback-interval ${CPEM_FEEDBACK_INTERVAL} \
            --cpem-credit-decay-alpha ${CPEM_CREDIT_DECAY_ALPHA} \
            --cpem-inflight-discount ${CPEM_INFLIGHT_DISCOUNT} \
            --cpem-credit-to-rate-gain ${CPEM_CREDIT_TO_RATE_GAIN} \
            --cpem-min-rate-ratio ${CPEM_MIN_RATE_RATIO} \
            --cpem-max-credit ${CPEM_MAX_CREDIT} \
            --cpem-use-dynamic-threshold ${CPEM_USE_DYNAMIC_THRESHOLD} \
            --cpem-threshold-low-ratio ${CPEM_THRESHOLD_LOW_RATIO} \
            --cpem-threshold-high-ratio ${CPEM_THRESHOLD_HIGH_RATIO} \
            --cpem-queue-threshold-low ${CPEM_QUEUE_THRESHOLD_LOW} \
            --cpem-queue-threshold-high ${CPEM_QUEUE_THRESHOLD_HIGH} \
            --id ${ROOT_EXP_NAME}/load${NETLOAD}/no_medu_${lb} \
            2>&1 | tee -a ${LOAD_LOG_DIR}/no_medu_${lb}.log &
        sleep 2
    done

    # Group 2: WITH MEDU (MEDU=1)
    for lb in "${EFFECTIVE_LB_ALGORITHMS[@]}"; do
<<<<<<< HEAD
        cecho "YELLOW" "  Starting: LB=${lb}, MEDU=ON, CPEM=${CPEM_ENABLED}, CC_MODE=${CC_MODE}(${CC_ALGO}), LOAD=${NETLOAD}%"
=======
        cecho "YELLOW" "  Starting: LB=${lb}, MEDU=ON, CPEM=1, CC_MODE=${CC_MODE}(${CC_ALGO}), LOAD=${NETLOAD}%"
>>>>>>> 176a7bd65d806d2ebf5b393dbc3e4c05384ea354
        python3 run.py --lb ${lb} --cc ${CC_ALGO} --pfc 1 --irn 0 \
            --simul_time ${RUNTIME} \
            --netload ${NETLOAD} \
            --topo ${TOPOLOGY} \
            --cdf ${CDF} \
            --buffer ${BUFFER_SIZE} \
            --sw_monitoring_interval ${SW_MONITORING_INTERVAL} \
            --flow-threshold-kb ${FLOW_THRESHOLD_KB} \
            --medu 1 \
            --diff-cc ${DIFF_CC} \
            --short-ai-factor ${SHORT_AI_FACTOR} \
            --short-hai-factor ${SHORT_HAI_FACTOR} \
            --short-ewma-gain ${SHORT_EWMA_GAIN} \
            --short-alpha-resume ${SHORT_ALPHA_RESUME} \
            --short-rate-decrease ${SHORT_RATE_DECREASE} \
            --short-rp-timer ${SHORT_RP_TIMER} \
            --short-fast-recovery ${SHORT_FAST_RECOVERY} \
            --long-ai-factor ${LONG_AI_FACTOR} \
            --long-hai-factor ${LONG_HAI_FACTOR} \
            --long-ewma-gain ${LONG_EWMA_GAIN} \
            --long-alpha-resume ${LONG_ALPHA_RESUME} \
            --long-rate-decrease ${LONG_RATE_DECREASE} \
            --long-rp-timer ${LONG_RP_TIMER} \
            --long-fast-recovery ${LONG_FAST_RECOVERY} \
<<<<<<< HEAD
            --cpem ${CPEM_ENABLED} \
=======
            --cpem 1 \
>>>>>>> 176a7bd65d806d2ebf5b393dbc3e4c05384ea354
            --cpem-feedback-interval ${CPEM_FEEDBACK_INTERVAL} \
            --cpem-credit-decay-alpha ${CPEM_CREDIT_DECAY_ALPHA} \
            --cpem-inflight-discount ${CPEM_INFLIGHT_DISCOUNT} \
            --cpem-credit-to-rate-gain ${CPEM_CREDIT_TO_RATE_GAIN} \
            --cpem-min-rate-ratio ${CPEM_MIN_RATE_RATIO} \
            --cpem-max-credit ${CPEM_MAX_CREDIT} \
            --cpem-use-dynamic-threshold ${CPEM_USE_DYNAMIC_THRESHOLD} \
            --cpem-threshold-low-ratio ${CPEM_THRESHOLD_LOW_RATIO} \
            --cpem-threshold-high-ratio ${CPEM_THRESHOLD_HIGH_RATIO} \
            --cpem-queue-threshold-low ${CPEM_QUEUE_THRESHOLD_LOW} \
            --cpem-queue-threshold-high ${CPEM_QUEUE_THRESHOLD_HIGH} \
            --id ${ROOT_EXP_NAME}/load${NETLOAD}/with_medu_${lb} \
            2>&1 | tee -a ${LOAD_LOG_DIR}/with_medu_${lb}.log &
        sleep 3
    done

    echo ""
done

EXPERIMENTS_PER_LOAD=$(( ${#EFFECTIVE_LB_ALGORITHMS[@]} * 2 ))
cecho "YELLOW" "All experiments (${#LOADS[@]} loads x ${EXPERIMENTS_PER_LOAD}) started in background. Waiting for completion..."
wait

cecho "GREEN" "============================================================"
cecho "GREEN" "  All multi-load experiments completed!"
cecho "GREEN" "  Final results saved in: ${ROOT_EXPERIMENT_DIR}"
cecho "GREEN" "============================================================"
