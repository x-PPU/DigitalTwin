#!/usr/bin/env python 3.10.15
"""
Create AAS from CONTELEC datasheets.

Table patterns:
- 3 columns: [feature, value, unit]  -> idShort = replace_str(feature)
    Property value = "{value}_{unit}" (unit may be empty; underscore kept)
    Multi-line value -> SMC {idShort} with Props {idShort}1/2/... (each "{line}_{unit}")
    Range "a ... b"  -> Range(min="a_unit", max="b_unit")
- 2 columns: [feature, value] -> same as Festo (no unit column)
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
from base.extract_pdf_info_Contelec import PDFExtractorContelec  

curPath = os.path.abspath(os.path.dirname(__file__))
sys.path.append(curPath)

logger = logging.getLogger(__name__)

def replace_str(string):
    if not string:
        return "unknown"
    dict_replace = {
        'ä': 'ae', 'Ä': 'Ae', 'ö': 'oe', 'Ö': 'Oe', 'ü': 'ue', 'Ü': 'Ue',
        '°C': 'degreeCelsius', 'Ω': 'ohm', 'µ': 'micro', '�': '',
        ' ': '_', '-': '_', '.': '_', '/': '_', '#': '_', '%': 'percentage',
        '+': '_', '[': '', ']': '', '(': '', ')': '', ',': '', '&': 'and', '@': 'at',
        '!': '', ':': '_', ';': '_', '"': '', "'": '', '~': '', '<': '', '>': '', '|': '_', '\\': '_', '^': '_', '`': '', '=': '_'
    }
    for w, r in dict_replace.items():
        string = string.replace(w, r)
    string = re.sub(r'[^a-zA-Z0-9_]', '', string)
    if not string[0].isalpha():
        string = 'ID_' + string
    return string

def generate_incremental_id_short(base_id_short, existing_ids):
    if base_id_short not in existing_ids:
        return base_id_short
    max_index = 0
    for e in existing_ids:
        if e.startswith(base_id_short + "_"):
            try:
                idx = int(e.split("_")[-1])
                max_index = max(max_index, idx)
            except ValueError:
                continue
    return f"{base_id_short}_{max_index + 1}"

def split_multiline_values(text: str):
    text = "" if text is None else str(text)
    parts = re.split(r'[\r\n]+', text)
    return [p.strip() for p in parts if p and p.strip()]

class AasFromContelec:
    def __init__(self, tables, title, filename):
        self.tables = tables   # {"type":"mixed","df":[...]}
        self.title = title
        self.filename = filename

        ent_instance = ent()
        self.obj_store = model.DictObjectStore()
        self.file_store = aasx.DictSupplementaryFileContainer()

        asset_name = replace_str(title)
        self.obj_store, self.asset_information = ent_instance.create_asset_information_rand_iri(
            self.obj_store, asset_name, 'I'
        )

        id_short = replace_str(title)
        aas_name = 'contelec'
        self.obj_store, self.id_aas, self.aas = ent_instance.create_aas_rand_iri(
            self.obj_store, id_short, aas_name, self.asset_information, None
        )

        submodel_elements = []
        sm_id_short = 'TechnicalData'
        part_number = PDFExtractorContelec(self.filename).extract_part_number()
        if part_number and part_number != "unknown":
            sm_semantic_id = f"https://TechnicalData.com/ids/sm/{part_number}"
        else:
            sm_semantic_id = 'http://admin-shell.io/tmp/SG2/TechnicalData/Submodel/1/0'
        sm_kind = 'I'
        self.obj_store, self.submodel = ent_instance.create_SM_rand_iri(
            self.obj_store, sm_id_short, 'TechnicalData', submodel_elements, sm_semantic_id, sm_kind
        )

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

    def _with_unit(self, value: str, unit: str):
        value = "" if value is None else str(value).strip()
        unit = "" if unit is None else str(unit).strip()
        return f"{value}_{unit}" if unit else value

    def _add_range(self, ent_instance, id_short, value, unit, feature):
        # Range "-25 ... +75"
        parts = value.split('...')
        min_value = parts[0].strip() if parts else value
        max_value = parts[1].strip() if len(parts) > 1 else value
        min_value = self._with_unit(min_value, unit)
        max_value = self._with_unit(max_value, unit)
        _, iri_prop = self.get_iri_and_unit(feature)
        rng = ent_instance.create_Range(
            id_short, model.datatypes.String, min_value, max_value, None, None, iri_prop
        )
        self.submodel.submodel_element.add(rng)

    def _add_smc_multiline(self, ent_instance, id_short, value, unit, feature):
        items = split_multiline_values(value)
        _, iri_prop = self.get_iri_and_unit(feature)
        props = []
        for idx, txt in enumerate(items, start=1):
            pid = f"{id_short}{idx}"
            val = self._with_unit(txt, unit)
            p = ent_instance.create_Prop(pid, model.datatypes.String, val, None, None, iri_prop)
            props.append(p)
        smc_iri_prop = f"https://example.com/semanticId/{id_short}"
        smc = ent_instance.create_SMC(id_short, props, None, None, smc_iri_prop)
        self.submodel.submodel_element.add(smc)

    def _add_property(self, ent_instance, id_short, value, unit, feature):
        val = self._with_unit(value, unit)
        val_text, _ = self.eclass_instance.extract_unit(val)  
        _, iri_prop = self.get_iri_and_unit(feature)
        prop = ent_instance.create_Prop(id_short, model.datatypes.String, str(val_text), None, None, iri_prop)
        self.submodel.submodel_element.add(prop)

    def create_aas_from_table(self):
        rows = self.tables["df"]
        ent_instance = ent()
        ids_short = []

        for row in rows:
            # 3 cols：feature, value, unit
            if len(row) >= 3:
                feature, value, unit = row[0], row[1], row[2]
                id_base = replace_str(feature)
                id_short = generate_incremental_id_short(id_base, ids_short); ids_short.append(id_short)
                value = "" if value is None else str(value)

                if re.search(r'\.\.\.', value):
                    self._add_range(ent_instance, id_short, value, unit, feature)
                elif '\n' in value or '\r' in value:
                    self._add_smc_multiline(ent_instance, id_short, value, unit, feature)
                else:
                    self._add_property(ent_instance, id_short, value, unit, feature)

            # 2 cols：feature, value
            elif len(row) == 2:
                feature, value = row[0], row[1]
                id_short = generate_incremental_id_short(replace_str(feature), ids_short); ids_short.append(id_short)
                value = "" if value is None else str(value)

                if re.search(r'\.\.\.', value):
                    # 2 cols no unit
                    self._add_range(ent_instance, id_short, value, "", feature)
                elif '\n' in value or '\r' in value:
                    self._add_smc_multiline(ent_instance, id_short, value, "", feature)
                else:
                    self._add_property(ent_instance, id_short, value, "", feature)

            else:
                continue

        self.create_Data_sheet(self.filename)

    def get_iri_and_unit(self, feature):
        unit, iri_prop, _ = self.eclass_instance.get_IrdiPR_unit_descr(feature)
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
    contelec_dir = os.path.join(parent_dir, "product_files", "Contelec")
    pdf_files = glob.glob(os.path.join(contelec_dir, "*.pdf"))
    output_dir = os.path.join(current_dir, "output", "Contelec")

    os.makedirs(output_dir, exist_ok=True)

    for filename in pdf_files:
        extractor = PDFExtractorContelec(filename)
        extractor.extract_tables_plumber()
        data_table = extractor.extract_stream()

        title = os.path.basename(filename).replace('.pdf', '')

        aas_builder = AasFromContelec(data_table, title, filename)
        aas_builder.create_aas_from_table()

        output_file = os.path.join(output_dir, f"{title}.aasx")
        aas_builder.aas_save(output_file)
