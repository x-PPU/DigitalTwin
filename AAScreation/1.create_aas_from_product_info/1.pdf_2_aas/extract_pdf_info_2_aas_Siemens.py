#!/usr/bin/env python 3.10.15
"""
Generates AAS from Festo product datasheets with two columns in Siemens PDF format.
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
from base.extract_pdf_info_Siemens import PDFExtractorSiemens

curPath = os.path.abspath(os.path.dirname(__file__))
sys.path.append(curPath)

logger = logging.getLogger(__name__)

def replace_str(string):
    if not string:
        return "unknown"
    s = str(string)
    s = re.sub(r'[\u2022\u00B7\u25CF]', '', s)  # kreispunkt
    s = re.sub(r'\s+', ' ', s) 
    repl = {
        'ä':'ae','Ä':'Ae','ö':'oe','Ö':'Oe','ü':'ue','Ü':'Ue',
        '°C':'degreeCelsius','Ω':'ohm','µ':'micro','�':'',
        ' ':'_','-':'_','.':'_','/':'_','#':'_','%':'percentage','±': 'plus_minus',
        '+':'_','[':'',']':'','(':'',')':'',',':'','&':'and','@':'at',
        '!':'',':':'_',';':'_','"':'',"'":'','~':'','<':'','>':'','|':'_',
        '\\':'_','^':'_','`':'','=':'_'
    }
    for k,v in repl.items():
        s = s.replace(k, v)
    s = re.sub(r'[^a-zA-Z0-9_]', '', s).lstrip('_')
    if not s or not s[0].isalpha():
        s = 'ID_' + s
    return s

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

        submodel_elements = []
        sm_id_short = 'Technicaldata'
        part_number = PDFExtractorSiemens(self.filename).extract_part_number()
        if part_number:
            sm_semantic_id = f"https://Technicaldata.com/ids/sm/{part_number}"
        else:
            sm_semantic_id = 'http://admin-shell.io/tmp/SG2/TechnicalData/Submodel/1/0'

        sm_kind = 'I'
        self.obj_store, self.submodel = ent_instance.create_SM_rand_iri(self.obj_store, sm_id_short, 'Technicaldata', submodel_elements, sm_semantic_id, sm_kind)

        self.aas.submodel.add(model.ModelReference.from_referable(self.submodel))
        self.eclass_instance = MapEClass()  # Create an instance of MapEClass

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
        ent_instance = ent()
        ids_short = []
        t = self.tables.get("type", 1)

        # 1 punkt（SMC -> Props）
        if t == 2:
            for grp in self.tables.get("groups", []):
                smc_id = generate_incremental_id_short(replace_str(grp["feature"]), ids_short)
                ids_short.append(smc_id)

                props = []
                for feat, val in grp.get("items", []):
                    pid = generate_incremental_id_short(replace_str(feat), ids_short)
                    ids_short.append(pid)
                    _, iri_prop = self.get_iri_and_unit(feat)

                    v = val or ""
                    if re.search(r'\.\.\.|…', v):  
                        mn, mx = [s.strip() for s in re.split(r'\.\.\.|…', v, maxsplit=1)]
                        props.append(ent_instance.create_Range(pid, model.datatypes.String, mn, mx, None, None, iri_prop))
                    else:                     
                        props.append(ent_instance.create_Prop(pid, model.datatypes.String, v, None, None, iri_prop))

                smc = ent_instance.create_SMC(smc_id, props, None, None, f"https://example.com/semanticId/{smc_id}")
                self.submodel.submodel_element.add(smc)

            # 2 Property
            for feature, value in self.tables.get("flat", []):
                pid = generate_incremental_id_short(replace_str(feature), ids_short)
                ids_short.append(pid)
                _, iri_prop = self.get_iri_and_unit(feature)
                v = "" if value is None else str(value)
                if re.search(r'\.\.\.|…', v):
                    mn, mx = [s.strip() for s in re.split(r'\.\.\.|…', v, maxsplit=1)]
                    el = ent_instance.create_Range(pid, model.datatypes.String, mn, mx, None, None, iri_prop)
                else:
                    el = ent_instance.create_Prop(pid, model.datatypes.String, v, None, None, iri_prop)
                self.submodel.submodel_element.add(el)

            self.create_Data_sheet(self.filename)
            return

 
        if t == 1:
            for feature, value in self.tables["df"]:
                pid = generate_incremental_id_short(replace_str(feature), ids_short)
                ids_short.append(pid)
                _, iri_prop = self.get_iri_and_unit(feature)
                v = "" if value is None else str(value)
                if re.search(r'\.\.\.|…', v):
                    mn, mx = [s.strip() for s in re.split(r'\.\.\.|…', v, maxsplit=1)]
                    el = ent_instance.create_Range(pid, model.datatypes.String, mn, mx, None, None, iri_prop)
                else:
                    el = ent_instance.create_Prop(pid, model.datatypes.String, v, None, None, iri_prop)
                self.submodel.submodel_element.add(el)

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
    Siemens_dir = os.path.join(parent_dir, "product_files", "Siemens")
    pdf_files = glob.glob(os.path.join(Siemens_dir, "*.pdf"))
    output_dir = os.path.join(current_dir, "output", "Siemens")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for filename in pdf_files:
        datasheet = PDFExtractorSiemens(filename)
        tables = datasheet.extract_tables_plumber()
        data_table = datasheet.extract_stream()

        title = os.path.basename(filename).replace('.pdf', '')

        aas_table = AasFromTable(data_table, title, filename)
        aas_table.create_aas_from_table()

        output_file = os.path.join(output_dir, f"{title}.aasx")
        aas_table.aas_save(output_file)
