#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import time
import csv
from pathlib import Path

CURRENT_DIR = Path(__file__).parent

SCRIPTS = [
    "1.extract_template_aasx_info.py",
    "2.extract_model_metadata.py",
    "3.extract_stateflow_data.py",
    "4.extract_OPC_Item_IDs.py",
    "5.add_data_to_template.py",
    "6.merge_csv_to_simulation.py",
]

def main():
    timing_results = []
    overall_start = time.time()

    for script in SCRIPTS:
        script_path = CURRENT_DIR / script
        print(f">>> {script}")
        start = time.time()
        subprocess.run([sys.executable, str(script_path)], check=True)
        elapsed = time.time() - start
        print(f"<<< {elapsed:.3f}s")
        timing_results.append([script, f"{elapsed:.3f}"])

    total = time.time() - overall_start
    timing_results.append(["Total", f"{total:.3f}"])

    csv_path = CURRENT_DIR / "slx_2_csv_timing.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "time"])
        writer.writerows(timing_results)

    print(f"\nTiming saved to {csv_path}")

if __name__ == "__main__":
    main()