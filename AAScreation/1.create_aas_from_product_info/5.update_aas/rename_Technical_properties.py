#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import sys
from basyx.aas import model
from basyx.aas.adapter.aasx import AASXReader, AASXWriter, DictSupplementaryFileContainer
from basyx.aas.model import DictObjectStore, AssetAdministrationShell, Submodel

TARGET_OLD = "Technical_properties"
TARGET_NEW = "Geometric_properties"

class SMCIdShortRenamer:
    def __init__(self, aasx_dir=None, out_dir=None):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.aasx_dir = aasx_dir or os.path.join(self.script_dir, "manual check")
        self.out_dir  = out_dir  or os.path.join(self.script_dir, "manual check output")
        self.stats = {"processed":0, "updated_files":0, "updated_elements":0, "no_change":0, "errors":0}

    def _get_container(self, sm):
        return getattr(sm, "submodel_element", None) or getattr(sm, "submodel_elements", None) or []

    def _walk_sm(self, sm):
        top = self._get_container(sm)
        stack = [(top, e) for e in list(top)]
        while stack:
            parent, cur = stack.pop()
            yield parent, cur
            if isinstance(cur, model.SubmodelElementCollection):
                for child in list(cur.value):
                    stack.append((cur.value, child))
            elif isinstance(cur, model.Entity):
                for child in list(cur.statement):
                    stack.append((cur.statement, child))

    def _rename_if_match(self, elem) -> bool:
        if isinstance(elem, model.SubmodelElementCollection) and getattr(elem, "id_short", None) == TARGET_OLD:
            setattr(elem, "id_short", TARGET_NEW)
            return True
        return False

    def _process_file(self, aasx_path):
        objs = DictObjectStore()
        files = DictSupplementaryFileContainer()
        with AASXReader(aasx_path) as reader:
            _ = reader.get_core_properties()
            reader.read_into(objs, files)

        changed = 0
        for obj in objs:
            if isinstance(obj, Submodel):
                for _parent, elm in self._walk_sm(obj):
                    if self._rename_if_match(elm):
                        changed += 1

        if changed == 0:
            self.stats["no_change"] += 1
            return False, 0

        os.makedirs(self.out_dir, exist_ok=True)
        out_path = os.path.join(self.out_dir, os.path.basename(aasx_path))
        store_out = DictObjectStore()
        aas_ids = []
        for obj in objs:
            store_out.add(obj)
            if isinstance(obj, AssetAdministrationShell):
                aas_ids.append(obj.id)

        with AASXWriter(out_path) as writer:
            writer.write_aas(aas_ids, store_out, files)

        self.stats["updated_files"] += 1
        self.stats["updated_elements"] += changed
        return True, changed

    def run(self):
        if not os.path.isdir(self.aasx_dir):
            print("ERROR: Input folder not found:", self.aasx_dir)
            return 1
        aasx_list = [f for f in os.listdir(self.aasx_dir) if f.lower().endswith(".aasx")]
        if not aasx_list:
            print("ERROR: no .aasx found in:", self.aasx_dir)
            return 1

        for fn in sorted(aasx_list):
            self.stats["processed"] += 1
            path = os.path.join(self.aasx_dir, fn)
            try:
                ok, cnt = self._process_file(path)
                print(f"[UPDATED] {fn}: {cnt} element(s)." if ok else f"[NO CHANGE] {fn}")
            except Exception as e:
                self.stats["errors"] += 1
                print(f"[ERROR] {fn} - {e}")

        print("\nSummary:",
              f"processed={self.stats['processed']},",
              f"updated_files={self.stats['updated_files']},",
              f"updated_elements={self.stats['updated_elements']},",
              f"no_change={self.stats['no_change']},",
              f"errors={self.stats['errors']}")
        return 0

def main():
    ap = argparse.ArgumentParser(description="Rename SMC idShort 'Technical_properties' -> 'Geometric_properties' in .aasx files.")
    ap.add_argument("-i", "--aasx-dir", help="(Optional) Input folder. Default: <script>/Input")
    ap.add_argument("-o", "--out-dir",  help="(Optional) Output folder. Default: <script>/output")
    args = ap.parse_args()
    renamer = SMCIdShortRenamer(args.aasx_dir, args.out_dir)
    sys.exit(renamer.run())

if __name__ == "__main__":
    main()
