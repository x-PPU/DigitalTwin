#!/usr/bin/env python3
import csv
import os
import glob

script_dir = os.path.dirname(os.path.abspath(__file__))
uml_dir = os.path.join(script_dir, "uml_2_csv")
aas_dir = os.path.join(script_dir, "csv_2_aas")
behavior_file = os.path.join(aas_dir, "behavior_processing_times.csv")

#sum up the times from UML CSV files
uml_total = {"Sc13": 0.0, "Sc14": 0.0, "Sc15": 0.0}
for f in glob.glob(os.path.join(uml_dir, "*.csv")):
    with open(f, encoding='utf-8') as fp:
        reader = csv.reader(fp)
        next(reader)  
        for name, t in reader:
            name = name.strip()
            if name in uml_total:
                uml_total[name] += float(t)

# read value of behavior_processing_times.csv
behavior = {}
with open(behavior_file, encoding='utf-8') as fp:
    reader = csv.reader(fp)
    next(reader)
    for name, t in reader:
        if name.startswith("Scenario_"):
            sc = name.replace("Scenario_", "Sc")
            behavior[sc] = float(t)


final = {}
for sc in ["Sc13", "Sc14", "Sc15"]:
    final[sc] = uml_total[sc] + behavior.get(sc, 0.0)

avg = sum(final.values()) / 3.0

out_dir = os.path.join(script_dir, "output")
os.makedirs(out_dir, exist_ok=True)
out_path = os.path.join(out_dir, "uml_2_aas.csv")
with open(out_path, "w", newline='', encoding='utf-8') as fp:
    writer = csv.writer(fp)
    writer.writerow(["name", "time"])
    for sc in ["Sc13", "Sc14", "Sc15"]:
        writer.writerow([sc, f"{final[sc]:.3f}"])
    writer.writerow(["Average", f"{avg:.3f}"])
