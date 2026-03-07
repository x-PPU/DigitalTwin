#!/usr/bin/env python3.10.8
"""
This script parses a UML file in XMI format and extracts the following fields:
    - xmi:id
    - name
    - xmi:type
    - description

Only the elements with a non-empty xmi:id that is present in the semanticId column 
(from Behavior1.csv and Behavior2.csv) are retained.

If an element's name is null, the name is filled in with the concatenation of 
xmi:type and xmi:id, and the original (empty) name is stored in the description column.

If the element's type is "OpaqueBehavior", the script searches for the nearest "State" element 
(previously processed) and constructs the name as "OpaqueBehaviorOf" followed by that state's name.

All special characters are removed from the name column when writing to the CSV.
Additionally, the script prints:
  - The first encountered Reference value from each Behavior CSV.
  - The first encountered non-empty xmi:id from the UML file.
"""

import os
import xml.etree.ElementTree as ET
import csv
import re

# Get the current directory, UML file path, and output CSV file path.
current_dir = os.path.dirname(os.path.abspath(__file__))



def load_semantic_ids(behavior1_csv_path, behavior2_csv_path):
    """
    Load semantic IDs from reference CSV files (Behavior1.csv and Behavior2.csv).
    The function reads the "Reference" column from each file (assumed to be in the "output" folder),
    strips whitespace, and ensures that the value starts with an underscore.
    It prints the first encountered Reference value from each file.
    
    Returns:
        set: A set of loaded semantic IDs.
    """
    semantic_ids = set()
    for file_path in [behavior1_csv_path, behavior2_csv_path]:
        file_name = os.path.basename(file_path)
        if os.path.exists(file_path):
            first_ref_printed = False
            with open(file_path, mode="r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                # Optional robustness: tolerate lowercase "reference"
                ref_key = "Reference"
                if reader.fieldnames:
                    lowers = {c.lower(): c for c in reader.fieldnames}
                    if "reference" in lowers:
                        ref_key = lowers["reference"]

                for row in reader:
                    if row.get(ref_key):
                        ref_id = row[ref_key].strip()
                        # Ensure the reference value starts with an underscore.
                        if not ref_id.startswith("_"):
                            ref_id = "_" + ref_id
                        if not first_ref_printed:
                            print(f"First Reference from {file_name}: {ref_id}")
                            first_ref_printed = True
                        semantic_ids.add(ref_id)
    print(f"Loaded {len(semantic_ids)} semantic IDs.")
    return semantic_ids

# Define XML namespaces for XMI and UML.
namespace = {
    'xmi': 'http://www.omg.org/spec/XMI/20131001',
    'uml': 'http://www.eclipse.org/uml2/5.0.0/UML'
}

def remove_special_characters(text):
    """
    Remove any character from text that is not a letter, digit, or underscore.
    
    Args:
        text (str): The input text.
    
    Returns:
        str: The cleaned text.
    """
    return re.sub(r'[^A-Za-z0-9]', '', text)

def add_element_to_csv(element, csv_data, semantic_ids, printed_xmi_types, csv_output_file):
    """
    Process a UML element and add a row to csv_data if its xmi:id is non-empty and present 
    in the semantic_ids set. If the element type is "OpaqueBehavior", find the nearest State element
    (from the already processed rows) and build the name accordingly.
    
    Args:
        element (ET.Element): The UML element.
        csv_data (list): The list accumulating CSV rows.
    """
    # Get the original name (to be used as the description) and the element id.
    original_name = element.get("name", "")
    element_id = element.get("{http://www.omg.org/spec/XMI/20131001}id", "")
    
    # Get the xmi:type (or fallback to the "xmi:type" attribute without namespace).
    xmi_type_full = element.get("{http://www.omg.org/spec/XMI/20131001}type", element.get("xmi:type", ""))
    
    # Print the first encountered non-empty xmi:id from the UML file.
    if not printed_xmi_types and element_id:
        print(f"First xmi:id from UML: {element_id}")
    
    # Only process elements that have a non-empty xmi:id present in the semantic_ids set.
    if not element_id or element_id not in semantic_ids:
        return
    
    # Determine the simple type name.
    if xmi_type_full and ":" in xmi_type_full:
        type_name = xmi_type_full.split(":")[-1]
    else:
        type_name = xmi_type_full

    # Special handling for OpaqueBehavior type.
    if type_name == "OpaqueBehavior":
        element_name = original_name
        # Look for the nearest "State" element among already processed rows.
        for previous_row in reversed(csv_data):
            if previous_row[0] == "State":
                previous_name = previous_row[1]
                element_name = f"OpaqueBehaviorOf{previous_name}"
                break
    else:
        # If name is empty, use type_name concatenated with element_id.
        element_name = original_name if original_name else f"{type_name}{element_id}"
    
    # Remove all special characters from the element name.
    element_name = remove_special_characters(element_name)
    
    # Check if the name length exceeds 128 characters.
    if len(element_name) > 128:
        print(f"file: {csv_output_file}, line: {len(csv_data) + 2}, name length: {len(element_name)}")
    
    # Create the CSV row: type, processed name, xmi:id, and original name as description.
    csv_row = [type_name, element_name, element_id, original_name]
    csv_data.append(csv_row)
    
    # Print header info once for each new type.
    if type_name not in printed_xmi_types:
        printed_xmi_types.add(type_name)
        print(f"{type_name} : xmi:type, name, xmi:id, description")

def process_uml_element(element, csv_data, semantic_ids, printed_xmi_types, csv_output_file):
    """
    Recursively process a UML element and its children.
    """
    add_element_to_csv(element, csv_data, semantic_ids, printed_xmi_types, csv_output_file)
    for child in element.findall("./*", namespaces=namespace):
        process_uml_element(child, csv_data, semantic_ids, printed_xmi_types, csv_output_file)

def generate_csv_data(root, semantic_ids, printed_xmi_types, csv_output_file):
    """
    Process the UML file by traversing all elements under <uml:Model> and generate CSV data.
    
    Returns:
        list: A list of CSV rows.
    """
    csv_data = []
    for model_element in root.findall(".//uml:Model", namespaces=namespace):
        process_uml_element(model_element, csv_data, semantic_ids, printed_xmi_types, csv_output_file)
    return csv_data

def write_csv(csv_data, csv_output_file):
    """
    Write the CSV data to the output CSV file.
    """
    os.makedirs(os.path.dirname(csv_output_file), exist_ok=True)
    with open(csv_output_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["xmi:type", "name", "xmi:id", "description"])
        writer.writerows(csv_data)
    print(f"Successfully generated: {csv_output_file}, total rows: {len(csv_data)}")

# ------- single-scenario runner -------
def run_once(uml_file_path, csv_output_file, behavior1_csv_path, behavior2_csv_path):
    """
    Run the original pipeline once for a given scenario (UML + Behavior1/2 -> ConceptDescription).
    """
    if not os.path.exists(uml_file_path):
        raise FileNotFoundError(f"UML file not found: {uml_file_path}")
    # 1) Load semantic ids per scenario
    semantic_ids = load_semantic_ids(behavior1_csv_path, behavior2_csv_path)

    # 2) Parse UML
    tree = ET.parse(uml_file_path)
    root = tree.getroot()

    # 3) Per-scenario printed types tracker (reset each run)
    printed_xmi_types = set()

    # 4) Generate data and write
    csv_data = generate_csv_data(root, semantic_ids, printed_xmi_types, csv_output_file)
    write_csv(csv_data, csv_output_file)

def main():
    # define three scenarios and run them one by one 
    scenarios = [
        {
            "uml": os.path.join(current_dir, "Papyrus - Scenario_13", "model_Sc13.uml"),
            "out": os.path.join(current_dir, "output", "ConceptDescription_Sc13.csv"),
            "b1":  os.path.join(current_dir, "output", "Behavior1_Sc13.csv"),
            "b2":  os.path.join(current_dir, "output", "Behavior2_Sc13.csv"),
        },
        {
            "uml": os.path.join(current_dir, "Papyrus - Scenario_14", "model_Sc14.uml"),
            "out": os.path.join(current_dir, "output", "ConceptDescription_Sc14.csv"),
            "b1":  os.path.join(current_dir, "output", "Behavior1_Sc14.csv"),
            "b2":  os.path.join(current_dir, "output", "Behavior2_Sc14.csv"),
        },
        {
            "uml": os.path.join(current_dir, "Papyrus - Scenario_15", "model_Sc15.uml"),
            "out": os.path.join(current_dir, "output", "ConceptDescription_Sc15.csv"),
            "b1":  os.path.join(current_dir, "output", "Behavior1_Sc15.csv"),
            "b2":  os.path.join(current_dir, "output", "Behavior2_Sc15.csv"),
        },
    ]

    for sc in scenarios:
        print("\n=== Running ConceptDescription for:", sc["uml"], "===")
        run_once(sc["uml"], sc["out"], sc["b1"], sc["b2"])

if __name__ == "__main__":
    main()
