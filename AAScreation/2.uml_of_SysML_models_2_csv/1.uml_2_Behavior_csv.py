#!/usr/bin/env python3
import os
import subprocess
import sys

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

    # 1) UML -> SCxx_UML_Structure.csv
    for sc, uml_path in scenarios.items():
        out_csv = os.path.join(out_dir, f"SC{sc[-2:]}_UML_Structure.csv")
        run([sys.executable, os.path.join(current_dir, "extract_uml_info_2_csv.py"), uml_path, out_csv])

    # 2) csv_2_process.py create Behavior1_ScXX.csv / Behavior2_ScXX.csv
    for sc in scenarios.keys():
        in_csv = os.path.join(out_dir, f"SC{sc[-2:]}_UML_Structure.csv")
        run([sys.executable, os.path.join(current_dir, "csv_2_process.py"), in_csv, sc])

    print("All scenarios completed.")

if __name__ == "__main__":
    main()
