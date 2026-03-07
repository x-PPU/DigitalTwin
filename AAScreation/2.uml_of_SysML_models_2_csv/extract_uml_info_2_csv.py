#!/usr/bin/env python3
"""
This script parses a UML file, processes elements such as OpaqueBehavior, Transition, PrimitiveType, 
and LiteralInteger/LiteralUnlimitedNatural, and generates a CSV output with a hierarchical structure.
"""

import os
import pandas as pd
import xml.etree.ElementTree as ET


class UMLParser:
    """
    UMLParser encapsulates the process of parsing a UML file and converting its hierarchical structure 
    into a CSV file.
    """

    def __init__(self, uml_file_path: str, csv_output_file: str):
        """
        Initialize the UMLParser with the input UML file path and the desired CSV output file path.
        
        Args:
            uml_file_path (str): The path to the UML file.
            csv_output_file (str): The path where the CSV output will be saved.
        """
        self.uml_file_path = uml_file_path
        self.csv_output_file = csv_output_file

        # Define XML namespaces for XMI and UML elements to properly parse the file.
        self.namespace = {
            'xmi': 'http://www.omg.org/spec/XMI/20131001',
            'uml': 'http://www.eclipse.org/uml2/5.0.0/UML'
        }
        # CSV header with a fixed number of columns.
        self.csv_header = [
            "xmi:type", "name", "xmi:id", "type", "href", "source", "target", 
            "aggregation", "association", "memberEnd", "key", "value", 
            "visibility", "classifier_behavior", "isActive", "kind", 
            "valueType", "description", "second_value"
        ]
        # List to accumulate rows for CSV output.
        self.csv_data = []
        # List to track indices of rows to be removed during post-processing.
        self.rows_to_delete = []

    @staticmethod
    def ensure_row_length(row: list, target_length: int) -> None:
        """
        Ensures that the provided row has at least target_length columns by appending empty strings.
        
        Args:
            row (list): The row to be checked.
            target_length (int): The desired number of columns.
        """
        while len(row) < target_length:
            row.append("")

    def add_element_to_csv(self, element: ET.Element, level: int) -> str:
        """
        Processes a single XML element, extracts its attributes, and adds one or more corresponding rows
        into the CSV data. Special cases such as OpaqueBehavior and Transition are handled with custom logic.
        
        Args:
            element (ET.Element): The XML element to process.
            level (int): The depth level of the element in the XML hierarchy (not used explicitly for CSV data, 
                         but can be used for debugging or indentation purposes).
        
        Returns:
            str: The simplified type name for further processing (or None for special cases that have been handled).
        """
        # Retrieve standard attributes from the XML element.
        element_name = element.get("name", "")
        element_id = element.get("{http://www.omg.org/spec/XMI/20131001}id", "")
        element_type = element.get("type", "")
        href = element.get("href", "")
        source = element.get("source", "")
        target = element.get("target", "")
        aggregation = element.get("aggregation", "")
        association = element.get("association", "")
        member_end = element.get("memberEnd", "")
        key = element.get("key", "")
        value = element.get("value", "")
        visibility = element.get("visibility", "")
        classifier_behavior = element.get("classifierBehavior", "")
        is_active = element.get("isActive", "")
        kind = element.get("kind", "")

        # Get the full xmi:type. This may be namespaced (e.g., "uml:OpaqueBehavior").
        xmi_type_full = element.get("{http://www.omg.org/spec/XMI/20131001}type", element.get("xmi:type", ""))
        if xmi_type_full and ":" in xmi_type_full:
            # Use the part after the colon as the simplified type name.
            type_name = xmi_type_full.split(":")[-1]
        else:
            type_name = xmi_type_full

        # Special handling: if the element is a Pseudostate or FinalState and its name is missing,
        # set a default name.
        if type_name == "Pseudostate" and not element_name:
            element_name = "Pseudostate"
        elif type_name == "FinalState" and not element_name:
            element_name = "FinalState"

        # Special handling for OpaqueBehavior elements:
        # If the type is OpaqueBehavior and the element has a name, then treat its content as
        # a semicolon-delimited list of property assignments.
        if type_name == "OpaqueBehavior" and element_name:
            # Start a SubmodelElementCollection block with a fixed name.
            submodel_collection_row = [
                "SubmodelElementCollection", "doActivities", "", "", "", "", "", "", "", "", "", "", "", "", "", ""
            ]
            self.ensure_row_length(submodel_collection_row, len(self.csv_header))
            self.csv_data.append(submodel_collection_row)

            # Split the element's name on semicolons to extract individual assignments.
            items = element_name.split(";")
            for item in items:
                item = item.strip()
                if item:
                    # Check for assignment operators (":=" or "=") to split property name and value.
                    if ":=" in item:
                        prop_name, prop_value = item.split(":=", 1)
                    elif "=" in item:
                        prop_name, prop_value = item.split("=", 1)
                    else:
                        prop_name, prop_value = item, ""
                    csv_row = [
                        "Property", prop_name.strip(), element_id, "", "", "", "", "", "", "", "", prop_value.strip(), "", "", "", ""
                    ]
                    self.ensure_row_length(csv_row, len(self.csv_header))
                    self.csv_data.append(csv_row)

            # End the SubmodelElementCollection block.
            end_collection_row = ["End-SubmodelElementCollection"] + [""] * (len(self.csv_header) - 1)
            self.ensure_row_length(end_collection_row, len(self.csv_header))
            self.csv_data.append(end_collection_row)

            # Add an extra row to specify that the xmi:type for this element is "OpaqueBehavior".
            xmi_type_property_row = [
                "Property", "xmi:type", element_id, "", "", "", "", "", "", "", "", "OpaqueBehavior", "", "", "", ""
            ]
            self.ensure_row_length(xmi_type_property_row, len(self.csv_header))
            self.csv_data.append(xmi_type_property_row)
            return None

        # Special handling for Transition elements:
        # If the element is a Transition and does not have source or target attributes, it is skipped.
        if type_name == "Transition":
            if not source and not target:
                return None

            # Begin a SubmodelElementCollection block for the Transition.
            submodel_collection_row = [
                "SubmodelElementCollection", "", element_id, "", "", "", "", "", "", "", "", "", "", "", "", ""
            ]
            self.ensure_row_length(submodel_collection_row, len(self.csv_header))
            self.csv_data.append(submodel_collection_row)

            # Create a row for the Transition element with its attributes.
            transition_row = [
                type_name, element_name, element_id, element_type, href, source, target,
                aggregation, association, member_end, key, value, visibility, classifier_behavior,
                is_active, kind
            ]
            self.ensure_row_length(transition_row, len(self.csv_header))
            self.csv_data.append(transition_row)

            # If the Transition has a name, add a Property row using that name.
            if element_name:
                property_row = ["Property", element_name] + [""] * (len(self.csv_header) - 2)
                self.ensure_row_length(property_row, len(self.csv_header))
                self.csv_data.append(property_row)

            # Close the SubmodelElementCollection block.
            end_collection_row = ["End-SubmodelElementCollection"] + [""] * (len(self.csv_header) - 1)
            self.ensure_row_length(end_collection_row, len(self.csv_header))
            self.csv_data.append(end_collection_row)
            return None

        # Default handling for all other element types:
        # Construct a CSV row with the simplified type name and other attributes.
        csv_row = [
            type_name, element_name, element_id, element_type, href, source, target,
            aggregation, association, member_end, key, value, visibility, classifier_behavior,
            is_active, kind
        ]
        self.ensure_row_length(csv_row, len(self.csv_header))
        self.csv_data.append(csv_row)
        return type_name

    def process_element(self, element: ET.Element, level: int = 0) -> None:
        """
        Recursively processes an XML element and its child elements.
        
        Args:
            element (ET.Element): The current XML element.
            level (int): The depth level of the current element (used for potential debugging).
        """
        # Process the current element and obtain its simplified type name.
        current_type_name = self.add_element_to_csv(element, level)
        # Find all child elements (using the defined XML namespaces).
        sub_elements = element.findall("./*", namespaces=self.namespace)
        # Recursively process each child element.
        for child in sub_elements:
            self.process_element(child, level + 1)
        # If there are sub-elements and the current element has a type name,
        # add an "End-" row to denote the end of the current element's block.
        if sub_elements and current_type_name:
            end_row = [f"End-{current_type_name}"] + [""] * (len(self.csv_header) - 1)
            self.ensure_row_length(end_row, len(self.csv_header))
            self.csv_data.append(end_row)

    def process_uml(self) -> None:
        """
        Parses the UML file and processes all UML Model elements found within the XML structure.
        """
        # Parse the UML XML file.
        tree = ET.parse(self.uml_file_path)
        root = tree.getroot()
        # Look for all elements matching the UML Model tag using the namespace.
        for model_element in root.findall(".//uml:Model", namespaces=self.namespace):
            self.process_element(model_element)

    def post_process(self) -> None:
        """
        Converts the accumulated CSV data into a DataFrame and performs additional post-processing.
        This includes handling PrimitiveType and LiteralInteger/LiteralUnlimitedNatural elements to update 
        the properties and remove unnecessary rows.
        """
        df = pd.DataFrame(self.csv_data, columns=self.csv_header)

        # Iterate over each row to handle "End-Property" rows.
        for index, row in df.iterrows():
            xmi_type = row['xmi:type']
            if xmi_type == "End-Property":
                end_property_index = index
                has_primitive = False
                has_literal = False
                literal_integer_value = None
                literal_unlimited_value = None

                # Search upward from the End-Property row to find the nearest Property row.
                for i in range(end_property_index - 1, -1, -1):
                    if df.iloc[i]['xmi:type'] == "Property":
                        # Between the Property and End-Property rows, look for PrimitiveType or Literal elements.
                        for j in range(i + 1, end_property_index):
                            inner_row = df.iloc[j]
                            # Check for PrimitiveType: if found, extract the value type from the 'href' attribute.
                            if (inner_row['xmi:type'] == "PrimitiveType" and inner_row['href'] 
                                    and "#" in inner_row['href']):
                                href = inner_row['href']
                                df.at[i, 'valueType'] = href.split("#")[-1]
                                has_primitive = True

                            # Check for LiteralInteger: record its value.
                            if inner_row['xmi:type'] == "LiteralInteger":
                                literal_integer_value = inner_row['value']
                                has_literal = True
                                self.rows_to_delete.append(j)

                            # Check for LiteralUnlimitedNatural: record its value.
                            if inner_row['xmi:type'] == "LiteralUnlimitedNatural":
                                literal_unlimited_value = inner_row['value']
                                has_literal = True
                                self.rows_to_delete.append(j)

                        # If any literal values were found, update the description in the Property row.
                        if has_literal:
                            cardinality_description = f"Cardinality [{literal_integer_value or ''} {literal_unlimited_value or ''}]"
                            df.at[i, 'description'] = cardinality_description

                        # If a PrimitiveType was found, mark all rows between the Property and End-Property for deletion.
                        if has_primitive:
                            self.rows_to_delete.extend(range(i + 1, end_property_index))
                            self.rows_to_delete.append(end_property_index)
                        # If literal values were found, also mark the End-Property row for deletion.
                        if has_literal:
                            self.rows_to_delete.append(end_property_index)
                        break

        # Remove the rows that have been marked for deletion.
        rows_to_delete = [idx for idx in self.rows_to_delete if idx in df.index]
        df.drop(rows_to_delete, inplace=True)
        # Store the final DataFrame for later export.
        self.df = df

    def save_csv(self) -> None:
        """
        Saves the processed DataFrame as a CSV file to the specified output path.
        Ensures that the output directory exists.
        """
        os.makedirs(os.path.dirname(self.csv_output_file), exist_ok=True)
        self.df.to_csv(self.csv_output_file, index=False, encoding="utf-8")
        print(f"CSV saved to {self.csv_output_file}")

    def run(self) -> None:
        """
        Runs the full UML parsing process, including reading the UML file, processing elements, 
        post-processing the CSV data, and saving the CSV file.
        """
        self.process_uml()     # Parse and process the UML elements.
        self.post_process()    # Apply additional processing to the CSV data.
        self.save_csv()        # Write the final CSV to disk.


def parse_uml_to_csv(uml_file_path: str, csv_output_file: str):
    parser = UMLParser(uml_file_path, csv_output_file)
    parser.run()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python uml_to_csv.py <uml_file_path> <csv_output_file>")
        raise SystemExit(1)
    parse_uml_to_csv(sys.argv[1], sys.argv[2])
