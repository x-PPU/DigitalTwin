#!/usr/bin/env python 3.10.15
"""
This script processes UML CSV data to remove "Region" rows, insert a new StateDiagram row, 
and add an End-SubmodelElementCollection row above "StructuralDiagram" if found.
"""

import csv
import sys

input_csv_file = sys.argv[1]
output_csv_file = sys.argv[2]

csv_data = []
with open(input_csv_file, mode="r", newline='', encoding="utf-8") as file:
    reader = csv.reader(file)
    csv_data = [row for row in reader]

# Get the column indices
header = csv_data[0]
xmi_type_index = header.index("xmi:type")
name_index = header.index("name")

# 1. Remove rows where xmi:type is "Region" or "End-Region"
csv_data = [row for row in csv_data if row[xmi_type_index] not in ["Region", "End-Region"]]

# 2. Insert a new row after the first row in the CSV
new_row = ["SubmodelElementCollection", "StateDiagram"] + [""] * (len(header) - 2)
csv_data.insert(1, new_row)

# 3. Insert a row above where xmi:type is "SubmodelElementCollection" and name is "StructuralDiagram"
for index, row in enumerate(csv_data):
    if row[xmi_type_index] == "SubmodelElementCollection" and row[name_index] == "StructuralDiagram":
        end_submodel_row = ["End-SubmodelElementCollection"] + [""] * (len(header) - 1)
        csv_data.insert(index, end_submodel_row)
        break  # Exit loop after inserting the row

# Save the modified CSV data
with open(output_csv_file, mode="w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(csv_data)
