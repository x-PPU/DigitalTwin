#!/usr/bin/env python 3.10.15
"""
This script is used to create an Asset Administration Shell (AAS) for products from the company HBM. 
It processes product data from PDF files and generates an AASX package that includes both the structured 
data and the associated PDF documents as supplementary files. The script leverages various modules to 
handle tasks such as PDF table extraction, data mapping to eClass standards, and the creation of AAS 
submodels and properties.

This script is designed to be run as a standalone tool, processing a list of PDF files to generate 
corresponding AASX packages.
"""

import os
import sys
import logging
import re
import glob

from basyx.aas import model
from basyx.aas.adapter import aasx

from base.create_ent import ent
from base.eClass import MapEClass 
from base.extract_pdf_info_HBM import PDFExtractor 

curPath = os.path.abspath(os.path.dirname(__file__))
sys.path.append(curPath)

logger = logging.getLogger(__name__)

def replace_str(string):
    if not string:
        return "unknown"

    dict_replace = {
        'ä': 'ae', 'Ä': 'Ae', 'ö': 'oe', 'Ö': 'Oe', 'ü': 'ue', 'Ü': 'Ue',
        '°C': 'degreeCelsius', 'Ω': 'ohm', 'µ': 'micro', '�': '',
        ' ': '_', '-': '_', '.': '', '/': '', '#': '', '%': 'percentage','±': 'plus_minus',
        '+': '', '[': '', ']': '', '(': '', ')': '', ',': '', '&': 'and', '@': 'at'
    }
    for word, replacement in dict_replace.items():
        string = string.replace(word, replacement)
    string = re.sub(r'\W+', '', string)

    if not string[0].isalpha():
        string = 'prefix_' + string

    return string

class AasFromTable:
    def __init__(self, tables, title, filename):
        self.tables = tables
        self.title = title
        self.filename = filename

        ent_instance = ent()
        self.obj_store = model.DictObjectStore()
        self.file_store = aasx.DictSupplementaryFileContainer()

        asset_name = replace_str(title)
        self.obj_store, self.asset_information = ent_instance.create_asset_information_rand_iri(
            self.obj_store, asset_name, 'I')

        id_short = replace_str(title)
        aas_name = 'hbm'
        self.obj_store, self.id_aas, self.aas = ent_instance.create_aas_rand_iri(
            self.obj_store, id_short, aas_name, self.asset_information, None)

        submodel_elements = []
        sm_id_short = 'Technical_data'
        sm_semantic_id = 'http://admin-shell.io/tmp/SG2/TechnicalData/Submodel/1/0'
        sm_kind = 'I'
        self.obj_store, self.submodel = ent_instance.create_SM_rand_iri(
            self.obj_store, sm_id_short, 'Technical_data', submodel_elements, sm_semantic_id, sm_kind)

        self.aas.submodel.add(model.ModelReference.from_referable(self.submodel))
        self.eclass_instance = MapEClass()  # Create an instance of MapEClass

    def create_Data_sheet(self, filename):
        ent_instance = ent()
        mime_type = "application/pdf"
        file_element = ent_instance.create_File(
            self.file_store, filename, "/aasx/Data_sheet.pdf", "DataSheet", mime_type, None, None)
        self.submodel.submodel_element.add(file_element)  # Only add the file element

    def create_aas_from_table(self):
        ent_instance = ent()
        ids_short = []
        processed_features = set()  # record processed features to avoid duplicates

        for row in self.tables:
            feature = row[0]
            value = row[1]
            if not feature or not value:
                continue

            value = value.replace('\n', ' ').replace('\r', ' ')  # deal with newlines in values
            id_short = replace_str(feature)
            original_id_short = id_short

            if original_id_short in processed_features:
                continue

            counter = 1
            while id_short in ids_short:
                id_short = f"{original_id_short}_{counter}"
                counter += 1
            ids_short.append(id_short)

            # case 1: values with units, e.g. "0.5 1 2 5 10 20 50 100 200 500 N"
            if re.search(r"^\s*(\d+[.,]?\d*\s+)+\d+[.,]?\d*\s*[a-zA-Z%°µΩ]+", value):
                smc_elements = []
                standard_unit, iri_prop = self.get_iri_and_unit(feature)

                values = re.findall(r"[\d.]+", value)
                unit_match = re.search(r"[a-zA-Z°µΩ/%]+$", value.strip())
                unit = unit_match.group() if unit_match else standard_unit or ""

                for i, val in enumerate(values):
                    val_with_unit = f"{val} {standard_unit or unit}".strip()
                    prop_id = id_short if i == 0 else f"{id_short}_{i+1}"
                    prop = ent_instance.create_Prop(prop_id, model.datatypes.String, val_with_unit, None, None, iri_prop)
                    smc_elements.append(prop)

                smc = ent_instance.create_SMC(id_short, smc_elements, None, None, iri_prop)
                self.submodel.submodel_element.add(smc)
                processed_features.add(original_id_short)
                continue

            # case 1.5: 3 or more numeric values without units, e.g. "1.0 2.0 5.0"
            elif (
                len(re.findall(r"[-+±]?\d+(?:[.,]\d+)?", value.replace(",", ""))) >= 3 and
                not re.fullmatch(r"\s*\d+(?:[.,]\d+)?\s*±\s*\d+(?:[.,]\d+)?\s*", value) 
            ):
                smc_elements = []
                values = re.findall(r"[-+±]?\d+(?:[.,]\d+)?", value.replace(",", ""))
                standard_unit, iri_prop = self.get_iri_and_unit(feature)

                for i, val in enumerate(values):
                    prop_id = id_short if i == 0 else f"{id_short}_{i+1}"
                    value_str = f"{val} {standard_unit}".strip() if standard_unit else val
                    prop = ent_instance.create_Prop(prop_id, model.datatypes.String, value_str, None, None, iri_prop)
                    smc_elements.append(prop)

                smc = ent_instance.create_SMC(id_short, smc_elements, None, None, iri_prop)
                self.submodel.submodel_element.add(smc)
                processed_features.add(original_id_short)
                continue

            # case 2: cess with multiple ranges in brackets, e.g. "[-20 ... 70] °C" or "[0 ... 10] V [1 ... 12] V"
            elif re.search(r"\[\s*[-+]?[\d.]+\s*\.\.\.\s*[-+]?[\d.]+\s*\]", value) and "..." in value:
                smc_elements = []
                matches = re.findall(r"([-+]?[\d.]+)\s*\.\.\.\s*([-+]?[\d.]+)", value)
                units = re.findall(r"°[CF]", value)
                standard_unit, iri_prop = self.get_iri_and_unit(feature)

                for i, ((min_val, max_val)) in enumerate(matches):
                    unit = units[i] if i < len(units) else standard_unit
                    range_id = id_short if i == 0 else f"{id_short}_{i+1}"
                    range_elem = ent_instance.create_Range(
                        range_id, model.datatypes.String,
                        f"{min_val} {unit}", f"{max_val} {unit}", None, None, iri_prop
                    )
                    smc_elements.append(range_elem)

                smc = ent_instance.create_SMC(id_short, smc_elements, None, None, iri_prop)
                self.submodel.submodel_element.add(smc)
                processed_features.add(original_id_short)
                continue

            # case 3: Range values, e.g. "0...10 V", "10 ... 100 N", "2.0 ± 0.2 V"
            elif "..." in value:
                min_value, min_unit = self.eclass_instance.extract_unit(value.split('...')[0])
                max_value, max_unit = self.eclass_instance.extract_unit(value.split('...')[1])
                standard_unit, iri_prop = self.get_iri_and_unit(feature)

                if min_unit and standard_unit and min_unit.lower() != standard_unit.lower():
                    min_value = self.eclass_instance.convert_unit(standard_unit, min_unit, min_value)

                if max_unit and standard_unit and max_unit.lower() != standard_unit.lower():
                    max_value = self.eclass_instance.convert_unit(standard_unit, max_unit, max_value)

                range_element = ent_instance.create_Range(
                    id_short, model.datatypes.String,
                    f"{min_value} {standard_unit}", f"{max_value} {standard_unit}",
                    None, None, iri_prop
                )
                self.submodel.submodel_element.add(range_element)
                processed_features.add(original_id_short)
                continue

            # case 4: normal single value with or without unit
            else:
                value_clean, unit = self.eclass_instance.extract_unit(value)
                standard_unit, iri_prop = self.get_iri_and_unit(feature)

                if unit and standard_unit and unit.lower() != standard_unit.lower():
                    value_clean = self.eclass_instance.convert_unit(standard_unit, unit, value_clean)

                value_str = f"{value_clean} {standard_unit}" if standard_unit else str(value_clean)
                prop = ent_instance.create_Prop(id_short, model.datatypes.String, value_str, None, None, iri_prop)
                self.submodel.submodel_element.add(prop)
                processed_features.add(original_id_short)

        self.create_Data_sheet(self.filename)

    def get_iri_and_unit(self, feature):
        unit, iri_prop, descr = self.eclass_instance.get_IrdiPR_unit_descr(feature)
        return unit, iri_prop

    def aas_save(self, outfile):
        object_store = model.DictObjectStore([self.submodel, self.aas])
        # Pass the file_store to AASXWriter
        with aasx.AASXWriter(outfile) as writer:
            writer.write_aas(
                aas_ids=[self.id_aas],
                object_store=object_store,
                file_store=self.file_store
            )


if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    HBM_dir = os.path.join(parent_dir, "product_files", "HBM")
    pdf_files = glob.glob(os.path.join(HBM_dir, "*.pdf"))
    output_dir = os.path.join(current_dir, "output", "HBM")
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in pdf_files:
        datasheet = PDFExtractor(filename)
        tables = datasheet.extract_tables_camelot(pages='all')
        data_table = datasheet.extract_stream()

        title = os.path.basename(filename).replace('.pdf', '')

        aas_table = AasFromTable(data_table, title, filename)
        aas_table.create_aas_from_table()

        output_file = os.path.join(output_dir, f"{title}.aasx")
        aas_table.aas_save(output_file)