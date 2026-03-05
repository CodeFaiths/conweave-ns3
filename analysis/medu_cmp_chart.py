#!/usr/bin/env python3
"""
Re-plot multiple MEDU experiments on the same axes (not image stitching).

Key behavior:
1) Output folder name: <timestamp>_<CDF>_cmp
2) Re-draw curves from raw summary data under mix/output
3) Generate 6 separate figures:
   - small_avg_slowdown_cmp
   - small_p99_slowdown_cmp
   - large_avg_slowdown_cmp
    - large_p99_slowdown_cmp
    - all_avg_slowdown_cmp
    - all_p99_slowdown_cmp

Input directories are experiment output roots under mix/output, for example:
- mix/output/medu_loop_20260203_221642_AliStorage2019
- mix/output/medu_loop_20260212_093305_AliStorage2019
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch


ALG_ORDER = ["conga", "conweave", "fecmp", "letflow"]
ALG_LABEL = {
    "conga": "CONGA",
    "conweave": "ConWeave",
    "fecmp": "FECMP",
    "letflow": "LetFlow",
}

# per algorithm color (stable across both experiments)
ALG_COLOR = {
    "conga": "#e41a1c",
    "conweave": "#377eb8",
    "fecmp": "#4daf4a",
    "letflow": "#ff7f00",
}

# (no_medu_hatch, with_medu_hatch, edgecolor)
CONDITION_STYLES = [
    ("", "///", "black"),
    ("..", "xx", "#4d4d4d"),
    ("\\\\", "++", "#7a7a7a"),
    ("oo", "--", "#5a5a5a"),
    ("**", "||", "#2f2f2f"),
]

ExpData = Dict[str, Dict[str, Dict[bool, Dict[str, Dict[str, float]]]]]
ExpEntry = Tuple[str, ExpData]


def parse_summary(summary_path: Path) -> Optional[Dict[str, Dict[str, float]]]:
    if not summary_path.exists():
        return None
    metrics: Dict[str, Dict[str, float]] = {}
    in_slowdown = False
    for raw_line in summary_path.read_text().splitlines():
        line = raw_line.strip()
        if line.startswith("SLOWDOWN"):
            in_slowdown = True
            continue
        if line.startswith("ABSOLUTE"):
            break
        if not in_slowdown:
            continue
        if line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue
        tag = parts[0]
        if tag in {"<THR", "<1BDP"}:
            norm_tag = "SMALL"
        elif tag in {">=THR", ">1BDP"}:
            norm_tag = "LARGE"
        elif tag.lower() == "all":
            norm_tag = "ALL"
        else:
            continue

        metrics[norm_tag] = {
            "avg": float(parts[1]),
            "p50": float(parts[2]),
            "p95": float(parts[3]),
            "p99": float(parts[4]),
            "p999": float(parts[5]),
        }
    if "SMALL" not in metrics or "LARGE" not in metrics:
        return None
    return metrics


def percentile_from_weighted(values: np.ndarray, weights: np.ndarray, percentile: float) -> float:
    total = int(weights.sum())
    if total <= 0:
        return float("nan")
    threshold = percentile / 100.0 * total
    cumsum = np.cumsum(weights)
    idx = int(np.searchsorted(cumsum, threshold, side="left"))
    idx = min(max(idx, 0), len(values) - 1)
    return float(values[idx])


def parse_all_slowdown_cdf(cdf_path: Path) -> Optional[Dict[str, float]]:
    if not cdf_path.exists():
        return None

    values: List[float] = []
    weights: List[int] = []
    for raw in cdf_path.read_text().splitlines():
        parts = raw.strip().split()
        if len(parts) < 2:
            continue
        try:
            values.append(float(parts[0]))
            weights.append(int(float(parts[1])))
        except ValueError:
            continue

    if not values:
        return None

    arr_values = np.array(values, dtype=float)
    arr_weights = np.array(weights, dtype=int)
    total = int(arr_weights.sum())
    if total <= 0:
        return None

    avg = float(np.average(arr_values, weights=arr_weights))
    return {
        "avg": avg,
        "p50": percentile_from_weighted(arr_values, arr_weights, 50),
        "p95": percentile_from_weighted(arr_values, arr_weights, 95),
        "p99": percentile_from_weighted(arr_values, arr_weights, 99),
        "p999": percentile_from_weighted(arr_values, arr_weights, 99.9),
    }


def parse_config(config_path: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not config_path.exists():
        return result
    for line in config_path.read_text().splitlines():
        parts = line.strip().split()
        if len(parts) < 2:
            continue
        key = parts[0]
        if key in {"LOAD", "FLOW_FILE", "BUFFER_SIZE"}:
            result[key] = parts[1]
    return result


def load_sort_key(load_name: str) -> float:
    # load30 -> 30.0
    try:
        return float(load_name.replace("load", ""))
    except Exception:
        return float("inf")


def infer_algo(run_name: str) -> Optional[str]:
    for a in ALG_ORDER:
        if run_name.endswith("_" + a):
            return a
    return None


def detect_cdf(exp_dir: Path) -> str:
    # Prefer from folder name: support both legacy medu_loop_<ts>_<CDF> and new <ts>_<CDF>
    m = re.match(r"(?:medu_loop_)?\d{8}_\d{6}_(.+)", exp_dir.name)
    if m:
        cdf_part = m.group(1)
        # Extract just the CDF name (first segment before _)
        return cdf_part.split("_")[0] if "_" in cdf_part else cdf_part

    # Fallback from config FLOW_FILE
    cfg_files = sorted(exp_dir.glob("load*/**/config.txt"))
    for cfg in cfg_files:
        data = parse_config(cfg)
        flow = data.get("FLOW_FILE", "")
        m2 = re.search(r"CDF_([^_]+)", flow)
        if m2:
            return m2.group(1)

    return "unknownCDF"


def collect_experiment(exp_dir: Path) -> Dict[str, Dict[str, Dict[bool, Dict[str, Dict[str, float]]]]]:
    """
    Return nested dict:
      data[load][algo][with_medu] = summary_metrics
    """
    data: Dict[str, Dict[str, Dict[bool, Dict[str, Dict[str, float]]]]] = defaultdict(lambda: defaultdict(dict))

    load_dirs = sorted([p for p in exp_dir.iterdir() if p.is_dir() and p.name.startswith("load")], key=lambda p: load_sort_key(p.name))
    for load_dir in load_dirs:
        for run_dir in sorted([p for p in load_dir.iterdir() if p.is_dir()]):
            run_name = run_dir.name
            algo = infer_algo(run_name)
            if algo is None:
                continue
            with_medu = run_name.startswith("with_medu")
            summary_path = run_dir / f"{run_name}_out_fct_summary.txt"
            summary = parse_summary(summary_path)
            if summary is None:
                continue

            if "ALL" not in summary:
                all_cdf_path = run_dir / f"{run_name}_out_fct_all_slowdown_cdf.txt"
                all_metrics = parse_all_slowdown_cdf(all_cdf_path)
                if all_metrics is not None:
                    summary["ALL"] = all_metrics

            data[load_dir.name][algo][with_medu] = summary
    return data


def common_loads(experiments: List[ExpData]) -> List[str]:
    if not experiments:
        return []
    common = set(experiments[0].keys())
    for exp in experiments[1:]:
        common = common.intersection(set(exp.keys()))
    return sorted(common, key=load_sort_key)


def common_algos(experiments: List[ExpData]) -> List[str]:
    if not experiments:
        return []
    per_exp_algos = []
    for exp in experiments:
        algos = set()
        for d in exp.values():
            algos.update(d.keys())
        per_exp_algos.append(algos)

    common = per_exp_algos[0]
    for algos in per_exp_algos[1:]:
        common = common.intersection(algos)
    return [a for a in ALG_ORDER if a in common]


def build_conditions(experiments: List[ExpEntry], keep_only_exp_a_no_medu: bool = False):
    conditions = []
    for idx, (label, _) in enumerate(experiments):
        style_idx = idx % len(CONDITION_STYLES)
        no_hatch, yes_hatch, edgecolor = CONDITION_STYLES[style_idx]
        if not keep_only_exp_a_no_medu or idx == 0:
            conditions.append((idx, label, False, 0.55, no_hatch, edgecolor))
        conditions.append((idx, label, True, 1.0, yes_hatch, edgecolor))
    return conditions


def get_metric(
    exp: Dict[str, Dict[str, Dict[bool, Dict[str, Dict[str, float]]]]],
    load: str,
    algo: str,
    with_medu: bool,
    size_tag: str,
    metric: str,
) -> float:
    s = exp.get(load, {}).get(algo, {}).get(with_medu)
    if s is None:
        return float("nan")
    if size_tag not in s:
        return float("nan")
    return float(s[size_tag][metric])


def plot_metric_bars(
    loads: List[str],
    algos: List[str],
    experiments: List[ExpEntry],
    title: str,
    y_label: str,
    size_tag: str,
    metric: str,
    out_png: Path,
    keep_only_exp_a_no_medu: bool = False,
):
    fig, ax = plt.subplots(figsize=(15, 6.2))

    conditions = build_conditions(experiments, keep_only_exp_a_no_medu=keep_only_exp_a_no_medu)

    bar_w = 0.05
    group_gap = 0.42
    group_width = len(conditions) * len(algos) * bar_w

    tick_pos: List[float] = []
    tick_lbl: List[str] = []

    for li, load in enumerate(loads):
        group_start = li * (group_width + group_gap)
        tick_pos.append(group_start + group_width / 2.0)
        tick_lbl.append(load.replace("load", ""))

        for ci, (exp_idx, _label, with_medu, alpha, hatch, edgecolor) in enumerate(conditions):
            cond_start = group_start + ci * len(algos) * bar_w
            for ai, algo in enumerate(algos):
                x = cond_start + ai * bar_w
                exp_data = experiments[exp_idx][1]
                val = get_metric(exp_data, load, algo, with_medu, size_tag, metric)

                ax.bar(
                    x,
                    val,
                    width=bar_w,
                    color=ALG_COLOR.get(algo),
                    alpha=alpha,
                    hatch=hatch,
                    edgecolor=edgecolor,
                    linewidth=0.6,
                )

    ax.set_title(title)
    ax.set_xlabel("Network Load")
    ax.set_ylabel(y_label)
    ax.set_xticks(tick_pos)
    ax.set_xticklabels(tick_lbl)
    ax.grid(axis="y", alpha=0.3)

    algo_handles = [Patch(facecolor=ALG_COLOR[a], edgecolor="black", label=ALG_LABEL.get(a, a)) for a in algos]
    cond_handles = []
    for _exp_idx, label, with_medu, alpha, hatch, edgecolor in conditions:
        suffix = "With MEDU" if with_medu else "No MEDU"
        cond_handles.append(Patch(facecolor="gray", edgecolor=edgecolor, alpha=alpha, hatch=hatch, label=f"{label} ({suffix})"))

    legend1 = ax.legend(handles=algo_handles, loc="upper left", fontsize=8, title="Algorithm")
    ax.add_artist(legend1)
    ax.legend(handles=cond_handles, loc="upper right", fontsize=8, title="Condition")

    plt.tight_layout()

    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    plt.close(fig)


def _plot_metric_bars_on_axis(
    ax,
    load: str,
    algos: List[str],
    experiments: List[ExpEntry],
    title: str,
    y_label: str,
    size_tag: str,
    metric: str,
    show_legend: bool = False,
    keep_only_exp_a_no_medu: bool = False,
):
    conditions = build_conditions(experiments, keep_only_exp_a_no_medu=keep_only_exp_a_no_medu)

    bar_w = 0.12
    x = np.arange(len(algos))

    # offsets for condition bars around each algorithm center
    offsets = [(-2.5 + i) * bar_w for i in range(len(conditions))]

    for ci, (exp_idx, _label, with_medu, alpha, hatch, edgecolor) in enumerate(conditions):
        vals = []
        exp_data = experiments[exp_idx][1]
        for algo in algos:
            val = get_metric(exp_data, load, algo, with_medu, size_tag, metric)
            vals.append(val)

        ax.bar(
            x + offsets[ci],
            vals,
            width=bar_w,
            color=[ALG_COLOR.get(a) for a in algos],
            alpha=alpha,
            hatch=hatch,
            edgecolor=edgecolor,
            linewidth=0.6,
        )

    ax.set_title(title)
    ax.set_ylabel(y_label)
    ax.set_xticks(x)
    ax.set_xticklabels([ALG_LABEL.get(a, a) for a in algos], rotation=0)
    ax.grid(axis="y", alpha=0.3)

    if show_legend:
        algo_handles = [Patch(facecolor=ALG_COLOR[a], edgecolor="black", label=ALG_LABEL.get(a, a)) for a in algos]
        cond_handles = []
        for _exp_idx, label, with_medu, alpha, hatch, edgecolor in conditions:
            suffix = "With MEDU" if with_medu else "No MEDU"
            cond_handles.append(Patch(facecolor="gray", edgecolor=edgecolor, alpha=alpha, hatch=hatch, label=f"{label} ({suffix})"))
        legend1 = ax.legend(handles=algo_handles, loc="upper left", fontsize=8, title="Algorithm")
        ax.add_artist(legend1)
        ax.legend(handles=cond_handles, loc="upper right", fontsize=8, title="Condition")


def plot_per_load_collage(
    loads: List[str],
    algos: List[str],
    experiments: List[ExpEntry],
    out_dir: Path,
    keep_only_exp_a_no_medu: bool = False,
):
    for load in loads:
        fig, axes = plt.subplots(3, 2, figsize=(14, 13))

        _plot_metric_bars_on_axis(
            axes[0, 0], load, algos, experiments,
            "Small Flow (<THR) - Average Slowdown", "Average FCT Slowdown", "SMALL", "avg", show_legend=True,
            keep_only_exp_a_no_medu=keep_only_exp_a_no_medu
        )
        _plot_metric_bars_on_axis(
            axes[0, 1], load, algos, experiments,
            "Small Flow (<THR) - p99 Slowdown", "p99 FCT Slowdown", "SMALL", "p99", show_legend=False,
            keep_only_exp_a_no_medu=keep_only_exp_a_no_medu
        )
        _plot_metric_bars_on_axis(
            axes[1, 0], load, algos, experiments,
            "Large Flow (>=THR) - Average Slowdown", "Average FCT Slowdown", "LARGE", "avg", show_legend=False,
            keep_only_exp_a_no_medu=keep_only_exp_a_no_medu
        )
        _plot_metric_bars_on_axis(
            axes[1, 1], load, algos, experiments,
            "Large Flow (>=THR) - p99 Slowdown", "p99 FCT Slowdown", "LARGE", "p99", show_legend=False,
            keep_only_exp_a_no_medu=keep_only_exp_a_no_medu
        )
        _plot_metric_bars_on_axis(
            axes[2, 0], load, algos, experiments,
            "All Flow - Average Slowdown", "Average FCT Slowdown", "ALL", "avg", show_legend=False,
            keep_only_exp_a_no_medu=keep_only_exp_a_no_medu
        )
        _plot_metric_bars_on_axis(
            axes[2, 1], load, algos, experiments,
            "All Flow - p99 Slowdown", "p99 FCT Slowdown", "ALL", "p99", show_legend=False,
            keep_only_exp_a_no_medu=keep_only_exp_a_no_medu
        )

        load_num = load.replace("load", "")
        labels = [label for label, _ in experiments]
        fig.suptitle(f"Per-Load Comparison (Load={load_num}): {' vs '.join(labels)}", fontsize=14)
        plt.tight_layout(rect=[0, 0, 1, 0.96])

        out_png = out_dir / f"load{load_num}_collage_cmp.png"
        fig.savefig(out_png, dpi=180, bbox_inches="tight")
        plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-plot two to five experiments on same axes")
    parser.add_argument("--exp-a", type=Path, required=True, help="Experiment A directory under mix/output")
    parser.add_argument("--exp-b", type=Path, required=True, help="Experiment B directory under mix/output")
    parser.add_argument("--exp-c", type=Path, default=None, help="Optional Experiment C directory under mix/output")
    parser.add_argument("--exp-d", type=Path, default=None, help="Optional Experiment D directory under mix/output")
    parser.add_argument("--exp-e", type=Path, default=None, help="Optional Experiment E directory under mix/output")
    parser.add_argument("--label-a", type=str, default="9MB")
    parser.add_argument("--label-b", type=str, default="4MB")
    parser.add_argument("--label-c", type=str, default="ExpC")
    parser.add_argument("--label-d", type=str, default="ExpD")
    parser.add_argument("--label-e", type=str, default="ExpE")
    parser.add_argument(
        "--keep-only-exp-a-no-medu",
        action="store_true",
        help="If set, keep only experiment A No MEDU bars/legend; still keep all experiments With MEDU",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=Path(__file__).resolve().parent / "figures",
        help="Output root directory",
    )

    args = parser.parse_args()

    exp_inputs: List[Tuple[str, Path]] = [
        (args.label_a, args.exp_a),
        (args.label_b, args.exp_b),
    ]
    if args.exp_c is not None:
        exp_inputs.append((args.label_c, args.exp_c))
    if args.exp_d is not None:
        exp_inputs.append((args.label_d, args.exp_d))
    if args.exp_e is not None:
        exp_inputs.append((args.label_e, args.exp_e))

    for label, exp_path in exp_inputs:
        if not exp_path.exists() or not exp_path.is_dir():
            raise SystemExit(f"{label} experiment not found: {exp_path}")

    experiments: List[ExpEntry] = [(label, collect_experiment(exp_path)) for label, exp_path in exp_inputs]

    loads = common_loads([data for _, data in experiments])
    if not loads:
        raise SystemExit("No common loads between experiments")

    algos = common_algos([data for _, data in experiments])
    if not algos:
        raise SystemExit("No common algorithms between experiments")

    cdf_list = [detect_cdf(exp_path) for _, exp_path in exp_inputs]
    if len(set(cdf_list)) == 1:
        cdf = cdf_list[0]
    else:
        cdf = "_vs_".join(cdf_list)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.out_root / f"{ts}_{cdf}_cmp"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Small avg slowdown
    plot_metric_bars(
        loads,
        algos,
        experiments,
        "Small Flow (<THR) - Average Slowdown",
        "Average FCT Slowdown",
        "SMALL",
        "avg",
        out_dir / "small_avg_slowdown_cmp.png",
        keep_only_exp_a_no_medu=args.keep_only_exp_a_no_medu,
    )

    # 2) Small p99 slowdown
    plot_metric_bars(
        loads,
        algos,
        experiments,
        "Small Flow (<THR) - p99 Slowdown",
        "p99 FCT Slowdown",
        "SMALL",
        "p99",
        out_dir / "small_p99_slowdown_cmp.png",
        keep_only_exp_a_no_medu=args.keep_only_exp_a_no_medu,
    )

    # 3) Large avg slowdown
    plot_metric_bars(
        loads,
        algos,
        experiments,
        "Large Flow (>=THR) - Average Slowdown",
        "Average FCT Slowdown",
        "LARGE",
        "avg",
        out_dir / "large_avg_slowdown_cmp.png",
        keep_only_exp_a_no_medu=args.keep_only_exp_a_no_medu,
    )

    # 4) Large p99 slowdown
    plot_metric_bars(
        loads,
        algos,
        experiments,
        "Large Flow (>=THR) - p99 Slowdown",
        "p99 FCT Slowdown",
        "LARGE",
        "p99",
        out_dir / "large_p99_slowdown_cmp.png",
        keep_only_exp_a_no_medu=args.keep_only_exp_a_no_medu,
    )

    # 5) Per-load collage images (3x2 each load)
    plot_per_load_collage(
        loads,
        algos,
        experiments,
        out_dir,
        keep_only_exp_a_no_medu=args.keep_only_exp_a_no_medu,
    )

    # 6) All-flow avg slowdown
    plot_metric_bars(
        loads,
        algos,
        experiments,
        "All Flow - Average Slowdown",
        "Average FCT Slowdown",
        "ALL",
        "avg",
        out_dir / "all_avg_slowdown_cmp.png",
        keep_only_exp_a_no_medu=args.keep_only_exp_a_no_medu,
    )

    # 7) All-flow p99 slowdown
    plot_metric_bars(
        loads,
        algos,
        experiments,
        "All Flow - p99 Slowdown",
        "p99 FCT Slowdown",
        "ALL",
        "p99",
        out_dir / "all_p99_slowdown_cmp.png",
        keep_only_exp_a_no_medu=args.keep_only_exp_a_no_medu,
    )

    # brief metadata
    meta = []
    for idx, (label, exp_path) in enumerate(exp_inputs, start=1):
        meta.append(f"exp_{idx}={exp_path}")
        meta.append(f"label_{idx}={label}")
    meta.extend([
        f"cdf={cdf}",
        f"loads={','.join(loads)}",
        f"algos={','.join(algos)}",
        f"keep_only_exp_a_no_medu={args.keep_only_exp_a_no_medu}",
    ])
    (out_dir / "compare_meta.txt").write_text("\n".join(meta))

    print(f"Output directory: {out_dir}")
    print(f"Generated 6 overview PNG files + {len(loads)} per-load collage PNG files")


if __name__ == "__main__":
    main()
