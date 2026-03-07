#/usr/bin/env python3
# coding: utf-8 -*-

"""
Append 'PlcTask Outputs' and 'PlcTask Inputs' as SMC collections under
'ReferenceImplementation_Instance' inside an existing SMC CSV.

Rules:
- idShort of each variable = sanitized original <Name>
- descriptionEN = original <Name>
- Two groups are inserted: 'PlcTask Outputs' and 'PlcTask Inputs'
- If those groups already exist (by idShort), they are removed and re-inserted
"""

import csv
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

CSV_HEADER = [
    "typeName", "idShort", "value", "valueType",
    "category", "descriptionEN", "descriptionDE", "semanticId"
]

def sanitize_idshort(text):
    """
    Sanitize a string for SMC idShort
    """
    s = (text or "").strip()
    s = re.sub(r"[^\w]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "item"
    if s[0].isdigit():
        s = "_" + s
    return s


def local_name(tag):
    """Namespace-agnostic local tag name."""
    return tag.split("}", 1)[-1] if isinstance(tag, str) else tag


def first_child_text(elem, lname):
    """Return text of the first direct child with given local name (or None)."""
    for c in list(elem):
        if isinstance(c.tag, str) and local_name(c.tag) == lname and c.text:
            return c.text.strip()
    return None


def make_start(label, description_en=""):
    """
    Build a 'SubmodelElementCollection' start row.
    'idShort' is sanitized from 'label'; 'descriptionEN' carries the raw label.
    """
    return [
        "SubmodelElementCollection",
        sanitize_idshort(label), "", "", "", description_en, "", ""
    ]


def make_end():
    """Build an 'End-SubmodelElementCollection' row."""
    return ["End-SubmodelElementCollection", "", "", "", "", "", "", ""]



class PlcTaskExtractor:
    """
    Reads variable names from <Vars> groups named:
      - 'PlcTask Outputs'
      - 'PlcTask Inputs'
    """

    def __init__(self, tsproj_bak_path):
        self.root = ET.parse(tsproj_bak_path).getroot()
        self.groups = ("PlcTask Outputs", "PlcTask Inputs")

    def extract(self):
        """
        Returns: dict {'PlcTask Outputs': [names...], 'PlcTask Inputs': [names...]}
        """
        data = {g: [] for g in self.groups}
        for el in self.root.iter():
            if not isinstance(el.tag, str) or local_name(el.tag) != "Vars":
                continue
            gname = first_child_text(el, "Name")
            if gname in data:
                for v in el.findall("./{*}Var"):
                    nm = first_child_text(v, "Name")
                    if nm:
                        data[gname].append(nm)
        return data

class SmcCsv:
    """
    Minimal editor for SMC-CSV structured with 'Start'/'End' rows.
    """

    def __init__(self, rows):
        self.rows = rows

    def write(self, path):
        """Save CSV as UTF-8."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(self.rows)

    # ---- structure helpers ----
    def _is_start(self, r):
        return len(r) >= 2 and r[0] == "SubmodelElementCollection"

    def _is_end(self, r):
        return len(r) >= 1 and r[0] == "End-SubmodelElementCollection"

    def _id(self, r):
        return r[1] if len(r) >= 2 else ""

    def find_collection_range(self, idshort):
        """
        Find [start_idx, end_idx] covering a collection with given idShort.
        'end_idx' is the index of the matching 'End-SubmodelElementCollection'.
        """
        start = None
        for i, r in enumerate(self.rows):
            if self._is_start(r) and self._id(r) == idshort:
                start = i
                break
        if start is None:
            raise ValueError("Collection '%s' not found." % idshort)

        depth = 0
        for j in range(start, len(self.rows)):
            if self._is_start(self.rows[j]):
                depth += 1
            elif self._is_end(self.rows[j]):
                depth -= 1
            if depth == 0:
                return start, j
        raise ValueError("Unbalanced SMC starting at row %d." % start)

    def remove_child_by_idshort(self, parent_start, parent_end, child_id):
        """
        Remove a direct child collection (by idShort) within [parent_start, parent_end].
        Returns updated 'parent_end' after deletion.
        """
        depth = 0
        i = parent_start + 1
        while i < parent_end:
            r = self.rows[i]
            if self._is_start(r):
                if depth == 0 and self._id(r) == child_id:
                    # find the matching end of this child
                    d = 1
                    k = i + 1
                    while k < parent_end:
                        if self._is_start(self.rows[k]):
                            d += 1
                        elif self._is_end(self.rows[k]):
                            d -= 1
                        k += 1
                        if d == 0:
                            break
                    # delete [i, k)
                    del self.rows[i:k]
                    return parent_end - (k - i)
                depth += 1
            elif self._is_end(r):
                depth -= 1
            i += 1
        return parent_end

def read_smc_csv(path):
    """Load CSV (UTF-8 with BOM tolerant) and return SmcCsv instance."""
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    return SmcCsv(rows)


def build_group_rows(group_name, var_names):
    """
    Build SMC rows:
      SubmodelElementCollection, idShort=sanitized(group_name)
        SubmodelElementCollection, idShort=sanitized(var), descriptionEN=raw var
        End-SubmodelElementCollection
        ...
      End-SubmodelElementCollection
    """
    rows = [make_start(group_name)]
    for nm in var_names:
        rows.append(make_start(nm, description_en=nm))
        rows.append(make_end())
    rows.append(make_end())
    return rows


def run(tsproj_bak_path, input_csv_path, output_csv_path):
    # 1 Extract groups from .tsproj.bak
    groups = PlcTaskExtractor(tsproj_bak_path).extract()

    # 2 Load SMC CSV
    smc = read_smc_csv(input_csv_path)
    if not smc.rows or smc.rows[0][:len(CSV_HEADER)] != CSV_HEADER:
        raise RuntimeError("CSV header mismatch. Expected SMC header.")

    # 3 Locate 'ReferenceImplementation_Instance'
    parent_start, parent_end = smc.find_collection_range("ReferenceImplementation_Instance")

    # 4 Remove old groups if present (use sanitized idShorts)
    for g_id in ("PlcTask_Outputs", "PlcTask_Inputs"):
        parent_end = smc.remove_child_by_idshort(parent_start, parent_end, g_id)

    # 5 Insert new groups just before parent's End
    to_insert = []
    to_insert += build_group_rows("PlcTask Outputs", groups.get("PlcTask Outputs", []))
    to_insert += build_group_rows("PlcTask Inputs",  groups.get("PlcTask Inputs",  []))
    smc.rows[parent_end:parent_end] = to_insert

    # 6 Save
    smc.write(output_csv_path)


def main(argv):
    script_dir = Path(__file__).parent

    tsproj_bak_default = script_dir / "plc-referenceimplementation" / "Resi4MPM-PLC-ReferenceImplementation.tsproj"
    input_csv_default  = script_dir / "PLC_base2.csv"
    output_csv_default = script_dir / "PLC_base3.csv"

    # CLI: input_csv [tsproj_bak] [output_csv]
    input_csv_path  = Path(argv[0]).resolve() if len(argv) >= 1 else input_csv_default
    tsproj_bak_path = Path(argv[1]).resolve() if len(argv) >= 2 else tsproj_bak_default
    output_csv_path = Path(argv[2]).resolve() if len(argv) >= 3 else output_csv_default

    run(tsproj_bak_path, input_csv_path, output_csv_path)
    print("Updated CSV saved in:", output_csv_path)


if __name__ == "__main__":
    main(sys.argv[1:])
