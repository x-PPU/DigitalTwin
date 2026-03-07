#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Siemens PDF table extractor with special structure handling.
"""

import re
import csv
import pdfplumber
from pdfminer.high_level import extract_text, extract_pages
from pdfminer.layout import LAParams, LTTextContainer, LTChar, LTTextLine


class PDFExtractorSiemens:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.tables_raw = []
        self.rows_with_bbox = [] 


    def extract_tables_plumber(self):
        self.tables_raw = []
        self.rows_with_bbox = []

        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,
            "join_tolerance": 3,
            "edge_min_length": 16,
            "min_words_vertical": 1,
            "min_words_horizontal": 1,
            "keep_blank_chars": True,
            "text_x_tolerance": 1,
            "text_y_tolerance": 1,
        }

        def cell_text_and_min_x0(page, cell):
            if cell is None:
                return None, None
            (x0, top, x1, bottom) = cell
            words = page.extract_words(x_tolerance=1, y_tolerance=1, keep_blank_chars=True)
            texts, xs = [], []
            for w in words:
                if (w["x0"] >= x0 - 0.5 and w["x1"] <= x1 + 0.5 and
                    w["top"] >= top - 0.5 and w["bottom"] <= bottom + 0.5):
                    texts.append(w["text"])
                    xs.append(w["x0"])
            txt = " ".join(texts).strip() if texts else None
            minx = min(xs) if xs else None
            return txt, minx

        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                # text-only tables (fallback)
                try:
                    self.tables_raw.extend(page.extract_tables(table_settings=table_settings))
                except Exception:
                    self.tables_raw.extend(page.extract_tables())

                # tables with geometry
                try:
                    tbls = page.find_tables(table_settings=table_settings)
                except Exception:
                    tbls = []

                for tbl in tbls:
                    for row in tbl.rows:
                        cells = row.cells or []
                        c0 = cells[0] if len(cells) > 0 else None
                        c1 = cells[1] if len(cells) > 1 else None
                        left_txt, left_x0 = cell_text_and_min_x0(page, c0)
                        right_txt, _      = cell_text_and_min_x0(page, c1)

                        if (left_txt and left_txt.strip()) or (right_txt and right_txt.strip()):
                            self.rows_with_bbox.append({
                                "left":  (left_txt or "").strip() or None,
                                "right": (right_txt or "").strip() or None,
                                "left_x0": left_x0
                            })

    def extract_text(self):
        laparams = LAParams()
        return extract_text(self.pdf_path, laparams=laparams)

    def extract_text_elements(self):
        #  extract text elements with layout info
        laparams = LAParams()
        pages = extract_pages(self.pdf_path, laparams=laparams)
        elements = []
        for page_layout in pages:
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    elements.extend(element)
        return elements


    def extract_stream(self):
        rows = self.rows_with_bbox

        # fallback: no geometry
        if not rows:
            flat = []
            for table in (self.tables_raw or []):
                if not table: 
                    continue
                for r in table:
                    if not r:
                        continue
                    if len(r) < 2:
                        r += [None] * (2 - len(r))
                    a = (r[0] or "").strip() if r[0] else None
                    b = (r[1] or "").strip() if r[1] else None
                    if a and b:
                        flat.append([a, b])
            return {"type": 1, "df": flat}

        bullet_pat = r'^[\u2022\u00B7\u25CF\-\*]\s*'
        #  bullet characters: • · ● - *
        def is_bullet(s: str) -> bool:
            return bool(s and re.match(bullet_pat, s))

        value_like_re = re.compile(
            r'('
            r'\d'
            r'|%|°|°C|bar|mbar|Pa|kPa|MPa'
            r'|ms|s|us|µs'
            r'|A|V|W|kW|VA|mA'
            r'|Hz|kHz|MHz|GHz'
            r'|mm|cm|m'
            r'|kg|g'
            r'|Nm'
            r'|kbit/?s|Mbit/?s|Gbit/?s|bit/?s'
            r'|IP\d{2}'
            r')', re.IGNORECASE)
        def looks_like_value(s: str) -> bool:
            return bool(s and value_like_re.search(s))

        # estimate indent threshold
        xs = sorted([r["left_x0"] for r in rows if r.get("left_x0") is not None])
        INDENT_DELTA = 6.0
        if len(xs) >= 10:
            import statistics as st
            q2 = st.median(xs)
            q1 = xs[len(xs)//4]
            INDENT_DELTA = max(3.0, abs(q2 - q1) * 0.8)

        groups = []
        used_hierarchy = False

        i, n = 0, len(rows)
        while i < n:
            cur = rows[i]
            left, right, x0 = cur["left"], cur["right"], cur["left_x0"]

            # parent header: left text, right empty
            if left and not right:
                parent_x0 = x0 or 0.0
                parent = {"feature": left, "children": []}
                j = i + 1

                while j < n:
                    r = rows[j]
                    a, b, ax0 = r["left"], r["right"], r["left_x0"]

                    # child header: left text, right empty, deeper indent
                    if a and not b and ax0 is not None and (ax0 - parent_x0) >= INDENT_DELTA:
                        child_title = a
                        child_items = []
                        k = j + 1
                        while k < n:
                            rr = rows[k]
                            ca, cb, cax0 = rr["left"], rr["right"], rr["left_x0"]

                            # item by bullet in either column
                            if (is_bullet(ca) and (cb is None or cb)) or (is_bullet(cb) and (ca is None or ca)):
                                ca_t = re.sub(bullet_pat, '', ca or '').strip()
                                cb_t = re.sub(bullet_pat, '', cb or '').strip()
                                feat = ca_t if ca_t else (cb_t or "")
                                val  = (cb if is_bullet(ca) else ca)  # take the opposite column as value if present
                                child_items.append((feat, (val or "").strip()))
                                k += 1
                                continue

                            # item: left text + right looks like a value
                            if ca and cb and looks_like_value(cb):
                                child_items.append((ca, cb))
                                k += 1
                                continue

                            # stop when next child header or a normal 2-col row with shallow indent
                            if ca and not cb and cax0 is not None and (cax0 - ax0) >= INDENT_DELTA:
                                # deeper single-line item (rare) -> use text as feature with empty value
                                child_items.append((ca.strip(), ""))
                                k += 1
                                continue

                            break

                        if child_items:
                            parent["children"].append({"feature": child_title, "items": child_items})
                            used_hierarchy = True
                            j = k
                            continue

                        break  # no items -> end parent block

                    # a normal 2-col row ends the parent block
                    if a and b:
                        break

                    j += 1

                if parent["children"]:
                    groups.append(parent)
                    i = j
                    continue

            i += 1

        if used_hierarchy and groups:
            return {"type": 2, "groups": groups}

        # fallback: flat pairs
        flat = []
        for r in rows:
            a = (r["left"] or "").strip() if r["left"] else None
            b = (r["right"] or "").strip() if r["right"] else None
            if a and b:
                flat.append([a, b])
        return {"type": 1, "df": flat}

    def extract_part_number(self):
    # Try to find Siemens' 'Part number' in full text.
        try:
            text = self.extract_text()

            # if no match, try pattern with hyphens
            m = re.search(r'\b[0-9A-Z]{2,}(?:-[0-9A-Z]{2,})+\b', text)
            if m:
                return m.group(0)

            # if no match, try another common pattern
            m2 = re.search(r'Part[ -]?number[:：]?\s*([0-9A-Z-]{5,})', text, re.IGNORECASE)
            if m2:
                return m2.group(1)
        except Exception as e:
            print(f"Could not extract part number: {e}")
        return "unknown"


