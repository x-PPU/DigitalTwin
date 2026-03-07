#!/usr/bin/env python 3.10.15
"""
This script reads a CSV file, processes 'Comment' blocks, and checks if child rows are empty or 
if the 'Comment' row itself is mostly empty. If so, the entire Comment structure is deleted.
"""

import csv
import sys

input_csv_file = sys.argv[1]
output_csv_file = sys.argv[2]

# Read CSV data
csv_data = []
with open(input_csv_file, mode="r", newline='', encoding="utf-8") as file:
    reader = csv.reader(file)
    csv_data = [row for row in reader]

# Get the column indices based on the first row (matching your provided column names)
header = csv_data[0]
xmi_type_index = header.index("xmi:type")
xmi_id_index = header.index("xmi:id")

# Function to check if a row (except for xmi:type and xmi:id) is completely empty
def is_row_content_empty(row):
    return all(not cell.strip() for i, cell in enumerate(row) if i not in [xmi_type_index, xmi_id_index])

# Function to check if all rows between Comment and End-Comment are empty
def are_comment_children_empty(comment_start_index, comment_end_index):
    for i in range(comment_start_index + 1, comment_end_index):
        if not is_row_content_empty(csv_data[i]):
            return False
    return True

# Iterate through CSV data to handle Comment blocks
filtered_csv_data = [header]  # Start with header row
index = 1  # Start at the first data row

while index < len(csv_data):
    row = csv_data[index]
    xmi_type = row[xmi_type_index]

    if xmi_type == "Comment":
        # Find the corresponding End-Comment row
        comment_start_index = index
        comment_end_index = None

        # Search for the End-Comment row
        for i in range(index + 1, len(csv_data)):
            if csv_data[i][xmi_type_index] == "End-Comment":
                comment_end_index = i
                break

        if comment_end_index is None:
            # If no End-Comment found, this is an incomplete Comment block, keep as is
            filtered_csv_data.append(row)
            index += 1
            continue

        # Check if the Comment row is mostly empty (except xmi:type and xmi:id)
        if is_row_content_empty(row):
            # If Comment row is empty, skip the entire Comment block
            index = comment_end_index + 1
            continue

        # Check if all child rows between Comment and End-Comment are empty
        if are_comment_children_empty(comment_start_index, comment_end_index):
            # If all children are empty, skip the entire Comment block
            index = comment_end_index + 1
            continue

        # If neither condition is met, keep the Comment block
        filtered_csv_data.append(row)  # Add the Comment row
        for i in range(comment_start_index + 1, comment_end_index):
            if not is_row_content_empty(csv_data[i]):
                filtered_csv_data.append(csv_data[i])  # Add non-empty child rows
        filtered_csv_data.append(csv_data[comment_end_index])  # Add the End-Comment row
        index = comment_end_index + 1

    else:
        # Add non-comment rows directly
        filtered_csv_data.append(row)
        index += 1

with open(output_csv_file, mode="w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(filtered_csv_data)

