#!/usr/bin/env python 3.10.15
"""
This script processes UML CSV data to remove ProfileApplication blocks, including rows between 
ProfileApplication and End-ProfileApplication, and saves the filtered result to a new file.
"""

import csv
import sys

input_csv_file = sys.argv[1]
output_csv_file = sys.argv[2]

csv_data = []
with open(input_csv_file, mode="r", newline='', encoding="utf-8") as file:
    reader = csv.reader(file)
    csv_data = [row for row in reader]

# Get the column index for xmi:type
header = csv_data[0]
xmi_type_index = header.index("xmi:type")

# Initialize variables to track ProfileApplication blocks
filtered_data = []
inside_profile_application = False  # Track whether we're inside ProfileApplication

# Iterate through CSV data and remove ProfileApplication blocks
for row in csv_data:
    xmi_type = row[xmi_type_index]
    
    # Detect the start of a ProfileApplication block
    if xmi_type == "ProfileApplication":
        inside_profile_application = True
        continue  # Skip this row
    
    # Detect the end of a ProfileApplication block
    if xmi_type.startswith("End-ProfileApplication"):
        inside_profile_application = False
        continue  # Skip this row

    # If inside ProfileApplication, skip all rows in the block
    if inside_profile_application:
        continue
    
    # If outside ProfileApplication, keep the row
    filtered_data.append(row)

with open(output_csv_file, mode="w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(filtered_data)
