import os
import re
import sys
from datetime import datetime

# Mappings from run.py
cc_modes_inv = {
    "1": "dcqcn",
    "3": "hpcc",
    "7": "timely",
    "8": "dctcp",
}

lb_modes_inv = {
    "0": "fecmp",
    "2": "drill",
    "3": "conga",
    "6": "letflow",
    "9": "conweave",
}

def parse_config(config_path):
    config = {}
    try:
        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split()
                if len(parts) >= 2:
                    config[parts[0]] = parts[1]
    except Exception as e:
        return None
    return config

def main():
    output_dir = "output"
    if not os.path.exists(output_dir):
        print(f"Error: {output_dir} not found.")
        return

    search_query = sys.argv[1].lower() if len(sys.argv) > 1 else None

    results = []
    for d in os.listdir(output_dir):
        dir_path = os.path.join(output_dir, d)
        if not os.path.isdir(dir_path):
            continue
        
        config_file = os.path.join(dir_path, "config.txt")
        if os.path.exists(config_file):
            config = parse_config(config_file)
            if config:
                # Extract load from FLOW_FILE (e.g., config/L_25.00_CDF_...)
                flow_file = config.get("FLOW_FILE", "")
                load_match = re.search(r'L_([\d\.]+)', flow_file)
                load = load_match.group(1) if load_match else "N/A"
                
                cc = cc_modes_inv.get(config.get("CC_MODE", ""), "unknown")
                lb = lb_modes_inv.get(config.get("LB_MODE", ""), "unknown")
                irn = "IRN" if config.get("ENABLE_IRN") == "1" else "PFC"
                cpem = "CPEM-ON" if config.get("CPEM_ENABLED") == "1" else "CPEM-OFF"
                
                # Get directory modification time
                mtime = os.path.getmtime(dir_path)
                time_str = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')

                row = {
                    "id": d,
                    "load": load,
                    "cc": cc,
                    "lb": lb,
                    "mode": irn,
                    "cpem": cpem,
                    "time": time_str,
                    "mtime": mtime
                }

                if search_query:
                    if search_query in d.lower() or \
                       search_query in load.lower() or \
                       search_query in lb.lower() or \
                       search_query in cc.lower() or \
                       search_query in irn.lower() or \
                       search_query in cpem.lower():
                        results.append(row)
                else:
                    results.append(row)

    # Sort by modification time (newest first)
    results.sort(key=lambda x: x['mtime'], reverse=True)

    print(f"{'ID':<12} | {'Load':<6} | {'LB':<10} | {'CC':<8} | {'Mode':<5} | {'CPEM':<10} | {'Time'}")
    print("-" * 85)
    for r in results:
        print(f"{r['id']:<12} | {r['load']:<6} | {r['lb']:<10} | {r['cc']:<8} | {r['mode']:<5} | {r['cpem']:<10} | {r['time']}")

if __name__ == "__main__":
    main()
