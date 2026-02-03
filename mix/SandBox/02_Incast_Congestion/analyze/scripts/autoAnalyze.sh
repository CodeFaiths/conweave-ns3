#!/bin/bash
# =================================================================
# NS3 Automatic Analysis Suite - 自动化分析脚本
# 自动运行所有分析脚本，生成完整的分析报告和图表
# =================================================================

# set -e  # 遇到错误立即退出 - 已禁用，允许部分分析失败

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# 实验目录 (analyze/scripts -> analyze -> experiment)
ANALYZE_DIR="$(dirname "$SCRIPT_DIR")"
EXPERIMENT_DIR="$(dirname "$ANALYZE_DIR")"

# 默认路径
OUTPUT_DIR="$EXPERIMENT_DIR/output"
TRACE_ANALYSIS_DIR="$ANALYZE_DIR/trace_analysis"
FIGURES_DIR="$ANALYZE_DIR/figures"
CONFIG_DIR="$EXPERIMENT_DIR/config"

# 输出文件路径
TRACE_FILE="$OUTPUT_DIR/trace_out.tr"
PFC_FILE="$OUTPUT_DIR/out_pfc.txt"
INGRESS_FILE="$OUTPUT_DIR/ingress_queue.txt"
LINK_UTIL_FILE="$OUTPUT_DIR/link_util.txt"
QLEN_FILE="$OUTPUT_DIR/out_qlen.txt"
THROUGHPUT_FILE="$OUTPUT_DIR/out_throughput.txt"
UTIL_MON_FILE="$OUTPUT_DIR/out_link_util.txt"
UPLINK_FILE="$OUTPUT_DIR/out_uplink.txt"
CONN_FILE="$OUTPUT_DIR/out_conn.txt"
FCT_FILE="$OUTPUT_DIR/out_fct.txt"

# 自动查找拓扑文件
TOPOLOGY_FILE=""
if [ -f "$CONFIG_DIR/topo_incast_5to1.txt" ]; then
    TOPOLOGY_FILE="$CONFIG_DIR/topo_incast_5to1.txt"
elif [ -f "$CONFIG_DIR/topology.txt" ]; then
    TOPOLOGY_FILE="$CONFIG_DIR/topology.txt"
elif [ -f "$EXPERIMENT_DIR/topology.txt" ]; then
    TOPOLOGY_FILE="$EXPERIMENT_DIR/topology.txt"
fi

# 端口过滤参数 (可选)
INCLUDE_PORTS=""

# 分析开关（默认全部开启）
ENABLE_TRACE_ANALYSIS=1
ENABLE_PFC_ANALYSIS=1
ENABLE_INGRESS_ANALYSIS=1
ENABLE_LINK_UTIL_ANALYSIS=1
ENABLE_QLEN_ANALYSIS=1
ENABLE_THROUGHPUT_ANALYSIS=1
ENABLE_UPLINK_ANALYSIS=1
ENABLE_FCT_ANALYSIS=1

print_banner() {
    echo -e "${BLUE}==================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}==================================================================${NC}"
}

print_step() {
    echo -e "\n${GREEN}▶ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_info() {
    echo -e "${CYAN}ℹ $1${NC}"
}

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -o, --output DIR       Output directory for analysis results (default: $OUTPUT_DIR)"
    echo "  -f, --figures DIR      Figures output directory (default: $FIGURES_DIR)"
    echo "  --include PORTS        Only include specified ports (e.g., 'SW6-P1 SW6-P6 H0-P1')"
    echo "  --skip-trace           Skip trace file analysis"
    echo "  --skip-pfc             Skip PFC analysis"
    echo "  --skip-ingress         Skip ingress queue analysis"
    echo "  --skip-qlen            Skip egress queue length analysis"
    echo "  --skip-throughput      Skip throughput analysis"
    echo "  --skip-uplink          Skip uplink monitoring analysis"
    echo "  --skip-fct             Skip FCT analysis"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all analyses with default paths"
    echo "  $0 --include 'SW6-P1 SW6-P6'          # Only analyze specific ports"
    echo "  $0 --skip-trace --skip-pfc            # Skip trace and PFC analysis"
    exit 0
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -f|--figures)
            FIGURES_DIR="$2"
            shift 2
            ;;
        --include)
            INCLUDE_PORTS="$2"
            shift 2
            ;;
        --skip-trace)
            ENABLE_TRACE_ANALYSIS=0
            shift
            ;;
        --skip-pfc)
            ENABLE_PFC_ANALYSIS=0
            shift
            ;;
        --skip-ingress)
            ENABLE_INGRESS_ANALYSIS=0
            shift
            ;;
        --skip-qlen)
            ENABLE_QLEN_ANALYSIS=0
            shift
            ;;
        --skip-throughput)
            ENABLE_THROUGHPUT_ANALYSIS=0
            shift
            ;;
        --skip-uplink)
            ENABLE_UPLINK_ANALYSIS=0
            shift
            ;;
        --skip-fct)
            ENABLE_FCT_ANALYSIS=0
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

print_banner "NS3 Automatic Analysis Suite"

echo ""
echo "Experiment Directory: $EXPERIMENT_DIR"
echo "Output Directory:     $OUTPUT_DIR"
echo "Analysis Output:      $TRACE_ANALYSIS_DIR"
echo "Figures Output:       $FIGURES_DIR"
if [ -n "$TOPOLOGY_FILE" ]; then
    echo "Topology File:        $TOPOLOGY_FILE"
fi
if [ -n "$INCLUDE_PORTS" ]; then
    echo "Port Filter:          $INCLUDE_PORTS"
fi

# 创建输出目录
mkdir -p "$TRACE_ANALYSIS_DIR"
mkdir -p "$FIGURES_DIR"

# 构建端口过滤参数
INCLUDE_ARGS=""
if [ -n "$INCLUDE_PORTS" ]; then
    INCLUDE_ARGS="--include $INCLUDE_PORTS"
fi

# 构建拓扑参数
TOPOLOGY_ARGS=""
if [ -n "$TOPOLOGY_FILE" ]; then
    TOPOLOGY_ARGS="--topology $TOPOLOGY_FILE"
fi

# 统计运行的分析数量
TOTAL_ANALYSES=0
COMPLETED_ANALYSES=0
STEP_NUM=1

# =================================================================
# Step: 分析Trace文件 (链路利用率与队列长度)
# =================================================================
if [ $ENABLE_TRACE_ANALYSIS -eq 1 ] && [ -f "$TRACE_FILE" ]; then
    ((TOTAL_ANALYSES++))
    print_step "Step $STEP_NUM: Analyzing trace data (link utilization & queue length)..."
    echo "  Input:  $TRACE_FILE"
    echo "  Output: $FIGURES_DIR/"

    python3 "$SCRIPT_DIR/plot_trace.py" "$TRACE_FILE" \
        --output-dir "$FIGURES_DIR" \
        --csv-dir "$TRACE_ANALYSIS_DIR" \
        $TOPOLOGY_ARGS \
        $INCLUDE_ARGS

    if [ $? -eq 0 ]; then
        print_success "Trace analysis completed"
        ((COMPLETED_ANALYSES++))
    else
        print_error "Trace analysis failed"
    fi
    ((STEP_NUM++))
elif [ $ENABLE_TRACE_ANALYSIS -eq 1 ]; then
    print_warning "Step $STEP_NUM: Trace file not found: $TRACE_FILE (skipped)"
    ((STEP_NUM++))
fi

# =================================================================
# Step: PFC分析 (统计汇总与Trace关联分析)
# =================================================================
if [ $ENABLE_PFC_ANALYSIS -eq 1 ] && [ -f "$PFC_FILE" ]; then
    ((TOTAL_ANALYSES++))
    print_step "Step $STEP_NUM: Analyzing PFC events..."
    echo "  Input:  $PFC_FILE"
    echo "  Output: $FIGURES_DIR/"

    # plot_pfc.py uses hardcoded paths, only pass optional arguments it supports
    python3 "$SCRIPT_DIR/plot_pfc.py" \
        $INCLUDE_ARGS

    if [ $? -eq 0 ]; then
        print_success "PFC analysis completed"
        ((COMPLETED_ANALYSES++))
    else
        print_error "PFC analysis failed"
    fi
    ((STEP_NUM++))
elif [ $ENABLE_PFC_ANALYSIS -eq 1 ]; then
    print_warning "Step $STEP_NUM: PFC file not found: $PFC_FILE (skipped)"
    ((STEP_NUM++))
fi

# =================================================================
# Step: Ingress队列分析 (用于PFC触发分析)
# =================================================================
if [ $ENABLE_INGRESS_ANALYSIS -eq 1 ] && [ -f "$INGRESS_FILE" ]; then
    ((TOTAL_ANALYSES++))
    print_step "Step $STEP_NUM: Analyzing ingress queue (PFC trigger analysis)..."
    echo "  Input:  $INGRESS_FILE"
    echo "  Output: $FIGURES_DIR/"

    python3 "$SCRIPT_DIR/plot_ingress_qlen.py" "$INGRESS_FILE" "$FIGURES_DIR" \
        $TOPOLOGY_ARGS \
        $INCLUDE_ARGS

    if [ $? -eq 0 ]; then
        print_success "Ingress queue analysis completed"
        ((COMPLETED_ANALYSES++))
    else
        print_error "Ingress queue analysis failed"
    fi
    ((STEP_NUM++))
elif [ $ENABLE_INGRESS_ANALYSIS -eq 1 ]; then
    print_warning "Step $STEP_NUM: Ingress queue file not found: $INGRESS_FILE (skipped)"
    ((STEP_NUM++))
fi

# =================================================================
# Step: Egress队列长度分析 (从monitor输出)
# =================================================================
if [ $ENABLE_QLEN_ANALYSIS -eq 1 ] && [ -f "$QLEN_FILE" ]; then
    ((TOTAL_ANALYSES++))
    print_step "Step $STEP_NUM: Analyzing egress queue length (from monitor)..."
    echo "  Input:  $QLEN_FILE"
    echo "  Output: $FIGURES_DIR/"

    python3 "$SCRIPT_DIR/plot_qlen.py" \
        -i "$QLEN_FILE" \
        -o "$FIGURES_DIR" \
        $INCLUDE_ARGS

    if [ $? -eq 0 ]; then
        print_success "Egress queue length analysis completed"
        ((COMPLETED_ANALYSES++))
    else
        print_error "Egress queue length analysis failed"
    fi
    ((STEP_NUM++))
elif [ $ENABLE_QLEN_ANALYSIS -eq 1 ]; then
    print_warning "Step $STEP_NUM: Qlen file not found: $QLEN_FILE (skipped)"
    ((STEP_NUM++))
fi

# =================================================================
# Step: 吞吐量和链路利用率分析 (新增)
# =================================================================
if [ $ENABLE_THROUGHPUT_ANALYSIS -eq 1 ] && ([ -f "$THROUGHPUT_FILE" ] || [ -f "$UTIL_MON_FILE" ]); then
    ((TOTAL_ANALYSES++))
    print_step "Step $STEP_NUM: Analyzing throughput and link utilization..."

    THROUGHPUT_ARGS=""
    UTIL_ARGS=""

    if [ -f "$THROUGHPUT_FILE" ]; then
        THROUGHPUT_ARGS="--throughput $THROUGHPUT_FILE"
        echo "  Input:  $THROUGHPUT_FILE"
    fi

    if [ -f "$UTIL_MON_FILE" ]; then
        UTIL_ARGS="--util $UTIL_MON_FILE"
        echo "  Input:  $UTIL_MON_FILE"
    fi

    echo "  Output: $FIGURES_DIR/"

    python3 "$SCRIPT_DIR/plot_throughput.py" \
        $THROUGHPUT_ARGS \
        $UTIL_ARGS \
        --output-dir "$FIGURES_DIR" \
        --csv-dir "$TRACE_ANALYSIS_DIR" \
        $INCLUDE_ARGS

    if [ $? -eq 0 ]; then
        print_success "Throughput and utilization analysis completed"
        ((COMPLETED_ANALYSES++))
    else
        print_error "Throughput and utilization analysis failed"
    fi
    ((STEP_NUM++))
elif [ $ENABLE_THROUGHPUT_ANALYSIS -eq 1 ]; then
    print_warning "Step $STEP_NUM: Throughput/utilization files not found (skipped)"
    ((STEP_NUM++))
fi

# =================================================================
# Step: Uplink监控分析
# =================================================================
if [ $ENABLE_UPLINK_ANALYSIS -eq 1 ] && [ -f "$UPLINK_FILE" ]; then
    ((TOTAL_ANALYSES++))
    print_step "Step $STEP_NUM: Analyzing uplink monitoring data..."
    echo "  Input:  $UPLINK_FILE"
    echo "  Output: $FIGURES_DIR/"

    # 检查是否有 plot_uplink.py 脚本
    if [ -f "$SCRIPT_DIR/plot_uplink.py" ]; then
        python3 "$SCRIPT_DIR/plot_uplink.py" "$UPLINK_FILE" \
            --output-dir "$FIGURES_DIR" \
            $TOPOLOGY_ARGS \
            $INCLUDE_ARGS

        if [ $? -eq 0 ]; then
            print_success "Uplink analysis completed"
            ((COMPLETED_ANALYSES++))
        else
            print_error "Uplink analysis failed"
        fi
    else
        print_info "plot_uplink.py not found, skipping uplink analysis"
    fi
    ((STEP_NUM++))
elif [ $ENABLE_UPLINK_ANALYSIS -eq 1 ]; then
    print_warning "Step $STEP_NUM: Uplink file not found: $UPLINK_FILE (skipped)"
    ((STEP_NUM++))
fi

# =================================================================
# Step: FCT (Flow Completion Time) 分析
# =================================================================
if [ $ENABLE_FCT_ANALYSIS -eq 1 ] && [ -f "$FCT_FILE" ]; then
    ((TOTAL_ANALYSES++))
    print_step "Step $STEP_NUM: Analyzing Flow Completion Time (FCT)..."
    echo "  Input:  $FCT_FILE"
    echo "  Output: $FIGURES_DIR/"

    python3 "$SCRIPT_DIR/plot_fct.py" "$FCT_FILE" \
        --output-dir "$FIGURES_DIR"

    if [ $? -eq 0 ]; then
        print_success "FCT analysis completed"
        ((COMPLETED_ANALYSES++))
    else
        print_error "FCT analysis failed"
    fi
    ((STEP_NUM++))
elif [ $ENABLE_FCT_ANALYSIS -eq 1 ]; then
    print_warning "Step $STEP_NUM: FCT file not found: $FCT_FILE (skipped)"
    ((STEP_NUM++))
fi

# =================================================================
# 完成统计
# =================================================================
print_banner "Analysis Complete!"

echo ""
echo "📊 Summary:"
echo "  Total analyses: $TOTAL_ANALYSES"
echo "  Completed:      $COMPLETED_ANALYSES"
echo "  Failed:         $((TOTAL_ANALYSES - COMPLETED_ANALYSES))"

echo ""
echo "📁 Results saved to:"
echo ""
echo "   CSV Data:    $TRACE_ANALYSIS_DIR/"
if [ -d "$TRACE_ANALYSIS_DIR" ]; then
    CSV_COUNT=$(find "$TRACE_ANALYSIS_DIR" -name "*.csv" -type f 2>/dev/null | wc -l)
    if [ $CSV_COUNT -gt 0 ]; then
        echo "                ($CSV_COUNT CSV files)"
        find "$TRACE_ANALYSIS_DIR" -name "*.csv" -type f 2>/dev/null | head -5 | while read f; do
            echo "                - $(basename $f)"
        done
        if [ $CSV_COUNT -gt 5 ]; then
            echo "                ... and $((CSV_COUNT - 5)) more"
        fi
    fi
fi

echo ""
echo "   Figures:     $FIGURES_DIR/"
if [ -d "$FIGURES_DIR" ]; then
    PNG_COUNT=$(find "$FIGURES_DIR" -name "*.png" -type f 2>/dev/null | wc -l)
    if [ $PNG_COUNT -gt 0 ]; then
        echo "                ($PNG_COUNT PNG files)"
        find "$FIGURES_DIR" -name "*.png" -type f 2>/dev/null | head -5 | while read f; do
            echo "                - ${f#$FIGURES_DIR/}"
        done
        if [ $PNG_COUNT -gt 5 ]; then
            echo "                ... and $((PNG_COUNT - 5)) more"
        fi
    fi
fi

echo ""
if [ $COMPLETED_ANALYSES -eq $TOTAL_ANALYSES ]; then
    echo -e "${GREEN}✓ All analyses completed successfully!${NC}"
elif [ $COMPLETED_ANALYSES -gt 0 ]; then
    echo -e "${YELLOW}⚠ Some analyses completed with errors${NC}"
else
    echo -e "${RED}✗ No analyses completed successfully${NC}"
fi

echo ""
print_info "Tip: Use --help to see all available options"
