import csv
import os
from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.model.provider import DictObjectStore


def load_aas_from_aasx(aasx_file_path):
    """
    Loads an AAS (Asset Administration Shell) from an AASX file.
    
    This function initializes the necessary object and file stores, reads the AASX file, 
    and returns the first found AAS along with the object store.
    
    :param aasx_file_path: Path to the AASX file.
    :return: Tuple of (aas, object_store) where 'aas' is the Asset Administration Shell object.
    :raises ValueError: If no valid AAS object is found in the AASX file.
    """
    # Initialize the object store to hold AAS objects and the file store for supplementary files
    object_store = DictObjectStore()
    file_store = aasx.DictSupplementaryFileContainer()
    
    # Open and read the AASX file into the object and file stores
    with aasx.AASXReader(aasx_file_path) as reader:
        reader.read_into(object_store, file_store)

    # Retrieve the first AAS object from the store
    aas = next((obj for obj in object_store if isinstance(obj, model.AssetAdministrationShell)), None)
    if aas is None:
        raise ValueError("No valid AAS object found in the AASX file.")
    
    return aas, object_store


def extract_submodel_to_csv(aas, object_store, submodel_id, csv_file_path):
    """
    Extracts a submodel from the AAS and writes its details into a CSV file.
    
    The CSV file will have the following headers:
    "typeName", "idShort", "value", "valueType", "category", "descriptionEN", "descriptionDE", "semanticId"
    
    :param aas: The Asset Administration Shell object.
    :param object_store: The store containing all AAS objects.
    :param submodel_id: The idShort of the submodel to extract.
    :param csv_file_path: The file path to save the CSV output.
    """
    # Define CSV header columns
    headers = [
        "typeName", "idShort", "value", "valueType", 
        "category", "descriptionEN", "descriptionDE", "semanticId"
    ]
    
    # Open the CSV file for writing
    with open(csv_file_path, mode="w", newline='', encoding='utf-8') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(headers)  # Write header row

        # Locate the target submodel by matching the id_short attribute
        submodel = next(
            (sm for sm in object_store if isinstance(sm, model.Submodel) and sm.id_short == submodel_id), 
            None
        )
        if submodel is None:
            print(f"Submodel with ID {submodel_id} not found.")
            return

        def process_element(element):
            """
            Recursively process each submodel element and its children.
            
            Writes the element details to the CSV writer.
            """
            # For SubmodelElementCollection, leave value empty; otherwise, get the element's value
            value = "" if isinstance(element, model.SubmodelElementCollection) else getattr(element, "value", "")
            
            # Retrieve the value type if it exists, using the type's name
            value_type = getattr(element, "value_type", None)
            value_type_name = value_type.__name__ if value_type else ""

            # Prepare the CSV row with element properties
            row = [
                element.__class__.__name__,      # Type of the element
                element.id_short,                # Short identifier
                value,                           # Element value
                value_type_name,                 # Value type name
                element.category,                # Category of the element
                element.description.get("en", "") if element.description else "",  # English description
                element.description.get("de", "") if element.description else "",  # German description
                element.semantic_id.key[0].value if element.semantic_id else ""      # Semantic ID value
            ]
            writer.writerow(row)

            # If the element is a collection, recursively process its child elements
            if isinstance(element, model.SubmodelElementCollection):
                for child in element.value:
                    process_element(child)
                # Write an end marker for the collection
                writer.writerow(["End-" + element.__class__.__name__, "", "", "", "", "", "", ""])

        # Process each top-level element in the submodel
        for element in submodel.submodel_element:
            process_element(element)


def main():
    """
    Main function to load an AASX file, extract a specific submodel, and save it to a CSV file.
    """
    # Define the base directory relative to this script's location
    base_dir = os.path.dirname(__file__)
    
    # Construct file paths for the AASX file and the output CSV file
    aasx_path = os.path.join(base_dir, "model", "IDTA 02005-1-0_Template_ProvisionOfSimulationModels.aasx")
    csv_output_path = os.path.join(base_dir, "1.template", "Template_ProvisionOfSimulationModels.csv")
    
    # Load the AAS and the corresponding object store from the AASX file
    aas, object_store = load_aas_from_aasx(aasx_path)
    
    # Specify the submodel ID to extract
    submodel_id = "SimulationModels"
    
    # Extract the submodel and write it to the CSV file
    extract_submodel_to_csv(aas, object_store, submodel_id, csv_output_path)


if __name__ == "__main__":
    main()
