#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AAS builder for OTT 'Elektrische Daten' tables (class-based, spiecal structure).

"""

from __future__ import annotations
import os
import re
import glob
from typing import List, Dict

from basyx.aas import model
from basyx.aas.adapter import aasx

from base.create_ent import ent
from base.eClass import MapEClass
from base.extract_pdf_info_Ott import OttPDFExtractor



def sanitize_idshort(s: str) -> str:
    """Sanitize idShort exactly like your project convention."""
    if not s:
        return "unknown"
    repl = {
        'ä': 'ae', 'Ä': 'Ae', 'ö': 'oe', 'Ö': 'Oe', 'ü': 'ue', 'Ü': 'Ue',
        '°C': 'degreeCelsius', 'Ω': 'ohm', 'µ': 'micro', '�': '',
        ' ': '_', '-': '_', '.': '_', '/': '_', '#': '_', '%': 'percentage','±': 'plus_minus',
        '+': '_', '[': '', ']': '', '(': '', ')': '', ',': '', '&': 'and', '@': 'at',
        '!': '', ':': '_', ';': '_', '"': '', "'": '', '~': '', '<': '', '>': '', '|': '_',
        '\\': '_', '^': '_', '`': '', '=': '_'
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    s = re.sub(r'[^a-zA-Z0-9_]', '', s)
    if not s[0].isalpha():
        s = 'ID_' + s
    return s

def uniq_idshort(base: str, used: List[str]) -> str:
    """De-duplicate idShorts with incremental suffixes."""
    if base not in used:
        return base
    max_idx = 0
    for e in used:
        if e.startswith(base + "_"):
            try:
                idx = int(e.split("_")[-1])
                max_idx = max(max_idx, idx)
            except ValueError:
                pass
    return f"{base}_{max_idx + 1}"

def join_val_unit(val: str, unit: str) -> str:
    val = (val or "").strip()
    unit = (unit or "").strip()
    return f"{val} {unit}".strip()

def get_col(row: List[str], col_index: Dict[str, int], name: str) -> str:
    i = col_index.get(name)
    if i is None or i >= len(row):
        return ""
    s = row[i]
    return re.sub(r"\s+", " ", s).strip() if s else ""



class OttAASBuilder:
    """
    Build an AAS from an OTT electrical data table.
    """
    # expected header
    HEADER = ["Parameter", "Symbol", "Testbedingung", "min.", "nom.", "max.", "Einheit"]

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.title = os.path.basename(pdf_path).replace(".pdf", "")

        self.ent = ent()
        self.eclass = MapEClass()

        self.obj_store = model.DictObjectStore()
        self.file_store = aasx.DictSupplementaryFileContainer()

        self.asset_information = None
        self.aas = None
        self.id_aas = None
        self.submodel = None


    def build(self, table: List[List[str]], part_number: str):
        """Build AAS objects in memory from the given table."""
        self._create_asset_and_aas()
        self._create_technicaldata_sm(part_number)
        self._fill_submodel_from_table(table)
        self._attach_datasheet()

    def save(self, outfile: str):
        """Write AASX to disk."""
        object_store = model.DictObjectStore([self.submodel, self.aas])
        with aasx.AASXWriter(outfile) as writer:
            writer.write_aas(
                aas_ids=[self.id_aas],
                object_store=object_store,
                file_store=self.file_store
            )

    def _create_asset_and_aas(self):
        asset_name = sanitize_idshort(self.title)
        self.obj_store, self.asset_information = self.ent.create_asset_information_rand_iri(
            self.obj_store, asset_name, 'I'
        )
        aas_id_short = sanitize_idshort(self.title)
        aas_name = 'smart.ott'
        self.obj_store, self.id_aas, self.aas = self.ent.create_aas_rand_iri(
            self.obj_store, aas_id_short, aas_name, self.asset_information, None
        )

    def _create_technicaldata_sm(self, part_number: str):
        sm_id_short = 'Technicaldata'
        if part_number and part_number != "unknown":
            sm_semantic_id = f"https://Technicaldata.com/ids/sm/{part_number}"
        else:
            sm_semantic_id = 'http://admin-shell.io/tmp/SG2/TechnicalData/Submodel/1/0'
        self.obj_store, self.submodel = self.ent.create_SM_rand_iri(
            self.obj_store, sm_id_short, 'Technicaldata', [],
            sm_semantic_id, 'I'
        )
        self.aas.submodel.add(model.ModelReference.from_referable(self.submodel))

    def _attach_datasheet(self):
        mime_type = "application/pdf"
        base, ext = os.path.splitext(os.path.basename(self.pdf_path))
        safe_name = f"{sanitize_idshort(base)}{ext}"
        file_path = f"/aasx/Datasheet/{safe_name}"
        file_el = self.ent.create_File(self.file_store, self.pdf_path, file_path, "DataSheet", mime_type, None, None)
        self.submodel.submodel_element.add(file_el)

    def _fill_submodel_from_table(self, table: List[List[str]]):
        used_ids: List[str] = []
        header = table[0]
        col_index = {name.lower(): i for i, name in enumerate(header)}

        for row in table[1:]:
            parameter = get_col(row, col_index, "parameter")
            symbol    = get_col(row, col_index, "symbol")
            cond      = get_col(row, col_index, "testbedingung")
            vmin      = get_col(row, col_index, "min.")
            vref      = get_col(row, col_index, "nom.")
            vmax      = get_col(row, col_index, "max.")
            unit      = get_col(row, col_index, "einheit")

            if not parameter:
                continue

            # IRDI semantic id from eClass
            _, iri_prop, _ = self.eclass.get_IrdiPR_unit_descr(parameter)

            base = sanitize_idshort(f"{parameter}_{symbol}".strip("_"))
            base = uniq_idshort(base, used_ids)
            used_ids.append(base)

            # Test conditions
            if cond and cond != "-":
                pid = uniq_idshort(sanitize_idshort(f"{base}_TEST_CONDIITIONS"), used_ids)
                used_ids.append(pid)
                prop = self.ent.create_Prop(pid, model.datatypes.String, cond, None, None, iri_prop)
                self.submodel.submodel_element.add(prop)

            # nominal (REF)
            if vref and vref != "-":
                pid = uniq_idshort(sanitize_idshort(f"{base}_REF"), used_ids)
                used_ids.append(pid)
                prop = self.ent.create_Prop(pid, model.datatypes.String, join_val_unit(vref, unit), None, None, iri_prop)
                self.submodel.submodel_element.add(prop)

            # min/max handling
            has_min = bool(vmin and vmin != "-")
            has_max = bool(vmax and vmax != "-")
            if has_min and has_max:
                rid = uniq_idshort(sanitize_idshort(f"{base}_MIN_MAX"), used_ids)
                used_ids.append(rid)
                rng = self.ent.create_Range(
                    rid, model.datatypes.String,
                    join_val_unit(vmin, unit),
                    join_val_unit(vmax, unit),
                    None, None, iri_prop
                )
                self.submodel.submodel_element.add(rng)
            else:
                if has_min:
                    pid = uniq_idshort(sanitize_idshort(f"{base}_MIN"), used_ids)
                    used_ids.append(pid)
                    prop = self.ent.create_Prop(pid, model.datatypes.String, join_val_unit(vmin, unit), None, None, iri_prop)
                    self.submodel.submodel_element.add(prop)
                if has_max:
                    pid = uniq_idshort(sanitize_idshort(f"{base}_MAX"), used_ids)
                    used_ids.append(pid)
                    prop = self.ent.create_Prop(pid, model.datatypes.String, join_val_unit(vmax, unit), None, None, iri_prop)
                    self.submodel.submodel_element.add(prop)



def run_batch(ott_dir: str, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    pdf_paths = glob.glob(os.path.join(ott_dir, "*.pdf"))
    if not pdf_paths:
        print(f"No PDFs found in {ott_dir}")
        return

    for pdf in pdf_paths:
        try:
            extractor = OttPDFExtractor(pdf)
            table = extractor.extract_table()
            part_no = extractor.extract_part_number()

            builder = OttAASBuilder(pdf)
            builder.build(table, part_number=part_no)

            title = os.path.basename(pdf).replace(".pdf", "")
            outfile = os.path.join(out_dir, f"{title}.aasx")
            builder.save(outfile)
        except Exception as e:
            print(f"Warning Failed on {pdf}: {e}")

# ---------- CLI ----------

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    ott_dir = os.path.join(parent_dir, "product_files", "Ott")
    out_dir = os.path.join(current_dir, "output", "Ott")
    run_batch(ott_dir, out_dir)
