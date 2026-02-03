#!/usr/bin/env python3
"""
Throughput and Link Utilization Plotting Script
分析并绘制吞吐量和链路利用率数据

Usage:
    python plot_throughput.py [OPTIONS]
"""

import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys

def parse_throughput_file(filepath):
    """
    Parse throughput monitoring output file.
    Format: timestamp(ns),nodeType(0=host/1=switch),nodeId,portId,deltaTxBytes,deltaRxBytes,txThroughputMbps,rxThroughputMbps
    """
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found")
        return None
    
    # Skip header lines starting with #
    df = pd.read_csv(filepath, comment='#', header=None,
                     names=['timestamp_ns', 'node_type', 'node_id', 'port_id', 
                            'delta_tx_bytes', 'delta_rx_bytes', 'tx_mbps', 'rx_mbps'])
    
    # Convert timestamp to seconds
    df['timestamp_s'] = df['timestamp_ns'] / 1e9
    
    # Add node type label
    df['node_type_label'] = df['node_type'].map({0: 'Host', 1: 'Switch'})
    df['port_name'] = df.apply(lambda x: f"{x['node_type_label'][0]}{x['node_id']}-P{x['port_id']}", axis=1)
    
    return df

def parse_link_util_file(filepath):
    """
    Parse link utilization monitoring output file.
    Format: timestamp(ns),nodeType(0=host/1=switch),nodeId,portId,txUtilization%,rxUtilization%,linkBandwidthMbps
    """
    if not os.path.exists(filepath):
        print(f"Warning: {filepath} not found")
        return None
    
    # Skip header lines starting with #
    df = pd.read_csv(filepath, comment='#', header=None,
                     names=['timestamp_ns', 'node_type', 'node_id', 'port_id',
                            'tx_util_pct', 'rx_util_pct', 'link_bw_mbps'])
    
    # Convert timestamp to seconds
    df['timestamp_s'] = df['timestamp_ns'] / 1e9
    
    # Add node type label
    df['node_type_label'] = df['node_type'].map({0: 'Host', 1: 'Switch'})
    df['port_name'] = df.apply(lambda x: f"{x['node_type_label'][0]}{x['node_id']}-P{x['port_id']}", axis=1)
    
    return df

def plot_throughput_time_series(df, output_dir, include_ports=None):
    """Plot throughput over time for each port."""
    if df is None or df.empty:
        return
    
    # Filter ports if specified
    if include_ports:
        df = df[df['port_name'].isin(include_ports)]
    
    # Separate by node type
    for node_type, node_label in [(0, 'Host'), (1, 'Switch')]:
        type_df = df[df['node_type'] == node_type]
        if type_df.empty:
            continue
        
        # Plot TX throughput
        fig, ax = plt.subplots(figsize=(12, 6))
        for port_name in type_df['port_name'].unique():
            port_data = type_df[type_df['port_name'] == port_name]
            ax.plot(port_data['timestamp_s'], port_data['tx_mbps'], 
                   label=port_name, linewidth=1.5, alpha=0.7)
        
        ax.set_xlabel('Time (s)', fontsize=12)
        ax.set_ylabel('TX Throughput (Mbps)', fontsize=12)
        ax.set_title(f'{node_label} TX Throughput Over Time', fontsize=14, fontweight='bold')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        
        output_file = os.path.join(output_dir, f'{node_label.lower()}_tx_throughput_timeseries.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Saved: {output_file}")
        
        # Plot RX throughput
        fig, ax = plt.subplots(figsize=(12, 6))
        for port_name in type_df['port_name'].unique():
            port_data = type_df[type_df['port_name'] == port_name]
            ax.plot(port_data['timestamp_s'], port_data['rx_mbps'], 
                   label=port_name, linewidth=1.5, alpha=0.7)
        
        ax.set_xlabel('Time (s)', fontsize=12)
        ax.set_ylabel('RX Throughput (Mbps)', fontsize=12)
        ax.set_title(f'{node_label} RX Throughput Over Time', fontsize=14, fontweight='bold')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        plt.tight_layout()
        
        output_file = os.path.join(output_dir, f'{node_label.lower()}_rx_throughput_timeseries.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Saved: {output_file}")

def plot_utilization_time_series(df, output_dir, include_ports=None):
    """Plot link utilization over time for each port."""
    if df is None or df.empty:
        return
    
    # Filter ports if specified
    if include_ports:
        df = df[df['port_name'].isin(include_ports)]
    
    # Separate by node type
    for node_type, node_label in [(0, 'Host'), (1, 'Switch')]:
        type_df = df[df['node_type'] == node_type]
        if type_df.empty:
            continue
        
        # Plot TX utilization
        fig, ax = plt.subplots(figsize=(12, 6))
        for port_name in type_df['port_name'].unique():
            port_data = type_df[type_df['port_name'] == port_name]
            ax.plot(port_data['timestamp_s'], port_data['tx_util_pct'], 
                   label=port_name, linewidth=1.5, alpha=0.7)
        
        ax.axhline(y=80, color='r', linestyle='--', linewidth=1, alpha=0.5, label='80% threshold')
        ax.set_xlabel('Time (s)', fontsize=12)
        ax.set_ylabel('TX Utilization (%)', fontsize=12)
        ax.set_title(f'{node_label} TX Link Utilization Over Time', fontsize=14, fontweight='bold')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 105)
        plt.tight_layout()
        
        output_file = os.path.join(output_dir, f'{node_label.lower()}_tx_utilization_timeseries.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Saved: {output_file}")
        
        # Plot RX utilization
        fig, ax = plt.subplots(figsize=(12, 6))
        for port_name in type_df['port_name'].unique():
            port_data = type_df[type_df['port_name'] == port_name]
            ax.plot(port_data['timestamp_s'], port_data['rx_util_pct'], 
                   label=port_name, linewidth=1.5, alpha=0.7)
        
        ax.axhline(y=80, color='r', linestyle='--', linewidth=1, alpha=0.5, label='80% threshold')
        ax.set_xlabel('Time (s)', fontsize=12)
        ax.set_ylabel('RX Utilization (%)', fontsize=12)
        ax.set_title(f'{node_label} RX Link Utilization Over Time', fontsize=14, fontweight='bold')
        ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 105)
        plt.tight_layout()
        
        output_file = os.path.join(output_dir, f'{node_label.lower()}_rx_utilization_timeseries.png')
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"  ✓ Saved: {output_file}")

def analyze_throughput(df):
    """Generate throughput statistics."""
    if df is None or df.empty:
        return None
    
    stats = {}
    
    # Overall statistics
    stats['overall'] = {
        'avg_tx_mbps': df['tx_mbps'].mean(),
        'max_tx_mbps': df['tx_mbps'].max(),
        'avg_rx_mbps': df['rx_mbps'].mean(),
        'max_rx_mbps': df['rx_mbps'].max(),
        'total_tx_bytes': df['delta_tx_bytes'].sum(),
        'total_rx_bytes': df['delta_rx_bytes'].sum(),
    }
    
    # Per-node-type statistics
    for node_type in df['node_type'].unique():
        type_df = df[df['node_type'] == node_type]
        type_label = 'host' if node_type == 0 else 'switch'
        stats[type_label] = {
            'avg_tx_mbps': type_df['tx_mbps'].mean(),
            'max_tx_mbps': type_df['tx_mbps'].max(),
            'avg_rx_mbps': type_df['rx_mbps'].mean(),
            'max_rx_mbps': type_df['rx_mbps'].max(),
            'total_tx_bytes': type_df['delta_tx_bytes'].sum(),
            'total_rx_bytes': type_df['delta_rx_bytes'].sum(),
            'num_ports': type_df.groupby(['node_id', 'port_id']).ngroups,
        }
    
    return stats

def analyze_utilization(df):
    """Generate link utilization statistics."""
    if df is None or df.empty:
        return None
    
    stats = {}
    
    # Overall statistics
    stats['overall'] = {
        'avg_tx_util_pct': df['tx_util_pct'].mean(),
        'max_tx_util_pct': df['tx_util_pct'].max(),
        'avg_rx_util_pct': df['rx_util_pct'].mean(),
        'max_rx_util_pct': df['rx_util_pct'].max(),
    }
    
    # Per-node-type statistics
    for node_type in df['node_type'].unique():
        type_df = df[df['node_type'] == node_type]
        type_label = 'host' if node_type == 0 else 'switch'
        stats[type_label] = {
            'avg_tx_util_pct': type_df['tx_util_pct'].mean(),
            'max_tx_util_pct': type_df['tx_util_pct'].max(),
            'avg_rx_util_pct': type_df['rx_util_pct'].mean(),
            'max_rx_util_pct': type_df['rx_util_pct'].max(),
            'num_ports': type_df.groupby(['node_id', 'port_id']).ngroups,
        }
    
    # Find highly utilized links (>80%)
    high_util = df[(df['tx_util_pct'] > 80) | (df['rx_util_pct'] > 80)]
    stats['high_utilization_samples'] = len(high_util)
    stats['high_utilization_ratio'] = len(high_util) / len(df) if len(df) > 0 else 0
    
    return stats

def print_report(throughput_stats, util_stats):
    """Print analysis report."""
    print("\n" + "="*60)
    print("THROUGHPUT AND LINK UTILIZATION ANALYSIS REPORT")
    print("="*60)
    
    if throughput_stats:
        print("\n--- THROUGHPUT STATISTICS ---")
        print(f"\nOverall:")
        print(f"  Average TX Throughput: {throughput_stats['overall']['avg_tx_mbps']:.2f} Mbps")
        print(f"  Maximum TX Throughput: {throughput_stats['overall']['max_tx_mbps']:.2f} Mbps")
        print(f"  Average RX Throughput: {throughput_stats['overall']['avg_rx_mbps']:.2f} Mbps")
        print(f"  Maximum RX Throughput: {throughput_stats['overall']['max_rx_mbps']:.2f} Mbps")
        print(f"  Total TX Bytes: {throughput_stats['overall']['total_tx_bytes']:,}")
        print(f"  Total RX Bytes: {throughput_stats['overall']['total_rx_bytes']:,}")
        
        for node_type in ['host', 'switch']:
            if node_type in throughput_stats:
                print(f"\n{node_type.capitalize()}s:")
                print(f"  Number of ports: {throughput_stats[node_type]['num_ports']}")
                print(f"  Average TX: {throughput_stats[node_type]['avg_tx_mbps']:.2f} Mbps")
                print(f"  Maximum TX: {throughput_stats[node_type]['max_tx_mbps']:.2f} Mbps")
                print(f"  Average RX: {throughput_stats[node_type]['avg_rx_mbps']:.2f} Mbps")
                print(f"  Maximum RX: {throughput_stats[node_type]['max_rx_mbps']:.2f} Mbps")
    
    if util_stats:
        print("\n--- LINK UTILIZATION STATISTICS ---")
        print(f"\nOverall:")
        print(f"  Average TX Utilization: {util_stats['overall']['avg_tx_util_pct']:.2f}%")
        print(f"  Maximum TX Utilization: {util_stats['overall']['max_tx_util_pct']:.2f}%")
        print(f"  Average RX Utilization: {util_stats['overall']['avg_rx_util_pct']:.2f}%")
        print(f"  Maximum RX Utilization: {util_stats['overall']['max_rx_util_pct']:.2f}%")
        print(f"  High utilization samples (>80%): {util_stats['high_utilization_samples']}")
        print(f"  High utilization ratio: {util_stats['high_utilization_ratio']*100:.2f}%")
        
        for node_type in ['host', 'switch']:
            if node_type in util_stats:
                print(f"\n{node_type.capitalize()}s:")
                print(f"  Number of ports: {util_stats[node_type]['num_ports']}")
                print(f"  Average TX Util: {util_stats[node_type]['avg_tx_util_pct']:.2f}%")
                print(f"  Maximum TX Util: {util_stats[node_type]['max_tx_util_pct']:.2f}%")
                print(f"  Average RX Util: {util_stats[node_type]['avg_rx_util_pct']:.2f}%")
                print(f"  Maximum RX Util: {util_stats[node_type]['max_rx_util_pct']:.2f}%")
    
    print("\n" + "="*60)

def main():
    parser = argparse.ArgumentParser(description='Plot throughput and link utilization from ns-3 simulation')
    parser.add_argument('--throughput', type=str, 
                        help='Path to throughput monitoring output file')
    parser.add_argument('--util', type=str,
                        help='Path to link utilization monitoring output file')
    parser.add_argument('--output-dir', type=str, default='.',
                        help='Output directory for figures')
    parser.add_argument('--csv-dir', type=str, default='.',
                        help='Output directory for CSV files')
    parser.add_argument('--include', type=str, nargs='+',
                        help='Only include specified ports (e.g., H0-P1 S6-P1)')
    
    args = parser.parse_args()
    
    # Create output directories
    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.csv_dir, exist_ok=True)
    
    # Auto-detect files if not specified
    script_dir = os.path.dirname(os.path.abspath(__file__))
    experiment_dir = os.path.dirname(os.path.dirname(script_dir))
    output_dir = os.path.join(experiment_dir, 'output')
    
    if not args.throughput:
        args.throughput = os.path.join(output_dir, 'out_throughput.txt')
    if not args.util:
        args.util = os.path.join(output_dir, 'out_link_util.txt')
    
    print("\n=== Throughput and Link Utilization Analysis ===")
    print(f"Throughput file: {args.throughput}")
    print(f"Utilization file: {args.util}")
    print(f"Output directory: {args.output_dir}")
    
    # Parse files
    throughput_df = parse_throughput_file(args.throughput)
    util_df = parse_link_util_file(args.util)
    
    # Analyze
    throughput_stats = analyze_throughput(throughput_df)
    util_stats = analyze_utilization(util_df)
    
    # Print report
    print_report(throughput_stats, util_stats)
    
    # Plot time series
    if throughput_df is not None and not throughput_df.empty:
        print("\n--- Generating Throughput Plots ---")
        plot_throughput_time_series(throughput_df, args.output_dir, args.include)
        
        # Save time series summary
        time_series = throughput_df.groupby('timestamp_s').agg({
            'tx_mbps': ['mean', 'sum'],
            'rx_mbps': ['mean', 'sum']
        }).reset_index()
        time_series.columns = ['timestamp_s', 'avg_tx_mbps', 'total_tx_mbps', 'avg_rx_mbps', 'total_rx_mbps']
        time_series_path = os.path.join(args.csv_dir, 'throughput_time_series.csv')
        time_series.to_csv(time_series_path, index=False)
        print(f"  ✓ Time series CSV: {time_series_path}")
    
    if util_df is not None and not util_df.empty:
        print("\n--- Generating Utilization Plots ---")
        plot_utilization_time_series(util_df, args.output_dir, args.include)
        
        # Save utilization summary
        util_summary = util_df.groupby(['node_type_label', 'node_id', 'port_id', 'port_name']).agg({
            'tx_util_pct': ['mean', 'max'],
            'rx_util_pct': ['mean', 'max'],
            'link_bw_mbps': 'first'
        }).reset_index()
        util_summary.columns = ['node_type', 'node_id', 'port_id', 'port_name', 'avg_tx_util', 'max_tx_util', 
                               'avg_rx_util', 'max_rx_util', 'link_bw_mbps']
        util_summary_path = os.path.join(args.csv_dir, 'utilization_summary.csv')
        util_summary.to_csv(util_summary_path, index=False)
        print(f"  ✓ Utilization summary CSV: {util_summary_path}")
    
    print("\n✓ Analysis complete!")

if __name__ == '__main__':
    main()
