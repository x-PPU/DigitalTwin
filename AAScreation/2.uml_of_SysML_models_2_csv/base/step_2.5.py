#!/usr/bin/env python 3.10.15
"""
This script processes UML CSV data by replacing special characters in names, handling specific element pairs (e.g., State/End-State), 
and transforming xmi:type values. It generates a new CSV with the adjusted data.
"""

import csv
import sys

input_csv_file = sys.argv[1]
output_csv_file = sys.argv[2]

dict_replace = {
    'ä': 'ae', 'Ä': 'Ae', 'ö': 'oe', 'Ö': 'Oe', 'ü': 'ue', 'Ü': 'Ue',
    '°C': 'degreeCelsius', 'Ω': 'ohm', 'µ': 'micro', '�': '',
    ' ': '', '-': '', '.': '', '#': '', '%': 'percentage',
    '+': '', '[': '', ']': '', '(': '', ')': '', ',': '', '&': 'and', '@': 'at',
    '!': '', ':': '', ';': '', '"': '', "'": '', '~': '', '<': '', '>': '', '|': '', '\\': '', '^': '', '=': '', '/': ''
}

def replace_special_characters(text):
    if text:
        for old, new in dict_replace.items():
            text = text.replace(old, new)
    return text

csv_data = []
with open(input_csv_file, mode="r", newline='', encoding="utf-8") as file:
    reader = csv.reader(file)
    csv_data = [row for row in reader]

# Get the original header
header = csv_data[0]

# Create new header with adjusted column names and order, including second_value
new_header = ["typeName", "idShort", "value", "valueType", "category", "descriptionEN", "descriptionDE", "Reference", "second_value"]

# Initialize the list to store the modified CSV data
new_csv_data = []
new_csv_data.append(new_header)  # Add the new header

# Map original column positions (0-based indexing)
xmi_type_index = header.index("xmi:type")       
name_index = header.index("name")                
xmi_id_index = header.index("xmi:id")            
value_index = header.index("value")             
value_type_index = header.index("valueType")     
description_index = header.index("description") 
source_index = header.index("source")            
target_index = header.index("target")           
second_value_index = header.index("second_value") 

# Set to track unique typeName values (for printing to check)
unique_type_names = set()

# Track which elements (State/Class and End-State/End-Class) rows have been processed
processed_elements = set()
processed_end_elements = set()

# Define pairs of types to process together
element_pairs = [("State", "End-State"), ("Class", "End-Class")]

# Function to find the nearest preceding element (State/Class) for End-State/End-Class
def find_nearest_element(index, element_type):
    for i in range(index - 1, -1, -1):
        if csv_data[i][xmi_type_index] == element_type and i not in processed_elements:
            return i
    return None

# Process End-State and End-Class pairs until no more remain
def process_end_elements(element_pairs):
    while True:
        found_pair = False
        for index, row in enumerate(csv_data[1:], start=1):
            xmi_type = row[xmi_type_index]

            # Process each element pair (e.g., State/End-State, Class/End-Class)
            for element_type, end_element_type in element_pairs:
                if xmi_type == end_element_type and index not in processed_end_elements:
                    found_pair = True
                    nearest_element_index = find_nearest_element(index, element_type)

                    if nearest_element_index is not None:
                        # Replace the nearest element (State/Class) with SubmodelElementCollection
                        csv_data[nearest_element_index][xmi_type_index] = "SubmodelElementCollection"
                        processed_elements.add(nearest_element_index)

                        # Replace the current End-State or End-Class with End-SubmodelElementCollection
                        row[xmi_type_index] = "End-SubmodelElementCollection"
                        processed_end_elements.add(index)

                    # Break to handle the next End-State or End-Class after processing the current pair
                    break
            if found_pair:
                break

        # If no more unprocessed End-State or End-Class are found, exit the loop
        if not found_pair:
            break

process_end_elements(element_pairs)
# Second pass: process remaining States, Classes, and other elements
for index, row in enumerate(csv_data[1:], start=1):
    xmi_type = row[xmi_type_index]
    source_value = row[source_index]
    target_value = row[target_index]
    new_xmi_type = xmi_type  # Initialize with the original xmi:type

    # Handle remaining States and Classes
    if xmi_type in ["State", "Class"] and index not in processed_elements:
        new_xmi_type = "Property"  # Remaining States/Classes are classified as Property

    # Handle other xmi:type values according to the logic
    elif xmi_type in ["Enumeration", "StateMachine", "Region", "ProfileApplication", "EAnnotation", "Pseudostate", "FinalState", "Comment"]:
        new_xmi_type = "SubmodelElementCollection"
    elif xmi_type in [ "Profile", "EPackage", "OpaqueBehavior", "EnumerationLiteral", "LiteralInteger", "LiteralUnlimitedNatural"]:
        new_xmi_type = "Property"
    elif xmi_type == "Transition":
        if source_value and target_value:
            new_xmi_type = "RelationshipElement"
        else:
            new_xmi_type = "ReferenceElement"
    elif xmi_type == "Association":
        new_xmi_type = "RelationshipElement"
    elif xmi_type == "EStringToStringMapEntry":
        new_xmi_type = "Property"
    elif xmi_type == "Operation":  
        new_xmi_type = "SubmodelElementCollection"
    elif xmi_type.startswith("End-"):
        new_xmi_type = "End-SubmodelElementCollection"

    # Check if valueType should be set to Boolean
    value_type = row[value_type_index].strip() if row[value_type_index].strip() else None
    if value_type == "EBoolean":
        value_type = "Boolean"

    # Track unique typeName values for printing
    if new_xmi_type not in unique_type_names:
        unique_type_names.add(new_xmi_type)
        print(f"typeName encountered: {new_xmi_type}")

    # Ensure all values are correctly aligned in the row
    new_row = [
        new_xmi_type,  # typeName
        replace_special_characters(row[name_index]) if row[name_index].strip() else None,
        row[value_index] if row[value_index].strip() else None,
        value_type,  # Use the updated valueType here
        None,  # category 
        row[description_index] if row[description_index].strip() else None,
        None,  # descriptionDE (not used here)
        row[xmi_id_index] if row[xmi_id_index].strip() else None,
        row[second_value_index] if row[second_value_index].strip() else None 
    ]
    new_csv_data.append(new_row)

with open(output_csv_file, mode="w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(new_csv_data)