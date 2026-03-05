#!/bin/bash

# ==============================================================================
# MEDU Comparison Experiment Script (Multi-Load Loop Version)
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
TOPOLOGY="leaf_spine_8_100G_OS2" 
LOADS=("30" "50" "70" "80")  # List of loads to test as requested
#LOADS=("30")
CDF="search"           # CDF file name:AliStorage2019 webserver search Solar2022 FbHdp2015
RUNTIME="0.1"          # 0.1 second (traffic generation)

# ===== 可调整的额外参数 =====
BUFFER_SIZE="9"       # 交换机缓存大小 (MB)，默认: 9
FLOW_THRESHOLD_KB="100"   # MEDU长短流分界阈值 (KB)，默认: 100
# BANDWIDTH="100"      # NIC带宽 (Gbps)，默认: 100
# CC_MODE="dcqcn"      # 拥塞控制算法，默认: dcqcn
# CPEM_ENABLED=0       # 启用CPEM模块，默认: 0
# SW_MONITORING_INTERVAL=10000  # 采样间隔 (ns)，默认: 10000

# ===== 差异化拥塞控制参数 (MEDU开启时生效) =====
DIFF_CC=1                  # 是否启用长短流差异化CC参数，0=关闭, 1=开启
SHORT_AI_FACTOR="2.0"      # 短流 RATE_AI 倍数 (相对全局值)，默认: 2.0
SHORT_HAI_FACTOR="2.0"     # 短流 RATE_HAI 倍数 (相对全局值)，默认: 2.0
SHORT_EWMA_GAIN="0.00390625"   # 短流 EWMA_GAIN，默认: 0.00390625 (-1表示使用全局值)
SHORT_ALPHA_RESUME="1"     # 短流 ALPHA_RESUME_INTERVAL (us)，默认: 1
SHORT_RATE_DECREASE="4"    # 短流 RATE_DECREASE_INTERVAL (us)，默认: 4
SHORT_RP_TIMER="300"       # 短流 RP_TIMER (us)，默认: 300
SHORT_FAST_RECOVERY="1"    # 短流 FAST_RECOVERY_TIMES，默认: 1
LONG_AI_FACTOR="1.0"       # 长流 RATE_AI 倍数 (相对全局值)，默认: 1.0
LONG_HAI_FACTOR="1.0"      # 长流 RATE_HAI 倍数 (相对全局值)，默认: 1.0
LONG_EWMA_GAIN="0.00390625"    # 长流 EWMA_GAIN，默认: 0.00390625 (-1表示使用全局值)
LONG_ALPHA_RESUME="1"      # 长流 ALPHA_RESUME_INTERVAL (us)，默认: 1
LONG_RATE_DECREASE="4"     # 长流 RATE_DECREASE_INTERVAL (us)，默认: 4
LONG_RP_TIMER="20"        # 长流 RP_TIMER (us)，默认: 300
LONG_FAST_RECOVERY="1"     # 长流 FAST_RECOVERY_TIMES，默认: 1

# Load Balancing algorithms to test
LB_ALGORITHMS=("fecmp" "letflow" "conga" "conweave")

# ==============================================================================
# Parse --para command line argument
# Usage: ./autorunMeduLoop.sh --para 9MB TH100KB RPT300
# ==============================================================================
PARA_SUFFIX=""
while [[ $# -gt 0 ]]; do
    case "$1" in
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

# Global Output Setup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ROOT_EXP_NAME="${TIMESTAMP}_${CDF}${PARA_SUFFIX}"
ROOT_EXPERIMENT_DIR="mix/output/${ROOT_EXP_NAME}"

cecho "GREEN" "============================================================"
cecho "GREEN" "       MEDU Multi-Load Experiment Loop"
cecho "GREEN" "       (Long/Short Flow Separation)"
cecho "GREEN" "============================================================"
cecho "YELLOW" "TOPOLOGY: ${TOPOLOGY}" 
cecho "YELLOW" "LOADS TO TEST: ${LOADS[*]}" 
cecho "YELLOW" "CDF: ${CDF}" 
cecho "YELLOW" "SIMULATION TIME: ${RUNTIME}s" 
cecho "YELLOW" "FLOW THRESHOLD: ${FLOW_THRESHOLD_KB}KB"
cecho "YELLOW" "DIFF CC: ${DIFF_CC} (short AI×${SHORT_AI_FACTOR} HAI×${SHORT_HAI_FACTOR}, long AI×${LONG_AI_FACTOR} HAI×${LONG_HAI_FACTOR})"
cecho "YELLOW" "  Short: EWMA=${SHORT_EWMA_GAIN} α_resume=${SHORT_ALPHA_RESUME} rate_dec=${SHORT_RATE_DECREASE} rp_timer=${SHORT_RP_TIMER} fast_rec=${SHORT_FAST_RECOVERY}"
cecho "YELLOW" "  Long:  EWMA=${LONG_EWMA_GAIN} α_resume=${LONG_ALPHA_RESUME} rate_dec=${LONG_RATE_DECREASE} rp_timer=${LONG_RP_TIMER} fast_rec=${LONG_FAST_RECOVERY}"
cecho "YELLOW" "Load Balancers: ${LB_ALGORITHMS[*]}"
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

    # Group 1: WITHOUT MEDU (MEDU=0) - Run in parallel for this load
    for lb in "${LB_ALGORITHMS[@]}"; do
        cecho "YELLOW" "  Starting: LB=${lb}, MEDU=OFF, LOAD=${NETLOAD}%"
        python3 run.py --lb ${lb} --pfc 1 --irn 0 \
            --simul_time ${RUNTIME} \
            --netload ${NETLOAD} \
            --topo ${TOPOLOGY} \
            --cdf ${CDF} \
            --buffer ${BUFFER_SIZE} \
            --flow-threshold-kb ${FLOW_THRESHOLD_KB} \
            --medu 0 \
            --id ${ROOT_EXP_NAME}/load${NETLOAD}/no_medu_${lb} \
            2>&1 | tee -a ${LOAD_LOG_DIR}/no_medu_${lb}.log &
        sleep 2
    done

    # Group 2: WITH MEDU (MEDU=1) - Run in parallel for this load
    for lb in "${LB_ALGORITHMS[@]}"; do
        cecho "YELLOW" "  Starting: LB=${lb}, MEDU=ON, LOAD=${NETLOAD}%"
        python3 run.py --lb ${lb} --pfc 1 --irn 0 \
            --simul_time ${RUNTIME} \
            --netload ${NETLOAD} \
            --topo ${TOPOLOGY} \
            --cdf ${CDF} \
            --buffer ${BUFFER_SIZE} \
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
            --id ${ROOT_EXP_NAME}/load${NETLOAD}/with_medu_${lb} \
            2>&1 | tee -a ${LOAD_LOG_DIR}/with_medu_${lb}.log &
        sleep 3
    done

    echo ""
done

cecho "YELLOW" "All experiments (${#LOADS[@]} loads x 8) started in background. Waiting for completion..."
wait

cecho "GREEN" "============================================================"
cecho "GREEN" "  All multi-load experiments completed!"
cecho "GREEN" "  Final results saved in: ${ROOT_EXPERIMENT_DIR}"
cecho "GREEN" "============================================================"
