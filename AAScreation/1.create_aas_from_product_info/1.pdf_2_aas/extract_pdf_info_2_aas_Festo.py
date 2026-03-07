#!/usr/bin/env python 3.10.15
"""
Generates Asset Administration Shell (AAS) models from Festo product datasheets with two columns in PDF format.
Uses `PDFExtractor` to extract data and `ent` and `MapEClass` to create AAS elements. Saves the AAS as an AASX file.
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
from base.extract_pdf_info_Festo import PDFExtractor

curPath = os.path.abspath(os.path.dirname(__file__))
sys.path.append(curPath)

logger = logging.getLogger(__name__)

def replace_str(string):
    if not string:
        return "unknown"

    dict_replace = {
        'ä': 'ae', 'Ä': 'Ae', 'ö': 'oe', 'Ö': 'Oe', 'ü': 'ue', 'Ü': 'Ue',
        '°C': 'degreeCelsius', 'Ω': 'ohm', 'µ': 'micro', '�': '',
        ' ': '_', '-': '_', '.': '_', '/': '_', '#': '_', '%': 'percentage', '±': 'plus_minus',
        '+': '_', '[': '', ']': '', '(': '', ')': '', ',': '', '&': 'and', '@': 'at',
        '!': '', ':': '_', ';': '_', '"': '', "'": '', '~': '', '<': '', '>': '', '|': '_', '\\': '_', '^': '_', '`': '', '=': '_'
    }

    for word, replacement in dict_replace.items():
        string = string.replace(word, replacement)

    string = re.sub(r'[^a-zA-Z0-9_]', '', string)
    if not string[0].isalpha():
        string = 'ID_' + string

    return string

def generate_incremental_id_short(base_id_short, existing_ids):
    if base_id_short not in existing_ids:
        return base_id_short

    max_index = 0
    for existing_id in existing_ids:
        if existing_id.startswith(base_id_short + "_"):
            try:
                index = int(existing_id.split("_")[-1])
                if index > max_index:
                    max_index = index
            except ValueError:
                continue

    new_id_short = f"{base_id_short}_{max_index + 1}"
    return new_id_short

def split_multiline_values(text: str):
    """
    Split a multi-line string into list items.
    - Keep trailing colons as requested (no stripping ':').
    - Trim surrounding whitespace.
    - Skip empty lines.
    """
    text = "" if text is None else str(text)
    parts = re.split(r'[\r\n]+', text)
    out = []
    for p in parts:
        s = p.strip()
        if s:
            out.append(s)
    return out


class AasFromTable:
    def __init__(self, tables, title, filename):
        self.tables = tables
        self.title = title
        self.filename = filename

        ent_instance = ent()
        self.obj_store = model.DictObjectStore()
        self.file_store = aasx.DictSupplementaryFileContainer()

        asset_name = replace_str(title)
        self.obj_store, self.asset_information = ent_instance.create_asset_information_rand_iri(self.obj_store, asset_name, 'I')

        id_short = replace_str(title)
        aas_name = 'smart.festo'
        self.obj_store, self.id_aas, self.aas = ent_instance.create_aas_rand_iri(self.obj_store, id_short, aas_name, self.asset_information, None)

        # Submodel: Technicaldata
        submodel_elements = []
        sm_id_short = 'Technicaldata'
        part_number = PDFExtractor(self.filename).extract_part_number()
        if part_number:
            sm_semantic_id = f"https://Technicaldata.com/ids/sm/{part_number}"
        else:
            sm_semantic_id = 'http://admin-shell.io/tmp/SG2/TechnicalData/Submodel/1/0'

        sm_kind = 'I'
        self.obj_store, self.submodel = ent_instance.create_SM_rand_iri(
            self.obj_store, sm_id_short, 'Technicaldata', submodel_elements, sm_semantic_id, sm_kind
        )

        # Add PartNr property into the submodel (only when valid)
        if part_number and part_number != "unknown":
            PN_SEMANTIC_ID = "https://example.com/semanticId/PartNr"  
            partnr_prop = ent_instance.create_Prop(
                id_short="PartNr",
                value_type=model.datatypes.String,
                value=str(part_number),
                category=None,
                description=None,
                semantic_id=PN_SEMANTIC_ID
            )
            self.submodel.submodel_element.add(partnr_prop)

        # Link SM to AAS
        self.aas.submodel.add(model.ModelReference.from_referable(self.submodel))

        self.eclass_instance = MapEClass()


    def create_Data_sheet(self, filename):
        ent_instance = ent()
        mime_type = "application/pdf"
        file_name = os.path.basename(filename)
        file_name_without_ext, file_extension = os.path.splitext(file_name)
        replace_file_name = replace_str(file_name_without_ext)
        full_file_name = f"{replace_file_name}{file_extension}"
        file_path = f"/aasx/Datasheet/{full_file_name}"
        file_element = ent_instance.create_File(self.file_store, filename, file_path, "DataSheet", mime_type, None, None)
        self.submodel.submodel_element.add(file_element)

    def create_aas_from_table(self):
        type = self.tables["type"]
        table = self.tables["df"]
        ent_instance = ent()
        ids_short = []

        if type == 1:
            i = 0
            while i < len(table):
                feature = table[i][0]
                value = table[i][1]
                value = "" if value is None else str(value)

                #  Range（eg "1 ... 10 bar"）
                if bool(re.search(r'\.\.\.', value)):
                    id_short = replace_str(feature)
                    id_short = generate_incremental_id_short(id_short, ids_short)
                    ids_short.append(id_short)

                    min_value = value.split('...')[0].strip()
                    max_value = value.split('...')[1].strip()
                    _, iri_prop = self.get_iri_and_unit(feature)

                    range_element = ent_instance.create_Range(
                        id_short,
                        model.datatypes.String,
                        min_value,
                        max_value,
                        None,
                        None,
                        iri_prop
                    )
                    self.submodel.submodel_element.add(range_element)

                # 2) multiple value → create SMC and Property
                elif '\n' in value or '\r' in value:
                    smc_id = replace_str(feature)
                    smc_id = generate_incremental_id_short(smc_id, ids_short)
                    ids_short.append(smc_id)

                    items = split_multiline_values(value)
                    _, iri_prop = self.get_iri_and_unit(feature)

                    smc_props = []
                    for idx, txt in enumerate(items, start=1):
                        prop_id = f"{smc_id}{idx}"   
                        prop = ent_instance.create_Prop(
                            prop_id, model.datatypes.String, str(txt), None, None, iri_prop
                        )
                        smc_props.append(prop)

                    smc_iri_prop = f"https://example.com/semanticId/{smc_id}"
                    smc = ent_instance.create_SMC(smc_id, smc_props, None, None, smc_iri_prop)
                    self.submodel.submodel_element.add(smc)

                # 3) single value  (Property)
                else:
                    id_short = replace_str(feature)
                    id_short = generate_incremental_id_short(id_short, ids_short)
                    ids_short.append(id_short)

                    if id_short:
                        value_text, _ = self.eclass_instance.extract_unit(value) 
                        _, iri_prop = self.get_iri_and_unit(feature)
                        value_text = str(value_text)

                        property_element = ent_instance.create_Prop(
                            id_short, model.datatypes.String, value_text, None, None, iri_prop
                        )
                        self.submodel.submodel_element.add(property_element)

                i += 1

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
    Festo_dir = os.path.join(parent_dir, "product_files", "Festo")
    pdf_files = glob.glob(os.path.join(Festo_dir, "*.pdf"))
    output_dir = os.path.join(current_dir, "output", "Festo")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in pdf_files:
        datasheet = PDFExtractor(filename)
        tables = datasheet.extract_tables_plumber()
        data_table = datasheet.extract_stream()

        title = os.path.basename(filename).replace('.pdf', '')

        aas_table = AasFromTable(data_table, title, filename)
        aas_table.create_aas_from_table()

        output_file = os.path.join(output_dir, f"{title}.aasx")
        aas_table.aas_save(output_file)
