#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import io
import os
import re
import sys

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXReader, AASXWriter, DictSupplementaryFileContainer
from basyx.aas.model import DictObjectStore, AssetAdministrationShell, Submodel


class ProductImageFixer:
    """
    - Product images in product_files.
    - Embed matched image into AASX at /aasx/ProductImage
    - Update all File elements whose idShort equals 'ProductImage' .
    """

    def __init__(self, aasx_dir=None, product_files=None, out_dir=None):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.aasx_dir, self.product_files, self.out_dir = self._derive_defaults()
        if aasx_dir:
            self.aasx_dir = aasx_dir
        if product_files:
            self.product_files = product_files
        if out_dir:
            self.out_dir = out_dir

        self.stats = {
            "processed": 0,
            "updated": 0,
            "skipped_no_image": 0,
            "no_productimage_elem": 0,
            "errors": 0,
        }
        self.no_image_files = [] 

    def _find_upwards_dir(self, start, target_name):
        cur = os.path.abspath(start)
        while True:
            candidate = os.path.join(cur, target_name)
            if os.path.isdir(candidate):
                return candidate
            parent = os.path.dirname(cur)
            if parent == cur:
                return None
            cur = parent

    def _find_first_output_with_aasx(self, root):
        for r, _dirs, files in os.walk(root):
            if os.path.basename(r).lower() == "output" and any(f.lower().endswith(".aasx") for f in files):
                return r
        return None

    def _derive_defaults(self):
        root = self._find_upwards_dir(self.script_dir, "1.create_aas_from_product_info") or self.script_dir
        product_files = os.path.join(root, "product_files")
        product_files = product_files if os.path.isdir(product_files) else root

        aasx_dir = os.path.join(root, "5.update_aas", "output1")


        out_dir = os.path.join(self.script_dir, "output2")
        return aasx_dir, product_files, out_dir

    def _guess_content_type(self, path):
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        return {
            "png":  "image/png",
            "webp": "image/webp",
            "jpg":  "image/jpeg",
            "jpeg": "image/jpeg",
        }.get(ext, "application/octet-stream")


    def _norm_id(self, s):
        return "".join(ch for ch in (s or "").strip().lower() if ch not in "_- ")

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

    def _sanitize_part_segment(self, name):
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "").strip())
        safe = re.sub(r"_+", "_", safe).strip("_")
        return safe or "unnamed"

    
    def _build_image_index(self, root):
        # collect .png/.webp/.jpg/.jpeg, png>webp>jpg/jpeg
        pri = {".png": 3, ".webp": 2, ".jpg": 1, ".jpeg": 1}
        idx = {}
        for r, _d, files in os.walk(root):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in pri:
                    continue
                base = os.path.splitext(fn)[0].lower()
                path = os.path.join(r, fn)
                if base not in idx or pri[ext] > idx[base][1]:
                    idx[base] = (path, pri[ext])
        return idx


    def _process_file(self, aasx_path, img_index):
        base = os.path.splitext(os.path.basename(aasx_path))[0]
        key = base.lower()


        if key not in img_index:
            self.stats["skipped_no_image"] += 1
            self.no_image_files.append(os.path.basename(aasx_path)) 
            return


        img_path = img_index[key][0]
        ext = os.path.splitext(img_path)[1].lower()
        safe_base = self._sanitize_part_segment(base)
        container_path = f"/aasx/ProductImage/{safe_base}{ext}"
        content_type = self._guess_content_type(img_path)

        objs = DictObjectStore()
        files = DictSupplementaryFileContainer()
        with AASXReader(aasx_path) as reader:
            _ = reader.get_core_properties()
            reader.read_into(objs, files)

        with open(img_path, "rb") as f:
            files.add_file(container_path, io.BytesIO(f.read()), content_type)

        updated_elems = 0
        for obj in objs:
            if isinstance(obj, Submodel):
                for _parent, elm in self._walk_sm(obj):
                    if isinstance(elm, model.File) and self._norm_id(getattr(elm, "id_short", "")) == "productimage":
                        elm.value = container_path
                        setattr(elm, "content_type", content_type)
                        updated_elems += 1

        if updated_elems == 0:
            self.stats["no_productimage_elem"] += 1
        else:
            self.stats["updated"] += 1

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


    def run(self):
        if not os.path.isdir(self.aasx_dir):
            print("ERROR: AASX dir not found:", self.aasx_dir)
            return 1
        if not os.path.isdir(self.product_files):
            print("ERROR: product_files dir not found:", self.product_files)
            return 1

        img_index = self._build_image_index(self.product_files)
        if not img_index:
            print("ERROR: no .png/.jpg/.jpeg found under:", self.product_files)
            return 1

        aasx_list = [f for f in os.listdir(self.aasx_dir) if f.lower().endswith(".aasx")]
        if not aasx_list:
            print("ERROR: no .aasx found in:", self.aasx_dir)
            return 1

        for fn in aasx_list:
            self.stats["processed"] += 1
            path = os.path.join(self.aasx_dir, fn)
            try:
                self._process_file(path, img_index)
            except Exception as e:
                self.stats["errors"] += 1
                print("ERROR:", fn, "-", e)

        if self.no_image_files:
            print("\n[No matched image for these .aasx files]:")
            for name in sorted(self.no_image_files):
                print(" -", name)

        print("Summary:",
            f"processed={self.stats['processed']},",
            f"updated={self.stats['updated']},",
            f"skipped_no_image={self.stats['skipped_no_image']},",
            f"no_ProductImage_element={self.stats['no_productimage_elem']},",
            f"errors={self.stats['errors']}")

        return 0


def main():
    # dynamic defaults (can be overridden by CLI)
    fixer = ProductImageFixer()
    ap = argparse.ArgumentParser(description="Embed same-named images into AASX and update File(ProductImage).")
    ap.add_argument("-i", "--aasx-dir", help="Directory of input .aasx files (auto-discovered if omitted).")
    ap.add_argument("-p", "--product-files", help="Root of product images; searched recursively.")
    ap.add_argument("-o", "--out-dir", help="Output directory for updated .aasx.")
    args = ap.parse_args()

    if args.aasx_dir or args.product_files or args.out_dir:
        fixer = ProductImageFixer(args.aasx_dir, args.product_files, args.out_dir)

    sys.exit(fixer.run())


if __name__ == "__main__":
    main()

