#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FCT (Flow Completion Time) Analysis Script
Analyze and visualize flow completion time from ns-3 simulation
"""

import os
import sys
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

# Default paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FCT_FILE = os.path.join(BASE_DIR, "..", "..", "output", "out_fct.txt")
DEFAULT_OUT_DIR = os.path.join(BASE_DIR, "..", "figures")

# Flow size thresholds (in bytes)
SMALL_FLOW_THRESHOLD = 100000  # 100 KB
LARGE_FLOW_THRESHOLD = 1000000  # 1 MB

# Plot styling
plt.rcParams['font.size'] = 12
plt.rcParams['font.family'] = 'serif'
plt.rcParams['axes.labelsize'] = 14
plt.rcParams['axes.titlesize'] = 16
plt.rcParams['xtick.labelsize'] = 11
plt.rcParams['ytick.labelsize'] = 11
plt.rcParams['legend.fontsize'] = 11
plt.rcParams['figure.titlesize'] = 18


def parse_fct_file(file_path):
    """
    Parse FCT data file.
    Expected format: flowId src dst srcPort dstPort startTime fct baseRTT
    
    Returns:
        list of dict with keys: 
            - flow_id, src, dst, src_port, dst_port
            - start_time (ns), fct (ns), base_rtt (ns)
            - flow_size (bytes), slowdown
    """
    flows = []
    
    if not os.path.exists(file_path):
        print(f"Error: FCT file not found: {file_path}")
        return flows
    
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if len(parts) < 8:
                print(f"Warning: Skipping malformed line {line_num}: {line}")
                continue
            
            try:
                flow_id = int(parts[0])
                src = int(parts[1])
                dst = int(parts[2])
                src_port = int(parts[3])
                dst_port = int(parts[4])
                start_time = int(parts[5])  # ns
                fct = int(parts[6])  # ns
                base_rtt = int(parts[7])  # ns
                
                # Calculate flow size from FCT and base RTT
                # This is an approximation; adjust if actual size is available
                flow_size = dst_port  # In the data format, sometimes size is encoded in port
                
                # Calculate slowdown (normalized delay)
                slowdown = max(1.0, fct / base_rtt if base_rtt > 0 else 1.0)
                
                flows.append({
                    'flow_id': flow_id,
                    'src': src,
                    'dst': dst,
                    'src_port': src_port,
                    'dst_port': dst_port,
                    'start_time': start_time,
                    'fct': fct,
                    'fct_us': fct / 1000.0,  # Convert to microseconds
                    'fct_ms': fct / 1e6,  # Convert to milliseconds
                    'base_rtt': base_rtt,
                    'flow_size': flow_size,
                    'slowdown': slowdown
                })
            except (ValueError, IndexError) as e:
                print(f"Warning: Error parsing line {line_num}: {e}")
                continue
    
    print(f"Loaded {len(flows)} flows from {file_path}")
    return flows


def filter_flows_by_time(flows, start_time=None, end_time=None):
    """Filter flows by start time range."""
    filtered = []
    for flow in flows:
        if start_time and flow['start_time'] < start_time:
            continue
        if end_time and flow['start_time'] > end_time:
            continue
        filtered.append(flow)
    return filtered


def categorize_flows(flows, small_threshold=None, large_threshold=None):
    """Categorize flows by size."""
    if small_threshold is None:
        small_threshold = SMALL_FLOW_THRESHOLD
    if large_threshold is None:
        large_threshold = LARGE_FLOW_THRESHOLD
    
    small_flows = [f for f in flows if f['flow_size'] < small_threshold]
    medium_flows = [f for f in flows if small_threshold <= f['flow_size'] < large_threshold]
    large_flows = [f for f in flows if f['flow_size'] >= large_threshold]
    
    return {
        'all': flows,
        'small': small_flows,
        'medium': medium_flows,
        'large': large_flows
    }


def compute_statistics(flows, metric='fct_us'):
    """Compute statistics for a list of flows."""
    if not flows:
        return None
    
    values = [f[metric] for f in flows]
    values = np.array(values)
    
    return {
        'count': len(values),
        'mean': np.mean(values),
        'median': np.median(values),
        'std': np.std(values),
        'min': np.min(values),
        'max': np.max(values),
        'p50': np.percentile(values, 50),
        'p95': np.percentile(values, 95),
        'p99': np.percentile(values, 99),
        'p999': np.percentile(values, 99.9)
    }


def plot_slowdown_bar_comparison(flows_dict, output_dir, title_suffix=''):
    """Plot bar chart comparing average and 99.9th percentile slowdown across flow categories."""
    categories = ['small', 'medium', 'large', 'all']
    labels = ['Small\n(<100KB)', 'Medium\n(100KB-1MB)', 'Large\n(>1MB)', 'All\nFlows']
    
    avg_slowdowns = []
    p999_slowdowns = []
    counts = []
    valid_labels = []
    
    for cat, label in zip(categories, labels):
        if cat in flows_dict and flows_dict[cat]:
            flows = flows_dict[cat]
            slowdown_values = [f['slowdown'] for f in flows]
            avg_slowdowns.append(np.mean(slowdown_values))
            p999_slowdowns.append(np.percentile(slowdown_values, 99.9))
            counts.append(len(flows))
            valid_labels.append(label)
    
    if not avg_slowdowns:
        print("Warning: No data to plot slowdown comparison")
        return
    
    x = np.arange(len(valid_labels))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    bars1 = ax.bar(x - width/2, avg_slowdowns, width, label='Average Slowdown',
                   color='#2ca02c', alpha=0.8, edgecolor='black', linewidth=1.2)
    bars2 = ax.bar(x + width/2, p999_slowdowns, width, label='99.9th Percentile Slowdown',
                   color='#d62728', alpha=0.8, edgecolor='black', linewidth=1.2)
    
    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.2f}x',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # Add flow counts below x-axis labels
    for i, (label, count) in enumerate(zip(valid_labels, counts)):
        ax.text(i, -0.15 * max(max(avg_slowdowns), max(p999_slowdowns)),
               f'n={count}',
               ha='center', va='top', fontsize=9, style='italic', color='gray')
    
    ax.set_xlabel('Flow Category', fontsize=12, fontweight='bold')
    ax.set_ylabel('Slowdown (FCT / Base RTT)', fontsize=12, fontweight='bold')
    ax.set_title(f'Slowdown Comparison by Flow Size{title_suffix}', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(valid_labels)
    ax.legend(loc='upper right', fontsize=11)
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax.set_ylim(bottom=0)
    
    plt.tight_layout()
    output_file = os.path.join(output_dir, 'slowdown_comparison.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_file}")


def plot_slowdown_detailed_metrics(flows_dict, output_dir, title_suffix=''):
    """Plot detailed slowdown metrics (min, avg, p50, p95, p99, p99.9, max) for each category."""
    categories = ['small', 'medium', 'large', 'all']
    labels = ['Small (<100KB)', 'Medium (100KB-1MB)', 'Large (>1MB)', 'All Flows']
    
    metrics_data = []
    valid_labels = []
    
    for cat, label in zip(categories, labels):
        if cat in flows_dict and flows_dict[cat]:
            flows = flows_dict[cat]
            slowdown_values = np.array([f['slowdown'] for f in flows])
            metrics = {
                'Min': np.min(slowdown_values),
                'Avg': np.mean(slowdown_values),
                'Median': np.median(slowdown_values),
                'P95': np.percentile(slowdown_values, 95),
                'P99': np.percentile(slowdown_values, 99),
                'P99.9': np.percentile(slowdown_values, 99.9),
                'Max': np.max(slowdown_values)
            }
            metrics_data.append(metrics)
            valid_labels.append(f"{label}\n(n={len(flows)})")
    
    if not metrics_data:
        print("Warning: No data to plot detailed slowdown metrics")
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    x = np.arange(len(valid_labels))
    metric_names = ['Min', 'Avg', 'Median', 'P95', 'P99', 'P99.9', 'Max']
    colors = ['#8dd3c7', '#ffffb3', '#bebada', '#fb8072', '#80b1d3', '#fdb462', '#b3de69']
    width = 0.12
    
    for i, (metric_name, color) in enumerate(zip(metric_names, colors)):
        values = [m[metric_name] for m in metrics_data]
        offset = (i - len(metric_names)/2 + 0.5) * width
        ax.bar(x + offset, values, width, label=metric_name, 
               color=color, alpha=0.85, edgecolor='black', linewidth=0.8)
    
    ax.set_xlabel('Flow Category', fontsize=12, fontweight='bold')
    ax.set_ylabel('Slowdown (FCT / Base RTT)', fontsize=12, fontweight='bold')
    ax.set_title(f'Detailed Slowdown Metrics by Flow Size{title_suffix}', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(valid_labels)
    ax.legend(loc='upper right', fontsize=9, ncol=2)
    ax.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax.set_ylim(bottom=0)
    
    plt.tight_layout()
    output_file = os.path.join(output_dir, 'slowdown_detailed_metrics.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_file}")


def plot_fct_vs_size(flows, output_dir, title_suffix=''):
    """Plot FCT vs flow size scatter plot."""
    if not flows:
        return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    sizes = [f['flow_size'] for f in flows]
    fcts = [f['fct_us'] for f in flows]
    
    ax.scatter(sizes, fcts, alpha=0.5, s=20, c='#1f77b4')
    
    ax.set_xlabel('Flow Size (Bytes)')
    ax.set_ylabel('FCT (μs)')
    ax.set_title(f'Flow Completion Time vs Flow Size{title_suffix}')
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Use log scale for better visualization
    ax.set_xscale('log')
    ax.set_yscale('log')
    
    plt.tight_layout()
    output_file = os.path.join(output_dir, 'fct_vs_size.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_file}")


def plot_fct_timeline(flows, output_dir, title_suffix=''):
    """Plot FCT over time."""
    if not flows:
        return
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Sort by start time
    sorted_flows = sorted(flows, key=lambda x: x['start_time'])
    
    times = [f['start_time'] / 1e9 for f in sorted_flows]  # Convert to seconds
    fcts = [f['fct_us'] for f in sorted_flows]
    
    ax.scatter(times, fcts, alpha=0.5, s=10, c='#1f77b4')
    
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('FCT (μs)')
    ax.set_title(f'Flow Completion Time Over Time{title_suffix}')
    ax.grid(True, alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    output_file = os.path.join(output_dir, 'fct_timeline.png')
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {output_file}")


def generate_statistics_report(flows_dict, output_dir):
    """Generate a text report with FCT statistics."""
    report_file = os.path.join(output_dir, 'fct_statistics.txt')
    
    with open(report_file, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("Flow Completion Time (FCT) Analysis Report\n")
        f.write("=" * 80 + "\n\n")
        
        for category in ['all', 'small', 'medium', 'large']:
            if category not in flows_dict or not flows_dict[category]:
                continue
            
            flows = flows_dict[category]
            f.write(f"\n{'=' * 80}\n")
            f.write(f"{category.upper()} FLOWS (n={len(flows)})\n")
            f.write(f"{'=' * 80}\n\n")
            
            # FCT statistics (microseconds)
            fct_stats = compute_statistics(flows, 'fct_us')
            if fct_stats:
                f.write("FCT Statistics (microseconds):\n")
                f.write(f"  Count:      {fct_stats['count']:,}\n")
                f.write(f"  Mean:       {fct_stats['mean']:,.2f} μs\n")
                f.write(f"  Median:     {fct_stats['median']:,.2f} μs\n")
                f.write(f"  Std Dev:    {fct_stats['std']:,.2f} μs\n")
                f.write(f"  Min:        {fct_stats['min']:,.2f} μs\n")
                f.write(f"  Max:        {fct_stats['max']:,.2f} μs\n")
                f.write(f"  50th %ile:  {fct_stats['p50']:,.2f} μs\n")
                f.write(f"  95th %ile:  {fct_stats['p95']:,.2f} μs\n")
                f.write(f"  99th %ile:  {fct_stats['p99']:,.2f} μs\n")
                f.write(f"  99.9th %ile:{fct_stats['p999']:,.2f} μs\n")
            
            # Slowdown statistics
            slowdown_stats = compute_statistics(flows, 'slowdown')
            if slowdown_stats:
                f.write("\nSlowdown Statistics (FCT / Base RTT):\n")
                f.write(f"  Mean:       {slowdown_stats['mean']:.3f}x\n")
                f.write(f"  Median:     {slowdown_stats['median']:.3f}x\n")
                f.write(f"  Std Dev:    {slowdown_stats['std']:.3f}x\n")
                f.write(f"  Min:        {slowdown_stats['min']:.3f}x\n")
                f.write(f"  Max:        {slowdown_stats['max']:.3f}x\n")
                f.write(f"  50th %ile:  {slowdown_stats['p50']:.3f}x\n")
                f.write(f"  95th %ile:  {slowdown_stats['p95']:.3f}x\n")
                f.write(f"  99th %ile:  {slowdown_stats['p99']:.3f}x\n")
                f.write(f"  99.9th %ile:{slowdown_stats['p999']:.3f}x\n")
            
            f.write("\n")
        
        f.write("=" * 80 + "\n")
        f.write("End of Report\n")
        f.write("=" * 80 + "\n")
    
    print(f"Saved statistics report: {report_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze and visualize Flow Completion Time (FCT) from ns-3 simulation',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument('fct_file', nargs='?', default=DEFAULT_FCT_FILE,
                        help=f'Path to FCT data file (default: {DEFAULT_FCT_FILE})')
    parser.add_argument('-o', '--output-dir', default=DEFAULT_OUT_DIR,
                        help=f'Output directory for figures (default: {DEFAULT_OUT_DIR})')
    parser.add_argument('--start-time', type=float,
                        help='Filter flows starting after this time (ns)')
    parser.add_argument('--end-time', type=float,
                        help='Filter flows starting before this time (ns)')
    parser.add_argument('--small-threshold', type=int, default=SMALL_FLOW_THRESHOLD,
                        help=f'Small flow size threshold in bytes (default: {SMALL_FLOW_THRESHOLD})')
    parser.add_argument('--large-threshold', type=int, default=LARGE_FLOW_THRESHOLD,
                        help=f'Large flow size threshold in bytes (default: {LARGE_FLOW_THRESHOLD})')
    
    args = parser.parse_args()
    
    # Use thresholds from arguments
    small_threshold = args.small_threshold
    large_threshold = args.large_threshold
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Parse FCT data
    print(f"\nParsing FCT data from: {args.fct_file}")
    flows = parse_fct_file(args.fct_file)
    
    if not flows:
        print("Error: No flows found in FCT file")
        return 1
    
    # Filter by time if specified
    if args.start_time or args.end_time:
        print(f"Filtering flows by time range...")
        flows = filter_flows_by_time(flows, args.start_time, args.end_time)
        print(f"Flows after filtering: {len(flows)}")
    
    # Categorize flows
    flows_dict = categorize_flows(flows, small_threshold, large_threshold)
    
    print(f"\nFlow categories:")
    print(f"  Small flows (<{small_threshold:,} B):   {len(flows_dict['small']):,}")
    print(f"  Medium flows ({small_threshold:,}-{large_threshold:,} B): {len(flows_dict['medium']):,}")
    print(f"  Large flows (>{large_threshold:,} B):   {len(flows_dict['large']):,}")
    print(f"  Total flows:                {len(flows_dict['all']):,}")
    
    # Generate plots
    print(f"\nGenerating plots in: {args.output_dir}")
    
    # Slowdown analysis (主要关注)
    plot_slowdown_bar_comparison(flows_dict, args.output_dir)
    plot_slowdown_detailed_metrics(flows_dict, args.output_dir)
    
    # Additional plots
    plot_fct_vs_size(flows, args.output_dir)
    plot_fct_timeline(flows, args.output_dir)
    
    # Generate statistics report
    generate_statistics_report(flows_dict, args.output_dir)
    
    print("\n✓ FCT analysis completed successfully!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
