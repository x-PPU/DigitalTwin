#!/usr/bin/env python 3.10.15
"""
This script processes a UML CSV file by splitting the content into two separate files:
one containing rows from "StateDiagram" to "StructuralDiagram" (excluding "StructuralDiagram"),
and another containing "StructuralDiagram" and all subsequent rows.
"""

import csv
import sys

input_csv_file = sys.argv[1]
output_csv_file_1 = sys.argv[2] 
output_csv_file_2 = sys.argv[3]

csv_data = []
with open(input_csv_file, mode="r", newline='', encoding="utf-8") as file:
    reader = csv.reader(file)
    csv_data = [row for row in reader]

header = csv_data[0]
typeName_index = header.index("typeName")
idShort_index = header.index("idShort")

# Find the row indices for SubmodelElementCollection with idShort as "StateDiagram" and "Structural Diagram"
state_diagram_index = None
sysml_14_index = None

for index, row in enumerate(csv_data):
    if row[typeName_index] == "SubmodelElementCollection":
        if row[idShort_index] == "StateDiagram":
            state_diagram_index = index
        elif row[idShort_index] == "StructuralDiagram":
            sysml_14_index = index

# Ensure both "StateDiagram" and "StructuralDiagram" rows are found
if state_diagram_index is None or sysml_14_index is None:
    print("Could not find 'StateDiagram' or 'StructuralDiagram' rows. Cannot proceed.")
    sys.exit(1)

# Create two new CSV files
# First CSV: includes rows from StateDiagram to StructuralDiagram (excluding StructuralDiagram)
csv_part_1 = [header] + csv_data[state_diagram_index:sysml_14_index]

# Second CSV: includes StructuralDiagram and all subsequent rows
csv_part_2 = [header] + csv_data[sysml_14_index:]

# Write the data into new CSV files
with open(output_csv_file_1, mode="w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(csv_part_1)

with open(output_csv_file_2, mode="w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(csv_part_2)
