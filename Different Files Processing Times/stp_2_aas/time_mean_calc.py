#!/usr/bin/env python3
import pandas as pd
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(script_dir, "output"), exist_ok=True)

files = [
    "stp_processing_times.csv",
]

df_list = []
for fname in files:
    df = pd.read_csv(os.path.join(script_dir, fname))
    df_list.append(df)

combined = pd.concat(df_list, ignore_index=True)
avg_time = combined["time"].mean()
# 在add the mean row to the combined DataFrame
avg_row = pd.DataFrame([["Average", avg_time]], columns=combined.columns)
combined = pd.concat([combined, avg_row], ignore_index=True)

combined.to_csv(os.path.join(script_dir, "output", "stp_2_aas.csv"), index=False)
