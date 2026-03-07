#!/usr/bin/env python 3.10.15
"""
Merge AASX from PDF-side and STP-side.

Rules:
- If both exist, PDF is the primary; append only missing submodels/files from STP.
- If only one exists (PDF or STP), copy that AASX to output unchanged.
"""

import io
import os
import shutil
from basyx.aas.adapter.aasx import AASXReader, AASXWriter, DictSupplementaryFileContainer
from basyx.aas.model import DictObjectStore, AssetAdministrationShell, Submodel
from basyx.aas.model.base import ModelReference


class AasxMerger:
    def __init__(self, pdf_path: str, stp_path: str | None, out_path: str):
        self.pdf_path = pdf_path
        self.stp_path = stp_path
        self.out_path = out_path

    def _read_aasx(self, path):
        objects = DictObjectStore()
        files = DictSupplementaryFileContainer()
        with AASXReader(path) as reader:
            _ = reader.get_core_properties()
            reader.read_into(objects, files)
        return objects, files

    def _write_aasx(self, out_path, aas, submodels, files):
        with AASXWriter(out_path) as writer:
            store = DictObjectStore()
            store.add(aas)
            for sm in submodels:
                store.add(sm)
            writer.write_aas([aas.id], store, files)
        
    def merge(self):
        # if only one side exists, copy it directly
        if not self.stp_path:
            shutil.copy2(self.pdf_path, self.out_path)
            return

        # if both sides exist, merge them
        objs_pdf, files_pdf = self._read_aasx(self.pdf_path)
        objs_stp, files_stp = self._read_aasx(self.stp_path)

        # take AAS and existing submodels from PDF-side
        aas = None
        submodels = []
        for obj in objs_pdf:
            if isinstance(obj, AssetAdministrationShell):
                aas = obj
                for sm_ref in obj.submodel:
                    submodels.append(sm_ref.resolve(objs_pdf))
                break
        if aas is None:
            raise ValueError(f"No AAS found in PDF-side AASX: {self.pdf_path}")

        # remember existing submodel IDs
        have_ids = {sm.id for sm in submodels}

        # add stp-side submodels if missing
        for obj in objs_stp:
            if isinstance(obj, Submodel) and obj.id not in have_ids:
                submodels.append(obj)
                have_ids.add(obj.id)
                aas.submodel.add(ModelReference.from_referable(obj))

        merged_files = DictSupplementaryFileContainer()
        for fp in files_pdf:
            merged_files.add_file(
                fp,
                io.BytesIO(files_pdf._store[files_pdf.get_sha256(fp)]),
                files_pdf.get_content_type(fp)
            )
        for fp in files_stp:
            if fp not in merged_files: 
                merged_files.add_file(
                    fp,
                    io.BytesIO(files_stp._store[files_stp.get_sha256(fp)]),
                    files_stp.get_content_type(fp)
                )

        # write out
        self._write_aasx(self.out_path, aas, submodels, merged_files)


def _all_aasx_under(root_dir: str):
    """Recursively collect all .aasx files under root_dir."""
    out = []
    if not os.path.isdir(root_dir):
        return out
    for r, _, files in os.walk(root_dir):
        for f in files:
            if f.lower().endswith(".aasx"):
                out.append(os.path.join(r, f))
    return out


if __name__ == "__main__":
    # script paths with dynamic repo root
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root   = os.path.dirname(current_dir)

    pdf_root = os.path.join(repo_root, "1.pdf_2_aas", "output")
    stp_root = os.path.join(repo_root, "2.stp_2_aas", "output")
    out_root = os.path.join(current_dir, "output")
    os.makedirs(out_root, exist_ok=True)

    pdf_files = _all_aasx_under(pdf_root)
    stp_files = _all_aasx_under(stp_root)
    pdf_map = {os.path.basename(p): p for p in pdf_files}
    stp_map = {os.path.basename(s): s for s in stp_files}



    # if both exist, merge; else copy single source
    all_names = sorted(set(pdf_map) | set(stp_map))
    for name in all_names:
        pdf = pdf_map.get(name)
        stp = stp_map.get(name)
        out = os.path.join(out_root, name)

        if pdf and stp:
            print(f"Merging: {name}")
            AasxMerger(pdf, stp, out).merge()
        else:
            only = pdf or stp
            print(f"Single source, copy: {name}")
            shutil.copy2(only, out)
