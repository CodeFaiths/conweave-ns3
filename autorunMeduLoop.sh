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
TOPOLOGY="leaf_spine_128_100G_OS2"
LOADS=("30" "50" "70" "80")  # List of loads to test as requested
CDF="AliStorage2019"           # CDF file name:AliStorage2019 webserver search Solar2022 FbHdp2015
RUNTIME="0.1"          # 0.1 second (traffic generation)

# ===== 可调整的额外参数 =====
BUFFER_SIZE="2"       # 交换机缓存大小 (MB)，默认: 9
# BANDWIDTH="100"      # NIC带宽 (Gbps)，默认: 100
# CC_MODE="dcqcn"      # 拥塞控制算法，默认: dcqcn
# CPEM_ENABLED=0       # 启用CPEM模块，默认: 0
# SW_MONITORING_INTERVAL=10000  # 采样间隔 (ns)，默认: 10000

# Load Balancing algorithms to test
LB_ALGORITHMS=("fecmp" "letflow" "conga" "conweave")

# Global Output Setup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
ROOT_EXP_NAME="medu_loop_${TIMESTAMP}_${CDF}_${BUFFER_SIZE}MB"
ROOT_EXPERIMENT_DIR="mix/output/${ROOT_EXP_NAME}"

cecho "GREEN" "============================================================"
cecho "GREEN" "       MEDU Multi-Load Experiment Loop"
cecho "GREEN" "       (Long/Short Flow Separation)"
cecho "GREEN" "============================================================"
cecho "YELLOW" "TOPOLOGY: ${TOPOLOGY}" 
cecho "YELLOW" "LOADS TO TEST: ${LOADS[*]}" 
cecho "YELLOW" "CDF: ${CDF}" 
cecho "YELLOW" "SIMULATION TIME: ${RUNTIME}s" 
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
            --medu 1 \
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
