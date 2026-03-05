import os
import matplotlib.pyplot as plt
import argparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PAPER_PLOT_STYLE = "line"
PAPER_BIN_MS = 0.5
PAPER_BIN_STAT = "max"
PAPER_SMOOTH_WINDOW = 3
PAPER_LINE_WIDTH_SCALE = 1.8
DEFAULT_PLOT_STYLE = "line"
DEFAULT_BIN_STAT = "mean"
DEFAULT_SMOOTH_WINDOW = 1
DEFAULT_LINE_WIDTH_SCALE = 1.0

# Default paths (can be overridden by command line arguments)
DEFAULT_QLEN_FILE = os.path.join(BASE_DIR, "..", "..", "output", "out_qlen.txt")
DEFAULT_OUT_DIR = os.path.join(BASE_DIR, "..", "figures")

def compute_stat(values, stat):
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
    raise ValueError("Unsupported stat: {}".format(stat))


def aggregate_series(times, values, bin_ms, stat):
    if not times or not values or bin_ms is None or bin_ms <= 0:
        return times, values

    grouped_times = []
    grouped_values = []
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


def smooth_values(values, window):
    if not values or window <= 1:
        return values

    half_window = window // 2
    prefix_sum = [0.0]
    for value in values:
        prefix_sum.append(prefix_sum[-1] + value)

    smoothed = []
    for idx in range(len(values)):
        left = max(0, idx - half_window)
        right = min(len(values), idx + half_window + 1)
        smoothed.append((prefix_sum[right] - prefix_sum[left]) / (right - left))

    return smoothed


def smooth_series(times, values, window):
    if not times or not values:
        return times, values
    return times, smooth_values(values, window)


def transform_series(times, values, bin_ms, bin_stat, smooth_window):
    out_times, out_values = aggregate_series(times, values, bin_ms, bin_stat)
    return smooth_series(out_times, out_values, smooth_window)


def transform_flow_split_series(times, ingress, short_values, long_values, bin_ms, bin_stat, smooth_window):
    if not times:
        return times, ingress, short_values, long_values

    agg_times = list(times)
    agg_ingress = list(ingress)
    agg_short = list(short_values)
    agg_long = list(long_values)

    if bin_ms is not None and bin_ms > 0:
        grouped_times = []
        grouped_ingress = []
        grouped_short = []
        grouped_long = []
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


def draw_series(ax, times, values, plot_style, **kwargs):
    if plot_style == "step":
        ax.step(times, values, where="post", **kwargs)
    else:
        ax.plot(times, values, **kwargs)


def resolve_plot_options(args):
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


def resolve_input_file(file_path):
    if file_path.endswith("out_qlen.txt"):
        flow_candidate = file_path[:-len("out_qlen.txt")] + "out_flow_qlen.txt"
        if os.path.exists(flow_candidate):
            print("[INFO] Found flow-split queue file, using {}".format(flow_candidate))
            return flow_candidate
    return file_path


def parse_qlen(file_path):
    """
    Parse queue length data from CSV-like file.
    Legacy format: timestamp(ns), switchId, portId, ingressBytes, egressBytes
    Flow-split format: timestamp(ns), switchId, portId, ingressBytes, egressBytes,
                       shortFlowPg, shortFlowEgressBytes, longFlowPg, longFlowEgressBytes
    """
    data = {} # (sw, port) -> dict of series
    fmt = None
    if not os.path.exists(file_path):
        return fmt, data

    with open(file_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.strip().split(",")
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

                key = (sw, port)
                if key not in data:
                    data[key] = {'times': [], 'ingress': [], 'egress': []}
                    if fmt == "flow-split":
                        data[key]['short'] = []
                        data[key]['long'] = []
                        data[key]['short_pg'] = short_pg
                        data[key]['long_pg'] = long_pg

                data[key]['times'].append(t_ns / 1e6) # Convert to ms
                data[key]['ingress'].append(ing / 1000.0) # Convert to KB
                data[key]['egress'].append(eg / 1000.0) # Convert to KB
                if fmt == "flow-split":
                    data[key]['short'].append(short_eg / 1000.0)
                    data[key]['long'].append(long_eg / 1000.0)
            except ValueError:
                continue
    return fmt, data

def parse_include_label(lbl: str):
    """Accept SW{node}-P{port}, S{node}-{port}, or SW{node}-{port} -> return (node, port)."""
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

def main():
    parser = argparse.ArgumentParser(description="Plot Ingress and Egress queue length over time.")
    parser.add_argument(
        "-i", "--input",
        default=DEFAULT_QLEN_FILE,
        help="Input qlen file path (default: {})".format(DEFAULT_QLEN_FILE),
    )
    parser.add_argument(
        "-o", "--output",
        default=DEFAULT_OUT_DIR,
        help="Output directory for figures (default: {})".format(DEFAULT_OUT_DIR),
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

    # Setup paths from arguments
    qlen_file = resolve_input_file(args.input)
    out_dir = args.output
    out_png = os.path.join(out_dir, os.path.splitext(os.path.basename(qlen_file))[0] + ".png")

    # Ensure output directory exists
    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    fmt, data = parse_qlen(qlen_file)
    if not data:
        print("No data found in {}".format(qlen_file))
        return

    # Filter ports
    include_pairs = None
    if args.include:
        include_pairs = set()
        for lbl in args.include:
            pair = parse_include_label(lbl)
            if pair:
                include_pairs.add(pair)

    plot_keys = sorted(data.keys())
    if include_pairs:
        plot_keys = [k for k in plot_keys if k in include_pairs]

    if not plot_keys:
        print("No matching ports found to plot.")
        return

    # Time range filtering (convert seconds to ms)
    t_start_ms = args.time[0] * 1000.0 if args.time else None
    t_end_ms = args.time[1] * 1000.0 if args.time else None

    # Limit number of ports if too many
    if not include_pairs and len(plot_keys) > 8:
        print("Too many ports ({}), only plotting first 8. Use --include to specify.".format(len(plot_keys)))
        plot_keys = plot_keys[:8]

    # Define different line styles and markers for better distinction
    line_styles = ['-', '--', '-.', ':']
    markers = ['o', 's', '^', 'v', 'D', 'p', '*', 'h']

    if fmt == "flow-split":
        fig, (ax_port, ax_long, ax_short) = plt.subplots(3, 1, figsize=(12, 13), sharex=True)
    else:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    has_data_to_plot = False
    for idx, key in enumerate(plot_keys):
        d = data[key]

        # Filter by time
        times = d['times']
        ingress = d['ingress']
        egress = d['egress']
        short_q = list(d.get('short', []))
        long_q = list(d.get('long', []))

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

        has_data_to_plot = True
        label = "SW{}-P{}".format(key[0], key[1])

        # Use different styles for each line
        linestyle = line_styles[idx % len(line_styles)]
        marker = markers[idx % len(markers)] if bin_ms is None and smooth_window <= 1 and plot_style == "line" else None
        linewidth = (1.5 + (idx % 3) * 0.3) * line_width_scale  # Vary linewidth slightly
        alpha = 0.85  # Add some transparency

        # Add markers every N points to distinguish lines
        markevery = max(1, len(times) // 20)  # Show about 20 markers per line

        if fmt == "flow-split":
            flow_times, ingress_vals, egress_vals, short_vals, long_vals = transform_flow_split_series(
                times, ingress, short_q, long_q, bin_ms, bin_stat, smooth_window
            )
            short_pg = d.get('short_pg')
            long_pg = d.get('long_pg')

            draw_series(ax_port, flow_times, egress_vals, plot_style,
                        label="{} total-egress".format(label), linewidth=linewidth,
                        linestyle=linestyle, marker=marker, markersize=4,
                        markevery=markevery, alpha=alpha)
            draw_series(ax_port, flow_times, ingress_vals, plot_style,
                        label="{} ingress".format(label), linewidth=max(1.0, linewidth - 0.2),
                        linestyle=":", marker=None, alpha=0.6)
            draw_series(ax_short, flow_times, short_vals, plot_style,
                        label="{} short(PG{})".format(label, short_pg), linewidth=linewidth,
                        linestyle='-', marker=marker, markersize=4,
                        markevery=markevery, alpha=0.9)
            draw_series(ax_long, flow_times, long_vals, plot_style,
                        label="{} long(PG{})".format(label, long_pg), linewidth=linewidth,
                        linestyle='--', marker=None, alpha=0.9)
        else:
            ingress_times, ingress_vals = transform_series(times, ingress, bin_ms, bin_stat, smooth_window)
            egress_times, egress_vals = transform_series(times, egress, bin_ms, bin_stat, smooth_window)

            draw_series(ax1, ingress_times, ingress_vals, plot_style,
                        label=label, linewidth=linewidth, linestyle=linestyle,
                        marker=marker, markersize=4, markevery=markevery, alpha=alpha)
            draw_series(ax2, egress_times, egress_vals, plot_style,
                        label=label, linewidth=linewidth, linestyle=linestyle,
                        marker=marker, markersize=4, markevery=markevery, alpha=alpha)

    if not has_data_to_plot:
        print("No data points found in the specified time range.")
        plt.close(fig)
        return

    if fmt == "flow-split":
        ax_port.set_ylabel("Port Queue (KB)", fontsize=12)
        ax_port.set_title("Queue Length over Time ({})".format(os.path.basename(qlen_file)), fontsize=14)
        ax_long.set_ylabel("Long Queue (KB)", fontsize=12)
        ax_short.set_ylabel("Short Queue (KB)", fontsize=12)

        ax_port.grid(True, linestyle=":", alpha=0.5)
        ax_port.legend(fontsize=8, loc='best', ncol=2, framealpha=0.9)
        ax_long.grid(True, linestyle=":", alpha=0.5)
        ax_long.legend(fontsize=8, loc='best', ncol=2, framealpha=0.9)
        ax_short.set_xlabel("Time (ms)", fontsize=12)
        ax_short.grid(True, linestyle=":", alpha=0.5)
        ax_short.legend(fontsize=8, loc='best', ncol=2, framealpha=0.9)
    else:
        ax1.set_ylabel("Ingress Queue (KB)", fontsize=12)
        ax1.set_title("Switch Port Queue Length over Time", fontsize=14)
        ax1.grid(True, linestyle=":", alpha=0.5)
        ax1.legend(fontsize=8, loc='best', ncol=2, framealpha=0.9)

        ax2.set_ylabel("Egress Queue (KB)", fontsize=12)
        ax2.set_xlabel("Time (ms)", fontsize=12)
        ax2.grid(True, linestyle=":", alpha=0.5)
        ax2.legend(fontsize=8, loc='best', ncol=2, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(out_png, dpi=200)
    print("Saved figure to {}".format(out_png))

if __name__ == "__main__":
    main()
