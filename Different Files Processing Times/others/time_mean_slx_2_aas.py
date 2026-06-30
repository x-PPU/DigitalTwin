#!/usr/bin/env python3
import csv
import os
import glob

script_dir = os.path.dirname(os.path.abspath(__file__))
slx_dir = os.path.join(script_dir, "slx_2_csv")
aas_dir = os.path.join(script_dir, "csv_2_aas")
sim_file = os.path.join(aas_dir, "otherSM_processing_times.csv")


slx_total = 0.0
for f in glob.glob(os.path.join(slx_dir, "*.csv")):
    with open(f, encoding='utf-8') as fp:
        reader = csv.reader(fp)
        next(reader)  # 跳过表头
        for name, t in reader:
            if name.strip() == "Total":
                slx_total += float(t)
                break  # only read the Total entry in each file

# read otherSM_processing_times.csv  simulation time
sim_time = 0.0
with open(sim_file, encoding='utf-8') as fp:
    reader = csv.reader(fp)
    next(reader)
    for name, t in reader:
        if name.strip() == "Simulation":
            sim_time = float(t)
            break

total = slx_total + sim_time
avg = total / 4.0  # 4 simulation models

out_dir = os.path.join(script_dir, "output")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "slx_2_aas.csv")
with open(out_path, "w", newline='', encoding='utf-8') as fp:
    writer = csv.writer(fp)
    writer.writerow(["name", "time"])
    writer.writerow(["Simulation_Total", f"{total:.3f}"])
    writer.writerow(["Average", f"{avg:.3f}"])

print(f"Done, output: {out_path}")