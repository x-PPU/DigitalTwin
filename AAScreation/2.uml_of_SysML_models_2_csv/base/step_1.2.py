#!/usr/bin/env python 3.10.15
"""
This script processes UML CSV data, handling Root, Block, and Association blocks,
and generates a final CSV with SubmodelElementCollection and relationships.
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
aggregation_index = header.index("aggregation")
description_index = header.index("description")
name_index = header.index("name")
type_index = header.index("type")
association_index = header.index("association")

# Cache all key positions
root_blocks = []
block_indices = {}
association_blocks = {}

# Find Root1, Root3, Block1 - Block3, and Association block positions
for idx, row in enumerate(csv_data):
    if row[description_index] == "Root1" and row[xmi_type_index] == "Class":
        root_blocks.append((idx, None))
    elif row[description_index] == "Root3" and root_blocks and root_blocks[-1][1] is None:
        root_blocks[-1] = (root_blocks[-1][0], idx)
    elif row[description_index] == "Block1":
        block1_id = row[xmi_id_index]
        # Find Block3 end position
        end_idx = idx + 1
        while end_idx < len(csv_data) and csv_data[end_idx][description_index] != "Block3":
            end_idx += 1
        if end_idx < len(csv_data):
            block_indices[block1_id] = (idx, end_idx)
    elif row[xmi_type_index] == "Association":
        # Find Association to End-Association block
        association_start = idx
        association_end = idx + 1
        while association_end < len(csv_data) and csv_data[association_end][xmi_type_index] != "End-Association":
            association_end += 1
        if association_end < len(csv_data):
            association_id = row[xmi_id_index]
            association_blocks[association_id] = (association_start, association_end)

output_data = []
skip_until_index = -1  

# Track whether each type_value has already copied the Block
block_copied_dict = {}

for i, row in enumerate(csv_data):
    if i <= skip_until_index:
        continue 
    output_data.append(row)

    # Check if the row is Root3, and insert Sub1-Sub3 and relationship structure after Root3
    if i in [root[1] for root in root_blocks]:
        root1_index = next(root[0] for root in root_blocks if root[1] == i)
        pending_insertions = []
        for j in range(root1_index, i + 1):
            row = csv_data[j]
            if len(row) > aggregation_index and row[aggregation_index] == "composite":
                type_value = row[type_index]
                composite_name = row[name_index]
                association_value = row[association_index]

                # Check if the Block has already been copied
                if type_value not in block_copied_dict:
                    block_copied_dict[type_value] = False  # Initialize as not copied

                # Find Block1 - Block3 and Block2 blocks
                if type_value in block_indices and not block_copied_dict[type_value]:
                    start_idx, end_idx = block_indices[type_value]
                    
                    if csv_data[start_idx][description_index] == "Block1":
                        sub_block = [list(csv_data[l]) for l in range(start_idx, end_idx + 1)]
                        for line in sub_block:
                            if line[description_index] == "Block1":
                                line[description_index] = "Sub1"
                            elif line[description_index] == "Block3":
                                line[description_index] = "Sub3"
                        block_copied_dict[type_value] = True  # Mark as copied
                    elif csv_data[start_idx][description_index] == "Block2":
                        sub_block = [list(csv_data[start_idx])]
                        sub_block[0][description_index] = "Sub2"
                        block_copied_dict[type_value] = True  # Mark as copied
                    pending_insertions.extend(sub_block)

                # If Block1 or Block3 is not found, check for Block2
                if not block_copied_dict[type_value]:
                    for block_row in csv_data:
                        if block_row[xmi_id_index] == type_value and block_row[description_index] == "Block2":
                            sub_block = [list(block_row)]
                            sub_block[0][description_index] = "Sub2"
                            pending_insertions.extend(sub_block)
                            block_copied_dict[type_value] = True  # Mark as copied Block2

                # Build relation_block
                relation_name1 = composite_name
                relation_block = [
                    # First row: SubmodelElementCollection with the relation name
                    ["SubmodelElementCollection", f"Relation_{csv_data[root1_index][name_index]}To{composite_name}", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
                    
                    # Second row: Property with the name attribute value, xmi:type as Property, name as "name", value as composite_name
                    ["Property", "name", "", "", "", "", "", "", "", "", "", composite_name, "", "", "", "", "", "", ""],
                    
                    # Third row: Property with aggregation attribute value, xmi:type as Property, name as "aggregation", value as "composite"
                    ["Property", "aggregation", "", "", "", "", "", "", "", "", "", "composite", "", "", "", "", "", "", ""]
                ]

                # Check if there is a Cardinality attribute
                if "Cardinality [1 1]" in row[description_index]:
                    relation_block.append(
                        ["Property", "Cardinality", "", "", "", "", "", "", "", "", "", "[1 1]", "", "", "", "", "", "", ""]
                    )

                # Handle Association block
                if association_value in association_blocks:
                    assoc_start, assoc_end = association_blocks[association_value]
                    association_block = [csv_data[k] for k in range(assoc_start, assoc_end + 1)]
                    
                    # Add Association related properties
                    relation_block.append(["Property", "type", association_value, "", "", "", "", "", "", "", "", "Association", "", "", "", "", "", "", ""])
                    
                    # Check EAnnotation and EStringToStringMapEntry inside Association block
                    for assoc_row in association_block:
                        if assoc_row[xmi_type_index] == "EAnnotation":
                            relation_block.append(
                                ["Property", "EAnnotation", "", "", "", "", "", "", "", "", "", "EStringToStringMapEntry", "", "", "", "", "", "", ""]
                            )
                        elif assoc_row[xmi_type_index] == "Property":
                            roottype_value = assoc_row[type_index]
                            relation_block.append(
                                ["RelationshipElement", f"Association_{csv_data[root1_index][name_index]}To{relation_name1}", "", "", "", "", "", "", "", "", "", roottype_value, "", "", "", "", "", "", type_value]
                            )        
                    # Mark Association block as delete
                    for assoc_row in association_block:
                        assoc_row[description_index] = "delete"

                # Add End-SubmodelElementCollection row
                relation_block.append(["End-SubmodelElementCollection"] + [""] * (len(header) - 1))
                
                pending_insertions.extend(relation_block)
                
                # Mark composite row as delete
                csv_data[j][description_index] = "delete"
        
        output_data.extend(pending_insertions)

# Write the result to a new CSV file
with open(output_csv_file, mode="w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(output_data)
