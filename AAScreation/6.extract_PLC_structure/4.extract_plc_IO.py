#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TwinCAT .tsproj I/O → SMC CSV exporter (no type hints).

What it does
------------
- Writes a fixed I/O structure to CSV (SubmodelElementCollection rows).
- Under "I/O" it always creates two top-level sections:
   "Devices"
     - For each device, it emits a fixed set of sub-sections (Image, Image-Info,
       SyncUnits, Inputs, Outputs, InfoData) and then appends the *real* EtherCAT
       Boxes recursively, including a hierarchical breakdown of PDO entries.
   "Mappings"
     - User-provided labels (hard-coded list), emitted as-is.
"""

import csv
import re
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict
from pathlib import Path



class SmcWriter:
    """Accumulate SMC rows and write to CSV."""
    def __init__(self, header):
        self._rows = [list(header)]

    def sanitize_idshort(text):
        """Keep [A-Za-z0-9_]; replace others with '_', strip surrounding underscores."""
        s = (text or "").strip()
        s = re.sub(r"\W+", "_", s).strip("_")
        return s or "item"

    def start(self, id_short):
        """Open a collection."""
        self._rows.append([
            "SubmodelElementCollection",
            SmcWriter.sanitize_idshort(id_short),
            "", "", "", "", "", "",
        ])

    def end(self):
        """Close the last-opened collection."""
        self._rows.append([
            "End-SubmodelElementCollection",
            "", "", "", "", "", "", "",
        ])

    def save(self, path):
        """Write accumulated rows to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(self._rows)



class XmlNav:
    """Small helpers for namespace-agnostic XML navigation."""

    def local_name(tag):
        """Strip the XML namespace; return tag as-is if it's not a string."""
        if not isinstance(tag, str):
            return tag
        return tag.split("}", 1)[-1]

    def child_text(elem, local):
        """Return text of the first *direct* child whose localname matches."""
        for c in list(elem):
            if isinstance(c.tag, str) and XmlNav.local_name(c.tag) == local and c.text:
                return c.text.strip()
        return None



class IoSmcExporter:
    """Core exporter that reads a .tsproj and writes a SMC CSV."""

    def __init__(self, cfg):
        self.cfg = cfg


    def _insert_path(self, tree, parts):
        """Insert a path (e.g., ["Status", "Limit_1"]) into a nested OrderedDict."""
        node = tree
        for p in parts:
            if p not in node:
                node[p] = OrderedDict()
            node = node[p]

    def _emit_tree(self, w, tree):
        """Emit a nested dict as SMC rows."""
        for name, sub in tree.items():
            w.start(name)
            self._emit_tree(w, sub)
            w.end()

    def _emit_pdos(self, w, ethercat_elem):
        """
        Emit PDOs under an <EtherCAT> element.
        PDO entry names may include '__' to indicate hierarchy, e.g.:
           'Status__Limit_1' : Status / Limit_1
        """
        for pdo in ethercat_elem.findall("./{*}Pdo"):
            pdo_name = pdo.get("Name") or XmlNav.child_text(pdo, "Name") or "Pdo"
            w.start(pdo_name)

            # Build a nested tree from entry names split by '__'
            tree = OrderedDict()
            for entry in pdo.findall("./{*}Entry"):
                raw = entry.get("Name") or XmlNav.child_text(entry, "Name") or "Entry"
                parts = [t.strip() for t in re.split(r"__+", raw) if t.strip()] or [raw.strip()]
                self._insert_path(tree, parts)

            self._emit_tree(w, tree)
            w.end()

    #fixed sections (device children) 

    def _emit_from_spec(self, w, spec):
        """Emit nested structures from a 'spec'."""
        if spec is None:
            return
        if isinstance(spec, str):
            w.start(spec); w.end()
            return
        if isinstance(spec, dict):
            for label, children in spec.items():
                w.start(label)
                if isinstance(children, list):
                    for child in children:
                        self._emit_from_spec(w, child)
                w.end()
            return
        if isinstance(spec, list):
            for item in spec:
                self._emit_from_spec(w, item)
            return
        # Fallback: stringify unknown types
        w.start(str(spec)); w.end()

    def _emit_fixed_sections(self, w):
        """Emit built-in device sections defined in the config."""
        for label, children in self.cfg.fixed_sections:
            if children is None:
                w.start(label); w.end()
            else:
                w.start(label)
                self._emit_from_spec(w, children)
                w.end()


    def _emit_box_recursive(self, w, box_elem):
        """Emit a <Box> node and recurse into nested boxes."""
        name = XmlNav.child_text(box_elem, "Name") or "Box"
        w.start(name)

        # Look for a direct <EtherCAT> child and emit PDO hierarchy if present.
        ethercat = next(
            (c for c in list(box_elem)
             if isinstance(c.tag, str) and XmlNav.local_name(c.tag) == "EtherCAT"),
            None
        )
        if ethercat is not None:
            self._emit_pdos(w, ethercat)

        # Recurse into nested <Box> elements (direct children).
        for child_box in box_elem.findall("./{*}Box"):
            self._emit_box_recursive(w, child_box)

        w.end()

    def _emit_device(self, w, dev_elem):
        """Emit a single <Device> node: fixed sections + real EtherCAT topology."""
        name = (
            XmlNav.child_text(dev_elem, "Name")
            or dev_elem.get("RemoteName")
            or "Device"
        )
        w.start(name)

        # 1) Fixed human-friendly sections
        self._emit_fixed_sections(w)

        # 2) Real EtherCAT topology (Boxes + PDOs)
        for box in dev_elem.findall("./{*}Box"):
            self._emit_box_recursive(w, box)

        w.end()


    def _emit_fixed_mappings(self, w):
        """Emit the hard-coded 'Mappings' sibling section."""
        w.start("Mappings")
        for label in self.cfg.fixed_mappings:
            w.start(label); w.end()
        w.end()


    def export(self, tsproj_path, out_csv):
        """
        Parse the TwinCAT .tsproj, locate <Io>, and write an SMC CSV reflecting:
          I/O
            Devices
              <Device ...> (fixed sections + boxes)
            Mappings
              <labels...>
        """
        root = ET.parse(tsproj_path).getroot()

        # Find the <Io> branch (namespace-agnostic).
        io_elem = None
        for el in root.iter():
            if isinstance(el.tag, str) and XmlNav.local_name(el.tag) == "Io":
                io_elem = el
                break
        if io_elem is None:
            raise RuntimeError("I/O tree (<Io>...) not found in this .tsproj.")

        # Emit CSV
        writer = SmcWriter(self.cfg.header)
        writer.start("I/O")

        devices = list(io_elem.findall("./{*}Device"))
        if devices:
            writer.start("Devices")
            for dev in devices:
                self._emit_device(writer, dev)
            writer.end()

        self._emit_fixed_mappings(writer)

        writer.end()  # end "I/O"
        writer.save(out_csv)




class Config:
    # CSV header used by the target SMC template.
    header = [
        "typeName", "idShort", "value", "valueType",
        "category", "descriptionEN", "descriptionDE", "semanticId",
    ]

    # Built-in sections that appear under each device *before* real EtherCAT boxes.
    # Strings create a leaf SMC; dicts create nested collections.
    fixed_sections = [
        ("Image", None),
        ("Image-Info", None),
        ("SyncUnits", [
            "<default>",
            "<unreferenced>",
            {"PlcTask": [
                "WcState",
                {"InfoData": ["ObjectId", "State", "SlaveCount"]},
            ]},
        ]),
        ("Inputs",  ["Frm0State", "Frm0WcState", "Frm0InputToggle", "SlaveCount", "DevState"]),
        ("Outputs", ["Frm0Ctrl", "Frm0WcCtrl", "DevCtrl"]),
        ("InfoData",["ChangeCount", "DevId", "AmsNetId", "CfgSlaveCount"]),
    ]

    # Hard-coded "Mappings" content (sibling of "Devices").
    fixed_mappings = [
        "ReferenceImplementation Instance - Device 1 (EtherCAT) 1",
    ]

    def default_paths(self, script_dir):
        tsproj = script_dir / "plc-referenceimplementation" / "Resi4MPM-PLC-ReferenceImplementation.tsproj"
        out_csv = script_dir / "IO_smc.csv"
        return tsproj, out_csv


def main(argv):
    cfg = Config()
    script_dir = Path(__file__).parent.resolve()
    default_tsproj, default_out = cfg.default_paths(script_dir)

    tsproj_path = Path(argv[0]).resolve() if len(argv) >= 1 else default_tsproj
    out_csv     = Path(argv[1]).resolve() if len(argv) >= 2 else default_out

    IoSmcExporter(cfg).export(tsproj_path, out_csv)
    print(f"I/O SMC CSV saved in: {out_csv}")


if __name__ == "__main__":
    main(sys.argv[1:])
