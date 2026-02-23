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
import bisect
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
    cfg: Dict[str, Optional[str]] = {"load": None, "flow_file": None, "buffer": None}
    for raw in config_path.read_text().splitlines():
        parts = raw.strip().split()
        if len(parts) < 2:
            continue
        key, value = parts[0], parts[1]
        if key == "LOAD":
            cfg["load"] = value
        elif key == "FLOW_FILE":
            cfg["flow_file"] = value
        elif key == "BUFFER_SIZE":
            cfg["buffer"] = value
    return cfg


def parse_summary(summary_path: Path) -> Dict[str, Dict[str, float]]:
    """Parse slowdown stats from summary file (<1BDP, >1BDP, optional ALL)."""
    metrics: Dict[str, Dict[str, float]] = {}
    pattern = re.compile(r"^(<1BDP|>1BDP|ALL|All|all),([\d.eE+-]+),([\d.eE+-]+),([\d.eE+-]+),([\d.eE+-]+),([\d.eE+-]+)")
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

        match = pattern.match(line)
        if not match:
            continue
        tag, avg, p50, p95, p99, p999 = match.groups()
        if tag.lower() == "all":
            tag = "ALL"
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


def parse_all_slowdown_from_fct(fct_path: Path) -> Dict[str, float]:
    """Compute all-flow slowdown stats from *_out_fct.txt as fallback."""
    slowdown_values: List[float] = []
    with fct_path.open() as handle:
        for raw in handle:
            parts = raw.strip().split()
            if len(parts) < 8:
                continue
            try:
                fct_ns = float(parts[6])
                ideal_fct_ns = float(parts[7])
            except ValueError:
                continue
            if ideal_fct_ns <= 0:
                continue
            slowdown_values.append(max(1.0, fct_ns / ideal_fct_ns))

    if not slowdown_values:
        raise ValueError(f"No valid flow records found in {fct_path}")

    arr = np.array(slowdown_values, dtype=float)
    return {
        "avg": float(np.average(arr)),
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
        "p999": float(np.percentile(arr, 99.9)),
    }


def parse_all_slowdown_from_cdf(cdf_path: Path) -> Dict[str, float]:
    """Compute all-flow slowdown stats from *_out_fct_all_slowdown_cdf.txt."""
    values: List[float] = []
    counts: List[int] = []

    with cdf_path.open() as handle:
        for raw in handle:
            parts = raw.strip().split()
            if len(parts) < 2:
                continue
            try:
                value = float(parts[0])
                count = int(parts[1])
            except ValueError:
                continue
            if count <= 0:
                continue
            values.append(value)
            counts.append(count)

    if not values:
        raise ValueError(f"No valid CDF records found in {cdf_path}")

    cumulative: List[int] = []
    running = 0
    weighted_sum = 0.0
    for value, count in zip(values, counts):
        running += count
        cumulative.append(running)
        weighted_sum += value * count

    total = cumulative[-1]
    if total <= 0:
        raise ValueError(f"Invalid sample count in {cdf_path}")

    def value_at_index(index: int) -> float:
        idx = bisect.bisect_right(cumulative, index)
        return values[min(idx, len(values) - 1)]

    def percentile(q: float) -> float:
        rank = (q / 100.0) * (total - 1)
        lo = int(np.floor(rank))
        hi = int(np.ceil(rank))
        if lo == hi:
            return value_at_index(lo)
        lo_v = value_at_index(lo)
        hi_v = value_at_index(hi)
        frac = rank - lo
        return (1.0 - frac) * lo_v + frac * hi_v

    return {
        "avg": weighted_sum / total,
        "p50": percentile(50),
        "p95": percentile(95),
        "p99": percentile(99),
        "p999": percentile(99.9),
    }


def collect_runs(base_dir: Path, pattern: str) -> List[Dict[str, object]]:
    """Collect all runs under base_dir, supporting medu_loop and legacy layouts."""
    runs: List[Dict[str, object]] = []

    def iter_comparison_dirs() -> List[Tuple[Path, Path]]:
        load_dirs = sorted(base_dir.glob("load*"))
        if load_dirs:
            return [(base_dir, load_dir) for load_dir in load_dirs if load_dir.is_dir()]

        comp_dirs: List[Tuple[Path, Path]] = []
        for exp_dir in sorted(base_dir.glob(pattern)):
            if not exp_dir.is_dir():
                continue
            exp_load_dirs = sorted(exp_dir.glob("load*"))
            if exp_load_dirs:
                comp_dirs.extend((exp_dir, load_dir) for load_dir in exp_load_dirs if load_dir.is_dir())
            else:
                comp_dirs.append((base_dir, exp_dir))
        return comp_dirs

    for exp_root, comp_dir in iter_comparison_dirs():
        load_hint = None
        match = re.match(r"load(\d+(?:\.\d+)?)", comp_dir.name)
        if match:
            load_hint = match.group(1)

        for log_file in sorted(comp_dir.glob("*.log")):
            run_name = log_file.stem  # e.g., 'no_medu_conga'
            run_root = comp_dir / run_name
            summary_path = run_root / f"{run_name}_out_fct_summary.txt"
            all_slowdown_cdf_path = run_root / f"{run_name}_out_fct_all_slowdown_cdf.txt"
            fct_path = run_root / f"{run_name}_out_fct.txt"
            config_path = run_root / "config.txt"

            # Fallback for old flat structure if needed
            if not summary_path.exists():
                try:
                    run_id = parse_log_for_id(log_file)
                    alt_root = base_dir / run_id
                    if alt_root.exists():
                        run_root = alt_root
                        summary_path = run_root / f"{run_id}_out_fct_summary.txt"
                        all_slowdown_cdf_path = run_root / f"{run_id}_out_fct_all_slowdown_cdf.txt"
                        fct_path = run_root / f"{run_id}_out_fct.txt"
                        config_path = run_root / "config.txt"
                except Exception:
                    pass

            if not summary_path.exists() or not config_path.exists():
                print(f"Skipping {run_name} (missing files in {run_root})")
                continue

            summary = parse_summary(summary_path)
            if "ALL" not in summary:
                try:
                    if all_slowdown_cdf_path.exists():
                        summary["ALL"] = parse_all_slowdown_from_cdf(all_slowdown_cdf_path)
                    elif fct_path.exists():
                        summary["ALL"] = parse_all_slowdown_from_fct(fct_path)
                except Exception as exc:
                    print(f"Warning: failed to compute ALL-flow metrics for {run_name}: {exc}")
            cfg = parse_config(config_path)
            if cfg["load"] is None and load_hint is not None:
                cfg["load"] = load_hint

            algo_key = run_name.split("_")[-1].lower()
            algo = ALG_NAME_MAP.get(algo_key, algo_key.upper())
            with_medu = "with_medu" in run_name

            try:
                run_id = str(run_root.relative_to(base_dir))
            except ValueError:
                run_id = str(run_root)

            runs.append(
                {
                    "load": cfg["load"],
                    "flow_file": cfg["flow_file"],
                    "buffer": cfg["buffer"],
                    "algo": algo,
                    "with_medu": with_medu,
                    "summary": summary,
                    "run_id": run_id,
                    "source_dir": str(exp_root.name),
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
    """Prepare arrays for plotting small/large/all-flow avg and p99 metrics."""
    small_avg_no, small_avg_yes = {}, {}
    small_p99_no, small_p99_yes = {}, {}
    large_avg_no, large_avg_yes = {}, {}
    large_p99_no, large_p99_yes = {}, {}
    all_avg_no, all_avg_yes = {}, {}
    all_p99_no, all_p99_yes = {}, {}

    loads_float = [float(l) for l in load_labels]

    for algo in algos:
        small_avg_no[algo], small_avg_yes[algo] = [], []
        small_p99_no[algo], small_p99_yes[algo] = [], []
        large_avg_no[algo], large_avg_yes[algo] = [], []
        large_p99_no[algo], large_p99_yes[algo] = [], []
        all_avg_no[algo], all_avg_yes[algo] = [], []
        all_p99_no[algo], all_p99_yes[algo] = [], []
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
            large_p99_no[algo].append(metrics_no[">1BDP"]["p99"] if metrics_no else np.nan)
            large_p99_yes[algo].append(metrics_yes[">1BDP"]["p99"] if metrics_yes else np.nan)
            all_avg_no[algo].append(metrics_no["ALL"]["avg"] if metrics_no and "ALL" in metrics_no else np.nan)
            all_avg_yes[algo].append(metrics_yes["ALL"]["avg"] if metrics_yes and "ALL" in metrics_yes else np.nan)
            all_p99_no[algo].append(metrics_no["ALL"]["p99"] if metrics_no and "ALL" in metrics_no else np.nan)
            all_p99_yes[algo].append(metrics_yes["ALL"]["p99"] if metrics_yes and "ALL" in metrics_yes else np.nan)

    return (
        loads_float,
        small_avg_no,
        small_avg_yes,
        small_p99_no,
        small_p99_yes,
        large_avg_no,
        large_avg_yes,
        large_p99_no,
        large_p99_yes,
        all_avg_no,
        all_avg_yes,
        all_p99_no,
        all_p99_yes,
    )


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
    large_p99_no: Dict[str, List[float]],
    large_p99_yes: Dict[str, List[float]],
    all_avg_no: Dict[str, List[float]],
    all_avg_yes: Dict[str, List[float]],
    all_p99_no: Dict[str, List[float]],
    all_p99_yes: Dict[str, List[float]],
    output_dir: Path,
    prefix: str,
):
    fig, axes = plt.subplots(3, 2, figsize=(16, 16))
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

    # Large flow p99
    ax4 = axes[1, 1]
    for i, algo in enumerate(algos):
        ax4.bar(x - 1.5 * width + i * width * 0.8, large_p99_no[algo], width * 0.8,
                label=f"{algo} (No MEDU)", color=colors_no[i % len(colors_no)], alpha=0.7)
    for i, algo in enumerate(algos):
        ax4.bar(x + 0.5 * width + i * width * 0.8, large_p99_yes[algo], width * 0.8,
                label=f"{algo} (With MEDU)", color=colors_yes[i % len(colors_yes)], hatch='///')
    ax4.set_ylabel('p99 FCT Slowdown')
    ax4.set_xlabel('Network Load')
    ax4.set_title('Large Flow (>1BDP) - p99 Slowdown')
    ax4.set_xticks(x)
    ax4.set_xticklabels(load_labels)
    ax4.legend(loc='upper left', fontsize=9, ncol=2)
    ax4.grid(axis='y', alpha=0.3)

    # All flow avg
    ax5 = axes[2, 0]
    for i, algo in enumerate(algos):
        ax5.bar(x - 1.5 * width + i * width * 0.8, all_avg_no[algo], width * 0.8,
                label=f"{algo} (No MEDU)", color=colors_no[i % len(colors_no)], alpha=0.7)
    for i, algo in enumerate(algos):
        ax5.bar(x + 0.5 * width + i * width * 0.8, all_avg_yes[algo], width * 0.8,
                label=f"{algo} (With MEDU)", color=colors_yes[i % len(colors_yes)], hatch='///')
    ax5.set_ylabel('Average FCT Slowdown')
    ax5.set_xlabel('Network Load')
    ax5.set_title('All Flow - Average Slowdown')
    ax5.set_xticks(x)
    ax5.set_xticklabels(load_labels)
    ax5.legend(loc='upper left', fontsize=9, ncol=2)
    ax5.grid(axis='y', alpha=0.3)

    # All flow p99
    ax6 = axes[2, 1]
    for i, algo in enumerate(algos):
        ax6.bar(x - 1.5 * width + i * width * 0.8, all_p99_no[algo], width * 0.8,
                label=f"{algo} (No MEDU)", color=colors_no[i % len(colors_no)], alpha=0.7)
    for i, algo in enumerate(algos):
        ax6.bar(x + 0.5 * width + i * width * 0.8, all_p99_yes[algo], width * 0.8,
                label=f"{algo} (With MEDU)", color=colors_yes[i % len(colors_yes)], hatch='///')
    ax6.set_ylabel('p99 FCT Slowdown')
    ax6.set_xlabel('Network Load')
    ax6.set_title('All Flow - p99 Slowdown')
    ax6.set_xticks(x)
    ax6.set_xticklabels(load_labels)
    ax6.legend(loc='upper left', fontsize=9, ncol=2)
    ax6.grid(axis='y', alpha=0.3)

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
    all_avg_no: Dict[str, List[float]],
    all_avg_yes: Dict[str, List[float]],
    all_p99_no: Dict[str, List[float]],
    all_p99_yes: Dict[str, List[float]],
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

    lines.append("")
    lines.append("ALL-flow average slowdown")
    header_avg = ["Load"] + [f"{algo}-NoMEDU" for algo in algos] + [f"{algo}-WithMEDU" for algo in algos]
    lines.append("\t".join(header_avg))
    for idx, label in enumerate(load_labels):
        row = [label]
        for algo in algos:
            val = all_avg_no[algo][idx]
            row.append(f"{val:.3f}" if not np.isnan(val) else "NA")
        for algo in algos:
            val = all_avg_yes[algo][idx]
            row.append(f"{val:.3f}" if not np.isnan(val) else "NA")
        lines.append("\t".join(row))

    lines.append("")
    lines.append("ALL-flow p99 slowdown")
    header_p99 = ["Load"] + [f"{algo}-NoMEDU" for algo in algos] + [f"{algo}-WithMEDU" for algo in algos]
    lines.append("\t".join(header_p99))
    for idx, label in enumerate(load_labels):
        row = [label]
        for algo in algos:
            val = all_p99_no[algo][idx]
            row.append(f"{val:.3f}" if not np.isnan(val) else "NA")
        for algo in algos:
            val = all_p99_yes[algo][idx]
            row.append(f"{val:.3f}" if not np.isnan(val) else "NA")
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
    parser.add_argument("--pattern", type=str, default="medu_loop_*", help="Glob pattern for comparison folders")
    parser.add_argument("--output-dir", type=Path, default=default_out, help="Directory to place charts and stats")
    parser.add_argument("--prefix", type=str, default="medu_comparison", help="Filename prefix for outputs")
    args = parser.parse_args()

    exp_dirs = sorted([d for d in args.base_dir.glob(args.pattern) if d.is_dir()])
    if not exp_dirs:
        exp_dirs = [args.base_dir]

    any_runs = False
    for exp_dir in exp_dirs:
        runs = collect_runs(exp_dir, args.pattern)
        if not runs:
            continue
        any_runs = True

        match = re.match(r"medu_loop_(\d{8}_\d{6})_(.+)", exp_dir.name)
        if match:
            ts_part = match.group(1)
            desc_part = match.group(2)
            
            # Detect buffer size from runs to ensure it's in the name
            buf_val = None
            for r in runs:
                if r.get("buffer"):
                    buf_val = r["buffer"]
                    break
            
            if buf_val and not desc_part.endswith(f"_{buf_val}MB"):
                subdir_name = f"{ts_part}_{desc_part}_{buf_val}MB"
            else:
                subdir_name = f"{ts_part}_{desc_part}"
        else:
            subdir_name = exp_dir.name
        output_dir = args.output_dir / subdir_name

        load_labels, series = pivot_data(runs)
        algos = sorted({r["algo"] for r in runs})

        (
            loads_float,
            small_avg_no,
            small_avg_yes,
            small_p99_no,
            small_p99_yes,
            large_avg_no,
            large_avg_yes,
            large_p99_no,
            large_p99_yes,
            all_avg_no,
            all_avg_yes,
            all_p99_no,
            all_p99_yes,
        ) = build_metric_arrays(load_labels, series, algos)

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
            large_p99_no,
            large_p99_yes,
            all_avg_no,
            all_avg_yes,
            all_p99_no,
            all_p99_yes,
            output_dir,
            args.prefix,
        )

        write_stats(
            load_labels,
            algos,
            small_p99_no,
            small_p99_yes,
            all_avg_no,
            all_avg_yes,
            all_p99_no,
            all_p99_yes,
            output_dir,
            args.prefix,
        )

    if not any_runs:
        raise SystemExit("No runs found. Check --base-dir and --pattern.")


if __name__ == "__main__":
    main()
