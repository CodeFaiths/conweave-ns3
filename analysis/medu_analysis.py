#!/usr/bin/env python3
"""
Generic MEDU experiment analyzer.

This script scans experiment outputs, parses FCT summaries, and produces charts
and text reports that compare MEDU on/off across loads and load-balancing
algorithms. It is designed to work for new experiment configurations (e.g., new
loads such as 90 or different traffic CDFs) without code changes.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np


ALG_NAME_MAP = {
    "conga": "CONGA",
    "conweave": "ConWeave",
    "fecmp": "FECMP",
    "letflow": "LetFlow",
}


def parse_log_for_id(log_path: Path) -> str:
    """Extract the numeric experiment ID from a log file."""
    pattern = re.compile(r"output/(\d{6,})/")
    for line in log_path.read_text().splitlines():
        match = pattern.search(line)
        if match:
            return match.group(1)
    raise ValueError(f"Run ID not found in {log_path}")


def parse_config(config_path: Path) -> Dict[str, Optional[str]]:
    """Parse key fields from a config.txt file."""
    cfg: Dict[str, Optional[str]] = {"load": None, "flow_file": None}
    for raw in config_path.read_text().splitlines():
        parts = raw.strip().split()
        if len(parts) < 2:
            continue
        key, value = parts[0], parts[1]
        if key == "LOAD":
            cfg["load"] = value
        elif key == "FLOW_FILE":
            cfg["flow_file"] = value
    return cfg


def parse_summary(summary_path: Path) -> Dict[str, Dict[str, float]]:
    """Parse slowdown stats for <1BDP and >1BDP from summary file."""
    metrics: Dict[str, Dict[str, float]] = {}
    pattern = re.compile(r"^(<1BDP|>1BDP),([\d.eE+-]+),([\d.eE+-]+),([\d.eE+-]+),([\d.eE+-]+),([\d.eE+-]+)")
    for line in summary_path.read_text().splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        tag, avg, p50, p95, p99, p999 = match.groups()
        metrics[tag] = {
            "avg": float(avg),
            "p50": float(p50),
            "p95": float(p95),
            "p99": float(p99),
            "p999": float(p999),
        }
    if "<1BDP" not in metrics or ">1BDP" not in metrics:
        raise ValueError(f"Missing slowdown metrics in {summary_path}")
    return metrics


def collect_runs(base_dir: Path, pattern: str) -> List[Dict[str, object]]:
    """Collect all runs that match the pattern under base_dir."""
    runs: List[Dict[str, object]] = []
    for comp_dir in sorted(base_dir.glob(pattern)):
        if not comp_dir.is_dir():
            continue
        for log_file in sorted(comp_dir.glob("*.log")):
            run_id = parse_log_for_id(log_file)
            run_root = base_dir / run_id
            summary_path = run_root / f"{run_id}_out_fct_summary.txt"
            config_path = run_root / "config.txt"
            if not summary_path.exists():
                raise FileNotFoundError(summary_path)
            if not config_path.exists():
                raise FileNotFoundError(config_path)

            summary = parse_summary(summary_path)
            cfg = parse_config(config_path)

            algo_key = log_file.stem.split("_")[-1].lower()
            algo = ALG_NAME_MAP.get(algo_key, algo_key.upper())
            with_medu = "with_medu" in log_file.name

            runs.append(
                {
                    "load": cfg["load"],
                    "flow_file": cfg["flow_file"],
                    "algo": algo,
                    "with_medu": with_medu,
                    "summary": summary,
                    "run_id": run_id,
                    "source_dir": str(comp_dir.name),
                }
            )
    return runs


def to_float_load(load_value: Optional[str]) -> float:
    if load_value is None:
        return float("nan")
    try:
        return float(load_value)
    except ValueError:
        return float("nan")


def pivot_data(runs: List[Dict[str, object]]) -> Tuple[List[str], Dict[str, Dict[str, Dict[bool, Dict[str, float]]]]]:
    """Pivot runs into a structure keyed by load -> algo -> medu flag."""
    load_values: List[float] = []
    series: Dict[str, Dict[str, Dict[bool, Dict[str, float]]]] = defaultdict(lambda: defaultdict(dict))

    for run in runs:
        load = to_float_load(run["load"])
        load_values.append(load)
        algo = str(run["algo"])
        with_medu = bool(run["with_medu"])
        series[load][algo][with_medu] = run["summary"]

    unique_loads = sorted(set(load_values))
    load_labels = [str(int(l)) if l.is_integer() else str(l) for l in unique_loads if not np.isnan(l)]
    return load_labels, series


def build_metric_arrays(load_labels: List[str], series: Dict[str, Dict[str, Dict[bool, Dict[str, float]]]], algos: List[str]):
    """Prepare arrays for plotting small-flow avg/p99 and large-flow avg."""
    small_avg_no, small_avg_yes = {}, {}
    small_p99_no, small_p99_yes = {}, {}
    large_avg_no, large_avg_yes = {}, {}

    loads_float = [float(l) for l in load_labels]

    for algo in algos:
        small_avg_no[algo], small_avg_yes[algo] = [], []
        small_p99_no[algo], small_p99_yes[algo] = [], []
        large_avg_no[algo], large_avg_yes[algo] = [], []
        for load in loads_float:
            metrics_no = series.get(load, {}).get(algo, {}).get(False)
            metrics_yes = series.get(load, {}).get(algo, {}).get(True)
            # Use NaN if data is missing so plots stay aligned.
            small_avg_no[algo].append(metrics_no["<1BDP"]["avg"] if metrics_no else np.nan)
            small_avg_yes[algo].append(metrics_yes["<1BDP"]["avg"] if metrics_yes else np.nan)
            small_p99_no[algo].append(metrics_no["<1BDP"]["p99"] if metrics_no else np.nan)
            small_p99_yes[algo].append(metrics_yes["<1BDP"]["p99"] if metrics_yes else np.nan)
            large_avg_no[algo].append(metrics_no[">1BDP"]["avg"] if metrics_no else np.nan)
            large_avg_yes[algo].append(metrics_yes[">1BDP"]["avg"] if metrics_yes else np.nan)

    return loads_float, small_avg_no, small_avg_yes, small_p99_no, small_p99_yes, large_avg_no, large_avg_yes


def plot_comparison(
    loads: List[float],
    load_labels: List[str],
    algos: List[str],
    small_avg_no: Dict[str, List[float]],
    small_avg_yes: Dict[str, List[float]],
    small_p99_no: Dict[str, List[float]],
    small_p99_yes: Dict[str, List[float]],
    large_avg_no: Dict[str, List[float]],
    large_avg_yes: Dict[str, List[float]],
    output_dir: Path,
    prefix: str,
):
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    colors_no = ['#ff7f7f', '#7fb3ff', '#7fff7f', '#ffbf7f']
    colors_yes = ['#cc0000', '#0050cc', '#00cc00', '#cc8000']

    x = np.arange(len(loads))
    width = 0.18

    # Small flow avg
    ax1 = axes[0, 0]
    for i, algo in enumerate(algos):
        ax1.bar(x - 1.5 * width + i * width * 0.8, small_avg_no[algo], width * 0.8,
                label=f"{algo} (No MEDU)", color=colors_no[i % len(colors_no)], alpha=0.7)
    for i, algo in enumerate(algos):
        ax1.bar(x + 0.5 * width + i * width * 0.8, small_avg_yes[algo], width * 0.8,
                label=f"{algo} (With MEDU)", color=colors_yes[i % len(colors_yes)], hatch='///')
    ax1.set_ylabel('Average FCT Slowdown')
    ax1.set_xlabel('Network Load')
    ax1.set_title('Small Flow (<1BDP) - Average Slowdown')
    ax1.set_xticks(x)
    ax1.set_xticklabels(load_labels)
    ax1.legend(loc='upper left', fontsize=9, ncol=2)
    ax1.grid(axis='y', alpha=0.3)

    # Small flow p99
    ax2 = axes[0, 1]
    for i, algo in enumerate(algos):
        ax2.bar(x - 1.5 * width + i * width * 0.8, small_p99_no[algo], width * 0.8,
                label=f"{algo} (No MEDU)", color=colors_no[i % len(colors_no)], alpha=0.7)
    for i, algo in enumerate(algos):
        ax2.bar(x + 0.5 * width + i * width * 0.8, small_p99_yes[algo], width * 0.8,
                label=f"{algo} (With MEDU)", color=colors_yes[i % len(colors_yes)], hatch='///')
    ax2.set_ylabel('p99 FCT Slowdown')
    ax2.set_xlabel('Network Load')
    ax2.set_title('Small Flow (<1BDP) - p99 Slowdown')
    ax2.set_xticks(x)
    ax2.set_xticklabels(load_labels)
    ax2.legend(loc='upper left', fontsize=9, ncol=2)
    ax2.grid(axis='y', alpha=0.3)

    # Large flow avg
    ax3 = axes[1, 0]
    for i, algo in enumerate(algos):
        ax3.bar(x - 1.5 * width + i * width * 0.8, large_avg_no[algo], width * 0.8,
                label=f"{algo} (No MEDU)", color=colors_no[i % len(colors_no)], alpha=0.7)
    for i, algo in enumerate(algos):
        ax3.bar(x + 0.5 * width + i * width * 0.8, large_avg_yes[algo], width * 0.8,
                label=f"{algo} (With MEDU)", color=colors_yes[i % len(colors_yes)], hatch='///')
    ax3.set_ylabel('Average FCT Slowdown')
    ax3.set_xlabel('Network Load')
    ax3.set_title('Large Flow (>1BDP) - Average Slowdown')
    ax3.set_xticks(x)
    ax3.set_xticklabels(load_labels)
    ax3.legend(loc='upper left', fontsize=9, ncol=2)
    ax3.grid(axis='y', alpha=0.3)

    # Improvement in p99 small-flow
    ax4 = axes[1, 1]
    for i, algo in enumerate(algos):
        improvements = []
        for a_no, a_yes in zip(small_p99_no[algo], small_p99_yes[algo]):
            if np.isnan(a_no) or np.isnan(a_yes) or a_no == 0:
                improvements.append(np.nan)
            else:
                improvements.append((1 - a_yes / a_no) * 100)
        ax4.plot(load_labels, improvements, marker='o', linewidth=2, markersize=7,
                 label=algo, color=colors_yes[i % len(colors_yes)])
    ax4.set_ylabel('Improvement Rate (%)')
    ax4.set_xlabel('Network Load')
    ax4.set_title('Small Flow p99 Improvement with MEDU')
    ax4.set_ylim(0, 100)
    ax4.legend(loc='lower right', fontsize=9)
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    output_dir.mkdir(parents=True, exist_ok=True)
    png_path = output_dir / f"{prefix}_charts.png"
    pdf_path = output_dir / f"{prefix}_charts.pdf"
    plt.savefig(png_path, dpi=150, bbox_inches='tight')
    plt.savefig(pdf_path, bbox_inches='tight')
    print(f"Charts saved to {png_path} and {pdf_path}")


def write_stats(
    load_labels: List[str],
    algos: List[str],
    small_p99_no: Dict[str, List[float]],
    small_p99_yes: Dict[str, List[float]],
    output_dir: Path,
    prefix: str,
):
    lines: List[str] = []
    lines.append("MEDU tail-latency improvement (small flow p99)")
    header = ["Load"] + algos
    lines.append("\t".join(header))
    for idx, label in enumerate(load_labels):
        row = [label]
        for algo in algos:
            base = small_p99_no[algo][idx]
            medu = small_p99_yes[algo][idx]
            if np.isnan(base) or np.isnan(medu) or base == 0:
                row.append("NA")
            else:
                row.append(f"{(1 - medu / base) * 100:.1f}%")
        lines.append("\t".join(row))

    output_dir.mkdir(parents=True, exist_ok=True)
    stats_path = output_dir / f"{prefix}_stats.txt"
    stats_path.write_text("\n".join(lines))
    print(f"Stats saved to {stats_path}")


def main():
    repo_root = Path(__file__).resolve().parent.parent
    default_base = repo_root / "mix" / "output"
    default_out = repo_root / "analysis" / "figures"

    parser = argparse.ArgumentParser(description="MEDU experiment analyzer")
    parser.add_argument("--base-dir", type=Path, default=default_base, help="Directory containing experiment outputs")
    parser.add_argument("--pattern", type=str, default="medu_comparison_*", help="Glob pattern for comparison folders")
    parser.add_argument("--output-dir", type=Path, default=default_out, help="Directory to place charts and stats")
    parser.add_argument("--prefix", type=str, default="medu_comparison", help="Filename prefix for outputs")
    args = parser.parse_args()

    runs = collect_runs(args.base_dir, args.pattern)
    if not runs:
        raise SystemExit("No runs found. Check --base-dir and --pattern.")

    load_labels, series = pivot_data(runs)
    algos = sorted({r["algo"] for r in runs})

    loads_float, small_avg_no, small_avg_yes, small_p99_no, small_p99_yes, large_avg_no, large_avg_yes = build_metric_arrays(
        load_labels, series, algos
    )

    plot_comparison(
        loads_float,
        load_labels,
        algos,
        small_avg_no,
        small_avg_yes,
        small_p99_no,
        small_p99_yes,
        large_avg_no,
        large_avg_yes,
        args.output_dir,
        args.prefix,
    )

    write_stats(load_labels, algos, small_p99_no, small_p99_yes, args.output_dir, args.prefix)


if __name__ == "__main__":
    main()
