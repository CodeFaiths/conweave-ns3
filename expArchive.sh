#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_ROOT="${SCRIPT_DIR}/mix/output"
FIG_ROOT="${SCRIPT_DIR}/analysis/figures"
ARCHIVE_ROOT="${SCRIPT_DIR}/expArchive"

FORCE=0
MODE="new"
declare -a INPUT_TARGETS=()

usage() {
    cat <<EOF
Usage:
    ./expArchive.sh                      # archive all unarchived experiments (default)
        ./expArchive.sh new                 # archive all unarchived experiments
        ./expArchive.sh latest              # archive latest experiment only
        ./expArchive.sh all                 # archive all experiments under mix/output
        ./expArchive.sh <config_name> ...   # archive one or more specific configs
        ./expArchive.sh -f <target>         # overwrite existing archive folder

config_name format examples:
    20260203_221642_AliStorage2019
    20260203_221642_AliStorage2019_9MB_TH100KB
    20260227_121716_search_9MB_TH100KB_RPT300

Notes:
  - Source output dir: mix/output/<config_name>
    - Source figure dir: auto matched by prefix:
            analysis/figures/<config_name>*
  - Archived files per algorithm dir:
      config.log, config.txt, *_out_fct_summary.txt
  - Archived figure files:
            *.png, *.pdf, *.txt
    - Archive path layout:
            expArchive/<group>/<config_name>
        where <group> is auto-extracted from config name
EOF
}

cecho() {
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

normalize_config_name() {
    local raw="$1"
    # Support legacy medu_loop_ prefix for backward compatibility
    if [[ "$raw" == medu_loop_* ]]; then
        echo "${raw#medu_loop_}"
    else
        echo "$raw"
    fi
}

extract_cdf() {
    local config_name="$1"
    if [[ "$config_name" =~ ^[0-9]{8}_[0-9]{6}_(.+)$ ]]; then
        local suffix="${BASH_REMATCH[1]}"
        if [[ "$suffix" == *_* ]]; then
            echo "${suffix%%_*}"
        else
            echo "$suffix"
        fi
    else
        echo ""
    fi
}

collect_figure_dirs() {
    local config_name="$1"
    local fig_dir
    local exact_dir="${FIG_ROOT}/${config_name}"

    if [[ -d "$exact_dir" ]]; then
        echo "$exact_dir"
    fi

    shopt -s nullglob
    for fig_dir in "${FIG_ROOT}/${config_name}"*; do
        [[ -d "$fig_dir" ]] || continue
        if [[ "$fig_dir" != "$exact_dir" ]]; then
            echo "$fig_dir"
        fi
    done
    shopt -u nullglob
}

collect_all_configs() {
    local d
    local -a configs=()
    shopt -s nullglob
    for d in "${OUTPUT_ROOT}"/[0-9]*; do
        [[ -d "$d" ]] || continue
        configs+=("$(basename "$d")")
    done
    shopt -u nullglob
    printf "%s\n" "${configs[@]}"
}

is_already_archived() {
    local config_name="$1"
    local cdf
    cdf="$(extract_cdf "$config_name")"
    if [[ -z "$cdf" ]]; then
        return 1
    fi
    [[ -d "${ARCHIVE_ROOT}/${cdf}/${config_name}" ]]
}

collect_unarchived_configs() {
    local cfg
    local -a configs=()
    mapfile -t configs < <(collect_all_configs | sort)
    for cfg in "${configs[@]}"; do
        if ! is_already_archived "$cfg"; then
            echo "$cfg"
        fi
    done
}

archive_one_config() {
    local config_name="$1"
    local cdf="$2"
    local src_output_dir="${OUTPUT_ROOT}/${config_name}"
    local dst_base_dir="${ARCHIVE_ROOT}/${cdf}/${config_name}"
    local dst_analysis_dir="${dst_base_dir}/analysis/figures"
    local dst_output_dir="${dst_base_dir}/output"

    if [[ ! -d "$src_output_dir" ]]; then
        cecho "RED" "[SKIP] Missing output dir: $src_output_dir"
        return 1
    fi

    if [[ -d "$dst_base_dir" && "$FORCE" -eq 0 ]]; then
        cecho "YELLOW" "[SKIP] Archive exists (use -f to overwrite): $dst_base_dir"
        return 0
    fi

    if [[ -d "$dst_base_dir" && "$FORCE" -eq 1 ]]; then
        rm -rf "$dst_base_dir"
    fi

    mkdir -p "$dst_analysis_dir" "$dst_output_dir"

    local -a fig_dirs=()
    local fig_dir
    mapfile -t fig_dirs < <(collect_figure_dirs "$config_name")
    if [[ ${#fig_dirs[@]} -gt 0 ]]; then
        local fig_count=0
        local fig_file
        local dst_fig_dir

        for fig_dir in "${fig_dirs[@]}"; do
            dst_fig_dir="${dst_analysis_dir}/$(basename "$fig_dir")"
            mkdir -p "$dst_fig_dir"

            shopt -s nullglob
            for fig_file in "${fig_dir}"/*.png "${fig_dir}"/*.pdf "${fig_dir}"/*.txt; do
                [[ -f "$fig_file" ]] || continue
                cp -a "$fig_file" "$dst_fig_dir/"
                fig_count=$((fig_count + 1))
            done
            shopt -u nullglob
        done

        cecho "CYAN" "  Copied figure files: ${fig_count} from ${#fig_dirs[@]} dirs -> ${dst_analysis_dir}"
    else
        cecho "YELLOW" "  No figure directories found for: ${config_name}"
    fi

    local load_dir algo_dir algo_name
    local copied_count=0
    local missing_count=0

    shopt -s nullglob
    for load_dir in "$src_output_dir"/load*; do
        [[ -d "$load_dir" ]] || continue
        local load_name
        load_name="$(basename "$load_dir")"

        for algo_dir in "$load_dir"/*; do
            [[ -d "$algo_dir" ]] || continue
            algo_name="$(basename "$algo_dir")"

            local dst_algo_dir="${dst_output_dir}/${load_name}/${algo_name}"
            mkdir -p "$dst_algo_dir"

            local required_fixed=("config.log" "config.txt")
            local f
            for f in "${required_fixed[@]}"; do
                if [[ -f "${algo_dir}/${f}" ]]; then
                    cp -a "${algo_dir}/${f}" "$dst_algo_dir/"
                    copied_count=$((copied_count + 1))
                else
                    cecho "YELLOW" "  Missing ${load_name}/${algo_name}/${f}"
                    missing_count=$((missing_count + 1))
                fi
            done

            local matched=0
            local fct_summary_files=("${algo_dir}"/*_out_fct_summary.txt)
            for f in "${fct_summary_files[@]}"; do
                if [[ -f "$f" ]]; then
                    cp -a "$f" "$dst_algo_dir/"
                    copied_count=$((copied_count + 1))
                    matched=1
                fi
            done
            if [[ "$matched" -eq 0 ]]; then
                cecho "YELLOW" "  Missing ${load_name}/${algo_name}/*_out_fct_summary.txt"
                missing_count=$((missing_count + 1))
            fi

        done
    done
    shopt -u nullglob

    cecho "GREEN" "  Output copied files: ${copied_count}, missing items: ${missing_count}"
    return 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        -f|--force)
            FORCE=1
            shift
            ;;
        latest|all|new)
            MODE="$1"
            shift
            ;;
        *)
            INPUT_TARGETS+=("$1")
            shift
            ;;
    esac
done

if [[ ! -d "$OUTPUT_ROOT" ]]; then
    cecho "RED" "Output root not found: $OUTPUT_ROOT"
    exit 1
fi

mkdir -p "$ARCHIVE_ROOT"

declare -a TARGET_CONFIGS=()

if [[ ${#INPUT_TARGETS[@]} -gt 0 ]]; then
    MODE="manual"
    for t in "${INPUT_TARGETS[@]}"; do
        TARGET_CONFIGS+=("$(normalize_config_name "$t")")
    done
elif [[ "$MODE" == "all" ]]; then
    mapfile -t TARGET_CONFIGS < <(collect_all_configs | sort)
elif [[ "$MODE" == "new" ]]; then
    mapfile -t TARGET_CONFIGS < <(collect_unarchived_configs)
else
    mapfile -t TARGET_CONFIGS < <(collect_all_configs | sort)
    if [[ ${#TARGET_CONFIGS[@]} -eq 0 ]]; then
        cecho "RED" "No experiments found under ${OUTPUT_ROOT}/"
        exit 1
    fi
    TARGET_CONFIGS=("${TARGET_CONFIGS[-1]}")
fi

if [[ ${#TARGET_CONFIGS[@]} -eq 0 ]]; then
    if [[ "$MODE" == "new" ]]; then
        cecho "GREEN" "No new experiments to archive."
        exit 0
    fi
    cecho "RED" "No target experiments to archive."
    exit 1
fi

cecho "GREEN" "============================================================"
cecho "GREEN" "             Experiment Archive Started"
cecho "GREEN" "============================================================"
cecho "YELLOW" "Mode: ${MODE}"
cecho "YELLOW" "Targets: ${TARGET_CONFIGS[*]}"
cecho "YELLOW" "Archive root: ${ARCHIVE_ROOT}"
echo ""

ok=0
fail=0

for config_name in "${TARGET_CONFIGS[@]}"; do
    cdf="$(extract_cdf "$config_name")"
    if [[ -z "$cdf" ]]; then
        cecho "RED" "[SKIP] Invalid config name format (expected: YYYYMMDD_HHMMSS_*): ${config_name}"
        fail=$((fail + 1))
        continue
    fi

    cecho "CYAN" "------------------------------------------------------------"
    cecho "CYAN" "Archiving: ${config_name}"
    cecho "CYAN" "CDF: ${cdf}"

    if archive_one_config "$config_name" "$cdf"; then
        ok=$((ok + 1))
    else
        fail=$((fail + 1))
    fi
    echo ""
done

cecho "GREEN" "============================================================"
cecho "GREEN" "Archive finished: success=${ok}, failed=${fail}"
cecho "GREEN" "============================================================"

if [[ "$fail" -gt 0 ]]; then
    exit 1
fi
