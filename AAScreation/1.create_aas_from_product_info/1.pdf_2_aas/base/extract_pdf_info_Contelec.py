#!/usr/bin/env python3.12.4
"""
Robust extractor for CONTELEC PDFs (3 columns, all left-aligned).
Strategy:
1) Try multiple pdfplumber table settings.
2) If still none, fallback to word-level reconstruction:
   - Build a vertical text density histogram over the left table area.
   - Choose two global cut positions (column separators) that minimize density (fewest word crossings).
   - For each visual line (bucketed by y), assign words to [Feature | Value | Unit] by x compared to the two cuts.
Output rows are normalized to:
  * [feature, value, unit] for 3-col rows
  * [feature, value] for 2-col rows
"""

import re
import pdfplumber
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams

HEADER_CANDIDATES = {
    "electrical data", "mechanical data", "standards",
    "technical data", "features", "applications", "options"
}

def _is_header_row(cells):
    cells = [(c or "").strip() for c in cells]
    nonempty = [c for c in cells if c]
    if len(nonempty) == 1:
        t = nonempty[0].lower()
        if t in HEADER_CANDIDATES or t.endswith(":"):
            return True
    if len(cells) >= 2:
        text = " ".join(cells).lower()
        if "feature" in text and "value" in text:
            return True
        if "unit" in text:
            return True
    return False


class PDFExtractorContelec:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.tables = []

    def extract_tables_plumber(self):
        """Multi-strategy extraction; fallback to histogram-based 3-column splitter."""
        self.tables = []
        strategies = [
            {},  # default
            dict(vertical_strategy="lines", horizontal_strategy="lines",
                 snap_tolerance=3, join_tolerance=3, edge_min_length=15),
            dict(vertical_strategy="text", horizontal_strategy="text",
                 intersection_x_tolerance=5, intersection_y_tolerance=3,
                 text_x_tolerance=2, text_y_tolerance=2),
            dict(vertical_strategy="lines_strict", horizontal_strategy="text",
                 snap_tolerance=3, join_tolerance=3, text_x_tolerance=2),
        ]

        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                page_tables = []
                # 1) Built-in pdfplumber strategies
                for ts in strategies:
                    try:
                        tbs = page.extract_tables(table_settings=ts) if ts else page.extract_tables()
                        if tbs:
                            page_tables.extend(tbs)
                    except Exception:
                        continue
                # 2) If still empty, use fallback: vertical projection + two minimum-density cut lines
                if not page_tables:
                    reconstructed = self._fallback_histogram_splits(page)
                    if reconstructed:
                        page_tables.extend([reconstructed])

                for raw in page_tables:
                    clean = [row for row in raw if row and any((c or "").strip() for c in row)]
                    if clean:
                        self.tables.append(clean)

    # ---------- Core fallback: vertical projection to find two cut lines ----------
    def _fallback_histogram_splits(self, page, bins=300, min_gap_bins=15):
        """
        1) Take the left area of the page (exclude right-side notes/lists), default 75% width;
        2) Build a 1D histogram over this area using words' (x0, x1) text coverage density;
        3) Find two global minima in the histogram (with at least min_gap_bins distance) as column separators;
        4) Using these separators, assign each line's words into [Feature | Value | Unit].
        """
        try:
            words = page.extract_words(
                x_tolerance=2, y_tolerance=3,
                keep_blank_chars=False, use_text_flow=True
            )
        except Exception:
            return None
        if not words:
            return None

        page_w = page.width
        # Keep only the left table area to avoid right-side bullet interference (can tune 0.70~0.8)
        left_limit = page_w * 0.05
        right_limit = page_w * 0.75
        words = [w for w in words if (w["x0"] >= left_limit and w["x1"] <= right_limit)]
        if not words:
            return None

        # 1D histogram
        hist = [0] * bins
        span = right_limit - left_limit
        if span <= 0:
            return None

        for w in words:
            i0 = int(max(0, min(bins - 1, (w["x0"] - left_limit) / span * bins)))
            i1 = int(max(0, min(bins - 1, (w["x1"] - left_limit) / span * bins)))
            for i in range(i0, i1 + 1):
                hist[i] += 1

        # Simple smoothing (moving average)
        def smooth(arr, k=3):
            if k <= 1:
                return arr[:]
            out = []
            for i in range(len(arr)):
                s = 0
                c = 0
                for j in range(i - (k // 2), i + (k // 2) + 1):
                    if 0 <= j < len(arr):
                        s += arr[j]
                        c += 1
                out.append(s / max(1, c))
            return out

        shist = smooth(hist, k=5)

        # Select several candidate minima from the histogram, then pick a pair far enough apart
        candidates = sorted(range(bins), key=lambda i: shist[i])[:50]
        candidates = [i for i in candidates if 20 <= i <= bins - 20]  # avoid edges
        if not candidates:
            return None

        best_pair = None
        best_score = 1e18
        for i in candidates:
            for j in candidates:
                if abs(i - j) < min_gap_bins:
                    continue
                score = shist[i] + shist[j]
                if score < best_score:
                    best_score = score
                    best_pair = (min(i, j), max(i, j))

        if not best_pair:
            return None

        cut1_x = left_limit + (best_pair[0] / bins) * span
        cut2_x = left_limit + (best_pair[1] / bins) * span

        # Assign each line (by y) into three columns
        rows_map = {}
        for w in words:
            key = round(w["top"] / 2)  # y clustering
            rows_map.setdefault(key, []).append(w)

        def join_words(ws):
            return " ".join(w["text"] for w in sorted(ws, key=lambda x: x["x0"])).strip()

        lines = []
        for _, ws in sorted(rows_map.items(), key=lambda kv: kv[0]):
            f_col, v_col, u_col = [], [], []
            for w in sorted(ws, key=lambda x: x["x0"]):
                cx = (w["x0"] + w["x1"]) / 2
                if cx <= cut1_x:
                    f_col.append(w)
                elif cx <= cut2_x:
                    v_col.append(w)
                else:
                    u_col.append(w)

            feature = join_words(f_col)
            value   = join_words(v_col)
            unit    = join_words(u_col)

            # Ignore empty rows and header rows
            cells = [feature, value, unit]
            if not any(cells):
                continue
            if _is_header_row(cells):
                continue

            if feature and value and unit:
                lines.append([feature, value, unit])
            elif feature and value:
                lines.append([feature, value])

        return lines if lines else None

    def extract_stream(self):
        """Normalize to a single flat list (3-col or 2-col rows)."""
        out = []
        for tbl in self.tables:
            for row in tbl:
                cells = [(c or "").strip() for c in row]
                if _is_header_row(cells):
                    continue
                if len(cells) >= 3 and cells[0] and cells[1]:
                    out.append([cells[0], cells[1], cells[2]])
                elif len(cells) >= 2 and cells[0] and cells[1]:
                    out.append([cells[0], cells[1]])
        return {"type": "mixed", "df": out}

    def extract_text(self):
        laparams = LAParams()
        return extract_text(self.pdf_path, laparams=laparams)

    def extract_part_number(self):
        try:
            text = self.extract_text()
            m = re.search(r'(Part|Article)\s+(?:number|no\.?)[:：]?\s*([A-Za-z0-9-/.]+)', text, re.IGNORECASE)
            if m:
                return m.group(2)
        except Exception as e:
            print(f"Part number extraction failed: {e}")
        return "unknown"