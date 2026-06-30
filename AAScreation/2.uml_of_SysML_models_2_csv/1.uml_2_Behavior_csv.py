#!/usr/bin/env python3
import os
import subprocess
import sys
import time
import csv

current_dir = os.path.dirname(os.path.abspath(__file__))

def run(cmd):
    print(">>", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    scenarios = {
        "Sc13": os.path.join(current_dir, "Papyrus - Scenario_13", "model_Sc13.uml"),
        "Sc14": os.path.join(current_dir, "Papyrus - Scenario_14", "model_Sc14.uml"),
        "Sc15": os.path.join(current_dir, "Papyrus - Scenario_15", "model_Sc15.uml"),
    }

    out_dir = os.path.join(current_dir, "output")
    os.makedirs(out_dir, exist_ok=True)

    timing_csv = os.path.join(out_dir, "scenario_info_timing.csv")
    timing_results = []  

    # after a single scenario is processed using step_1.0.py to step_2.6.py, then the next scenario is processed, and so on. The timing for each scenario is recorded.
    for sc, uml_path in scenarios.items():
        start_time = time.time()

        # 1) UML -> SCxx_UML_Structure.csv
        out_csv = os.path.join(out_dir, f"SC{sc[-2:]}_UML_Structure.csv")
        run([sys.executable, os.path.join(current_dir, "extract_uml_info_2_csv.py"), uml_path, out_csv])

        # 2) csv_2_process.py -> Behavior1_ScXX.csv / Behavior2_ScXX.csv
        in_csv = os.path.join(out_dir, f"SC{sc[-2:]}_UML_Structure.csv")
        run([sys.executable, os.path.join(current_dir, "csv_2_process.py"), in_csv, sc])

        end_time = time.time()
        elapsed = end_time - start_time
        print(f"===v {sc}  time cost: {elapsed:.3f} s\n")

        
        timing_results.append([sc, f"{elapsed:.3f}"])


    with open(timing_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["name", "time"])
        writer.writerows(timing_results)

    print("All scenarios completed.")
    print(f"Timing results saved to: {timing_csv}")

if __name__ == "__main__":
    main()
