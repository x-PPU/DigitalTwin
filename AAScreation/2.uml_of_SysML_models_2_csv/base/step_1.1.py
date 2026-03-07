#!/usr/bin/env python 3.10.15
"""
This script processes UML CSV data, marks specific Class elements as Block1, Block3, and handles composite structures.
It generates a final CSV output with BlockDefinitionDiagram structures.
"""

import csv
import sys

input_csv_file = sys.argv[1]
output_csv_file = sys.argv[2]

XMI_TYPE_INDEX = 0
NAME_INDEX = 1
AGGREGATION_INDEX = 7
SECOND_VALUE_INDEX = 17

csv_data = []
with open(input_csv_file, mode="r", newline='', encoding="utf-8") as file:
    reader = csv.reader(file)
    csv_data = [row for row in reader]

# Ensure each row has enough columns
def ensure_row_length(row, target_length):
    while len(row) < target_length:
        row.append("")

# Mark Block1, Block2, and Block3
for i, row in enumerate(csv_data):
    if row[XMI_TYPE_INDEX] == "End-Class":
        class_index = i - 1
        while class_index >= 0 and csv_data[class_index][XMI_TYPE_INDEX] != "Class":
            class_index -= 1
        if class_index >= 0 and csv_data[class_index][NAME_INDEX].startswith("BDD_"):
            # Mark as Block1
            csv_data[class_index][NAME_INDEX] = csv_data[class_index][NAME_INDEX].replace("BDD_", "")
            ensure_row_length(csv_data[class_index], SECOND_VALUE_INDEX + 1)
            csv_data[class_index][SECOND_VALUE_INDEX] = "Block1"

            # Mark corresponding End-Class as Block3
            ensure_row_length(csv_data[i], SECOND_VALUE_INDEX + 1)
            csv_data[i][SECOND_VALUE_INDEX] = "Block3"

# Mark other remaining Class rows
for i, row in enumerate(csv_data):
    if row[XMI_TYPE_INDEX] == "Class" and row[SECOND_VALUE_INDEX] != "Block1":
        if row[NAME_INDEX].startswith("BDD_"):
            # Mark current row as Block1
            row[NAME_INDEX] = row[NAME_INDEX].replace("BDD_", "")
            ensure_row_length(row, SECOND_VALUE_INDEX + 1)
            row[SECOND_VALUE_INDEX] = "Block1"
            
            # Insert an End-Class row marked as Block3
            end_class_row = ["End-Class"] + [""] * (len(csv_data[0]) - 1)
            ensure_row_length(end_class_row, SECOND_VALUE_INDEX + 1)
            end_class_row[SECOND_VALUE_INDEX] = "Block3"
            
            # Insert End-Class row after current Class row
            csv_data.insert(i + 1, end_class_row)

# Handle sections marked as Block1
output_data = csv_data.copy()
for i, row in enumerate(csv_data):
    if row[SECOND_VALUE_INDEX] == "Block1":
        class_index = i
        end_class_index = class_index + 1
        while end_class_index < len(csv_data) and csv_data[end_class_index][SECOND_VALUE_INDEX] != "Block3":
            end_class_index += 1

        has_composite = any(len(csv_data[j]) > AGGREGATION_INDEX and csv_data[j][AGGREGATION_INDEX] == "composite" for j in range(class_index + 1, end_class_index))
        
        # If a composite row is found, create a copy
        if has_composite:
            # Create SubmodelElementCollection structure
            block_name = "BlockDefinitionDiagram_" + csv_data[class_index][NAME_INDEX]
            new_rows = [
                ["SubmodelElementCollection", block_name] + [""] * (len(csv_data[0]) - 2),
                ["End-SubmodelElementCollection"] + [""] * (len(csv_data[0]) - 1)
            ]
            
            # Copy rows from Block1 to Block3
            section_copy = [list(csv_data[j]) for j in range(class_index, end_class_index + 1)]
            for line in section_copy:
                ensure_row_length(line, SECOND_VALUE_INDEX + 1)
                if line[SECOND_VALUE_INDEX] == "Block1":
                    line[SECOND_VALUE_INDEX] = "Root1"
                elif line[SECOND_VALUE_INDEX] == "Block3":
                    line[SECOND_VALUE_INDEX] = "Root3"

            output_data.extend(new_rows[:1] + section_copy + new_rows[1:])

output_data = [row for row in output_data if row]
with open(output_csv_file, mode="w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(output_data)
