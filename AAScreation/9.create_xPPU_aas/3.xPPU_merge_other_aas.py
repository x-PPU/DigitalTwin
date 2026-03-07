#!/usr/bin/env python3.10.15
"""
This script merges an existing AASX file (base_filename) with multiple AASX files 
from a specified directory (directory_merge). The merged output is saved as a new AASX file (output_filename).

The process includes:
1. Reading the base AASX file to extract all Asset Administration Shells (AAS) and Submodels.
2. Iterating through each AASX file in the merge directory to extract additional AAS and Submodels.
3. Combining all extracted AAS, Submodels, and supplementary files (e.g., thumbnails, documents).
4. Writing the combined data into a new AASX file.
"""

import io
import os
from basyx.aas.adapter.aasx import AASXReader, AASXWriter, DictSupplementaryFileContainer
from basyx.aas.model import DictObjectStore, AssetAdministrationShell, Submodel

class AASMerger:
    """
    AASMerger handles merging a base AASX file with additional AASX files from a given directory.
    It extracts Asset Administration Shells (AAS) and Submodels from each file, 
    and merges supplementary files into one output AASX file.
    """
    def __init__(self, base_filename: str, directory_merge: str, output_filename: str):
        """
        Initializes the merger with the base file, merge directory, and output file path.

        :param base_filename: Path to the base AASX file.
        :param directory_merge: Directory containing additional AASX files to merge.
        :param output_filename: Path to save the merged AASX file.
        """
        self.base_filename = base_filename
        self.directory_merge = directory_merge
        self.output_filename = output_filename

    def read_aasx(self, aasx_filepath: str):
        """
        Reads an AASX file and extracts its core metadata, object store, and supplementary files.

        :param aasx_filepath: The path of the AASX file to read.
        :return: A tuple (meta_data, objects, files) from the AASX file.
        """
        objects = DictObjectStore()
        files = DictSupplementaryFileContainer()
        with AASXReader(aasx_filepath) as reader:
            meta_data = reader.get_core_properties()
            reader.read_into(objects, files)
        return meta_data, objects, files

    def write_aasx(self, aas_list: list, submodels: list, files: DictSupplementaryFileContainer):
        """
        Writes the merged Asset Administration Shells (AAS) and Submodels along with supplementary files 
        into an output AASX file.

        :param aas_list: List of AAS objects.
        :param submodels: List of Submodel objects.
        :param files: Container holding supplementary files.
        """
        with AASXWriter(self.output_filename) as writer:
            object_store = DictObjectStore()
            # Add all AAS objects to the object store.
            for aas in aas_list:
                object_store.add(aas)
            # Add all Submodel objects to the object store.
            for submodel in submodels:
                object_store.add(submodel)
            # Write the combined AAS and supplementary files.
            writer.write_aas([aas.id for aas in aas_list], object_store, files)

    def merge_aas(self):
        """
        Merges the base AASX file with all AASX files in the merge directory.
        
        This method:
          1. Reads the base AASX file to extract AAS objects, Submodels, and supplementary files.
          2. Iterates over each additional AASX file in the specified directory, extracting 
             additional AAS objects, Submodels, and merging supplementary files.
          3. Writes all collected data into the output AASX file.
        """
        # Read the base AASX file.
        _, base_objs, base_files = self.read_aasx(self.base_filename)

        new_aas_list = []
        submodels = []

        # Separate AssetAdministrationShell and Submodel objects from the base file.
        for obj in base_objs:
            if isinstance(obj, AssetAdministrationShell):
                new_aas_list.append(obj)
            elif isinstance(obj, Submodel):
                submodels.append(obj)

        # Iterate over all files in the merge directory.
        for filename in os.listdir(self.directory_merge):
            if filename.endswith(".aasx"):
                filepath = os.path.join(self.directory_merge, filename)
                _, objs, files = self.read_aasx(filepath)
                
                # Extract AAS and Submodels from the current file.
                for obj in objs:
                    if isinstance(obj, AssetAdministrationShell):
                        new_aas_list.append(obj)
                    elif isinstance(obj, Submodel):
                        submodels.append(obj)
                
                # Merge supplementary files:
                # For each file in the current file's supplementary container,
                # add it to the base container if not already present.
                for file_path in files:
                    if file_path not in base_files:
                        file_data = files._store[files.get_sha256(file_path)]
                        base_files.add_file(file_path, io.BytesIO(file_data), files.get_content_type(file_path))

        # Write the merged data to the output AASX file.
        self.write_aasx(new_aas_list, submodels, base_files)

if __name__ == '__main__':
    # Determine the current directory.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    
    # Set paths for the base AASX file, directory containing additional AASX files, and output file.
    base_aasx = os.path.join(current_dir, "output", "xPPU_2.aasx")

    dir_merge = os.path.join(
        os.path.dirname(current_dir),  
        "1.create_aas_from_product_info",
        "5.update_aas",
        "manual check"
    )    
    output_aasx = os.path.join(current_dir, "output", "xPPU_3.aasx")
    
    # Create an instance of AASMerger and perform the merge.
    aas_merger = AASMerger(base_aasx, dir_merge, output_aasx)
    aas_merger.merge_aas()
    
