#!/usr/bin/env python3
import subprocess
import os
import sys
import re

current_dir = os.path.dirname(os.path.abspath(__file__))

def get_suffix_from_path(path: str) -> str:
    m = re.search(r"(Sc\d+)", path, re.IGNORECASE)
    return m.group(1) if m else "Sc14"

def run_step(step_file, input_args):
    step_path = os.path.join(current_dir, "base", step_file)
    subprocess.run([sys.executable, step_path] + input_args, check=True)
    print(f"{step_file} completed.")

def main(input_file, scenario_suffix: str | None = None):
    suffix = scenario_suffix or get_suffix_from_path(input_file)

    steps = [
        "step_1.0.py",
        "step_1.1.py",
        "step_1.2.py",
        "step_1.3.py",
        "step_1.4.py",
        "step_2.0.py",
        "step_2.1.py",
        "step_2.2.py",
        "step_2.3.py",
        "step_2.4.py",
        "step_2.5.py"
    ]

    out_dir = os.path.join(current_dir, 'output')
    os.makedirs(out_dir, exist_ok=True)

    temp_files = [
        os.path.join(out_dir, f"UML_Structure_1.0_{suffix}.csv"),
        os.path.join(out_dir, f"UML_Structure_1.1_{suffix}.csv"),
        os.path.join(out_dir, f"UML_Structure_1.2_{suffix}.csv"),
        os.path.join(out_dir, f"UML_Structure_1.3_{suffix}.csv"),
        os.path.join(out_dir, f"UML_Structure_1.4_{suffix}.csv"),
        os.path.join(out_dir, f"UML_Structure_2.0_{suffix}.csv"),
        os.path.join(out_dir, f"UML_Structure_2.1_{suffix}.csv"),
        os.path.join(out_dir, f"UML_Structure_2.2_{suffix}.csv"),
        os.path.join(out_dir, f"UML_Structure_2.3_{suffix}.csv"),
        os.path.join(out_dir, f"UML_Structure_2.4_{suffix}.csv"),
        os.path.join(out_dir, f"UML_Structure_2.5_{suffix}.csv"),
        os.path.join(out_dir, f"UML_Structure_2.6.1_{suffix}.csv"),
        os.path.join(out_dir, f"Behavior2_{suffix}.csv"),
    ]

    run_step(steps[0], [input_file, temp_files[0]])
    for i in range(1, len(steps)):
        run_step(steps[i], [temp_files[i - 1], temp_files[i]])

    # step_2.6.py:  2.5 → 2.6.1 for Behavior2
    run_step("step_2.6.py", [temp_files[-3], temp_files[-2], temp_files[-1]])

    # step_2.7.py: Behavior1
    final_part_1 = os.path.join(out_dir, f"Behavior1_{suffix}.csv")
    run_step("step_2.7.py", [temp_files[-2], final_part_1])

    print(f"Final outputs: {final_part_1}, {temp_files[-1]}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <input_csv_path> [scenario_suffix]")
        sys.exit(1)
    input_csv = sys.argv[1]
    scenario = sys.argv[2] if len(sys.argv) >= 3 else None
    main(input_csv, scenario)
