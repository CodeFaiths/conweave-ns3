import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
DEFAULT_INPUT_PATH = REPO_ROOT / "mix" / "output"
DEFAULT_OUT_ROOT = REPO_ROOT / "analysis" / "figures"
DEFAULT_PLOT_STYLE = "line"
DEFAULT_BIN_STAT = "mean"
DEFAULT_SMOOTH_WINDOW = 1
DEFAULT_LINE_WIDTH_SCALE = 2.0
PAPER_PLOT_STYLE = "line"
PAPER_BIN_MS = 0.5
PAPER_BIN_STAT = "max"
PAPER_SMOOTH_WINDOW = 3
PAPER_LINE_WIDTH_SCALE = 3.5


def compute_stat(values: List[float], stat: str) -> float:
    if not values:
        return 0.0
    if stat == "mean":
        return sum(values) / len(values)
    if stat == "max":
        return max(values)
    if stat == "p95":
        sorted_values = sorted(values)
        if len(sorted_values) == 1:
            return sorted_values[0]
        rank = 0.95 * (len(sorted_values) - 1)
        lower = int(rank)
        upper = min(lower + 1, len(sorted_values) - 1)
        weight = rank - lower
        return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight
    raise ValueError(f"Unsupported stat: {stat}")


def aggregate_series(times: List[float], values: List[float], bin_ms: Optional[float], stat: str) -> Tuple[List[float], List[float]]:
    if not times or not values or bin_ms is None or bin_ms <= 0:
        return times, values

    grouped_times: List[List[float]] = []
    grouped_values: List[List[float]] = []
    start_time = times[0]
    current_bin = None

    for time_ms, value in zip(times, values):
        bin_index = int((time_ms - start_time) // bin_ms)
        if current_bin != bin_index:
            grouped_times.append([])
            grouped_values.append([])
            current_bin = bin_index
        grouped_times[-1].append(time_ms)
        grouped_values[-1].append(value)

    agg_times = [sum(bucket) / len(bucket) for bucket in grouped_times if bucket]
    agg_values = [compute_stat(bucket, stat) for bucket in grouped_values if bucket]
    return agg_times, agg_values


def smooth_values(values: List[float], window: int) -> List[float]:
    if not values or window <= 1:
        return values

    half_window = window // 2
    prefix_sum = [0.0]
    for value in values:
        prefix_sum.append(prefix_sum[-1] + value)

    smoothed: List[float] = []
    for idx in range(len(values)):
        left = max(0, idx - half_window)
        right = min(len(values), idx + half_window + 1)
        smoothed.append((prefix_sum[right] - prefix_sum[left]) / (right - left))

    return smoothed


def smooth_series(times: List[float], values: List[float], window: int) -> Tuple[List[float], List[float]]:
    if not times or not values:
        return times, values

    return times, smooth_values(values, window)


def transform_series(
    times: List[float],
    values: List[float],
    bin_ms: Optional[float],
    bin_stat: str,
    smooth_window: int,
) -> Tuple[List[float], List[float]]:
    out_times, out_values = aggregate_series(times, values, bin_ms, bin_stat)
    return smooth_series(out_times, out_values, smooth_window)


def transform_flow_split_series(
    times: List[float],
    ingress: List[float],
    short_values: List[float],
    long_values: List[float],
    bin_ms: Optional[float],
    bin_stat: str,
    smooth_window: int,
) -> Tuple[List[float], List[float], List[float], List[float]]:
    if not times:
        return times, ingress, short_values, long_values

    agg_times = list(times)
    agg_ingress = list(ingress)
    agg_short = list(short_values)
    agg_long = list(long_values)

    if bin_ms is not None and bin_ms > 0:
        grouped_times: List[List[float]] = []
        grouped_ingress: List[List[float]] = []
        grouped_short: List[List[float]] = []
        grouped_long: List[List[float]] = []
        start_time = times[0]
        current_bin = None

        for time_ms, ingress_value, short_value, long_value in zip(times, ingress, short_values, long_values):
            bin_index = int((time_ms - start_time) // bin_ms)
            if current_bin != bin_index:
                grouped_times.append([])
                grouped_ingress.append([])
                grouped_short.append([])
                grouped_long.append([])
                current_bin = bin_index
            grouped_times[-1].append(time_ms)
            grouped_ingress[-1].append(ingress_value)
            grouped_short[-1].append(short_value)
            grouped_long[-1].append(long_value)

        agg_times = [sum(bucket) / len(bucket) for bucket in grouped_times if bucket]
        agg_ingress = [compute_stat(bucket, bin_stat) for bucket in grouped_ingress if bucket]
        agg_short = [compute_stat(bucket, bin_stat) for bucket in grouped_short if bucket]
        agg_long = [compute_stat(bucket, bin_stat) for bucket in grouped_long if bucket]

    smooth_ingress = smooth_values(agg_ingress, smooth_window)
    smooth_short = smooth_values(agg_short, smooth_window)
    smooth_long = smooth_values(agg_long, smooth_window)
    smooth_total = [short_value + long_value for short_value, long_value in zip(smooth_short, smooth_long)]

    return agg_times, smooth_ingress, smooth_total, smooth_short, smooth_long


def draw_series(ax, times: List[float], values: List[float], plot_style: str, **kwargs) -> None:
    if plot_style == "step":
        ax.step(times, values, where="post", **kwargs)
    else:
        ax.plot(times, values, **kwargs)


def resolve_plot_options(args) -> Tuple[str, Optional[float], str, int, float]:
    if args.paper:
        plot_style = args.plot_style or PAPER_PLOT_STYLE
        bin_ms = args.bin_ms if args.bin_ms is not None else PAPER_BIN_MS
        bin_stat = args.bin_stat or PAPER_BIN_STAT
        smooth_window = args.smooth_window if args.smooth_window is not None else PAPER_SMOOTH_WINDOW
        line_width_scale = args.line_width_scale if args.line_width_scale is not None else PAPER_LINE_WIDTH_SCALE
    else:
        plot_style = args.plot_style or DEFAULT_PLOT_STYLE
        bin_ms = args.bin_ms
        bin_stat = args.bin_stat or DEFAULT_BIN_STAT
        smooth_window = args.smooth_window if args.smooth_window is not None else DEFAULT_SMOOTH_WINDOW
        line_width_scale = args.line_width_scale if args.line_width_scale is not None else DEFAULT_LINE_WIDTH_SCALE

    return plot_style, bin_ms, bin_stat, max(1, smooth_window), max(0.1, line_width_scale)

def parse_qlen(file_path: Path) -> Tuple[Optional[str], Dict[Tuple[int, int], Dict[str, object]]]:
    data: Dict[Tuple[int, int], Dict[str, object]] = {}
    fmt: Optional[str] = None
    if not file_path.exists():
        return fmt, data

    with file_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            parts = [x.strip() for x in line.split(",")]
            if fmt is None:
                if len(parts) == 5:
                    fmt = "legacy"
                elif len(parts) == 9:
                    fmt = "flow-split"
                else:
                    continue

            if fmt == "legacy" and len(parts) != 5:
                continue
            if fmt == "flow-split" and len(parts) != 9:
                continue

            try:
                t_ns = int(parts[0])
                sw = int(parts[1])
                port = int(parts[2])
                ing = int(parts[3])
                eg = int(parts[4])
                short_pg = int(parts[5]) if fmt == "flow-split" else None
                short_eg = int(parts[6]) if fmt == "flow-split" else None
                long_pg = int(parts[7]) if fmt == "flow-split" else None
                long_eg = int(parts[8]) if fmt == "flow-split" else None
            except ValueError:
                continue

            key = (sw, port)
            if key not in data:
                data[key] = {"times": [], "ingress": [], "egress": []}
                if fmt == "flow-split":
                    data[key]["short"] = []
                    data[key]["long"] = []
                    data[key]["short_pg"] = short_pg
                    data[key]["long_pg"] = long_pg

            data[key]["times"].append(t_ns / 1e6)
            data[key]["ingress"].append(ing / 1000.0)
            data[key]["egress"].append(eg / 1000.0)
            if fmt == "flow-split":
                data[key]["short"].append(short_eg / 1000.0)
                data[key]["long"].append(long_eg / 1000.0)

    return fmt, data

def parse_include_label(lbl: str) -> Optional[Tuple[int, int]]:
    s = lbl.strip().upper()
    if not s:
        return None
    if s.startswith("SW"):
        body = s[2:]
    elif s.startswith("S"):
        body = s[1:]
    else:
        return None
    parts = body.split("-")
    if len(parts) != 2:
        return None
    node_str, port_str = parts[0], parts[1]
    if port_str.startswith("P"):
        port_str = port_str[1:]
    if node_str.isdigit() and port_str.isdigit():
        return (int(node_str), int(port_str))
    return None


def collect_qlen_files(input_path: Path, pattern: str) -> List[Path]:
    if input_path.is_file():
        return [input_path] if input_path.name.endswith("qlen.txt") else []

    if not input_path.exists() or not input_path.is_dir():
        return []

    return sorted([p for p in input_path.rglob(pattern) if p.is_file()])


def resolve_output_dir(qlen_file: Path, output_root: Path, base_output_dir: Path) -> Path:
    qlen_parent = qlen_file.resolve().parent
    base_resolved = base_output_dir.resolve()
    try:
        rel = qlen_parent.relative_to(base_resolved)
        return output_root / rel
    except ValueError:
        return output_root / qlen_parent.name


def plot_one_file(
    qlen_file: Path,
    output_dir: Path,
    include_pairs: Optional[set],
    time_range: Optional[List[float]],
    max_ports: int,
    plot_style: str,
    bin_ms: Optional[float],
    bin_stat: str,
    smooth_window: int,
    line_width_scale: float,
) -> Optional[Path]:
    fmt, data = parse_qlen(qlen_file)
    if not data:
        print(f"[SKIP] no valid data: {qlen_file}")
        return None

    plot_keys = sorted(data.keys())
    if include_pairs:
        plot_keys = [k for k in plot_keys if k in include_pairs]

    if not plot_keys:
        print(f"[SKIP] no matching ports after --include filter: {qlen_file}")
        return None

    t_start_ms = time_range[0] * 1000.0 if time_range else None
    t_end_ms = time_range[1] * 1000.0 if time_range else None

    if len(plot_keys) > max_ports:
        print(
            f"[INFO] {qlen_file.name}: ports {len(plot_keys)} > max-ports {max_ports}, keep first {max_ports}."
        )
        plot_keys = plot_keys[:max_ports]

    line_styles = ["-", "--", "-.", ":"]
    markers = ["o", "s", "^", "v", "D", "p", "*", "h"]

    if fmt == "flow-split":
        fig, (ax_port, ax_long, ax_short) = plt.subplots(3, 1, figsize=(12, 13), sharex=True)
    else:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)
    has_data = False

    for idx, key in enumerate(plot_keys):
        d = data[key]
        times = list(d["times"])
        ingress = list(d["ingress"])
        egress = list(d["egress"])
        short_q = list(d.get("short", []))
        long_q = list(d.get("long", []))

        if t_start_ms is not None and t_end_ms is not None:
            filtered_indices = [i for i, t in enumerate(times) if t_start_ms <= t <= t_end_ms]
            if not filtered_indices:
                continue
            times = [times[i] for i in filtered_indices]
            ingress = [ingress[i] for i in filtered_indices]
            egress = [egress[i] for i in filtered_indices]
            if fmt == "flow-split":
                short_q = [short_q[i] for i in filtered_indices]
                long_q = [long_q[i] for i in filtered_indices]

        if not times:
            continue

        has_data = True
        label = f"SW{key[0]}-P{key[1]}"
        linestyle = line_styles[idx % len(line_styles)]
        marker = markers[idx % len(markers)] if bin_ms is None and smooth_window <= 1 and plot_style == "line" else None
        linewidth = (1.5 + (idx % 3) * 0.3) * line_width_scale
        markevery = max(1, len(times) // 20)

        if fmt == "flow-split":
            flow_times, ingress_vals, egress_vals, short_vals, long_vals = transform_flow_split_series(
                times,
                ingress,
                short_q,
                long_q,
                bin_ms,
                bin_stat,
                smooth_window,
            )

            draw_series(
                ax_port,
                flow_times,
                egress_vals,
                plot_style=plot_style,
                label=f"{label} total-egress",
                linewidth=linewidth,
                linestyle=linestyle,
                marker=marker,
                markersize=4,
                markevery=markevery,
                alpha=0.85,
            )
            draw_series(
                ax_port,
                flow_times,
                ingress_vals,
                plot_style=plot_style,
                label=f"{label} ingress",
                linewidth=max(1.0, linewidth - 0.2),
                linestyle=":",
                marker=None,
                alpha=0.6,
            )

            short_pg = d.get("short_pg")
            long_pg = d.get("long_pg")
            draw_series(
                ax_short,
                flow_times,
                short_vals,
                plot_style=plot_style,
                label=f"{label} short(PG{short_pg})",
                linewidth=linewidth,
                linestyle="-",
                marker=marker,
                markersize=4,
                markevery=markevery,
                alpha=0.9,
            )
            draw_series(
                ax_long,
                flow_times,
                long_vals,
                plot_style=plot_style,
                label=f"{label} long(PG{long_pg})",
                linewidth=linewidth,
                linestyle="--",
                marker=None,
                alpha=0.9,
            )
        else:
            ingress_times, ingress_vals = transform_series(times, ingress, bin_ms, bin_stat, smooth_window)
            egress_times, egress_vals = transform_series(times, egress, bin_ms, bin_stat, smooth_window)

            draw_series(
                ax1,
                ingress_times,
                ingress_vals,
                plot_style=plot_style,
                label=label,
                linewidth=linewidth,
                linestyle=linestyle,
                marker=marker,
                markersize=4,
                markevery=markevery,
                alpha=0.85,
            )
            draw_series(
                ax2,
                egress_times,
                egress_vals,
                plot_style=plot_style,
                label=label,
                linewidth=linewidth,
                linestyle=linestyle,
                marker=marker,
                markersize=4,
                markevery=markevery,
                alpha=0.85,
            )

    if not has_data:
        print(f"[SKIP] no data in requested time range: {qlen_file}")
        plt.close(fig)
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    out_png = output_dir / f"{qlen_file.stem}.png"

    if fmt == "flow-split":
        ax_port.set_ylabel("Port Queue (KB)", fontsize=12)
        ax_port.set_title(f"Queue Length over Time - {qlen_file.stem} (flow split)", fontsize=14)
        ax_long.set_ylabel("Long Queue (KB)", fontsize=12)
        ax_short.set_ylabel("Short Queue (KB)", fontsize=12)

        ax_port.grid(True, linestyle=":", alpha=0.5)
        ax_port.legend(fontsize=8, loc="best", ncol=2, framealpha=0.9)
        ax_long.grid(True, linestyle=":", alpha=0.5)
        ax_long.legend(fontsize=8, loc="best", ncol=2, framealpha=0.9)
        ax_short.set_xlabel("Time (ms)", fontsize=12)
        ax_short.grid(True, linestyle=":", alpha=0.5)
        ax_short.legend(fontsize=8, loc="best", ncol=2, framealpha=0.9)

        fig.tight_layout()
        fig.savefig(out_png, dpi=200)
        plt.close(fig)
        print(f"[OK] saved: {out_png}")
        return out_png
    else:
        ax1.set_ylabel("Ingress Queue (KB)", fontsize=12)
        ax1.set_title(f"Queue Length over Time - {qlen_file.stem}", fontsize=14)
        ax2.set_ylabel("Egress Queue (KB)", fontsize=12)

        ax1.grid(True, linestyle=":", alpha=0.5)
        ax1.legend(fontsize=8, loc="best", ncol=2, framealpha=0.9)

        ax2.set_xlabel("Time (ms)", fontsize=12)
        ax2.grid(True, linestyle=":", alpha=0.5)
        ax2.legend(fontsize=8, loc="best", ncol=2, framealpha=0.9)

        plt.tight_layout()
        plt.savefig(out_png, dpi=200)
        plt.close(fig)
        print(f"[OK] saved: {out_png}")
        return out_png

def main():
    parser = argparse.ArgumentParser(description="Plot switch port queue length over time from qlen.txt files.")
    parser.add_argument(
        "-i", "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Input file or directory. Directory mode scans qlen files recursively.",
    )
    parser.add_argument(
        "-o", "--output-root",
        type=Path,
        default=DEFAULT_OUT_ROOT,
        help="Root directory for generated figures.",
    )
    parser.add_argument(
        "--include",
        nargs="*",
        help="Optional list of port labels to keep. e.g., SW2-P1 SW2-P2",
    )
    parser.add_argument(
        "--time",
        nargs=2,
        type=float,
        metavar=('START', 'END'),
        help="Time range to plot in seconds (e.g., --time 2.0 2.02)",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*qlen.txt",
        help="Glob pattern used when input is a directory (default: *qlen.txt).",
    )
    parser.add_argument(
        "--max-ports",
        type=int,
        default=12,
        help="Maximum number of switch ports to plot for each file (default: 12).",
    )
    parser.add_argument(
        "--paper",
        action="store_true",
        help="Use paper-style plotting defaults: line plot, 0.5ms bins, max-per-bin, smooth-window 3, thicker lines.",
    )
    parser.add_argument(
        "--plot-style",
        choices=["line", "step"],
        help="Render as a normal line or a step plot.",
    )
    parser.add_argument(
        "--bin-ms",
        type=float,
        help="Aggregate samples into time bins of this size in milliseconds before plotting.",
    )
    parser.add_argument(
        "--bin-stat",
        choices=["mean", "max", "p95"],
        help="Statistic to keep for each time bin.",
    )
    parser.add_argument(
        "--smooth-window",
        type=int,
        help="Centered moving-average window in points after binning.",
    )
    parser.add_argument(
        "--line-width-scale",
        type=float,
        help="Multiply all series line widths by this factor.",
    )
    args = parser.parse_args()

    plot_style, bin_ms, bin_stat, smooth_window, line_width_scale = resolve_plot_options(args)

    include_pairs = None
    if args.include:
        include_pairs = set()
        for lbl in args.include:
            pair = parse_include_label(lbl)
            if pair:
                include_pairs.add(pair)

    qlen_files = collect_qlen_files(args.input, args.pattern)
    if not qlen_files:
        raise SystemExit(f"No qlen file found from input: {args.input}")

    ok_count = 0
    for qlen_file in qlen_files:
        out_dir = resolve_output_dir(qlen_file, args.output_root, DEFAULT_INPUT_PATH)
        out_path = plot_one_file(
            qlen_file=qlen_file,
            output_dir=out_dir,
            include_pairs=include_pairs,
            time_range=args.time,
            max_ports=args.max_ports,
            plot_style=plot_style,
            bin_ms=bin_ms,
            bin_stat=bin_stat,
            smooth_window=smooth_window,
            line_width_scale=line_width_scale,
        )
        if out_path is not None:
            ok_count += 1

    print(f"Done. generated {ok_count}/{len(qlen_files)} figures under {args.output_root}")

if __name__ == "__main__":
    main()
