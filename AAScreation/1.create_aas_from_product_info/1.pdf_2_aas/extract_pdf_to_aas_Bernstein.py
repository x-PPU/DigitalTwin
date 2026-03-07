#!/usr/bin/env python 3.10.15
"""
Create AAS from BERNSTEIN datasheets.
- Mixed tables: 3 columns [feature, symbol, value] and 2 columns [feature, value].
- 3-col: idShort = feature_symbol(sanitized). 2-col: same as Festo.

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
from base.extract_pdf_info_Bernstein import PDFExtractorBernstein  # same folder

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
    for word, repl in dict_replace.items():
        string = string.replace(word, repl)
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
                idx = int(existing_id.split("_")[-1])
                max_index = max(max_index, idx)
            except ValueError:
                continue
    return f"{base_id_short}_{max_index + 1}"

def split_multiline_values(text: str):
    text = "" if text is None else str(text)
    parts = re.split(r'[\r\n]+', text)
    return [p.strip() for p in parts if p and p.strip()]

class AasFromBernstein:
    def __init__(self, tables, title, filename):
        self.tables = tables           # {"type": "mixed", "df": rows}
        self.title = title
        self.filename = filename

        ent_instance = ent()
        self.obj_store = model.DictObjectStore()
        self.file_store = aasx.DictSupplementaryFileContainer()

        # Asset & AAS
        asset_name = replace_str(title)
        self.obj_store, self.asset_information = ent_instance.create_asset_information_rand_iri(
            self.obj_store, asset_name, 'I'
        )

        id_short = replace_str(title)
        aas_name = 'bernstein'
        self.obj_store, self.id_aas, self.aas = ent_instance.create_aas_rand_iri(
            self.obj_store, id_short, aas_name, self.asset_information, None
        )

        # Submodel: TechnicalData
        submodel_elements = []
        sm_id_short = 'TechnicalData'
        part_number = PDFExtractorBernstein(self.filename).extract_part_number()
        if part_number and part_number != "unknown":
            sm_semantic_id = f"https://TechnicalData.com/ids/sm/{part_number}"
        else:
            sm_semantic_id = 'http://admin-shell.io/tmp/SG2/TechnicalData/Submodel/1/0'
        sm_kind = 'I'
        self.obj_store, self.submodel = ent_instance.create_SM_rand_iri(
            self.obj_store, sm_id_short, 'TechnicalData', submodel_elements, sm_semantic_id, sm_kind
        )
        
        # --- add Property PartNr ---
        if part_number and part_number.lower() != "unknown":
            PN_SEMANTIC_ID = "https://example.com/semanticId/PartNr"
            pn_prop = ent_instance.create_Prop(
                id_short="PartNr",
                value_type=model.datatypes.String,
                value=str(part_number),
                category=None,
                description=None,
                semantic_id=PN_SEMANTIC_ID
            )
            self.submodel.submodel_element.add(pn_prop)

        self.aas.submodel.add(model.ModelReference.from_referable(self.submodel))
        self.eclass_instance = MapEClass()


    def create_Data_sheet(self, filename):
        ent_instance = ent()
        mime_type = "application/pdf"
        base = os.path.basename(filename)
        name_no_ext, ext = os.path.splitext(base)
        replace_file_name = replace_str(name_no_ext)
        full_name = f"{replace_file_name}{ext}"
        file_path = f"/aasx/Datasheet/{full_name}"
        file_el = ent_instance.create_File(self.file_store, filename, file_path, "DataSheet", mime_type, None, None)
        self.submodel.submodel_element.add(file_el)

    def _add_range(self, ent_instance, id_short, value, feature):
        min_value = value.split('...')[0].strip()
        max_value = value.split('...')[1].strip()
        _, iri_prop = self.get_iri_and_unit(feature)
        rng = ent_instance.create_Range(
            id_short, model.datatypes.String, min_value, max_value, None, None, iri_prop
        )
        self.submodel.submodel_element.add(rng)

    def _add_smc_multiline(self, ent_instance, id_short, value, feature):
        items = split_multiline_values(value)
        _, iri_prop = self.get_iri_and_unit(feature)
        props = []
        for idx, txt in enumerate(items, start=1):
            pid = f"{id_short}{idx}"
            p = ent_instance.create_Prop(pid, model.datatypes.String, str(txt), None, None, iri_prop)
            props.append(p)
        smc_iri_prop = f"https://example.com/semanticId/{id_short}"
        smc = ent_instance.create_SMC(id_short, props, None, None, smc_iri_prop)
        self.submodel.submodel_element.add(smc)

    def _add_property(self, ent_instance, id_short, value, feature):
        val_text, _ = self.eclass_instance.extract_unit(value)
        _, iri_prop = self.get_iri_and_unit(feature)
        prop = ent_instance.create_Prop(id_short, model.datatypes.String, str(val_text), None, None, iri_prop)
        self.submodel.submodel_element.add(prop)

    def create_aas_from_table(self):
        rows = self.tables["df"]
        ent_instance = ent()
        ids_short = []

        for row in rows:
            # 3 cols：feature, abbrev, value
            if len(row) >= 3:
                feature, abbrev, value = row[0], row[1], row[2]
                id_base = replace_str(f"{feature}_{abbrev}") if abbrev else replace_str(feature)
                id_short = generate_incremental_id_short(id_base, ids_short); ids_short.append(id_short)
                value = "" if value is None else str(value)

                if re.search(r'\.\.\.', value):
                    self._add_range(ent_instance, id_short, value, feature)
                elif '\n' in value or '\r' in value:
                    self._add_smc_multiline(ent_instance, id_short, value, feature)
                else:
                    self._add_property(ent_instance, id_short, value, feature)

            # 2 cols：feature, value same with Festo 
            elif len(row) == 2:
                feature, value = row[0], row[1]
                id_short = generate_incremental_id_short(replace_str(feature), ids_short); ids_short.append(id_short)
                value = "" if value is None else str(value)

                if re.search(r'\.\.\.', value):
                    self._add_range(ent_instance, id_short, value, feature)
                elif '\n' in value or '\r' in value:
                    self._add_smc_multiline(ent_instance, id_short, value, feature)
                else:
                    self._add_property(ent_instance, id_short, value, feature)

            else:
                continue

        self.create_Data_sheet(self.filename)

    def get_iri_and_unit(self, feature):
        unit, iri_prop, descr = self.eclass_instance.get_IrdiPR_unit_descr(feature)
        return unit, iri_prop

    def aas_save(self, outfile):
        object_store = model.DictObjectStore([self.submodel, self.aas])
        with aasx.AASXWriter(outfile) as writer:
            writer.write_aas(
                aas_ids=[self.id_aas],
                object_store=object_store,
                file_store=self.file_store
            )

if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    bernstein_dir = os.path.join(parent_dir, "product_files", "Bernstein")
    pdf_files = glob.glob(os.path.join(bernstein_dir, "*.pdf"))
    output_dir = os.path.join(current_dir, "output", "Bernstein")

    os.makedirs(output_dir, exist_ok=True)

    for filename in pdf_files:
        extractor = PDFExtractorBernstein(filename)
        extractor.extract_tables_plumber()
        data_table = extractor.extract_stream()

        title = os.path.basename(filename).replace('.pdf', '')

        aas_builder = AasFromBernstein(data_table, title, filename)
        aas_builder.create_aas_from_table()

        output_file = os.path.join(output_dir, f"{title}.aasx")
        aas_builder.aas_save(output_file)
