#!/usr/bin/env python3.10
# -*- coding: utf-8 -*-

import os
import re
import csv
from collections import OrderedDict
from xml.etree import ElementTree as ET
from pathlib import Path

class ProjectScanner:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.pou_index = {}

    def index_pous(self, parser):
        self.pou_index.clear()
        for cur, _, files in os.walk(self.root_dir):
            for fn in files:
                if not fn.lower().endswith(".tcpou"):
                    continue
                fp = os.path.join(cur, fn)
                name = parser.read_pou_name_quick(fp)
                if not name:
                    name = Path(fp).stem  
                if name:
                    self.pou_index[name] = fp
        return self.pou_index


class TcPouParser:
    DECLARATION_PATTERN = re.compile(
        r"<Declaration>\s*<!\[CDATA\[(.*?)\]\]>\s*</Declaration>", re.S | re.IGNORECASE
    )
    FB_HEADER_PATTERN = re.compile(r"\bFUNCTION_BLOCK\s+([A-Za-z_]\w*)", re.IGNORECASE)
    EXTENDS_PATTERN    = re.compile(r"\bEXTENDS\s+([A-Za-z_]\w*)",        re.IGNORECASE)
    IMPLEMENTS_PATTERN = re.compile(r"\bIMPLEMENTS\s+([A-Za-z_]\w*(?:\s*,\s*[A-Za-z_]\w*)*)", re.IGNORECASE)

    BLOCK_PATTERNS = {
        "VAR_INPUT":  re.compile(r"\bVAR_INPUT\b(.*?)(?=\bEND_VAR\b)", re.S | re.IGNORECASE),
        "VAR_OUTPUT": re.compile(r"\bVAR_OUTPUT\b(.*?)(?=\bEND_VAR\b)", re.S | re.IGNORECASE),
        "VAR":        re.compile(r"\bVAR\b(?!_)(.*?)(?=\bEND_VAR\b)",   re.S | re.IGNORECASE),
    }

    VAR_LINE_PATTERN = re.compile(
        r"^\s*([A-Za-z_]\w*)\s*(?:AT\s*%[^\s:;]+)?\s*:\s*([^;:=]+?)(?:\s*:=\s*[^;]+)?\s*;",
        re.IGNORECASE | re.MULTILINE
    )

    def __init__(self, encoding="utf-8"):
        self.encoding = encoding

    def _strip_ns(self, tag):
        return tag.split('}', 1)[-1]

    def _remove_line_comments(self, text):
        return re.sub(r"//.*?$", "", text, flags=re.MULTILINE)

    def read_pou_name_quick(self, file_path):
        try:
            for _ev, elem in ET.iterparse(file_path, events=("start",)):
                if self._strip_ns(elem.tag) == "POU" and "Name" in elem.attrib:
                    return elem.attrib["Name"]
        except Exception:
            return None
        return None

    def read_declaration_texts(self, file_path):
        try:
            content = open(file_path, "r", encoding=self.encoding, errors="ignore").read()
        except Exception:
            return []
        m = self.DECLARATION_PATTERN.findall(content)
        return m if m else [content]

    def parse_header(self, decl_texts):
        pou, base, ifaces = None, None, []
        for t in decl_texts:
            if pou is None:
                m = self.FB_HEADER_PATTERN.search(t)
                if m: pou = m.group(1)
            if base is None:
                m = self.EXTENDS_PATTERN.search(t)
                if m: base = m.group(1)
            if not ifaces:
                m = self.IMPLEMENTS_PATTERN.search(t)
                if m: ifaces = [s.strip() for s in m.group(1).split(",") if s.strip()]
        return pou, base, ifaces

    def parse_vars3(self, decl_texts):
        groups = {"VAR_INPUT": OrderedDict(), "VAR_OUTPUT": OrderedDict(), "VAR": OrderedDict()}
        for t in decl_texts:
            clean = self._remove_line_comments(t)
            for g, pat in self.BLOCK_PATTERNS.items():
                for block in pat.findall(clean):
                    for m in self.VAR_LINE_PATTERN.finditer(block):
                        name = m.group(1)
                        vtype = m.group(2).strip()
                        if name not in groups[g]:
                            groups[g][name] = vtype
        return groups


class InheritanceResolver:
    def __init__(self, pou_index, parser):
        self.pou_index = pou_index
        self.parser = parser

    def collect(self, pou_name, seen=None):
        if seen is None:
            seen = set()
        if pou_name in seen:
            empty = {"VAR_INPUT": OrderedDict(), "VAR_OUTPUT": OrderedDict(), "VAR": OrderedDict()}
            return empty, [], None

        seen.add(pou_name)
        path = self.pou_index.get(pou_name)
        if not path:
            empty = {"VAR_INPUT": OrderedDict(), "VAR_OUTPUT": OrderedDict(), "VAR": OrderedDict()}
            return empty, [], None

        decls = self.parser.read_declaration_texts(path)
        _n, base, ifaces = self.parser.parse_header(decls)

        merged = {"VAR_INPUT": OrderedDict(), "VAR_OUTPUT": OrderedDict(), "VAR": OrderedDict()}
        if base:
            parent_vars, _i, _b = self.collect(base, seen)
            for k in merged:
                merged[k].update(parent_vars[k])

        own = self.parser.parse_vars3(decls)
        for k in merged:
            merged[k].update(own[k])  # child overrides parent
        return merged, ifaces, base


class CsvTreeUpdater:
    HEADER = ["typeName","idShort","value","valueType","category","descriptionEN","descriptionDE","semanticId"]

    def __init__(self, csv_path, out_path):
        self.csv_path = csv_path
        self.out_path = out_path
        self.rows = []

    # ---- IO ----
    def load(self):
        with open(self.csv_path, "r", encoding="utf-8-sig", newline="") as f:
            rdr = csv.reader(f)
            self.rows = [row for row in rdr]
        if not self.rows:
            raise RuntimeError("CSV empty.")
        if [c.lower() for c in self.rows[0][:2]] != ["typename", "idshort"]:
            self.rows.insert(0, self.HEADER[:])

    def save(self):
        with open(self.out_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            for r in self.rows:
                w.writerow(r)

    def _t(self, i):
        return (self.rows[i][0] if i < len(self.rows) and self.rows[i] else "").strip()

    def _id(self, i):
        s = (self.rows[i][1] if i < len(self.rows) and len(self.rows[i])>1 else "")
        return s.replace("\ufeff","").replace("\u200b","").replace("\u3000"," ").strip()

    def _row(self, *cols):
        row = list(cols)
        row += [""] * (len(self.HEADER) - len(row))
        return row

    def find_smc_end(self, start_idx):
        depth = 0
        for i in range(start_idx, len(self.rows)):
            t = self._t(i)
            if t == "SubmodelElementCollection": depth += 1
            elif t == "End-SubmodelElementCollection":
                depth -= 1
                if depth == 0: return i
        return -1

    def find_child_block(self, start, end, child_name):
        i = start + 1
        while i < end:
            if self._t(i) == "SubmodelElementCollection" and self._id(i) == child_name:
                j = self.find_smc_end(i)
                return (i, j)
            i += 1
        return None

    def _normalize_reference_children(self, start, end):
        refs_idx = []
        i = start + 1
        while i < end:
            if self._t(i) == "SubmodelElementCollection":
                i = self.find_smc_end(i) + 1
                continue
            if self._t(i) == "ReferenceElement":
                refs_idx.append(i)
            i += 1

        n = len(refs_idx)
        if n == 0:
            return
        if n == 1:
            if len(self.rows[refs_idx[0]]) < 2:
                self.rows[refs_idx[0]].extend([""]*(2-len(self.rows[refs_idx[0]])))
            self.rows[refs_idx[0]][1] = "Reference"
        else:
            for k, ridx in enumerate(refs_idx, start=1):
                if len(self.rows[ridx]) < 2:
                    self.rows[ridx].extend([""]*(2-len(self.rows[ridx])))
                self.rows[ridx][1] = f"Reference{k}"

    def _transform_interfaces_to_implements(self, start, end):
        self.rows[start][1] = "Implements"
        i = start + 1
        while i < end:
            if self._t(i) == "SubmodelElementCollection":
                i = self.find_smc_end(i) + 1
                continue
            if self._t(i) == "Property":
                self.rows[i][0] = "ReferenceElement"
                if len(self.rows[i]) > 3:
                    self.rows[i][3] = ""  
            i += 1
        self._normalize_reference_children(start, end)

    def _build_reference_chunk(self, values):
        chunk = []
        if len(values) == 1:
            chunk.append(self._row("ReferenceElement", "Reference", values[0]))
        else:
            for i, val in enumerate(values, start=1):
                chunk.append(self._row("ReferenceElement", f"Reference{i}", val))
        return chunk

    def _insert_implements_block(self, insert_at, interfaces):
        if not interfaces:
            return 0
        chunk = [self._row("SubmodelElementCollection", "Implements")]
        chunk += self._build_reference_chunk(interfaces)
        chunk.append(self._row("End-SubmodelElementCollection"))
        self.rows[insert_at:insert_at] = chunk
        return len(chunk)

    def _insert_extends_block(self, insert_at, base_name):
        if not base_name:
            return 0
        chunk = [self._row("SubmodelElementCollection", "Extends")]
        chunk += self._build_reference_chunk([base_name])
        chunk.append(self._row("End-SubmodelElementCollection"))
        self.rows[insert_at:insert_at] = chunk
        return len(chunk)

    def _insert_group_block(self, insert_at, group_name, items, fb_name=None):
        if not items:
            return 0
        chunk = [self._row("SubmodelElementCollection", group_name)]
        for name, vtype in items.items():
            row = self._row("Property", name, "", vtype)
            # descriptionEN = FB name.idShort
            if fb_name:
                row = self._ensure_len(row, len(self.HEADER))
                row[5] = f"{fb_name}.{name}"
            chunk.append(row)
        chunk.append(self._row("End-SubmodelElementCollection"))
        self.rows[insert_at:insert_at] = chunk
        return len(chunk)

    def _normalize_existing_impl_ext(self, start, end):
        for blk_name in ("Implements", "Extends"):
            blk = self.find_child_block(start, end, blk_name)
            if not blk:
                continue
            s, e = blk
            self._normalize_reference_children(s, e)

    # once loaded all rows, return list of (start, end, name) of POU blocks under ControlModule
    def enumerate_pou_blocks_under_controlmodule(self, pou_index):
        results = []
        stack = []  # [(name, start_row)]
        i = 0
        n = len(self.rows)
        while i < n:
            t = self._t(i)
            if t == "SubmodelElementCollection":
                stack.append((self._id(i), i))
            elif t == "End-SubmodelElementCollection":
                if stack:
                    name, start = stack.pop()
                    in_ctrl = (name == "ControlModule") or any(s[0] == "ControlModule" for s in stack)
                    if in_ctrl and name in pou_index:
                        results.append((start, i, name))
            i += 1
        return results

    def _ensure_len(self, row, n):
        if len(row) < n:
            row += [""] * (n - len(row))
        return row

    def _set_property_desc_en(self, row_idx, fb_name):
        """set property descriptionEN to FBname.idShort"""
        idshort = self._id(row_idx)
        if not idshort or self._t(row_idx) != "Property":
            return
        self.rows[row_idx] = self._ensure_len(self.rows[row_idx], len(self.HEADER))
        self.rows[row_idx][5] = f"{fb_name}.{idshort}"

    def _set_group_descriptions(self, start, end, fb_name):
        j = start + 1
        while j < end:
            if self._t(j) == "Property":
                self._set_property_desc_en(j, fb_name)
            j += 1

class EnrichExistingCsv:
    def __init__(self, csv_in, root_dir, csv_out=None):
        self.csv_in = csv_in
        self.root_dir = root_dir

        p = Path(csv_in)
        self.csv_out = csv_out if csv_out else str(p.with_name(p.stem + "_enriched.csv"))

        self.parser   = TcPouParser()
        self.scanner  = ProjectScanner(root_dir)
        self.pou_idx  = self.scanner.index_pous(self.parser)
        self.resolver = InheritanceResolver(self.pou_idx, self.parser)
        self.updater  = CsvTreeUpdater(csv_in, self.csv_out)

    def run(self):
        self.updater.load()

        pou_blocks = self.updater.enumerate_pou_blocks_under_controlmodule(self.pou_idx)
        if not pou_blocks:
            self.updater.save()
            print("[WARN] No POU blocks found under 'ControlModule'. Nothing changed.")
            return

        # from bottom to top, prevent index shift
        pou_blocks.sort(key=lambda x: x[0], reverse=True)

        for (start, end, name) in pou_blocks:
            vars3, ifaces, base = self.resolver.collect(name)

            insert_at = end
            self.updater._normalize_existing_impl_ext(start, end)

            interfaces_blk = self.updater.find_child_block(start, end, "Interfaces")
            implements_blk = self.updater.find_child_block(start, end, "Implements")
            if ifaces:
                if interfaces_blk:
                    s, e = interfaces_blk
                    self.updater._transform_interfaces_to_implements(s, e)
                elif not implements_blk:
                    ins = self.updater._insert_implements_block(insert_at, ifaces)
                    end += ins; insert_at += ins
                else:
                    s, e = implements_blk
                    self.updater._normalize_reference_children(s, e)

            if base:
                extends_blk = self.updater.find_child_block(start, end, "Extends")
                if not extends_blk:
                    ins = self.updater._insert_extends_block(insert_at, base)
                    end += ins; insert_at += ins
                else:
                    s, e = extends_blk
                    self.updater._normalize_reference_children(s, e)

            for g in ("VAR_INPUT", "VAR_OUTPUT", "VAR"):
                blk = self.updater.find_child_block(start, end, g)
                items = vars3[g]
                if not blk:
                    ins = self.updater._insert_group_block(insert_at, g, items, fb_name=name)
                    end += ins; insert_at += ins
                    blk2 = self.updater.find_child_block(start, end, g)
                    if blk2:
                        s2, e2 = blk2
                        self.updater._set_group_descriptions(s2, e2, name)
                else:
                    s, e = blk
                    prop_cnt = 0
                    j = s + 1
                    while j < e:
                        if self.updater._t(j) == "Property":
                            prop_cnt += 1
                        j += 1
                    if prop_cnt == 0 and items:
                        props = [self.updater._row("Property", nm, "", tp) for nm, tp in items.items()]
                        # 先插入
                        self.updater.rows[e:e] = props
                        add_n = len(props)
                        end += add_n; insert_at += add_n
                        self.updater._set_group_descriptions(s, e + add_n, name)
                    else:
                        self.updater._set_group_descriptions(s, e, name)


        self.updater.save()


def main():
    cur = os.path.dirname(os.path.abspath(__file__))
    csv_in  = os.path.join(cur, "PLC_base6.csv")
    rootdir = os.path.join(cur, "plc-referenceimplementation")
    csv_out = os.path.join(cur, "PLC_base7.csv")

    EnrichExistingCsv(csv_in, rootdir, csv_out=csv_out).run()


if __name__ == "__main__":
    main()
