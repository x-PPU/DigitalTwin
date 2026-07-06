#!/usr/bin/env python3
import csv
import os
import glob

script_dir = os.path.dirname(os.path.abspath(__file__))
plc_dir = os.path.join(script_dir, "plc_2_csv")
aas_dir = os.path.join(script_dir, "csv_2_aas")
behavior_file = os.path.join(aas_dir, "skill_plc_process_times.csv")

plc_total = 0.0
for f in glob.glob(os.path.join(plc_dir, "*.csv")):
    with open(f, encoding='utf-8') as fp:
        reader = csv.reader(fp)
        next(reader)  
        for name, t in reader:
            if name.strip() == "Total":
                plc_total += float(t)
                break  
plc_time = 0.0
with open(behavior_file, encoding='utf-8') as fp:
    reader = csv.reader(fp)
    next(reader)
    for name, t in reader:
        if name.strip() == "PLC":
            plc_time = float(t)
            break

final = plc_total + plc_time


out_dir = os.path.join(script_dir, "output")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "plc_2_aas.csv")
with open(out_path, "w", newline='', encoding='utf-8') as fp:
    writer = csv.writer(fp)
    writer.writerow(["name", "time"])
    writer.writerow(["PLC_Total", f"{final:.3f}"])
    writer.writerow(["Average", f"{final:.3f}"])
