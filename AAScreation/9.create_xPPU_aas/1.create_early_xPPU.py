#!/usr/bin/env python3.10.15
"""
This script creates an Asset Administration Shell (AAS) with multiple submodels based on predefined data.
It uses the 'basyx' library to generate an AASX file, including asset information and several submodels.
Submodel IRIs are retrieved from eClass mappings, and the resulting AASX file is saved to the specified location.
"""

from pathlib import Path
from typing import Tuple, List
from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.adapter.aasx import AASXWriter
from base.create_ent import ent
from base.eClass import MapEClass



# Initialize the entity and eClass mapping instances.
ent_instance = ent()
eclass_instance = MapEClass()

def create_property(id_short: str, value: str, iri: str) -> model.SubmodelElement:
    """
    Creates a property submodel element with a specified IRI.

    :param id_short: The short identifier for the property.
    :param value: The value of the property.
    :param iri: The Internationalized Resource Identifier (IRI) for the property.
    :return: A submodel element representing the property.
    """
    return ent_instance.create_Prop(id_short, model.datatypes.String, value, 'PARAMETER', iri)

def get_iri_from_eclass(property_name: str) -> str:
    """
    Retrieves the IRI for a given property name from the eClass mappings.

    :param property_name: The name of the property.
    :return: The corresponding IRI.
    """
    unit, iri, descr = eclass_instance.get_IrdiPR_unit_descr(property_name)
    return iri



def create_submodels(obj_store: model.DictObjectStore) -> Tuple[model.DictObjectStore, List[model.Submodel]]:

    """
    Creates a list of submodels based on a predefined list of submodel idShorts.
    Each submodel is assigned an IRI obtained from the eClass mapping.

    :param obj_store: The object store to which submodels will be added.
    :return: A tuple of the updated object store and a list of submodel objects.
    """
    submodel_id_shorts = [
        "Mechanical_breakdown", "Behavior",
        "Simulation", "Capability", "ECAD", 
        "Operational_Data", "Process", "Skill", "PLC"
    ]
    
    submodels = []
    
    for id_short in submodel_id_shorts:
        # Retrieve the semantic ID (IRI) for the submodel.
        semantic_id = get_iri_from_eclass(id_short)
        
        # Create a submodel with a random IRI and add it to the object store.
        obj_store, sm = ent_instance.create_SM_rand_iri(
            obj_store,
            id_short,
            id_short,
            [],
            semantic_id,
            "I"  
        )
        submodels.append(sm)
    
    return obj_store, submodels

def create_aasx_with_submodels(output_filename_aasx: Path) -> None:
    """
    Creates an AASX file containing asset information and multiple submodels.
    The process includes:
      - Creating an object store and file store.
      - Creating asset information.
      - Creating the AAS.
      - Adding submodels to the AAS.
      - Writing the resulting AAS and related objects to an AASX file.

    :param output_filename_aasx: The file path where the AASX file will be saved.
    """
    # Initialize the object store and supplementary file container.
    obj_store = model.DictObjectStore()
    file_store = aasx.DictSupplementaryFileContainer()

    # Create asset information.
    asset_name = 'xPPU'
    obj_store, asset_information = ent_instance.create_asset_information_rand_iri(obj_store, asset_name, 'I')

    # Create the AAS (Asset Administration Shell) using asset information.
    id_short = 'xPPU'
    aas_name = 'xPPU_AAS'
    obj_store, id_aas, aas = ent_instance.create_aas_rand_iri(obj_store, id_short, aas_name, asset_information, None)

    # Create submodels and add them to the object store.
    obj_store, submodels = create_submodels(obj_store)
    for sm in submodels:
        # Add a reference of each submodel to the AAS.
        aas.submodel.add(model.ModelReference.from_referable(sm))

    # Create a complete object store with the AAS, asset information, and submodels.
    object_store = ent_instance.create_obj_store(aas, asset_information, submodels)

    # Write the AASX file using the AASXWriter.
    with AASXWriter(output_filename_aasx) as writer:
        writer.write_aas(
            aas_ids=[id_aas],
            object_store=object_store,
            file_store=file_store
        )

if __name__ == '__main__':
    # Determine the current directory and create an output directory if it doesn't exist.
    current_directory = Path(__file__).parent
    output_directory = current_directory / 'output'
    output_directory.mkdir(exist_ok=True)
    
    # Define the output filename for the AASX file.
    output_filename_aasx = output_directory / 'xPPU_1.aasx'
    
    # Create the AASX file with submodels.
    create_aasx_with_submodels(output_filename_aasx)
    print(f"AASX file has been created at: {output_filename_aasx}")
