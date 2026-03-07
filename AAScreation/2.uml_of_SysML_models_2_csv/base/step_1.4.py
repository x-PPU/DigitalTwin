#!/usr/bin/env python 3.10.15
"""
This script processes UML CSV data to handle Association blocks, update Enumeration names,
insert StructuralDiagram, manage Root and Sub blocks, and remove duplicates. It generates a final CSV file.
"""

import csv
import re
import sys

input_csv_file = sys.argv[1]
output_csv_file = sys.argv[2]

sysml_14_inserted = False 

with open(input_csv_file, mode='r', newline='', encoding='utf-8') as infile:
    reader = list(csv.reader(infile))

    header = reader[0]
    data = reader[1:]

processed_data = [header]
block_diagram_indices = []  
enumeration_blocks = [] 
block_diagram_found = False
first_block_diagram_index = None
last_block_diagram_index = None

# Main logic
i = 0
while i < len(data):
    row = data[i]
    xmi_type = row[header.index('xmi:type')]
    description = row[header.index('description')]
    name_index = header.index('name')
    delete_flag = row[header.index('description')] == "delete"

    # Skip rows marked as delete
    if delete_flag:
        i += 1
        continue

    # Mark Association block as delete if not already marked
    if xmi_type == "Association":
        association_start = i
        association_end = None
        already_deleted = row[header.index('description')] == "delete"
        
        if already_deleted:
            i += 1
            continue
        
        # Find the next End-Association row
        for j in range(i + 1, len(data)):
            if data[j][header.index('xmi:type')] == "End-Association":
                association_end = j
                break

        # Mark the entire block as delete if End-Association is found
        if association_end is not None:
            for idx in range(association_start, association_end + 1):
                data[idx][header.index('description')] = "delete"

    # Skip Block blocks
    if description == "Block1" or description == "Block2":
        # Find the end of the Block
        if description == "Block1":
            for j in range(i + 1, len(data)):
                if data[j][header.index('description')] == "Block3":
                    i = j  # Skip to the line after Block3
                    break
        i += 1
        continue

    # Update the name of Enumeration and EnumerationLiteral
    if xmi_type == "Enumeration" or xmi_type == "EnumerationLiteral":
        original_name = row[name_index]
        row[name_index] = f"{xmi_type}_{original_name}"

    # Insert StructuralDiagram above the first BlockDefinitionDiagram
    if not sysml_14_inserted and xmi_type == "SubmodelElementCollection" and row[name_index].startswith("BlockDefinitionDiagram_"):
        processed_data.append(["SubmodelElementCollection", "StructuralDiagram"] + [""] * (len(header) - 2))  
        sysml_14_inserted = True  
        first_block_diagram_index = i  

    # Handle Root and Sub blocks
    if description == "Root1" or description == "Sub1":
        block_start = i
        block_end = None
        end_marker = "Root3" if description == "Root1" else "Sub3"
        for j in range(i + 1, len(data)):
            if data[j][header.index('description')] == end_marker:
                block_end = j
                break
        
        if block_end:
            # New Property and Operation block rows
            new_property_block = ["SubmodelElementCollection", "Properties"] + [""] * (len(header) - 2)
            new_property_block_end = ["End-SubmodelElementCollection"] + [""] * (len(header) - 1)
            new_operation_block = ["SubmodelElementCollection", "Operations"] + [""] * (len(header) - 2)
            new_operation_block_end = ["End-SubmodelElementCollection"] + [""] * (len(header) - 1)

            # Insert original block start and new blocks
            processed_data.append(row)
            processed_data.append(new_property_block)
            
            # Move Property rows
            for k in range(block_start + 1, block_end):
                if data[k][header.index('xmi:type')] == "Property" and data[k][header.index('description')] != "delete":
                    processed_data.append(data[k])

            # Close Property block
            processed_data.append(new_property_block_end)

            # Start Operation block
            processed_data.append(new_operation_block)

            # Move Operation rows
            for k in range(block_start + 1, block_end):
                if data[k][header.index('xmi:type')] == "Operation" and data[k][header.index('description')] != "delete":
                    processed_data.append(data[k])

            # Close Operation block
            processed_data.append(new_operation_block_end)

            # Update the name of Root or Sub block
            row[header.index('name')] = f"{row[header.index('xmi:type')]}_{row[header.index('name')]}"

            # Add End-Class after Sub3 or Root3
            end_class_row = ["End-Class"] + [""] * (len(header) - 1) + [end_marker]
            processed_data.append(end_class_row)

            # Skip to after Sub3 or Root3
            i = block_end
        else:
            # Append regular row if no Sub3 or Root3 found
            processed_data.append(row)

    else:
        # Append regular row
        processed_data.append(row)

    i += 1

# Feature 1: Insert End-SubmodelElementCollection after the last BlockDefinitionDiagram
if first_block_diagram_index is not None:
    for i, row in enumerate(data[first_block_diagram_index:], start=first_block_diagram_index):
        if row[header.index('xmi:type')] == "End-SubmodelElementCollection":
            last_block_diagram_index = i

if last_block_diagram_index is not None:
    processed_data.insert(last_block_diagram_index + 1, ["End-SubmodelElementCollection"] + [""] * (len(header) - 1))

# Feature 2: Mark Enumeration blocks not inside BlockDefinitionDiagram as delete
for i, row in enumerate(data):
    if row[header.index('xmi:type')] == "Enumeration":
        enumeration_start = i
        enumeration_end = None
        for j in range(i + 1, len(data)):
            if data[j][header.index('xmi:type')] == "End-Enumeration":
                enumeration_end = j
                break
        
        # Check if Enumeration is inside BlockDefinitionDiagram
        in_block = False
        if first_block_diagram_index is not None and last_block_diagram_index is not None:
            if enumeration_start >= first_block_diagram_index and enumeration_end <= last_block_diagram_index:
                in_block = True
        
        # Mark Enumeration block as delete if not in BlockDefinitionDiagram
        if not in_block:
            for idx in range(enumeration_start, enumeration_end + 1):
                data[idx][header.index('description')] = "delete"

# Feature 3: Remove duplicate Sub blocks in BlockDefinitionDiagram
unique_sub_blocks = set()
for i in range(first_block_diagram_index, last_block_diagram_index + 1):
    row = data[i]
    if row[header.index('xmi:type')] == "SubmodelElementCollection":
        sub_name = row[header.index('name')]
        if sub_name in unique_sub_blocks:
            data[i][header.index('description')] = "delete"
        else:
            unique_sub_blocks.add(sub_name)

# Remove markers like Sub1, Sub2, Sub3, Root1, Root2, Root3
for row in processed_data:
    for idx in range(len(row)-1, -1, -1):
        if row[idx].strip():
            row[idx] = re.sub(r'\b(Sub|Root)\d+\b', '', row[idx]).strip()
            break

# Remove rows marked as delete
final_data = [row for row in processed_data if row[header.index('description')] != "delete"]

with open(output_csv_file, mode='w', newline='', encoding='utf-8') as outfile:
    writer = csv.writer(outfile)
    writer.writerows(final_data)
