#!/usr/bin/env python 3.10.15
"""
This script merges multiple CSV files by cleaning and standardizing the 'idShort' column and saving the combined data to a new output file.

- Reads CSV files from the '5.1manually modify' directory.
- Cleans the 'idShort' column by removing periods, spaces, and ensuring it starts with a letter.
- Combines all CSV files into a single DataFrame.
- Saves the merged data to '6.output/Simulation.csv'.
"""

import pandas as pd
import os
import re

script_dir = os.path.dirname(os.path.abspath(__file__))
base_path = os.path.join(script_dir, "5.1manually modify")
output_file = os.path.join(script_dir, "6.output", "Simulation.csv")

csv_files = [
    os.path.join(base_path, "Simulink_to_xppu.csv"),
    os.path.join(base_path, "Scenario_13_CoDeSys.csv"),
    os.path.join(base_path, "dynamik_3.csv"),
    os.path.join(base_path, "xPPU_ohneVRNavigation.csv")
]

def clean_id_short(value):
    if pd.notna(value) and isinstance(value, str): 
        value = value.replace('.', '').replace(' ', '_')
        if not re.match(r'^[A-Za-z]', value):
            value = f"default{value}"
    return value

all_dataframes = []
for file in csv_files:
    if not os.path.exists(file):
        continue
    data = pd.read_csv(file)
    if 'idShort' in data.columns:
        data['idShort'] = data['idShort'].apply(clean_id_short)
    all_dataframes.append(data)

merged_data = pd.concat(all_dataframes, ignore_index=True)

merged_data.to_csv(output_file, index=False)
