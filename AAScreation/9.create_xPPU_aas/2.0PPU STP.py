#!/usr/bin/env python 3.10.15
"""
STP to AAS Conversion Script

This script processes STEP (.stp) file of xppu to extract 3D model data and converts 
it into an Asset Administration Shell (AAS) format. 

"""

import os
import numpy as np
import re
from pathlib import Path

from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop
from OCC.Extend.TopologyUtils import TopologyExplorer

from basyx.aas import model
from basyx.aas.adapter import aasx

from base.create_ent import ent
from base.eClass import MapEClass

class aasFromSTP:
    def __init__(self, filename, id_info, shape_info, output_filename):
        # store input parameters
        self.filename = filename
        self.id_info = id_info
        self.shape_info = shape_info
        self.output_filename = output_filename
        self.map_eclass = MapEClass()
        self.ent = ent()
        self.file_store = aasx.DictSupplementaryFileContainer()  # Define self.file_store

    def replace_str(self, str):
        # replace character in a string to another character
        dict_repalce = {'ä': 'ae', 'Ä': 'Ae', 'ö': 'oe', 'Ö': 'Oe', 'ü': 'ue', 'Ü': 'Ue',
                        '°C': 'degreeCelsius',
                        ' ': '_', '-': '_',
                        '.': '', '/': '', '#': '', '%': 'percentage', ',': '', '(': '', ')': '', '[': '', ']': ''}
        for word, replacement in dict_repalce.items():
            str = str.replace(word, replacement)
        return str


    def aas_save(self, submodels):
        # create asset information
        obj_store, asset_info = self.ent.create_asset_information_rand_iri(model.DictObjectStore(), self.replace_str(self.shape_info['Name']), 'I')

        # create aas with random IRI
        obj_store, id_aas, aas = self.ent.create_aas_rand_iri(obj_store, self.replace_str(self.shape_info['Name']), self.replace_str(self.shape_info['Name']), asset_info, None)

        # add submodels to AAS
        for sm in submodels:
            aas.submodel.add(model.ModelReference.from_referable(sm))
            obj_store.add(sm)

        # Create object store
        object_list = [aas]  # Remove asset_info from object_list
        object_list.extend(submodels)
        print(object_list)
        object_store = model.DictObjectStore(object_list)

        # write object store and file store into aasx
        self.ent.write_aas(self.output_filename, id_aas, object_store, self.file_store)

    def create_property(self, id_short, value_type, value, semantic_id):
        return self.ent.create_Prop(id_short, value_type, value, None, None, semantic_id)

    def create_submodel_element_collection(self, id_short, value, semantic_id):
        return self.ent.create_SMC(id_short, value, None, None, semantic_id)

    def create_range(self, id_short, value_type, min, max, semantic_id):
        return self.ent.create_Range(id_short, value_type, min, max, None, None, semantic_id)

    def create_file(self, id_short, mime_type, value):
        return model.File(id_short=id_short, content_type=mime_type, value=value)

    def create_cad_file(self, filename):
        ent_instance = ent()
        mime_type = "application/step"
        file_name = os.path.basename(filename)
        file_name_without_ext, file_extension = os.path.splitext(file_name)
        replace_file_name = self.replace_str(file_name_without_ext)
        file_path = f"/aasx/stp/{replace_file_name}{file_extension}"
        file_element = ent_instance.create_File(self.file_store, filename, file_path, "CadItem", mime_type, None, None)
        return file_element


    def create_aas_from_STP(self):
        # create submodel identification for identification information
        property_file_description = self.create_property('File_description', model.datatypes.String,
                                                         self.id_info['File_description']['Description'],
                                                         self.map_eclass.get_IrdiCC_descr('File description')[0])
        property_implementation_level = self.create_property('Implementation_level', model.datatypes.String,
                                                             self.id_info['File_description']['Implementation_level'],
                                                             self.map_eclass.get_IrdiCC_descr('Implementation level')[0])
        submodelelement_file_description = self.create_submodel_element_collection('File_Description',
                                                                                   (property_file_description, property_implementation_level),
                                                                                   self.map_eclass.get_IrdiCC_descr('File Description')[0])
        # create file name SubmodelElementCollection
        property_name = self.create_property('Name', model.datatypes.String,
                                             self.id_info['File_name']['name'],
                                             self.map_eclass.get_IrdiCC_descr('Name')[0])
        property_time_stamp = self.create_property('Time_stamp', model.datatypes.String,
                                                   self.id_info['File_name']['time_stamp'],
                                                   self.map_eclass.get_IrdiCC_descr('Time stamp')[0])
        property_author = self.create_property('Author', model.datatypes.String,
                                               self.id_info['File_name']['author'],
                                               self.map_eclass.get_IrdiCC_descr('Author')[0])
        property_organization = self.create_property('Organization', model.datatypes.String,
                                                     self.id_info['File_name']['organization'],
                                                     self.map_eclass.get_IrdiCC_descr('Organization')[0])
        property_preprocessor_version = self.create_property('Preprocessor_version', model.datatypes.String,
                                                             self.id_info['File_name']['preprocessor_version'],
                                                             self.map_eclass.get_IrdiCC_descr('Preprocessor_version')[0])
        property_originating_system = self.create_property('Originating_system', model.datatypes.String,
                                                           self.id_info['File_name']['originating_system'],
                                                           self.map_eclass.get_IrdiCC_descr('Originating_system')[0])
        property_authorisation = self.create_property('Authorisation', model.datatypes.String,
                                                      self.id_info['File_name']['authorisation'],
                                                      self.map_eclass.get_IrdiCC_descr('Authorisation')[0])
        submodelelement_file_name = self.create_submodel_element_collection('File_name',
                                                                           (property_name, property_time_stamp,
                                                                            property_author, property_organization,
                                                                            property_preprocessor_version,
                                                                            property_originating_system,
                                                                            property_authorisation),
                                                                           self.map_eclass.get_IrdiCC_descr('File name')[0])
        # create file schema property
        property_file_schema = self.create_property('File_schema', model.datatypes.String,
                                                    self.id_info['File_schema'],
                                                    self.map_eclass.get_IrdiCC_descr('File schema')[0])
        # Create SubmodelElementCollection for identification
        smc_identification = self.create_submodel_element_collection('Identification', (
            submodelelement_file_description,
            submodelelement_file_name,
            property_file_schema
        ), self.map_eclass.get_IrdiCC_descr(self.shape_info['Name'])[0])
    
        # create submodel technical properties for geometry information
        volume = self.shape_info['Volume']
        size_of_surface = self.shape_info['Size_of_surface']
        center_of_mass = self.shape_info['Center_of_mass']
        min_xyz = self.shape_info['min_xyz']
        max_xyz = self.shape_info['max_xyz']
        range_xyz = self.shape_info['range_xyz']
        # create property volume
        std_unit_volume, semantic_id_prop_volume, _ = self.map_eclass.get_IrdiPR_unit_descr('Volume')
        if std_unit_volume and std_unit_volume != 'millilitre':
            volume = self.map_eclass.convert_unit(std_unit_volume, 'millilitre', volume)
        property_volume = self.create_property('Volume', self.get_value_type(volume),
                                               volume, semantic_id_prop_volume)
        # create property size of surface
        std_unit_area, semantic_id_prop_area, _ = self.map_eclass.get_IrdiPR_unit_descr('Size of surface')
        if std_unit_area and std_unit_area != 'square milimetre':
             size_of_surface = self.map_eclass.convert_unit(std_unit_area, 'square milimetre', size_of_surface)
        property_area = self.create_property('Size_of_surface', self.get_value_type(size_of_surface),
                                             size_of_surface, semantic_id_prop_area)
        # create SMC of center of mass
        std_unit_center_of_mass, semantic_id_center_of_mass, _ = self.map_eclass.get_IrdiPR_unit_descr('Center of mass')
        if std_unit_center_of_mass and std_unit_center_of_mass != 'milimetre':
            center_of_mass[0] = self.map_eclass.convert_unit(std_unit_center_of_mass, 'milimetre', center_of_mass[0])
        property_center_of_mass_x = self.create_property('X', self.get_value_type(center_of_mass[0]),
                                                         center_of_mass[0], semantic_id_center_of_mass)
        if std_unit_center_of_mass and std_unit_center_of_mass != 'milimetre':
            center_of_mass[1] = self.map_eclass.convert_unit(std_unit_center_of_mass, 'milimetre', center_of_mass[1])
        property_center_of_mass_y = self.create_property('Y', self.get_value_type(center_of_mass[1]),
                                                         center_of_mass[1], semantic_id_center_of_mass)
        if std_unit_center_of_mass and std_unit_center_of_mass != 'milimetre':
            center_of_mass[2] = self.map_eclass.convert_unit(std_unit_center_of_mass, 'milimetre', center_of_mass[2])
        property_center_of_mass_z = self.create_property('Z', self.get_value_type(center_of_mass[2]),
                                                         center_of_mass[2], semantic_id_center_of_mass)
        smc_center_of_mass = self.create_submodel_element_collection('Center_of_mass',
                                                                                 (property_center_of_mass_x,
                                                                                  property_center_of_mass_y,
                                                                                  property_center_of_mass_z),
                                                                                 semantic_id_center_of_mass)
        # create SMC of center of coordinate range
        std_unit_length, semantic_id_length, _ = self.map_eclass.get_IrdiPR_unit_descr('Length')
        if std_unit_length and std_unit_length != 'milimetre':
            min_xyz[0] = self.map_eclass.convert_unit(std_unit_length, 'milimetre', min_xyz[0])
            max_xyz[0] = self.map_eclass.convert_unit(std_unit_length, 'milimetre', max_xyz[0])
        range_length = self.create_range('Length', model.datatypes.Float, min_xyz[0], max_xyz[0], semantic_id_length)
        std_unit_width, semantic_id_width, _ = self.map_eclass.get_IrdiPR_unit_descr('Width')
        if std_unit_length and std_unit_length != 'milimetre':
            min_xyz[1] = self.map_eclass.convert_unit(std_unit_width, 'milimetre', min_xyz[1])
            max_xyz[1] = self.map_eclass.convert_unit(std_unit_width, 'milimetre', max_xyz[1])
        range_width = self.create_range('Width', model.datatypes.Float, min_xyz[1], max_xyz[1], semantic_id_width)
        std_unit_height, semantic_id_height, _ = self.map_eclass.get_IrdiPR_unit_descr('Height')
        if std_unit_length and std_unit_length != 'milimetre':
            min_xyz[2] = self.map_eclass.convert_unit(std_unit_height, 'milimetre', min_xyz[2])
            max_xyz[2] = self.map_eclass.convert_unit(std_unit_height, 'milimetre', max_xyz[2])
        range_height = self.create_range('Height', model.datatypes.Float, min_xyz[2], max_xyz[2], semantic_id_height)
        _, semantic_id_range, _ = self.map_eclass.get_IrdiPR_unit_descr('Range')
        smc_range = self.create_submodel_element_collection('Range',
                                                                        (range_length, range_width, range_height),
                                                                        semantic_id_range)
        # Create SubmodelElementCollection for Geometric properties
        smc_tech_prop = self.create_submodel_element_collection('Geometric_properties', (
            property_volume, property_area, smc_center_of_mass, smc_range
        ), self.map_eclass.get_IrdiCC_descr(self.shape_info['Name'])[0])

        # Create and add CAD file element
        cad_file_element = self.create_cad_file(self.filename)

        # Create CAD submodel and add identification and technical properties to it
        id_submodel_cad = 'https://Geometry.com/ids/sm/' + self.map_eclass.get_IrdiCC_descr(self.shape_info['Name'])[0]
        sm_cad = model.Submodel(
            id_=model.Identifier(id_submodel_cad),
            id_short='Geometry',
            semantic_id=model.ExternalReference([
                model.Key(type_=model.KeyTypes.GLOBAL_REFERENCE, value='0173-1#02-BAD596#008')
            ])
        )

        sm_cad.submodel_element.add(smc_identification)
        sm_cad.submodel_element.add(smc_tech_prop)
        sm_cad.submodel_element.add(cad_file_element)

        self.aas_save([sm_cad])

    def get_value_type(self, value):
        type_value = type(value)
        if type_value is float:
            return model.datatypes.Float
        elif type_value is int:
            return model.datatypes.Int
        elif type_value is str:
            return model.datatypes.String

class STPParser:
    def __init__(self, filename):
        # store input parameters
        self.filename = filename
        self.props = GProp_GProps()
        self.tolerance = 1e-5
        self.identification = {'File_description': {'Description': '', 'Implementation_level': ''},
                               'File_name': {'name': '', 'time_stamp': '', 'author': '', 'organization': '',
                                             'preprocessor_version': '', 'originating_system': '', 'authorisation': ''},
                               'File_schema': ''}
        self.shape_info = {'Name': '', 'Volume': 0.0, 'Size_of_surface': 0.0, 'Center_of_mass': [],
                           'min_xyz': [], 'max_xyz': [], 'range_xyz': []}

    def extract_identification(self):
        # extract identification information (file description, file name, file schema) from STP file
        with open(self.filename, 'r') as f:
            content = f.read()

        # file_description
        file_description = re.findall(r'FILE_DESCRIPTION\s*\(\s*(.*?)\s*\)\s*;', content, re.DOTALL)
        file_description_new = re.findall(r'[\'](.*?)[\']', file_description[0])
        self.identification['File_description']['Description'] = file_description_new[0].strip()
        self.identification['File_description']['Implementation_level'] = file_description_new[1].strip()

        # file_name
        file_name_des = re.findall(r'FILE_NAME\s*\(\s*(.*?)\s*\)\s*;', content, re.DOTALL)
        file_name_des_new = re.findall(r'[\'](.*?)[\']', file_name_des[0])
        self.identification['File_name']['name'] = file_name_des_new[0].strip()
        self.identification['File_name']['time_stamp'] = file_name_des_new[1].strip()
        self.identification['File_name']['author'] = file_name_des_new[2].strip()
        self.identification['File_name']['organization'] = file_name_des_new[3].strip()
        self.identification['File_name']['preprocessor_version'] = file_name_des_new[4].strip()
        self.identification['File_name']['originating_system'] = file_name_des_new[5].strip()
        self.identification['File_name']['authorisation'] = file_name_des_new[6].strip()

        # file schema
        file_schema = re.findall(r'FILE_SCHEMA\s*\(\s*(.*?)\s*\)\s*;', content, re.DOTALL)
        file_schema_new = re.findall(r'[\'](.*?)[\']', file_schema[0])
        self.identification['File_schema'] = file_schema_new[0].strip()

        return self.identification

    def extract_shape_info(self):
        # extract geometry information (volume, size of surface, center of mass and coordinate range) from STP file
        step_reader = STEPControl_Reader()
        step_reader.ReadFile(self.filename)
        step_reader.TransferRoot()
        shape = step_reader.Shape()

        # get name and properties of shape
        volume = self.get_volume(shape)
        surface_area = self.get_size_of_surface(shape, self.tolerance)
        center_of_mass = self.get_center_of_mass()
        min_xyz, max_xyz, range_xyz = self.get_cor_range(shape, self.tolerance)

        # save name and properties in dic
        self.shape_info['Name'] = os.path.basename(self.filename).split('.')[0]
        self.shape_info['Volume'] = volume
        self.shape_info['Size_of_surface'] = surface_area
        self.shape_info['Center_of_mass'] = center_of_mass
        self.shape_info['min_xyz'] = min_xyz
        self.shape_info['max_xyz'] = max_xyz
        self.shape_info['range_xyz'] = range_xyz
        return self.shape_info

    def get_volume(self, shape):
        brepgprop.VolumeProperties(shape, self.props)
        mass = self.props.Mass()
        return mass

    def get_size_of_surface(self, shape, tolerance):
        t = TopologyExplorer(shape)
        surface = 0
        for face in t.faces():
            brepgprop.SurfaceProperties(face, self.props, tolerance)
            face_surf = self.props.Mass()
            surface += face_surf
        return surface

    def get_center_of_mass(self):
        cog = self.props.CentreOfMass()
        x, y, z = cog.Coord()
        return [x, y, z]

    def get_cor_range(self, shape, tolerance):
        bbox = Bnd_Box()
        bbox.SetGap(tolerance)
        brepbndlib.Add(shape, bbox)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        min_xyz = np.array([xmin, ymin, zmin])
        max_xyz = np.array([xmax, ymax, zmax])
        range = max_xyz - min_xyz
        return min_xyz, max_xyz, range

if __name__ == '__main__':
    current_directory = Path(__file__).parent

    stp_file_path = current_directory / '06_MCAD' / 'ppucad0304' / 'ppu_asm.stp'

    output_directory = current_directory / 'output'
    output_directory.mkdir(exist_ok=True)
    output_filename_aasx = output_directory / 'Stp.aasx'

    if not stp_file_path.exists():
        print(f"File not found: {stp_file_path}")
    else:
        print(f"Processing: {stp_file_path}")

        stp = STPParser(str(stp_file_path))
        id_info = stp.extract_identification()
        shape_info = stp.extract_shape_info()

        aas_stp = aasFromSTP(str(stp_file_path), id_info, shape_info, str(output_filename_aasx))
        aas_stp.create_aas_from_STP()

        print(f"Output saved to: {output_filename_aasx}")