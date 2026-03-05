#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NS3_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ALLINONE_ROOT="$(cd "${NS3_ROOT}/.." && pwd)"

EXP_A="${ALLINONE_ROOT}/ns-3.19/mix/output/20260302_031404_AliStorage2019_9MB_DCC0_Raw"
EXP_B="${ALLINONE_ROOT}/ns-3.19/mix/output/20260305_030043_AliStorage2019_9MB_DCC0_32H_Raw"
EXP_C="${ALLINONE_ROOT}/ns-3.19/mix/output/20260305_032140_AliStorage2019_9MB_DCC0_8H_Raw"
#EXP_D="${ALLINONE_ROOT}/ns-3.19/mix/output/20260305_064946_search_9MB_100KB_CC0_8H_RPT20"
#EXP_E="${ALLINONE_ROOT}/ns-3.19/mix/output/20260228_145529_search_9MB_100KB_CC1_RPT10"
LABEL_A="128"
LABEL_B="32"
LABEL_C="8"  
#LABEL_D="8_RPT20"
#LABEL_E="CC1RPT10"

echo "[1/2] Running medu_analysis.py ..."
cd "${SCRIPT_DIR}"
python3 medu_analysis.py

echo "[2/2] Running medu_cmp_chart.py ..."
cd "${ALLINONE_ROOT}"
python3 ns-3.19/analysis/medu_cmp_chart.py \
  --exp-a "${EXP_A}" \
  --exp-b "${EXP_B}" \
  --exp-c "${EXP_C}" \
  --label-a "${LABEL_A}" \
  --label-b "${LABEL_B}" \
  --label-c "${LABEL_C}" \
  #--keep-only-exp-a-no-medu

echo "Analysis completed."
