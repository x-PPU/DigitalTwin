#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Class-based extractor for OTT datasheets.

Features:
- Locate the 'Elektrische Daten' table on the page.
- Trim rows to the electrical spec part:
  (1) stop where the last column becomes empty; fallback to
  (2) stop at the row 'fallende Flanke' (inclusive).
- Translate German parameter names in the first column to English.
- Merge 'Flankensteilheit + steigende/fallende Flanke' into a single row
  named 'Output Rise Time' or 'Output Fall Time'.
- Remove spacer columns that are empty across all data rows (even if header is '-' etc.).
- Normalize header to:
    ["Parameter", "Symbol", "Testbedingung", "min.", "nom.", "max.", "Einheit"]

Public API:
    extractor = OttPDFExtractor(pdf_path)
    table = extractor.extract_table()
    part_no = extractor.extract_part_number()
"""

from __future__ import annotations
import re
from typing import List, Optional, Tuple
import pdfplumber
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams


class OttPDFExtractor:
    TITLE_PATTERN = re.compile(r"^\s*Elektrische\s+Daten\s*$", re.IGNORECASE)
    NEXT_TITLE_CANDIDATES = [
        re.compile(r"^\s*Ausgangsbeschaltung\s*$", re.IGNORECASE),
        re.compile(r"^\s*Ausgänge\s*$", re.IGNORECASE),
        re.compile(r"^\s*Stecker\s*$", re.IGNORECASE),
        re.compile(r"^\s*Anschluss\s*$", re.IGNORECASE),
    ]

    GERMAN_TO_EN = {
        "versorgungsspannung": "Supply Voltage",
        "sättigungsspannung": "Output Saturation Voltage",
        "leckstrom": "Output Leakage Current",
        "stromaufnahme": "Supply Current",
        "steigende flanke": "Output Rise Time",
        "fallende flanke": "Output Fall Time",
    }

    STD_HEADER = ["Parameter", "Symbol", "Testbedingung", "min.", "nom.", "max.", "Einheit"]

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path

    def extract_table(self) -> List[List[str]]:
        raw = self._extract_raw_table()
        trimmed = self._trim_rows(raw)
        translated = self._translate_and_merge(trimmed)
        squeezed = self._remove_empty_columns(translated)
        normalized = self._normalize_header(squeezed)
        return normalized

    def extract_part_number(self) -> str:
        try:
            txt = extract_text(self.pdf_path, laparams=LAParams())
            m = re.search(r'Part\s*number[:：]?\s*([A-Za-z0-9\-_/\.]+)', txt, re.IGNORECASE)
            if m:
                return m.group(1)
        except Exception:
            pass
        return "unknown"

    def _clean(self, s) -> str:
        if s is None:
            return ""
        return re.sub(r"\s+", " ", str(s)).strip()

    def _join_line(self, words_row) -> str:
        ws = sorted(words_row, key=lambda w: w["x0"])
        return self._clean(" ".join(w["text"] for w in ws if w.get("text")))

    def _group_words_by_line(self, page) -> List[Tuple[float, list, str]]:
        words = page.extract_words(use_text_flow=True, keep_blank_chars=False) or []
        buckets = {}
        for w in words:
            y_mid = round((w["top"] + w["bottom"]) / 2, 1)
            buckets.setdefault(y_mid, []).append(w)
        rows = []
        for y, ws in buckets.items():
            txt = self._join_line(ws)
            if txt:
                rows.append((y, ws, txt))
        rows.sort(key=lambda t: t[0])
        return rows

    def _find_title_and_next(self, page) -> Tuple[Optional[float], Optional[float]]:
        rows = self._group_words_by_line(page)
        y_title = None
        y_next = None
        for y, ws, txt in rows:
            if self.TITLE_PATTERN.match(txt):
                y_title = max(w["bottom"] for w in ws)
                break
        if y_title is None:
            return None, None
        for y, ws, txt in rows:
            if y <= y_title:
                continue
            if any(pat.match(txt) for pat in self.NEXT_TITLE_CANDIDATES):
                y_next = min(w["top"] for w in ws)
                break
        if y_next is None:
            y_next = page.height - 2
        return y_title, y_next

    def _looks_like_table(self, tbl: List[List[str]]) -> bool:
        if not tbl or not tbl[0]:
            return False
        header = " ".join(self._clean(c).lower() for c in tbl[0] if c)
        needed = ["parameter", "symbol", "min", "max", "einheit"]
        return sum(1 for k in needed if k in header) >= 3

    def _try_extract_in_region(self, page, bbox) -> Optional[List[List[str]]]:
        reg = page.crop(bbox)
        settings_list = [
            {"vertical_strategy": "text", "horizontal_strategy": "text",
             "text_x_tolerance": 2, "text_y_tolerance": 2},
            {"vertical_strategy": "text", "horizontal_strategy": "lines"},
            {"vertical_strategy": "lines", "horizontal_strategy": "text"},
            {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
            {"vertical_strategy": "edges", "horizontal_strategy": "text"},
            {"vertical_strategy": "text", "horizontal_strategy": "edges"},
        ]
        for st in settings_list:
            tables = reg.extract_tables(table_settings=st) or []
            for t in tables:
                tt = [[self._clean(c) for c in row] for row in t if any(self._clean(c) for c in row)]
                if self._looks_like_table(tt):
                    return tt
        return None

    def _extract_raw_table(self) -> List[List[str]]:
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                y_top, y_bot = self._find_title_and_next(page)
                if y_top is None:
                    continue
                for bbox in [
                    (0, y_top + 2, page.width, y_bot - 2),
                    (0, y_top + 0, page.width, min(page.height, y_bot + 80)),
                    (0, max(0, y_top - 20), page.width, min(page.height, y_bot + 200)),
                ]:
                    tbl = self._try_extract_in_region(page, bbox)
                    if tbl:
                        return tbl
        raise RuntimeError("Elektrische Daten table not found.")

    def _trim_rows(self, table: List[List[str]]) -> List[List[str]]:
        if not table or len(table) <= 1:
            return table
        cut_idx = None
        for i, row in enumerate(table[1:], start=1):
            last = self._clean(row[-1]) if row else ""
            if last == "":
                cut_idx = i - 1
                break
        if cut_idx is not None and cut_idx >= 1:
            return table[:cut_idx + 1]
        for i, row in enumerate(table[1:], start=1):
            first = self._clean(row[0]).lower() if row else ""
            if first.startswith("fallende flanke"):
                return table[:i + 1]
        return table

    def _translate_and_merge(self, table: List[List[str]]) -> List[List[str]]:
        if not table:
            return table
        out = [table[0]]
        i = 1
        while i < len(table):
            row = table[i]
            first = self._clean(row[0]).lower() if row else ""

            if first == "flankensteilheit" and (i + 1) < len(table):
                next_first = self._clean(table[i + 1][0]).lower() if table[i + 1] else ""
                if next_first.startswith("steigende flanke"):
                    merged = list(row)
                    merged[0] = "Output Rise Time"
                    out.append(merged)
                    i += 2
                    continue
                if next_first.startswith("fallende flanke"):
                    merged = list(row)
                    merged[0] = "Output Fall Time"
                    out.append(merged)
                    i += 2
                    continue

            key = first
            if key in self.GERMAN_TO_EN:
                row = list(row)
                row[0] = self.GERMAN_TO_EN[key]
            out.append(row)
            i += 1
        return out

    def _remove_empty_columns(self, table: List[List[str]]) -> List[List[str]]:
        if not table:
            return table
        EMPTY_HDR = {"", "-", "—", "–", "."}
        EMPTY_CELL = {"", "-", "."}

        cols = max(len(r) for r in table)
        keep_idx = []
        for c in range(cols):
            header_txt = self._clean(table[0][c] if c < len(table[0]) else "")
            header_meaningful = header_txt not in EMPTY_HDR

            has_data = False
            for r in table[1:]:
                val = self._clean(r[c] if c < len(r) else "")
                if val not in EMPTY_CELL:
                    has_data = True
                    break

            if header_meaningful or has_data:
                keep_idx.append(c)

        squeezed = []
        for r in table:
            squeezed.append([(r[i] if i < len(r) else "") for i in keep_idx])
        return squeezed

    def _normalize_header(self, table: List[List[str]]) -> List[List[str]]:
        if not table:
            return table
        cols = max(len(r) for r in table)
        norm = []
        for r in table:
            rr = list(r) + [""] * (cols - len(r))
            norm.append(rr[: len(self.STD_HEADER)])
        norm[0] = list(self.STD_HEADER)
        return norm


if __name__ == "__main__":
    path = r"D:/xPPU_DT-main/AAScreation/1.create_aas_from_product_info/product_files/Ott/Ott XDS 035 005-03 Motor.pdf"
    tbl = OttPDFExtractor(path).extract_table()
    for r in tbl:
        print(" | ".join(r))
