#!/bin/bash

# ==============================================================================
# CPEM Comparison Experiment Script (Multi-Load)
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
NETLOAD="40"           # Network load (e.g., 40, 50, 70, 80)
RUNTIME="0.1"          # 0.1 second (traffic generation)

# Load Balancing algorithms to test
LB_ALGORITHMS=("fecmp" "letflow" "conga" "conweave")

cecho "GREEN" "============================================================"
cecho "GREEN" "       CPEM Comparison Experiment"
cecho "GREEN" "============================================================"
cecho "YELLOW" "TOPOLOGY: ${TOPOLOGY}" 
cecho "YELLOW" "NETWORK LOAD: ${NETLOAD}%" 
cecho "YELLOW" "SIMULATION TIME: ${RUNTIME}s" 
cecho "YELLOW" "Load Balancers: ${LB_ALGORITHMS[*]}"
cecho "GREEN" "============================================================"
echo ""

# Create output directory for experiment results
EXPERIMENT_DIR="mix/output/cpem_comparison_$(date +%Y%m%d_%H%M%S)_load${NETLOAD}"
mkdir -p ${EXPERIMENT_DIR}

cecho "CYAN" "Output directory: ${EXPERIMENT_DIR}"
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

# ==============================================================================
# Group 1: WITHOUT CPEM (CPEM_ENABLED=0) - Run in parallel
# ==============================================================================
cecho "GREEN" "============================================================"
cecho "GREEN" "  Group 1: Running experiments WITHOUT CPEM"
cecho "GREEN" "============================================================"

for lb in "${LB_ALGORITHMS[@]}"; do
    cecho "YELLOW" "  Starting: LB=${lb}, CPEM=OFF"
    python3 run.py --lb ${lb} --pfc 1 --irn 0 \
        --simul_time ${RUNTIME} \
        --netload ${NETLOAD} \
        --topo ${TOPOLOGY} \
        --cpem 0 \
        2>&1 | tee -a ${EXPERIMENT_DIR}/no_cpem_${lb}.log &
    sleep 3
done

# ==============================================================================
# Group 2: WITH CPEM (CPEM_ENABLED=1) - Run in parallel
# ==============================================================================
cecho "GREEN" "============================================================"
cecho "GREEN" "  Group 2: Running experiments WITH CPEM"
cecho "GREEN" "============================================================"

for lb in "${LB_ALGORITHMS[@]}"; do
    cecho "YELLOW" "  Starting: LB=${lb}, CPEM=ON"
    python3 run.py --lb ${lb} --pfc 1 --irn 0 \
        --simul_time ${RUNTIME} \
        --netload ${NETLOAD} \
        --topo ${TOPOLOGY} \
        --cpem 1 \
        2>&1 | tee -a ${EXPERIMENT_DIR}/with_cpem_${lb}.log &
    sleep 3
done

cecho "YELLOW" "All 8 experiments started in background. Waiting for completion..."
wait

cecho "GREEN" "============================================================"

cecho "GREEN" "============================================================"
cecho "GREEN" "  All experiments completed!"
cecho "GREEN" "============================================================"
