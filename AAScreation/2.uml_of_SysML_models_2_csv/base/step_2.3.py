#!/usr/bin/env python 3.10.15
"""
This script processes CSV data containing UML transition elements. It updates the 'value' and 'second_value' columns
based on the 'source' and 'target' values from the transition, determining if the transition is a 'RelationshipElement', 
'ReferenceElement', or 'Property'. The script modifies the 'xmi:type' column accordingly and saves the updated data 
to a new CSV file.
"""

import csv
import sys

input_csv_file = sys.argv[1]
output_csv_file = sys.argv[2]

csv_data = []
with open(input_csv_file, mode="r", newline='', encoding="utf-8") as file:
    reader = csv.reader(file)
    csv_data = [row for row in reader]

# Get the column indices based on the first row
header = csv_data[0]
xmi_type_index = header.index("xmi:type")
xmi_id_index = header.index("xmi:id")
source_index = header.index("source")
target_index = header.index("target")
value_index = header.index("value")
second_value_index = header.index("second_value")  # Adding second_value column
name_index = header.index("name")  # Get the index of the name column

# Iterate through CSV data, processing Transition rows
for index, row in enumerate(csv_data[1:], start=1):
    xmi_type = row[xmi_type_index]
    
    if xmi_type == "Transition":  # Handle rows of type Transition
        path3 = ""
        path4 = ""
        
        # Extract source and target values
        source_value = row[source_index]
        target_value = row[target_index]
        
        # Search for the corresponding path3 in the xmi:id column
        for i, check_row in enumerate(csv_data):
            if check_row[xmi_id_index] == source_value:
                path3 = check_row[name_index]
                break  # Stop once the first match is found

        # Search for the corresponding path4 in the xmi:id column
        for i, check_row in enumerate(csv_data):
            if check_row[xmi_id_index] == target_value:
                path4 = check_row[name_index]
                break  # Stop once the first match is found
        
        # according to source and target value to update value、second_value、xmi:type 和 name
        if source_value and target_value:
            row[value_index] = source_value  # Store source in value column
            row[second_value_index] = target_value  # Store target in second_value column
            row[xmi_type_index] = "RelationshipElement"  # Update xmi:type to RelationshipElement
            updated_name = f"{path3}To{path4}"  # Update name to Transition_path3Topath4
            row[name_index] = updated_name
        elif source_value:
            row[value_index] = source_value  # Store source in value column
            row[second_value_index] = ""  # Clear second_value column
            row[xmi_type_index] = "ReferenceElement"  # Update xmi:type to ReferenceElement
            updated_name = f"{path3}To"  # Update name to Transition_path3To
            row[name_index] = updated_name
        elif target_value:
            row[value_index] = target_value  # Store target in value column
            row[second_value_index] = ""  # Clear second_value column
            row[xmi_type_index] = "ReferenceElement"  # Update xmi:type to ReferenceElement
            updated_name = f"To{path4}"  # Update name to Transition_ToPath4
            row[name_index] = updated_name
        else:
            row[xmi_type_index] = "Property"  # Update xmi:type to Property
            row[value_index] = ""  # Clear value column
            row[second_value_index] = ""  # Clear second_value column
            updated_name = row[name_index]  # Keep name as is if empty or not set

        # Additional logic to update SubmodelElementCollection name if Transition is between SubmodelElementCollection and End-SubmodelElementCollection
        end_collection_index = None
        for j in range(index + 1, len(csv_data)):
            if csv_data[j][xmi_type_index] == "End-SubmodelElementCollection":
                end_collection_index = j
                break

        if end_collection_index is not None:
            submodel_collection_index = None
            for k in range(end_collection_index - 1, -1, -1):
                if csv_data[k][xmi_type_index] == "SubmodelElementCollection":
                    submodel_collection_index = k
                    break

            # Check if current Transition row is within the bounds of SubmodelElementCollection and End-SubmodelElementCollection
            if submodel_collection_index is not None and submodel_collection_index < index < end_collection_index:
                # Update SubmodelElementCollection's name to Transition_path3Topath4
                csv_data[submodel_collection_index][name_index] = f"Transition_{updated_name}"

with open(output_csv_file, mode="w", newline='', encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerows(csv_data)


