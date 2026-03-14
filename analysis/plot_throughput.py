#!/usr/bin/env python3

from __future__ import annotations

import argparse
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np


ALG_ORDER = ["fecmp", "letflow", "conga", "conweave"]
ALG_LABEL = {
    "fecmp": "FECMP",
    "letflow": "LetFlow",
    "conga": "CONGA",
    "conweave": "ConWeave",
}
MEDU_LABEL = {
    "no_medu": "MEDU Off",
    "with_medu": "MEDU On",
}
MEDU_COLOR = {
    "no_medu": "#4c566a",
    "with_medu": "#1f77b4",
}
GAIN_COLOR = {
    "short": "#2ca02c",
    "long": "#d62728",
}


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    default_output_dir = script_dir / "figures"
    parser = argparse.ArgumentParser(
        description="Plot short/long throughput vs load and MEDU gain charts from mix/output runs."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help="Directory for output figures. Default: analysis/figures",
    )
    parser.add_argument(
        "--roots",
        nargs="*",
        default=None,
        help="Optional experiment root directories under mix/output. Default: auto-discover *_CC0/*_CC1 roots.",
    )
    parser.add_argument(
        "--metric",
        choices=["flow-mean", "aggregate"],
        default="flow-mean",
        help="Throughput definition: mean per-flow throughput or aggregate goodput.",
    )
    parser.add_argument(
        "--time-limit-begin",
        type=int,
        default=2005000000,
        help="Only consider flows with start time > this value (ns).",
    )
    parser.add_argument(
        "--time-limit-end",
        type=int,
        default=100000000000,
        help="Only consider flows with end time < this value (ns).",
    )
    return parser.parse_args()


def infer_dataset(root_name: str) -> str:
    tokens = root_name.split("_")
    if len(tokens) < 4:
        return root_name
    return tokens[2]


def infer_cc_mode(root_name: str) -> str:
    if root_name.endswith("_CC1"):
        return "CC1"
    if root_name.endswith("_CC0"):
        return "CC0"
    return "unknown"


def load_sort_key(load_name: str) -> float:
    try:
        return float(load_name.replace("load", ""))
    except ValueError:
        return math.inf


def discover_roots(output_root: Path) -> List[Path]:
    roots = []
    for path in sorted(output_root.iterdir()):
        if not path.is_dir():
            continue
        if path.name.endswith("_CC0") or path.name.endswith("_CC1"):
            if any(child.is_dir() and child.name.startswith("load") for child in path.iterdir()):
                roots.append(path)
    return roots


def parse_threshold(config_path: Path) -> int:
    for line in config_path.read_text().splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0] == "FLOW_SIZE_THRESHOLD":
            return int(parts[1])
    raise ValueError(f"FLOW_SIZE_THRESHOLD missing in {config_path}")


def parse_run_name(run_name: str) -> Optional[Tuple[str, str]]:
    match = re.match(r"^(no_medu|with_medu)_(.+)$", run_name)
    if match is None:
        return None
    medu, lb = match.group(1), match.group(2)
    if lb not in ALG_ORDER:
        return None
    return medu, lb


def compute_run_metrics(
    fct_path: Path,
    threshold: int,
    metric: str,
    time_limit_begin: int,
    time_limit_end: int,
) -> Dict[str, float]:
    short_values: List[float] = []
    long_values: List[float] = []
    short_bytes = 0
    long_bytes = 0
    short_fct_ns = 0
    long_fct_ns = 0

    with fct_path.open() as handle:
        for raw_line in handle:
            parts = raw_line.split()
            if len(parts) < 8:
                continue
            size = int(parts[4])
            start_time = int(parts[5])
            fct_ns = int(parts[6])
            end_time = start_time + fct_ns
            if not (start_time > time_limit_begin and end_time < time_limit_end):
                continue
            flow_gbps = size * 8.0 / fct_ns
            if size < threshold:
                short_values.append(flow_gbps)
                short_bytes += size
                short_fct_ns += fct_ns
            else:
                long_values.append(flow_gbps)
                long_bytes += size
                long_fct_ns += fct_ns

    if not short_values or not long_values:
        raise ValueError(f"Missing short/long flows in {fct_path}")

    if metric == "flow-mean":
        short_tp = float(sum(short_values) / len(short_values))
        long_tp = float(sum(long_values) / len(long_values))
    else:
        short_tp = float(short_bytes * 8.0 / short_fct_ns)
        long_tp = float(long_bytes * 8.0 / long_fct_ns)

    return {
        "short": short_tp,
        "long": long_tp,
    }


def collect_data(
    roots: Iterable[Path],
    metric: str,
    time_limit_begin: int,
    time_limit_end: int,
) -> Dict[str, Dict[str, Dict[int, Dict[str, Dict[str, float]]]]]:
    data: Dict[str, Dict[str, Dict[int, Dict[str, Dict[str, float]]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    )

    for root in roots:
        dataset = infer_dataset(root.name)
        cc_mode = infer_cc_mode(root.name)
        for load_dir in sorted(root.iterdir(), key=lambda path: load_sort_key(path.name)):
            if not load_dir.is_dir() or not load_dir.name.startswith("load"):
                continue
            load = int(load_dir.name.replace("load", ""))
            for run_dir in sorted(load_dir.iterdir()):
                if not run_dir.is_dir():
                    continue
                parsed = parse_run_name(run_dir.name)
                if parsed is None:
                    continue
                medu, lb = parsed
                threshold = parse_threshold(run_dir / "config.txt")
                fct_path = run_dir / f"{run_dir.name}_out_fct.txt"
                metrics = compute_run_metrics(
                    fct_path,
                    threshold,
                    metric,
                    time_limit_begin,
                    time_limit_end,
                )
                data[dataset][cc_mode][load][medu][lb] = metrics["short"]
                data[dataset][cc_mode][load].setdefault(f"{medu}_long", {})[lb] = metrics["long"]
    return data


def summarize_by_load(
    data: Dict[str, Dict[str, Dict[int, Dict[str, Dict[str, float]]]]]
) -> Dict[str, Dict[str, Dict[str, Dict[int, float]]]]:
    summary: Dict[str, Dict[str, Dict[str, Dict[int, float]]]] = defaultdict(lambda: defaultdict(dict))
    for dataset, cc_block in data.items():
        for cc_mode, load_block in cc_block.items():
            short_off: Dict[int, float] = {}
            short_on: Dict[int, float] = {}
            long_off: Dict[int, float] = {}
            long_on: Dict[int, float] = {}
            for load, medu_block in sorted(load_block.items()):
                short_off[load] = float(np.mean(list(medu_block["no_medu"].values())))
                short_on[load] = float(np.mean(list(medu_block["with_medu"].values())))
                long_off[load] = float(np.mean(list(medu_block["no_medu_long"].values())))
                long_on[load] = float(np.mean(list(medu_block["with_medu_long"].values())))
            summary[dataset][cc_mode]["short_no_medu"] = short_off
            summary[dataset][cc_mode]["short_with_medu"] = short_on
            summary[dataset][cc_mode]["long_no_medu"] = long_off
            summary[dataset][cc_mode]["long_with_medu"] = long_on
    return summary


def plot_throughput_curves(
    summary: Dict[str, Dict[str, Dict[str, Dict[int, float]]]],
    flow_type: str,
    metric: str,
    output_dir: Path,
) -> Path:
    datasets = sorted(summary.keys())
    cc_modes = ["CC0", "CC1"]
    fig, axes = plt.subplots(len(datasets), len(cc_modes), figsize=(12, 7), sharex=True)
    axes = np.atleast_2d(axes)
    marker_map = {"no_medu": "o", "with_medu": "s"}

    for row, dataset in enumerate(datasets):
        for col, cc_mode in enumerate(cc_modes):
            ax = axes[row, col]
            if cc_mode not in summary[dataset]:
                ax.set_visible(False)
                continue
            no_key = f"{flow_type}_no_medu"
            on_key = f"{flow_type}_with_medu"
            load_to_value = {
                "no_medu": summary[dataset][cc_mode][no_key],
                "with_medu": summary[dataset][cc_mode][on_key],
            }
            for medu, values in load_to_value.items():
                loads = sorted(values.keys())
                y = [values[load] for load in loads]
                ax.plot(
                    loads,
                    y,
                    marker=marker_map[medu],
                    linewidth=2.2,
                    markersize=6,
                    color=MEDU_COLOR[medu],
                    label=MEDU_LABEL[medu],
                )
            ax.set_title(f"{dataset} {cc_mode}")
            ax.set_xlabel("Load (%)")
            ax.set_ylabel(f"{flow_type.capitalize()} throughput (Gbps)")
            ax.grid(True, linestyle="--", linewidth=0.6, alpha=0.4)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.legend(frameon=False)

    fig.suptitle(f"{flow_type.capitalize()} throughput vs load ({metric})", fontsize=14)
    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    output_path = output_dir / f"{flow_type}_throughput_vs_load_{metric}.png"
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output_path


def plot_gain_bars(
    summary: Dict[str, Dict[str, Dict[str, Dict[int, float]]]],
    flow_type: str,
    metric: str,
    output_dir: Path,
) -> Path:
    datasets = sorted(summary.keys())
    cc_modes = ["CC0", "CC1"]
    fig, axes = plt.subplots(len(datasets), len(cc_modes), figsize=(12, 7), sharey=True)
    axes = np.atleast_2d(axes)
    bar_color = GAIN_COLOR[flow_type]

    for row, dataset in enumerate(datasets):
        for col, cc_mode in enumerate(cc_modes):
            ax = axes[row, col]
            if cc_mode not in summary[dataset]:
                ax.set_visible(False)
                continue
            no_values = summary[dataset][cc_mode][f"{flow_type}_no_medu"]
            on_values = summary[dataset][cc_mode][f"{flow_type}_with_medu"]
            loads = sorted(no_values.keys())
            gains = [((on_values[load] / no_values[load]) - 1.0) * 100.0 for load in loads]
            x = np.arange(len(loads))
            ax.bar(x, gains, color=bar_color, width=0.62, alpha=0.88)
            ax.axhline(0.0, color="#444444", linewidth=1.0)
            ax.set_xticks(x)
            ax.set_xticklabels([str(load) for load in loads])
            ax.set_title(f"{dataset} {cc_mode}")
            ax.set_xlabel("Load (%)")
            ax.set_ylabel("MEDU gain (%)")
            ax.grid(True, axis="y", linestyle="--", linewidth=0.6, alpha=0.35)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            for xpos, gain in zip(x, gains):
                va = "bottom" if gain >= 0 else "top"
                offset = 0.8 if gain >= 0 else -0.8
                ax.text(xpos, gain + offset, f"{gain:.1f}%", ha="center", va=va, fontsize=8)

    fig.suptitle(f"MEDU gain for {flow_type} throughput ({metric})", fontsize=14)
    fig.tight_layout(rect=[0, 0.02, 1, 0.95])
    output_path = output_dir / f"{flow_type}_medu_gain_{metric}.png"
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)
    return output_path


def write_summary_text(
    summary: Dict[str, Dict[str, Dict[str, Dict[int, float]]]],
    metric: str,
    output_dir: Path,
) -> Path:
    lines: List[str] = []
    for dataset in sorted(summary.keys()):
        for cc_mode in ["CC0", "CC1"]:
            if cc_mode not in summary[dataset]:
                continue
            lines.append(f"[{dataset} {cc_mode}]")
            for load in sorted(summary[dataset][cc_mode]["short_no_medu"].keys()):
                short_off = summary[dataset][cc_mode]["short_no_medu"][load]
                short_on = summary[dataset][cc_mode]["short_with_medu"][load]
                long_off = summary[dataset][cc_mode]["long_no_medu"][load]
                long_on = summary[dataset][cc_mode]["long_with_medu"][load]
                lines.append(
                    "load={load}: short {s0:.3f}->{s1:.3f} ({sg:+.2f}%), long {l0:.3f}->{l1:.3f} ({lg:+.2f}%)".format(
                        load=load,
                        s0=short_off,
                        s1=short_on,
                        sg=(short_on / short_off - 1.0) * 100.0,
                        l0=long_off,
                        l1=long_on,
                        lg=(long_on / long_off - 1.0) * 100.0,
                    )
                )
            lines.append("")
    output_path = output_dir / f"medu_throughput_summary_{metric}.txt"
    output_path.write_text("\n".join(lines))
    return output_path


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    output_root = script_dir.parent / "mix" / "output"
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.roots:
        roots = [output_root / root for root in args.roots]
    else:
        roots = discover_roots(output_root)
    if not roots:
        raise SystemExit("No experiment roots found under mix/output")

    data = collect_data(
        roots,
        args.metric,
        args.time_limit_begin,
        args.time_limit_end,
    )
    summary = summarize_by_load(data)

    generated = [
        plot_throughput_curves(summary, "short", args.metric, output_dir),
        plot_throughput_curves(summary, "long", args.metric, output_dir),
        plot_gain_bars(summary, "short", args.metric, output_dir),
        plot_gain_bars(summary, "long", args.metric, output_dir),
        write_summary_text(summary, args.metric, output_dir),
    ]

    print("Generated files:")
    for path in generated:
        print(path)


if __name__ == "__main__":
    main()