#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NS3_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ALLINONE_ROOT="$(cd "${NS3_ROOT}/.." && pwd)"

EXP_A="${ALLINONE_ROOT}/ns-3.19/mix/output/20260311_111502_AliStorage2019_32H_CC0"
EXP_B="${ALLINONE_ROOT}/ns-3.19/mix/output/20260311_114437_AliStorage2019_32H_CC1"
# EXP_C="${ALLINONE_ROOT}/ns-3.19/mix/output/20260306_132436_AliStorage2019_CC3_32H_HPCC"
# EXP_D="${ALLINONE_ROOT}/ns-3.19/mix/output/20260306_132523_AliStorage2019_CC0_32H_PFC"
# EXP_E="${ALLINONE_ROOT}/ns-3.19/mix/output/20260307_001637_AliStorage2019_CC0_32H_DCPEM"
LABEL_A="CC0"
LABEL_B="CC1"
# LABEL_C="HPCC"
# LABEL_D="PFC"
# LABEL_E="DCPEM"

echo "[1/2] Running medu_analysis.py ..."
cd "${SCRIPT_DIR}"
python3 medu_analysis.py

echo "[2/2] Running medu_cmp_chart.py ..."
cd "${ALLINONE_ROOT}"
python3 ns-3.19/analysis/medu_cmp_chart.py \
  --exp-a "${EXP_A}" \
  --exp-b "${EXP_B}" \
  --label-a "${LABEL_A}" \
  --label-b "${LABEL_B}" \
  --keep-only-exp-a-no-medu

echo "Analysis completed."
