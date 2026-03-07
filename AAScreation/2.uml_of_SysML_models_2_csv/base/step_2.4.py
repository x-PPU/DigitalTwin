#!/usr/bin/env python 3.10.15
"""
This script processes UML CSV data to apply name replacements for specific xmi:type values 
and adds new End-Pseudostate, End-FinalState, and End-Operation rows after their corresponding elements.
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

# Apply name replacement logic based on xmi:type
for row in csv_data[1:]:  # Skip the header row
    xmi_type = row[xmi_type_index]
    original_name = row[name_index].strip()

    # Replace names for StateMachine and State
    if xmi_type == "StateMachine":
        row[name_index] = f"StateDiagram_{original_name}"
    elif xmi_type == "State":
        row[name_index] = f"State_{original_name}"

# Logic to add End-Pseudostate, End-FinalState, and End-Operation rows
additional_rows = []
for index, row in enumerate(csv_data):
    xmi_type = row[xmi_type_index]

    # Add End-Pseudostate row
    if xmi_type == "Pseudostate":
        new_row = ["End-Pseudostate"] + [""] * (len(header) - 1)
        additional_rows.append((index + 1, new_row))

    # Add End-FinalState row
    elif xmi_type == "FinalState":
        new_row = ["End-FinalState"] + [""] * (len(header) - 1)
        additional_rows.append((index + 1, new_row))

    # Add End-Operation row
    elif xmi_type == "Operation":
        new_row = ["End-Operation"] + [""] * (len(header) - 1)
        additional_rows.append((index + 1, new_row))

# Insert additional rows in reverse order to avoid index shifting
for index, new_row in reversed(additional_rows):
    csv_data.insert(index, new_row)

# Save the modified CSV data
with open(output_csv_file, mode="w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(csv_data)
