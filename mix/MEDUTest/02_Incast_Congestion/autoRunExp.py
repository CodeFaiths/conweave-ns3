#!/usr/bin/env python3
import os
import sys
import shutil
import argparse
import subprocess
from datetime import datetime

"""
NS-3 Experiment Manager (MEDU Test - Incast Congestion Edition)
- Tags experiments with labels and timestamps
- Snapshots configurations for reproducibility
- Automates simulation and analysis workflow
"""

def main():
    parser = argparse.ArgumentParser(description='Run and Archive NS-3 Experiment')
    parser.add_argument('tag', help='Experiment tag (label), e.g., "cpem_alpha_0.8"')
    parser.add_argument('--desc', default='', help='Brief description of the experiment')
    args = parser.parse_args()

    # Setup paths
    # Current script directory: ns-3.19/mix/CPEMTest/02_Incast_Congestion/
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    # NS-3 root directory
    NS3_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../.."))
    # Relative path from NS-3 root to this script directory
    REL_SCRIPT_DIR = os.path.relpath(SCRIPT_DIR, NS3_ROOT)

    EXP_BASE_DIR = os.path.join(SCRIPT_DIR, "experiments")
    TIMESTAMP = datetime.now().strftime('%Y%m%d_%H%M%S')
    TAG = f"{TIMESTAMP}_{args.tag}"
    EXP_DIR = os.path.join(EXP_BASE_DIR, TAG)

    print("="*60)
    print(f"🚀 Starting Experiment: {args.tag}")
    print(f"📁 Directory:  {EXP_DIR}")
    print("="*60)

    # 1. Create directory structure
    os.makedirs(os.path.join(EXP_DIR, "config"), exist_ok=True)
    os.makedirs(os.path.join(EXP_DIR, "output"), exist_ok=True)
    os.makedirs(os.path.join(EXP_DIR, "figures"), exist_ok=True)
    os.makedirs(os.path.join(EXP_DIR, "analyze_csv"), exist_ok=True)

    # 2. Snapshot configurations
    source_config_dir = os.path.join(SCRIPT_DIR, "config")
    target_config_dir = os.path.join(EXP_DIR, "config")

    print(f"\n[1/4] Snapshotting configuration from {os.path.basename(source_config_dir)}...")
    if os.path.exists(source_config_dir):
        for item in os.listdir(source_config_dir):
            s = os.path.join(source_config_dir, item)
            d = os.path.join(target_config_dir, item)
            if os.path.isfile(s):
                shutil.copy2(s, d)

    # 3. Update paths in config.txt to point to the experiment directory
    config_file = os.path.join(target_config_dir, "config.txt")
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            lines = f.readlines()

        with open(config_file, 'w') as f:
            for line in lines:
                new_line = line
                if not line.strip().startswith('#') and ('_FILE ' in line or '_DIR ' in line):
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0]
                        val = parts[1]
                        filename = os.path.basename(val)
                        # Identify if it was originally in output or config
                        if 'output/' in val:
                            new_val = os.path.join(REL_SCRIPT_DIR, "experiments", TAG, "output", filename)
                            new_line = f"{key} {new_val}\n"
                        elif 'config/' in val:
                            new_val = os.path.join(REL_SCRIPT_DIR, "experiments", TAG, "config", filename)
                            new_line = f"{key} {new_val}\n"
                f.write(new_line)

    # 4. Save metadata
    with open(os.path.join(EXP_DIR, "metadata.txt"), 'w') as f:
        f.write(f"Experiment Tag: {args.tag}\n")
        f.write(f"Timestamp:      {TIMESTAMP}\n")
        f.write(f"Description:    {args.desc}\n")
        f.write(f"Source Code:    {NS3_ROOT}\n")
        try:
            commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=NS3_ROOT, stderr=subprocess.DEVNULL).decode().strip()
            f.write(f"Git Commit:     {commit}\n")
        except:
            f.write("Git Commit:     Unknown (not a git repo?)\n")

    # 5. Run Simulation
    print(f"\n[2/4] Running ns-3 Simulation...")
    # Path to config must be relative to ns-3 root
    rel_config_path = os.path.join(REL_SCRIPT_DIR, "experiments", TAG, "config", "config.txt")
    run_cmd = f"python2.7 ./waf --run 'scratch/network-load-balance {rel_config_path}'"
    print(f"  $ {run_cmd}")

    # Redirect stdout/stderr to a log file in the experiment directory
    log_file = os.path.join(EXP_DIR, "simulation.log")
    with open(log_file, 'w') as log:
        process = subprocess.Popen(run_cmd, shell=True, cwd=NS3_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            sys.stdout.write(line)
            log.write(line)
        process.wait()

    if process.returncode != 0:
        print(f"\n❌ Simulation failed with exit code {process.returncode}")
        sys.exit(process.returncode)

    # 6. Run Analysis
    print(f"\n[3/4] Running Analysis Suite...")
    analysis_script = os.path.join(SCRIPT_DIR, "analyze/scripts/autoAnalyze.sh")
    output_dir = os.path.normpath(os.path.join(EXP_DIR, "output"))
    figures_dir = os.path.normpath(os.path.join(EXP_DIR, "figures"))

    if os.path.exists(analysis_script):
        analysis_cmd = f"bash {analysis_script} -o {output_dir} -f {figures_dir}"
        print(f"  $ {analysis_cmd}")
        subprocess.run(analysis_cmd, shell=True)
    else:
        print(f"  ⚠️  Analysis script not found: {analysis_script}")
        print(f"  Skipping analysis step...")

    # 7. Add to history
    history_file = os.path.join(EXP_BASE_DIR, "experiment_history.csv")
    is_new = not os.path.exists(history_file)
    with open(history_file, 'a') as f:
        if is_new:
            f.write("timestamp,tag,directory,description\n")
        f.write(f"{TIMESTAMP},{args.tag},{EXP_DIR},{args.desc}\n")

    # 8. Create summary.md template for user notes
    summary_file = os.path.join(EXP_DIR, "summary.md")
    with open(summary_file, 'w') as f:
        f.write(f"# Experiment Summary: {args.tag}\n\n")
        f.write(f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- **Tag**: {args.tag}\n")
        f.write(f"- **Description**: {args.desc if args.desc else 'No description provided'}\n\n")
        f.write("## 1. Parameters & Configuration\n")
        f.write("*(Describe key parameter changes here)*\n\n")
        f.write("### CPEM Parameters\n")
        f.write("- **CPEM_ENABLED**: \n")
        f.write("- **CPEM_FEEDBACK_INTERVAL**: \n")
        f.write("- **CPEM_CREDIT_DECAY_ALPHA**: \n")
        f.write("- **CPEM_INFLIGHT_DISCOUNT**: \n")
        f.write("- **CPEM_CREDIT_TO_RATE_GAIN**: \n")
        f.write("- **CPEM_MIN_RATE_RATIO**: \n\n")
        f.write("### Incast Scenario Parameters\n")
        f.write("- **Number of Senders**: \n")
        f.write("- **Flow Size**: \n")
        f.write("- **LOAD**: \n\n")
        f.write("## 2. Quantitative Results\n")
        f.write("- **Average FCT**: \n")
        f.write("- **PFC Frames**: \n")
        f.write("- **Queue Occupancy**: \n")
        f.write("- **Throughput**: \n\n")
        f.write("## 3. Key Observations & Thoughts\n")
        f.write("*(Input your observations from the generated plots and simulation logs here)*\n")
        f.write("- \n\n")
        f.write("## 4. Conclusions & Next Steps\n")
        f.write("- \n")

    print("\n" + "="*60)
    print(f"✅ Experiment Completed Successfully!")
    print(f"📍 Results: {EXP_DIR}")
    print("="*60)

if __name__ == "__main__":
    main()
