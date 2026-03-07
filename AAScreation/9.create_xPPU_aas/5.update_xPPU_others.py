#!/usr/bin/env python3.10.15
"""
This script updates the "Mechanical_break_down" and "Control_unit" submodels (and others) in an existing AASX file
using data from CSV files. It reads submodel elements from the CSVs, creates and organizes these elements into collections
and entities, then adds them to the existing submodels. Finally, it writes the updated AASX file with the new elements included.

It uses the 'basyx' library for handling AASX files and the 'ent' class to create specific submodel elements.
"""

import os
import csv
import re
from basyx.aas.adapter.aasx import AASXReader, AASXWriter, DictSupplementaryFileContainer
from basyx.aas.model import DictObjectStore, Submodel, Key, KeyTypes, ModelReference, AssetAdministrationShell, EntityType
from base.create_ent import ent
from base.eClass import MapEClass

ent_creator = ent()
eclass_mapper = MapEClass()

def _find_aas_by_name(object_store, name_candidate):
    """
    Try to find an AAS in object_store by id_short or id (normalized).
    Returns the AssetAdministrationShell or None.
    """
    if not name_candidate:
        return None

    def _norm(s):
        return sanitize_id_short(s or "").lower()

    target = _norm(name_candidate)
    for obj in object_store:
        if isinstance(obj, AssetAdministrationShell):
            cur_id_short = _norm(getattr(obj, "id_short", "") or "")
            cur_id       = _norm(getattr(obj, "id", "") or "")
            if cur_id_short == target or cur_id == target:
                return obj
    return None


def sanitize_id_short(id_short):
    """
    Sanitize the given id_short by replacing non-alphanumeric characters with underscores.
    Ensures that the first character is a letter by prefixing 'default' if necessary.
    """
    if not id_short:
        return "default"
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', id_short)
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')  
    if not sanitized or not sanitized[0].isalpha():
        sanitized = 'default' + sanitized
    return sanitized


def create_submodel_elements_from_csv(csv_file_path, object_store, file_store):
    """
    Reads a CSV file containing submodel element data and creates corresponding elements.
    
    This function supports creating various element types including:
      - SubmodelElementCollection (and its 'End-' marker)
      - File elements
      - Entity elements
      - Property elements
      - Capability elements
      - ReferenceElement for Entity statements
      
    It also manages nested collections/entities using stacks.
    
    :param csv_file_path: Path to the CSV file containing submodel element data.
    :param object_store: The DictObjectStore to use for resolving references.
    :param file_store: The file store for file elements.
    :return: A list of created submodel elements.
    """
    submodel_elements = []
    current_collection_stack = []  # To handle nested SubmodelElementCollections
    current_entity_stack = []      # To handle nested Entities
    
    with open(csv_file_path, mode='r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=',')
        if not reader.fieldnames:
            raise ValueError(f"No header row in {csv_file_path}")
        reader.fieldnames = [(h or '').lstrip('\ufeff').strip() for h in reader.fieldnames]

        # Validate expected columns exist in CSV file
        expected_columns = ['typeName', 'idShort', 'value', 'valueType', 'category', 'descriptionEN', 'descriptionDE', 'semanticId']
        for column in expected_columns:
            if column not in reader.fieldnames:
                raise KeyError(f"Expected column '{column}' not found in CSV file. Found columns: {reader.fieldnames}")
        
        # Process each row in the CSV file.
        for line_number, row in enumerate(reader, start=2):  # Start at line 2 (after header)
            try:
                element_type = row['typeName']
                raw_id_short= row['idShort']
                id_short = sanitize_id_short(raw_id_short) 
                category = row['category'] if row['category'] else None  # Use None if category is empty
                
                # Process 'End-' markers to close open collections or entities
                if element_type.startswith("End-"):
                    if element_type == "End-SubmodelElementCollection" and current_collection_stack:
                        current_collection_stack.pop()
                    elif element_type == "End-Entity" and current_entity_stack:
                        current_entity_stack.pop()
                    continue  # Skip further processing for end markers
                
                # Determine the semantic ID using the eClass mapper if not provided in CSV.
                if not row['semanticId']:
                    if id_short:
                        unit, semantic_id, description = eclass_mapper.get_IrdiPR_unit_descr(id_short)
                    else:
                        unit, semantic_id, description = None, "0000", "No semantic ID provided"
                else:
                    semantic_id = row['semanticId']
                
                # Process element based on its type.
                if element_type == "SubmodelElementCollection":
                    # Create a collection element.
                    collection = ent_creator.create_SMC(
                        id_short=id_short,
                        value=[],
                        category=category,
                        description=row['descriptionEN'],
                        semantic_id=semantic_id
                    )
                    # If inside a parent collection, add to its value set; otherwise, add to root.
                    if current_collection_stack:
                        current_collection_stack[-1].value.add(collection)
                    else:
                        submodel_elements.append(collection)
                    # Push this collection onto the stack.
                    current_collection_stack.append(collection)
                
                elif element_type == "File":
                    # Create a file element using the file store.
                    file_path = row['value']
                    file_element = ent_creator.create_File(
                        file_store=file_store,
                        file_path=file_path,
                        aasx_file_path=f"/aasx/files/{id_short}",
                        id_short=id_short,
                        mime_type='image/jpeg',
                        category=category,
                        description=row['descriptionEN']
                    )
                    if current_collection_stack:
                        current_collection_stack[-1].value.add(file_element)
                    else:
                        submodel_elements.append(file_element)
                
                elif element_type == "Entity":
                    # Prioritize using the value column of CSV as an explicit link
                    link_hint = (row.get('value') or '').strip()

                
                    candidate_names = [link_hint, raw_id_short, id_short]
                    target_aas = None
                    for cand in candidate_names:
                        target_aas = _find_aas_by_name(object_store, cand)
                        if target_aas is not None:
                            break

                    # If the asset is found and includes a globalAssetId, then set managementType to SELF_MANAGED
                    # If not found, set managementType to CO_MANAGED and ensure AASd-014 is avoided.             
                    if target_aas is not None:
                        entity_type = EntityType.SELF_MANAGED_ENTITY
                        global_asset_id = target_aas.id  
                    else:
                        entity_type = EntityType.CO_MANAGED_ENTITY
                        global_asset_id = None

                    entity = ent_creator.create_Ent(
                        id_short=id_short,
                        description=row['descriptionEN'],
                        category=category,
                        ent_type=entity_type,
                        statement=[],
                        semantic_id=semantic_id,
                        global_asset_id=global_asset_id
                    )

                    if current_collection_stack:
                        current_collection_stack[-1].value.add(entity)
                    else:
                        submodel_elements.append(entity)

                    # Push this entity onto the entity stack to allow adding ReferenceElements to its statement.
                    current_entity_stack.append(entity)
                
                elif element_type == "Property":
    
                    value_type_str = (row['valueType'] or '').strip().lower()
                    value_type_map = {
                        'string': str, 'str': str, 'text': str,
                        'int': int, 'integer': int, 'dint': int, 'udint': int, 'uint': int, 'word': int,
                        'float': float, 'double': float, 'real': float, 'lreal': float,
                        'bool': bool, 'boolean': bool,
                    }
                    value_type = value_type_map.get(value_type_str, str)


                    raw = row['value']
                    s = (raw if raw is not None else '').strip()
                    value_converted = None
                    if s != '':
                        try:
                            if value_type == int:
                                # support hex (0x...) and decimal
                                value_converted = int(s, 16) if re.match(r"^0x[0-9a-fA-F]+$", s) else int(s)
                            elif value_type == float:
                                # allow both comma and dot as decimal separator
                                value_converted = float(s.replace(',', '.'))
                            elif value_type == bool:
                                value_converted = s.lower() in ('true', '1', 'yes', 'y', 'ja')
                            else:
                                value_converted = s
                        except Exception:
                            # If conversion fails, keep as string
                            value_converted = None

                    prop = ent_creator.create_Prop(
                        id_short=id_short,
                        value=value_converted,     
                        value_type=value_type,      
                        category=category,
                        description=row['descriptionEN'],
                        semantic_id=semantic_id
                    )
                    if current_collection_stack:
                        current_collection_stack[-1].value.add(prop)
                    else:
                        submodel_elements.append(prop)


                elif element_type == "Capability":
                    # Create a capability element.
                    cap = ent_creator.create_Cap(
                        id_short=id_short,
                        category=category,
                        description=row['descriptionEN'],
                        semantic_id=semantic_id
                    )
                    if current_collection_stack:
                        current_collection_stack[-1].value.add(cap)
                    else:
                        submodel_elements.append(cap)
                
                elif element_type == "ReferenceElement" and current_entity_stack:
                    # Create a reference element and add it to the current entity's statement.
                    ref_value = row['value']
                    if ref_value:
                        ref_element = ent_creator.create_Ref(
                            id_short=id_short,
                            value=ModelReference(
                                key=(Key(type_=KeyTypes.ASSET_ADMINISTRATION_SHELL, value=ref_value),),
                                type_=AssetAdministrationShell
                            ),
                            category=category,
                            description=row['descriptionEN'],
                            semantic_id=semantic_id
                        )
                        current_entity_stack[-1].statement.add(ref_element)
            except Exception as e:
                print(f"Error processing file '{csv_file_path}', line {line_number}: {e}")
                print(f"Row data: {row}")
                raise  # Re-raise the exception after logging the error

    return submodel_elements

def update_aasx_with_multiple_submodels(aasx_path, csv_file_paths, submodel_names, output_aasx_path):
    """
    Updates an existing AASX file by adding submodel elements to specific submodels.
    
    For each CSV file and corresponding submodel name, the function:
      1. Reads the AASX file to get the current object store and file store.
      2. Finds the submodel with the specified name.
      3. Creates new elements from the CSV file and adds them to the submodel.
      4. Writes the updated AASX file to the output path.
    
    :param aasx_path: Path to the existing AASX file.
    :param csv_file_paths: List of CSV file paths containing submodel element data.
    :param submodel_names: List of submodel names corresponding to each CSV file.
    :param output_aasx_path: Path to write the updated AASX file.
    """
    # Load the existing AASX file.
    object_store = DictObjectStore()
    file_store = DictSupplementaryFileContainer()
    with AASXReader(aasx_path) as reader:
        reader.read_into(object_store, file_store)
    
    # Process each submodel specified.
    for submodel_name, csv_file_path in zip(submodel_names, csv_file_paths):
        # Find the submodel by its id_short.
        submodel = None
        for obj in object_store:
            if isinstance(obj, Submodel) and obj.id_short == submodel_name:
                submodel = obj
                break
        if submodel is None:
            raise ValueError(f"{submodel_name} submodel not found in the AASX file.")
        
        # Create new submodel elements from the CSV and add them to the submodel.
        new_elements = create_submodel_elements_from_csv(csv_file_path, object_store, file_store)
        for element in new_elements:
            submodel.submodel_element.add(element)
    
    # Gather the identifiers for all AssetAdministrationShell objects.
    aas_ids = [aas.id for aas in object_store if isinstance(aas, AssetAdministrationShell)]
    
    # Write the updated AASX file.
    with AASXWriter(output_aasx_path) as writer:
        writer.write_aas(
            aas_ids=aas_ids,
            object_store=object_store,
            file_store=file_store
        )

if __name__ == '__main__':
    # Define the current directory.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Define paths for the input AASX file and CSV files.
    base_aasx = os.path.join(current_dir, "output", "xPPU_4.aasx")
    mechanical_breakdown_csv = os.path.join(current_dir, "csv", "Mechanical_breakdown.csv")
    simulation_csv = os.path.join(current_dir, "csv", "Simulation.csv")
    capability_csv = os.path.join(current_dir, "csv", "Capability.csv")
    operational_data_csv = os.path.join(current_dir, "csv", "Operational_Data.csv")

    
    # Define the output AASX file path.
    output_aasx = os.path.join(current_dir, "output", "xPPU_5.aasx")
    
    # Update the AASX file with new submodel elements.
    update_aasx_with_multiple_submodels(
        aasx_path=base_aasx,
        csv_file_paths=[mechanical_breakdown_csv, simulation_csv, capability_csv, operational_data_csv],
        submodel_names=["Mechanical_breakdown", "Simulation", "Capability", "Operational_Data"],
        output_aasx_path=output_aasx
    )
