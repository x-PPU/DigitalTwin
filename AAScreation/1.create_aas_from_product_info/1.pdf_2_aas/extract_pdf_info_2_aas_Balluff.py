#!/usr/bin/env python 3.10.8
"""
This script processes PDF data sheets with four columns to create Asset Administration Shell (AAS) representations.
Designed for Balluff company product data sheets.
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
from base.extract_pdf_info_Balluff import PDFExtractor 

curPath = os.path.abspath(os.path.dirname(__file__))
sys.path.append(curPath)

logger = logging.getLogger(__name__)

def replace_str(string):
    if not string:
        return "unknown"

    dict_replace = {
        'ä': 'ae', 'Ä': 'Ae', 'ö': 'oe', 'Ö': 'Oe', 'ü': 'ue', 'Ü': 'Ue',
        '°C': 'degreeCelsius', 'Ω': 'ohm', 'µ': 'micro', '�': '',
        ' ': '_', '-': '_', '.': '_', '/': '_', '#': '_', '%': 'percentage', '±': 'plus_minus', '±': 'plus_minus',
        '+': '_', '[': '', ']': '', '(': '', ')': '', ',': '', '&': 'and', '@': 'at',
        '!': '', ':': '_', ';': '_', '"': '', "'": '', '~': '', '<': '', '>': '', '|': '_', '\\': '_', '^': '_', '`': '', '=': '_'
    }

    for word, replacement in dict_replace.items():
        string = string.replace(word, replacement)

    string = re.sub(r'[^a-zA-Z0-9_]', '', string)
    if not string[0].isalpha():
        string = 'ID_' + string

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
        self.obj_store, self.asset_information = ent_instance.create_asset_information_rand_iri(self.obj_store, asset_name, 'I')

        id_short = replace_str(title)
        aas_name = 'balluff'
        self.obj_store, self.id_aas, self.aas = ent_instance.create_aas_rand_iri(self.obj_store, id_short, aas_name, self.asset_information, None)

        submodel_elements = []
        sm_id_short = 'TechnicalData'
        sm_semantic_id = 'http://admin-shell.io/tmp/SG2/TechnicalData/Submodel/1/0'
        sm_kind = 'I'
        self.obj_store, self.submodel = ent_instance.create_SM_rand_iri(self.obj_store, sm_id_short, 'TechnicalData', submodel_elements, sm_semantic_id, sm_kind)


        # ---- Add PartNr 
        order_code = PDFExtractor(self.filename).extract_order_code()
        if order_code and order_code.lower() != "unknown":
            PN_SEMANTIC_ID = "https://example.com/semanticId/PartNr"
            pn_prop = ent_instance.create_Prop(
                id_short="PartNr",
                value_type=model.datatypes.String,
                value=str(order_code),
                category=None,
                description=None,
                semantic_id=PN_SEMANTIC_ID
            )
            self.submodel.submodel_element.add(pn_prop)

        self.aas.submodel.add(model.ModelReference.from_referable(self.submodel))
        self.eclass_instance = MapEClass()  # Create an instance of MapEClass        


    def create_Data_sheet(self, filename):
        ent_instance = ent()
        mime_type = "application/pdf"
        file_name = os.path.basename(filename)
        replace_file_name = replace_str(file_name)
        file_path = f"/aasx/Datasheet/{ replace_file_name}"
        file_element = ent_instance.create_File(self.file_store, filename, file_path, "DataSheet", mime_type, None, None)
        self.submodel.submodel_element.add(file_element)  # Only add the file element

    def create_aas_from_table(self):
        type = self.tables["type"]
        table = self.tables["df"]
        ent_instance = ent()
        ids_short = set()

        if type == 1:
            i = 0
            while i < len(table):
                feature1 = table[i][0] if len(table[i]) > 0 else None
                value1 = table[i][1] if len(table[i]) > 1 else None

                feature2 = table[i][2] if len(table[i]) > 2 else None
                value2 = table[i][3] if len(table[i]) > 3 else None

                # Handle range values
                if feature1 and value1 and "..." in value1:
                    id_short = replace_str(feature1)
                    count = 2
                    while id_short in ids_short:
                        id_short = replace_str(feature1) + str(count)
                        count += 1
                    ids_short.add(id_short)

                    min_value = value1.split("...")[0].strip()
                    max_value = value1.split("...")[1].strip()
                    _, iri_prop = self.get_iri_and_unit(feature1)

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
                    i += 1
                    continue

                # Handle normal value (feature1)
                if feature1 and value1:
                    id_short = replace_str(feature1)
                    count = 2
                    while id_short in ids_short:
                        id_short = replace_str(feature1) + str(count)
                        count += 1
                    ids_short.add(id_short)

                    value = value1.strip()
                    _, iri_prop = self.get_iri_and_unit(feature1)

                    property_element = ent_instance.create_Prop(id_short, model.datatypes.String, value, None, None, iri_prop)
                    smc_temp_list = [property_element]
                    smc_temp_key = feature1

                    j = i + 1
                    while j < len(table) and not table[j][0] and table[j][1]:
                        next_value = table[j][1].strip()
                        next_property_element = ent_instance.create_Prop(
                            f"{id_short}_{len(smc_temp_list) + 1}",
                            model.datatypes.String,
                            next_value,
                            None,
                            None,
                            iri_prop
                        )
                        smc_temp_list.append(next_property_element)
                        j += 1

                    if len(smc_temp_list) > 1:
                        smc_id_short = replace_str(smc_temp_key)
                        count = 2
                        while smc_id_short in ids_short:
                            smc_id_short = replace_str(smc_temp_key) + str(count)
                            count += 1
                        ids_short.add(smc_id_short)
                        smc_iri_prop = f"https://example.com/semanticId/{smc_id_short}"
                        smc = ent_instance.create_SMC(smc_id_short, smc_temp_list, None, None, smc_iri_prop)
                        self.submodel.submodel_element.add(smc)
                    else:
                        self.submodel.submodel_element.add(property_element)

                    i = j - 1

                # Handle feature2
                if feature2 and value2:
                    id_short2 = replace_str(feature2)
                    count = 2
                    while id_short2 in ids_short:
                        id_short2 = replace_str(feature2) + str(count)
                        count += 1
                    ids_short.add(id_short2)

                    value2 = value2.strip()
                    _, iri_prop2 = self.get_iri_and_unit(feature2)

                    property_element2 = ent_instance.create_Prop(id_short2, model.datatypes.String, value2, None, None, iri_prop2)
                    smc_temp_list2 = [property_element2]
                    smc_temp_key2 = feature2

                    j = i + 1
                    while j < len(table) and len(table[j]) > 2 and not table[j][2] and table[j][3]:
                        next_value2 = table[j][3].strip()
                        next_property_element2 = ent_instance.create_Prop(
                            f"{id_short2}_{len(smc_temp_list2) + 1}",
                            model.datatypes.String,
                            next_value2,
                            None,
                            None,
                            iri_prop2
                        )
                        smc_temp_list2.append(next_property_element2)
                        j += 1

                    if len(smc_temp_list2) > 1:
                        smc_id_short2 = replace_str(smc_temp_key2)
                        count = 2
                        while smc_id_short2 in ids_short:
                            smc_id_short2 = replace_str(smc_temp_key2) + str(count)
                            count += 1
                        ids_short.add(smc_id_short2)
                        smc_iri_prop2 = f"https://example.com/semanticId/{smc_id_short2}"
                        smc2 = ent_instance.create_SMC(smc_id_short2, smc_temp_list2, None, None, smc_iri_prop2)
                        self.submodel.submodel_element.add(smc2)
                    else:
                        self.submodel.submodel_element.add(property_element2)

                    i = j - 1

                # Handle SMC for continuation rows
                if not feature1 and value1 and i > 0 and table[i - 1][0] and table[i - 1][1]:
                    smc_temp_key = table[i - 1][0]
                    id_short = replace_str(smc_temp_key)
                    count = 2
                    while id_short in ids_short:
                        id_short = replace_str(smc_temp_key) + str(count)
                        count += 1
                    ids_short.add(id_short)

                    iri = self.get_iri_and_unit(smc_temp_key)[1]
                    smc_temp_list = [ent_instance.create_Prop(id_short, model.datatypes.String, table[i - 1][1].strip(), None, None, iri)]

                    property_element = ent_instance.create_Prop(f"{id_short}_{len(smc_temp_list) + 1}", model.datatypes.String, value1.strip(), None, None, iri)
                    smc_temp_list.append(property_element)

                    j = i + 1
                    while j < len(table) and not table[j][0] and table[j][1]:
                        next_value = table[j][1].strip()
                        next_property_element = ent_instance.create_Prop(
                            f"{id_short}_{len(smc_temp_list) + 1}",
                            model.datatypes.String,
                            next_value,
                            None,
                            None,
                            iri
                        )
                        smc_temp_list.append(next_property_element)
                        j += 1

                    if len(smc_temp_list) > 1:
                        smc_id_short = replace_str(smc_temp_key)
                        count = 2
                        while smc_id_short in ids_short:
                            smc_id_short = replace_str(smc_temp_key) + str(count)
                            count += 1
                        ids_short.add(smc_id_short)
                        smc_iri_prop = f"https://example.com/semanticId/{smc_id_short}"
                        smc = ent_instance.create_SMC(smc_id_short, smc_temp_list, None, None, smc_iri_prop)
                        self.submodel.submodel_element.add(smc)

                    i = j - 1

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
    balluff_dir = os.path.join(parent_dir, "product_files", "Balluff")
    pdf_files = glob.glob(os.path.join(balluff_dir, "*.pdf"))
    output_dir = os.path.join(current_dir, "output", "Balluff")
    
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

