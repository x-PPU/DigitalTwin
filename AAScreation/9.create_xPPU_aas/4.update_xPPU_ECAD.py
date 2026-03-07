#!/usr/bin/env python3.10.15
# -*- coding: utf-8 -*-

#!/usr/bin/env python3.10.15
# -*- coding: utf-8 -*-
"""
Import ECAD Folder for AASX SM ECAD

This script imports the content of a local "ECAD" folder into the existing
Submodel "ECAD" of an AASX package.: 
 - Recursively scans the ECAD directory and creates a hierarchical
   SMC structure that mirrors the folder tree.

 - Each file in the folder is added as a File element with:

 - Existing AASX files are not overwritten; new part URIs are made unique if conflicts occur.

"""


import os
import re
from pathlib import Path

from basyx.aas.adapter.aasx import AASXReader, AASXWriter, DictSupplementaryFileContainer
from basyx.aas.model import DictObjectStore, Submodel, AssetAdministrationShell

from base.create_ent import ent
from base.eClass import MapEClass


class PathAndIdShort:
    """Helpers for idShort and AASX part URIs."""

    def __init__(self):
        self._safe_chars = re.compile(r"[^A-Za-z0-9_.-]")

    def sanitize_id_short(self, text):
        s = (text or "").strip()
        s = re.sub(r"[^A-Za-z0-9_]", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        if not s or not s[0].isalpha():
            s = "ID_" + s
        return s

    def ensure_unique_idshort(self, base, existing):
        if base not in existing:
            return base
        i = 2
        while True:
            cand = f"{base}_{i}"
            if cand not in existing:
                return cand
            i += 1

    def _safe_seg(self, seg):
        s = self._safe_chars.sub("_", seg.strip())
        s = re.sub(r"_+", "_", s)
        return s or "unnamed"

    def build_part_uri(self, relative_segments):
        base = ["aasx", "ECAD"]
        safe = [self._safe_seg(x) for x in (base + relative_segments)]
        return "/" + "/".join(safe)

    def ensure_unique_part_uri(self, part_uri, used):
        if part_uri not in used:
            return part_uri
        p = Path(part_uri)
        parent = p.parent.as_posix()
        stem, suffix = p.stem, p.suffix
        i = 2
        while True:
            cand = f"{parent}/{stem}_{i}{suffix}"
            if cand not in used:
                return cand
            i += 1


class AASXLoader:
    """Load/save AASX and get existing submodels."""

    def __init__(self, aasx_path):
        self.aasx_path = Path(aasx_path)
        self.object_store = DictObjectStore()
        self.file_store = DictSupplementaryFileContainer()

    def load(self):
        with AASXReader(str(self.aasx_path)) as reader:
            reader.read_into(self.object_store, self.file_store)

    def save(self, output_path):
        aas_ids = [a.id for a in self.object_store if isinstance(a, AssetAdministrationShell)]
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with AASXWriter(str(output_path)) as writer:
            writer.write_aas(aas_ids=aas_ids, object_store=self.object_store, file_store=self.file_store)

    def find_submodel(self, id_short):
        for obj in self.object_store:
            if isinstance(obj, Submodel) and (obj.id_short or "") == id_short:
                return obj
        raise ValueError(f"Submodel '{id_short}' not found in AASX")


class EcadImporter:
    """Import an ECAD folder tree as SMC/File into an existing submodel."""

    def __init__(self, aasx_helper, ecad_root, submodel_id_short="ECAD"):
        self.aasx = aasx_helper
        self.ecad_root = Path(ecad_root)
        self.submodel_id_short = submodel_id_short
        self.creator = ent()
        self.eclass = MapEClass()
        self.used_part_uris = set()
        self.pathutil = PathAndIdShort()

    def run(self, output_path):
        if not self.aasx.aasx_path.exists():
            raise FileNotFoundError(self.aasx.aasx_path)
        if not self.ecad_root.exists() or not self.ecad_root.is_dir():
            raise NotADirectoryError(self.ecad_root)

        self.aasx.load()
        submodel = self.aasx.find_submodel(self.submodel_id_short)

        added = 0
        for child in sorted(self.ecad_root.iterdir()):
            if not child.is_dir():
                continue
            smc = self._create_smc_recursive(child)
            submodel.submodel_element.add(smc)
            added += 1

        self.aasx.save(output_path)
        print(f"Imported {added} top-level folders into submodel '{self.submodel_id_short}'.")
        print(f"Saved: {output_path}")

    def _create_smc_recursive(self, folder):
        smc_id = self.pathutil.sanitize_id_short(folder.name)
        _unit, semantic_id, _desc = self.eclass.get_IrdiPR_unit_descr(smc_id)

        smc = self.creator.create_SMC(
            id_short=smc_id,
            value=[],
            category=None,
            description=None,
            semantic_id=semantic_id or "0000",
        )

        existing_ids = set()

        for entry in sorted(folder.iterdir()):
            if entry.is_dir():
                child_smc = self._create_smc_recursive(entry)
                smc.value.add(child_smc)
                existing_ids.add(child_smc.id_short)
                continue

            if entry.is_file():
                file_id = self.pathutil.ensure_unique_idshort(
                    self.pathutil.sanitize_id_short(entry.stem), existing_ids
                )
                rel_parts = list(entry.relative_to(self.ecad_root).parts)
                part_uri = self.pathutil.build_part_uri(rel_parts)
                part_uri = self.pathutil.ensure_unique_part_uri(part_uri, self.used_part_uris)
                self.used_part_uris.add(part_uri)

                file_elem = self.creator.create_File(
                    file_store=self.aasx.file_store,
                    file_path=str(entry),
                    aasx_file_path=part_uri,
                    id_short=file_id,
                    mime_type="application/pdf",
                    description=None,
                    category=None,
                )
                smc.value.add(file_elem)
                existing_ids.add(file_id)

        return smc


if __name__ == "__main__":
    base_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    input_aasx = base_dir / "output" / "xPPU_3.aasx"
    ecad_dir = base_dir / "ECAD"
    output_aasx = base_dir / "output" / "xPPU_4.aasx"

    submodel_id_short = "ECAD"

    helper = AASXLoader(input_aasx)
    importer = EcadImporter(helper, ecad_dir, submodel_id_short)
    importer.run(output_aasx)
