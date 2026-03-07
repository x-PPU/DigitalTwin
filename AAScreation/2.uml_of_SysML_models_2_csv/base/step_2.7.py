#!/usr/bin/env python 3.10.15
"""
This script processes a CSV file to update the `idShort` column:
1. Appends `doActivities+Of+<Previous idShort>` for rows with `doActivities`.
2. Ensures unique `idShort` values by appending `Reference` values when duplicates occur.
3. Replaces special characters in `idShort` with alphanumeric characters and underscores.
"""

import csv
import re
import sys
from collections import defaultdict

input_csv_file_1 = sys.argv[1]
output_csv_file_1 = sys.argv[2]

# Function to replace special characters in idShort
def replace_special_characters(name):
    """Replace characters that are not letters, numbers, or underscores."""
    return re.sub(r'[^a-zA-Z0-9_]', '', name)

def process_csv_file(input_csv_file, output_csv_file):
    # Read CSV data
    csv_data = []
    with open(input_csv_file, mode="r", newline='', encoding="utf-8") as file:
        reader = csv.reader(file)
        csv_data = [row for row in reader]

    # Get the column indices based on the first row
    header = csv_data[0]
    
    # Identify idShort and Reference column indices
    idShort_index = header.index("idShort")
    reference_index = header.index("Reference") if "Reference" in header else None

    # Update idShort values for rows with "doActivities"
    for i in range(1, len(csv_data)):  # Start from the second row to skip the header
        row = csv_data[i]
        if row[idShort_index] == "doActivities" and i > 1:
            previous_idShort = csv_data[i - 1][idShort_index]
            row[idShort_index] = f"doActivities+Of+{previous_idShort}"

    # Dictionary to track idShort occurrences
    name_occurrences = defaultdict(list)

    # Collect rows with non-empty idShort
    for index, row in enumerate(csv_data[1:], start=1):  # Skip the header row
        original_name = row[idShort_index].strip()

        if original_name:
            name_occurrences[original_name].append((index, row[reference_index] if reference_index else ''))

    # Process rows with the same idShort
    for name, occurrences in name_occurrences.items():
        if len(occurrences) > 1:
            for index, reference in occurrences:
                # Only append Reference to idShort if Reference is non-empty
                if reference:
                    new_idShort = f"{name}{reference}"
                    # Replace special characters in the new_idShort
                    csv_data[index][idShort_index] = replace_special_characters(new_idShort)

    # Replace any remaining special characters in idShort across all rows
    for row in csv_data[1:]:  # Skip the header row
        row[idShort_index] = replace_special_characters(row[idShort_index])

    # Write updated data to output CSV
    with open(output_csv_file, mode="w", newline='', encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerows(csv_data)

process_csv_file(input_csv_file_1, output_csv_file_1)
