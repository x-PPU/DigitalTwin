#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Link AAS IDs and ProductClassIds into Mechanical_break_down CSV.

Pipeline:
1) For each Entity row:
   - Title-case the trailing English words of idShort (manufacturer+model kept as-is).
   - Number duplicates by encounter order: "... Number 1", "... Number 2", ...
     (Numbering is per title-cased idShort without 'Number x' suffix)
2) For ReferenceElement rows inside each Entity block:
   - Set semanticId to a fixed value.
   - Fill 'value' with the AAS id extracted from matched AASX (by base idShort).
   - Fill the parent Entity row's 'semanticId' with ProductClassId.
3) Print the absolute path of the generated CSV and basic warnings.

"""

from __future__ import annotations

import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
from typing import Dict, Tuple, Optional, List


class EntityIdShortFormatter:
    """
    Handles idShort formatting:
    - Title-case the trailing English words of the idShort (keeps the head as-is).
    - Assign "Number N" suffix for duplicates (based on the formatted base idShort).
    """

    def __init__(self) -> None:
        # Counter: formatted base idShort (no "Number x") -> count
        self._counts: Dict[str, int] = defaultdict(int)

    def titlecase_trailing_words(self, s: str) -> str:
        """
        Title-case only the trailing alphabetic word sequence of the string.
        Examples:
          "Festo SFAB-200U 563795 Flow sensor" -> "Festo SFAB-200U 563795 Flow Sensor"
          "...-M8 Inductive position transmitter" -> "...-M8 Inductive Position Transmitter"
        Rule: match the longest trailing segment "[A-Za-z]+( [A-Za-z]+)*"
        """
        s = (s or "").strip()
        if not s:
            return s
        m = re.search(r"(.*?)([A-Za-z]+(?: [A-Za-z]+)*)$", s)
        if not m:
            # No pure-alphabet suffix: keep as-is
            return s
        head, tail = m.group(1), m.group(2)
        tail_tc = " ".join(w.capitalize() for w in tail.split(" "))
        return f"{head}{tail_tc}".strip()

    def format_and_number(self, raw_idshort: str) -> Tuple[str, str]:
        """
        Return (numbered_idshort, base_fixed):
        - base_fixed: title-cased trailing words, no numbering suffix.
        - numbered_idshort: base_fixed + " Number N" (N starts from 1 per base_fixed).
        """
        base_fixed = self.titlecase_trailing_words(raw_idshort.strip())
        self._counts[base_fixed] += 1
        numbered = f"{base_fixed} Number {self._counts[base_fixed]}"
        return numbered, base_fixed


class AASXResolver:
    """
    Resolve AASX file by entity base idShort (title-cased, no "Number x"),
    then extract (AAS id, ProductClassId). Results are cached per base idShort.
    """

    def __init__(self, manual_dir: Path) -> None:
        self.manual_dir = manual_dir
        self._cache: Dict[str, Tuple[Optional[str], Optional[str]]] = {}

        # Precompiled patterns used by normalization
        self._multi_sep = re.compile(r"[._\-:/\\]+")
        self._spaces = re.compile(r"\s+")

    def _norm_name(self, s: str) -> str:
        """Loose normalization: lowercase, collapse separators/spaces."""
        s = (s or "").strip().lower()
        s = self._multi_sep.sub(" ", s)
        s = self._spaces.sub(" ", s)
        return s

    def _local(self, tag: str) -> str:
        """Strip XML namespace: '{ns}tag' -> 'tag'"""
        return tag.split("}", 1)[1] if "}" in tag else tag

    def _find_data_xml_name(self, zf: zipfile.ZipFile) -> Optional[str]:
        """Prefer 'aasx/data.xml'; fallback to first 'aasx/*.xml'."""
        for n in zf.namelist():
            if n.lower() == "aasx/data.xml":
                return n
        for n in zf.namelist():
            ln = n.lower()
            if ln.startswith("aasx/") and ln.endswith(".xml"):
                return n
        return None

    def _extract_ids_from_aasx(self, aasx_path: Path) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse the data.xml inside the AASX:
        - AAS id: assetAdministrationShell/id
        - ProductClassId: property with idShort == 'ProductClassId' -> value
        """
        try:
            with zipfile.ZipFile(aasx_path, "r") as z:
                xml_name = self._find_data_xml_name(z)
                if not xml_name:
                    return None, None
                xml_bytes = z.read(xml_name)
        except Exception:
            return None, None

        try:
            root = ET.fromstring(xml_bytes)
        except Exception:
            return None, None

        # AAS id
        aas_id: Optional[str] = None
        for node in root.iter():
            if self._local(node.tag) == "assetAdministrationShell":
                for ch in node:
                    if self._local(ch.tag) == "id" and (ch.text or "").strip():
                        aas_id = ch.text.strip()
                        break
                if aas_id:
                    break

        # ProductClassId
        product_id: Optional[str] = None
        for node in root.iter():
            if self._local(node.tag) == "property":
                id_short = None
                value = None
                for ch in node:
                    ln = self._local(ch.tag)
                    if ln == "idShort":
                        id_short = (ch.text or "").strip()
                    elif ln == "value":
                        value = (ch.text or "").strip() if ch.text is not None else ""
                if (id_short or "").strip().lower() == "productclassid":
                    product_id = value
                    break

        return aas_id, product_id

    def _find_matching_aasx(self, entity_base_id: str) -> Optional[Path]:
        """
        Match AASX by entity base id (already title-cased, no numbering).
        Try exact filename match first, then normalized stem comparison.
        """
        exact = self.manual_dir / f"{entity_base_id}.aasx"
        if exact.is_file():
            return exact

        target = self._norm_name(entity_base_id)
        for p in self.manual_dir.glob("*.aasx"):
            if self._norm_name(p.stem) == target:
                return p
        return None

    def resolve(self, entity_base_id: str) -> Tuple[Optional[str], Optional[str], bool]:
        """
        Resolve and cache (aas_id, product_class_id) for the given base id.
        Returns (aas_id, product_class_id, found_bool).
        """
        if entity_base_id in self._cache:
            aas_id, pcid = self._cache[entity_base_id]
            return aas_id, pcid, (aas_id is not None or pcid is not None)

        aasx_path = self._find_matching_aasx(entity_base_id)
        if not aasx_path:
            self._cache[entity_base_id] = (None, None)
            return None, None, False

        aas_id, pcid = self._extract_ids_from_aasx(aasx_path)
        self._cache[entity_base_id] = (aas_id, pcid)
        return aas_id, pcid, (aas_id is not None or pcid is not None)


class AASXEntityLinker:
    """
    CSV processing:
    - Formats and numbers Entity idShorts via EntityIdShortFormatter.
    - Fills ReferenceElement.value (AAS id) and Entity.semanticId (ProductClassId)
      via AASXResolver using the base (un-numbered) idShort.
    """

    def __init__(self) -> None:
        # Fixed semanticId for ReferenceElement rows
        self.ref_semantic_id = "0173-1#01-AGW586#001"

        base_dir = Path(__file__).resolve().parent
        self.output_dir = base_dir / "output"
        self.manual_dir = base_dir.parent / "1.create_aas_from_product_info" / "5.update_aas" / "manual check"

        # Input / Output CSV
        self.input_csv = self.output_dir / "Mechanical_break_down_manual.csv"
        self.output_csv = self.output_dir / "Mechanical_breakdown.csv"

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Helpers
        self.formatter = EntityIdShortFormatter()
        self.resolver = AASXResolver(self.manual_dir)

    def process_csv(self, in_csv_path: Path, out_csv_path: Path) -> None:
        missing_aasx: set[str] = set()
        no_ref_entities: set[str] = set()

        current_entity_row: Optional[Dict[str, str]] = None
        current_entity_base_id: Optional[str] = None  # formatted base idShort (no "Number x")
        current_has_ref = False

        rows: List[Dict[str, str]] = []

        with in_csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return
            # Trim BOM/whitespace in header fields
            fieldnames = [(fn or "").lstrip("\ufeff").strip() for fn in reader.fieldnames]

            # Ensure required output fields
            if "semanticId" not in fieldnames:
                fieldnames.append("semanticId")
            if "value" not in fieldnames:
                fieldnames.append("value")

            for raw_row in reader:
                # Normalize keys and keep original values
                row = {(k or "").lstrip("\ufeff").strip(): v for k, v in raw_row.items()}

                t = (row.get("typeName") or "").strip()
                idshort_raw = (row.get("idShort") or "").strip()

                if t == "Entity":
                    # 1) Title-case trailing English part + numbering
                    numbered, base_fixed = self.formatter.format_and_number(idshort_raw)

                    # 2) Write back numbered idShort
                    row["idShort"] = numbered

                    # 3) Track current entity group
                    current_entity_row = row
                    current_entity_base_id = base_fixed  # used for AASX resolution
                    current_has_ref = False

                elif t == "ReferenceElement":
                    current_has_ref = True
                    row["semanticId"] = self.ref_semantic_id

                    if current_entity_base_id:
                        aas_id, pcid, found = self.resolver.resolve(current_entity_base_id)
                        if not found:
                            missing_aasx.add(current_entity_base_id)
                        if aas_id:
                            row["value"] = aas_id
                        if current_entity_row is not None and pcid:
                            current_entity_row["semanticId"] = pcid

                elif t == "End-Entity":
                    if current_entity_base_id and not current_has_ref:
                        no_ref_entities.add(current_entity_base_id)
                    # Reset group state
                    current_entity_row = None
                    current_entity_base_id = None
                    current_has_ref = False

                # Append row (modified or not)
                rows.append(row)

        # Write output CSV
        with out_csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k, "") for k in fieldnames})

        # Print output path
        print(f"\nSaved in: {out_csv_path.resolve()}")

        # Warnings
        if missing_aasx:
            print("Entities without matching AASX (base idShort):")
            for name in sorted(missing_aasx, key=str.casefold):
                print(f" - {name}")

        if no_ref_entities:
            print("Entities without any ReferenceElement (base idShort):")
            for name in sorted(no_ref_entities, key=str.casefold):
                print(f" - {name}")

    def run(self) -> None:
        if not self.input_csv.is_file():
            print(f"CSV not found: {self.input_csv.resolve()}")
            return
        self.process_csv(self.input_csv, self.output_csv)


def main() -> None:
    AASXEntityLinker().run()


if __name__ == "__main__":
    main()
