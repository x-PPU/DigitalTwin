#!/usr/bin/env python 3.10.15
"""
This script processes UML CSV data, identifies Enumeration blocks based on type, 
and inserts them between Root1 and Root3 blocks while marking the original Enumeration block as "delete."
"""

import csv
from copy import deepcopy
import sys

input_csv_file = sys.argv[1]
output_csv_file = sys.argv[2]

with open(input_csv_file, mode="r", newline='', encoding="utf-8") as file:
    reader = csv.reader(file)
    csv_data = [row for row in reader]

header = csv_data[0]
xmi_type_index = header.index("xmi:type")
xmi_id_index = header.index("xmi:id")
type_index = header.index("type")
description_index = header.index("description")
aggregation_index = header.index("aggregation")

# Cache positions of Root1 and Root3 blocks
root_blocks = []
for idx, row in enumerate(csv_data):
    if row[description_index] == "Root1" and row[xmi_type_index] == "Class":
        root_blocks.append([idx, None])  # Using list to update later
    elif row[description_index] == "Root3" and root_blocks and root_blocks[-1][1] is None:
        root_blocks[-1][1] = idx

# Iterate through Root1 and Root3 blocks, inserting matching Enumeration blocks
for k, (root1_index, root3_index) in enumerate(root_blocks):
    insertion_index = root3_index + 1  # Set initial insertion point after Root3
    
    # Iterate through rows between Root1 and Root3, skipping composite and empty type rows
    for i in range(root1_index + 1, root3_index):
        row = csv_data[i]
        if row[aggregation_index] == "composite" or row[type_index] == "":
            continue  # Skip composite and empty type rows

        type_value = row[type_index]
        # Find matching Enumeration row in csv_data
        for j in range(len(csv_data)):
            if csv_data[j][xmi_id_index] == type_value and csv_data[j][xmi_type_index] == "Enumeration":
                # Found Enumeration block, extract rows from Enumeration to End-Enumeration
                enum_start = j
                enum_end = j + 1
                while enum_end < len(csv_data) and csv_data[enum_end][xmi_type_index] != "End-Enumeration":
                    enum_end += 1
                if enum_end < len(csv_data):
                    # Copy the block without delete markers
                    enum_block = [deepcopy(csv_data[k]) for k in range(enum_start, enum_end + 1)]
                    
                    # Insert the found Enumeration block at the current insertion index
                    csv_data[insertion_index:insertion_index] = enum_block
                    insertion_index += len(enum_block)  # Update insertion index
                    
                    # Mark the original Enumeration block as delete
                    for delete_index in range(enum_start, enum_end + 1):
                        csv_data[delete_index][description_index] = "delete"

                    # Update root_blocks indices to reflect newly added rows
                    added_rows_count = len(enum_block)
                    for m in range(k + 1, len(root_blocks)):
                        root_blocks[m][0] += added_rows_count
                        root_blocks[m][1] += added_rows_count

                # Break inner loop and continue to the next non-empty type row
                break

# Write the result to a new CSV file, including all rows (without removing delete-marked rows)
with open(output_csv_file, mode="w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(csv_data)
