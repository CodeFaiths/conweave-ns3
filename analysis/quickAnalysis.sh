#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NS3_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ALLINONE_ROOT="$(cd "${NS3_ROOT}/.." && pwd)"

EXP_A="${ALLINONE_ROOT}/ns-3.19/mix/output/medu_loop_20260227_121716_AliStorage2019_9MB_CC0"
EXP_B="${ALLINONE_ROOT}/ns-3.19/mix/output/medu_loop_20260227_115241_AliStorage2019_9MB_CC1"
LABEL_A="CC0"
LABEL_B="CC1"

echo "[1/2] Running medu_analysis.py ..."
cd "${SCRIPT_DIR}"
python3 medu_analysis.py

echo "[2/2] Running medu_cmp_chart.py ..."
cd "${ALLINONE_ROOT}"
python3 ns-3.19/analysis/medu_cmp_chart.py \
  --exp-a "${EXP_A}" \
  --exp-b "${EXP_B}" \
  --label-a "${LABEL_A}" \
  --label-b "${LABEL_B}"

echo "Analysis completed."
