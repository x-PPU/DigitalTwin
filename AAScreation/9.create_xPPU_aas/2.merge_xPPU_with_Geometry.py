#!/usr/bin/env python3.10.15
"""
This script merges two AASX (Asset Administration Shell Package) files into a single AASX file.
Specifically, it merges the substructures under the submodel named `Geometry` in `Stp.aasx` (located in the `output` folder)
into the submodel named `Geometry` in `xPPU_1.aasx`, and saves the result as a new file `xPPU_2.aasx`.
"""

import io
import os
from pathlib import Path
from basyx.aas.adapter.aasx import AASXReader, AASXWriter, DictSupplementaryFileContainer
from basyx.aas.model import DictObjectStore, AssetAdministrationShell, Submodel
from basyx.aas.model.base import ModelReference

class AASMerger:
    """
    AASMerger is responsible for merging two AASX files into one.
    It reads the contents of the input AASX files, merges submodels and supplementary files,
    and writes the resulting merged AASX file.
    """
    def __init__(self, filename_aasx1: str, filename_aasx2: str, filename_merge: str):
        """
        Initializes the merger with the paths of the two input AASX files and the output filename.
        
        :param filename_aasx1: Path to the first AASX file.
        :param filename_aasx2: Path to the second AASX file.
        :param filename_merge: Path where the merged AASX file will be saved.
        """
        self.filename_aasx1 = filename_aasx1
        self.filename_aasx2 = filename_aasx2
        self.filename_merge = filename_merge

    def read_aasx(self, aasx_filepath: str):
        """
        Reads an AASX file and returns its core metadata, object store, and supplementary files.
        
        :param aasx_filepath: The path of the AASX file to be read.
        :return: A tuple (meta_data, objects, files) from the AASX file.
        """
        objects = DictObjectStore()
        files = DictSupplementaryFileContainer()
        with AASXReader(aasx_filepath) as reader:
            meta_data = reader.get_core_properties()
            reader.read_into(objects, files)
        return meta_data, objects, files

    def write_aasx(self, aas: AssetAdministrationShell, submodels: list, files: DictSupplementaryFileContainer):
        """
        Writes an AAS along with its submodels and supplementary files into an AASX file.
        
        :param aas: The Asset Administration Shell object.
        :param submodels: A list of submodel objects.
        :param files: A container of supplementary files.
        """
        with AASXWriter(self.filename_merge) as writer:
            # Create a new object store and add the AAS and its submodels
            object_store = DictObjectStore()
            object_store.add(aas)
            for submodel in submodels:
                object_store.add(submodel)
            writer.write_aas([aas.id], object_store, files)

    def merge_aas(self):
        """
        Merges the two AASX files.
        
        The process includes:
        1. Reading the first and second AASX files.
        2. Using the AAS from the first file as the base.
        3. Adding submodels from the second file (if they are not already present).
        4. Merging the supplementary file containers from both files.
        5. Writing the merged AAS and its submodels into a new AASX file.
        """
        # Read the first AASX file
        meta_data1, objs1, files1 = self.read_aasx(self.filename_aasx1)

        # Read the second AASX file if it exists
        if os.path.exists(self.filename_aasx2):
            meta_data2, objs2, files2 = self.read_aasx(self.filename_aasx2)
        else:
            meta_data2, objs2, files2 = None, None, None

        # Retrieve the AAS and its submodels from the first file
        new_aas = None
        submodels = []
        for obj in objs1:
            if isinstance(obj, AssetAdministrationShell):
                new_aas = obj
                # Resolve and collect all submodels referenced in the AAS
                for sm_ref in obj.submodel:
                    submodel = sm_ref.resolve(objs1)
                    submodels.append(submodel)

        if new_aas is None:
            raise ValueError("No AssetAdministrationShell found in the first AASX file")

        # If the second AASX file exists, add its submodels (avoiding duplicates)
        if objs2:
            for obj in objs2:
                if isinstance(obj, Submodel):
                    if obj not in submodels:
                        submodels.append(obj)
                        # Also add a reference to the new AAS
                        new_aas.submodel.add(ModelReference.from_referable(obj))

        # Merge supplementary files from both AASX files into a single container
        merged_files = DictSupplementaryFileContainer()
        # Add files from the first file
        for file_path in files1:
            sha256 = files1.get_sha256(file_path)
            file_data = files1._store[sha256]
            content_type = files1.get_content_type(file_path)
            merged_files.add_file(file_path, io.BytesIO(file_data), content_type)
        # Add files from the second file if available and not already present
        if files2:
            for file_path in files2:
                if file_path not in merged_files:
                    sha256 = files2.get_sha256(file_path)
                    file_data = files2._store[sha256]
                    content_type = files2.get_content_type(file_path)
                    merged_files.add_file(file_path, io.BytesIO(file_data), content_type)

        # Write the merged AASX file using the gathered AAS, submodels, and merged files.
        self.write_aasx(new_aas, submodels, merged_files)

if __name__ == '__main__':
    # Determine the current directory and the output folder
    current_dir = Path(__file__).parent.resolve()
    output_dir = current_dir / 'output'

    # Define paths for the input AASX files and the output merged file
    filename_aasx1 = output_dir / 'xPPU_1.aasx'
    filename_aasx2 = output_dir / 'Stp.aasx'
    filename_merge = output_dir / 'xPPU_2.aasx'

    # Check if both input files exist before attempting the merge
    if not filename_aasx1.exists():
        print(f"File not found: {filename_aasx1}")
    elif not filename_aasx2.exists():
        print(f"File not found: {filename_aasx2}")
    else:
        print(f"Merging {filename_aasx1} and {filename_aasx2} into {filename_merge}")
        merger = AASMerger(str(filename_aasx1), str(filename_aasx2), str(filename_merge))
        merger.merge_aas()

