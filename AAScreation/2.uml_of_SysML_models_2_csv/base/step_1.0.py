#!/usr/bin/env python 3.10.15
"""
# This script processes UML CSV data, identifies direct child elements of Class, and marks them as RootElements.
# It then generates an intermediate CSV output with specific logic for Class and RootElement handling.
"""

import csv
import sys

input_csv_file = sys.argv[1]
intermediate_csv_file = sys.argv[2]

csv_data = []
with open(input_csv_file, mode="r", newline='', encoding="utf-8") as file:
    reader = csv.reader(file)
    csv_data = [row for row in reader]

# Function to ensure row length
def ensure_row_length(row, target_length):
    while len(row) < target_length:
        row.append("")

# Function to check if the direct parent is Class without intermediate levels
def is_direct_class_child(element_index):
    end_class_index = element_index
    while end_class_index < len(csv_data) and csv_data[end_class_index][0] != "End-Class":
        end_class_index += 1
    
    if end_class_index == len(csv_data):
        return False

    class_index = end_class_index
    while class_index >= 0 and csv_data[class_index][0] != "Class":
        if csv_data[class_index][0].startswith("End-") and csv_data[class_index][0] != "End-Class":
            end_type_name = csv_data[class_index][0][4:]
            temp_index = class_index - 1
            while temp_index >= 0 and csv_data[temp_index][0] != end_type_name:
                temp_index -= 1
            if temp_index < element_index < class_index:
                return False
        class_index -= 1

    # Mark the Class and End-Class rows for the direct child
    if class_index >= 0 and end_class_index < len(csv_data):
        csv_data[class_index][1] += " (RootElement)"
        csv_data[end_class_index][1] += " (RootElement)"
    
    return class_index >= 0 and class_index < element_index

# Mark RootElement temporarily for internal logic
for i, row in enumerate(csv_data):
    xmi_type = row[0]
    if xmi_type in ["Operation", "Property"]:
        if is_direct_class_child(i):
            ensure_row_length(row, len(csv_data[i]))
            row[1] += " (RootElement)"  # Temporary marker for internal use

# Prepare output data with RootElement markers removed for final output
output_data = [[cell.replace(" (RootElement)", "") if isinstance(cell, str) else cell for cell in row] for row in csv_data]

# Set to track visited Class and End-Class indices
visited_indices = set()

# Process marked Class and End-Class pairs
for i, row in enumerate(csv_data):
    if row[0] == "Class" and i not in visited_indices and "(RootElement)" in row[1]:
        class_index = i
        end_class_index = class_index
        while end_class_index < len(csv_data) and csv_data[end_class_index][0] != "End-Class":
            end_class_index += 1

        if end_class_index < len(csv_data) and "(RootElement)" in csv_data[end_class_index][1]:
            visited_indices.add(class_index)
            visited_indices.add(end_class_index)
            
            section_copy = [list(csv_data[j]) for j in range(class_index, end_class_index + 1)]
            section_copy[0][1] = "BDD_" + section_copy[0][1]
            
            section_copy = [[cell.replace(" (RootElement)", "") if isinstance(cell, str) else cell for cell in line]
                            for line in section_copy if "(RootElement)" in line[1] or line[0] in ["Class", "End-Class"]]
            
            output_data.extend(section_copy)
            
            for j in range(class_index + 1, end_class_index):
                if "(RootElement)" in csv_data[j][1]:
                    output_data[j] = []  # Mark these lines for removal

            is_empty_after_removal = all(output_data[k] == [] for k in range(class_index + 1, end_class_index))
            if is_empty_after_removal:
                output_data[class_index] = []
                output_data[end_class_index] = []

# Additional logic to handle Class rows without corresponding End-Class
for i, row in enumerate(csv_data):
    if row[0] == "Class" and i not in visited_indices:
        standalone_class_copy = list(row)
        standalone_class_copy[1] = "BDD_" + standalone_class_copy[1]
        output_data.append(standalone_class_copy)
        
        output_data[i] = []
        visited_indices.add(i)

# Filter out marked lines (empty lists) from output data
output_data = [row for row in output_data if row]

# Write intermediate CSV data for step 1.1
with open(intermediate_csv_file, mode="w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(output_data)
