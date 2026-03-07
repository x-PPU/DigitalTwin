#!/usr/bin/env python3.12.4
"""
Extractor for BERNSTEIN PDFs.
- Uses pdfplumber to get tables from all pages.
- Returns a mixed list of table rows: each row is either [feature, value] or [feature, abbrev, value].
- Keeps original text; no unit post-processing here.
"""

import re
import sys
import pdfplumber
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams

HEADER_CANDIDATES = {
    "electrical data", "mechanical data", "technical data",
    "emc", "eu conformity", "environmental data"
}

class PDFExtractorBernstein:
    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.tables = []

    def extract_tables_plumber(self):
        """Extract raw tables from all pages using pdfplumber."""
        self.tables = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for raw in tables:
                    clean = [row for row in raw if row and any((c or "").strip() for c in row)]
                    if clean:
                        self.tables.append(clean)

    def _is_header_row(self, row):
        # check if the row is likely a header
        cells = [(c or "").strip() for c in row]
        nonempty = [c for c in cells if c]
        if len(nonempty) == 1:
            text = nonempty[0].lower()
            # check against known header candidates
            if text in HEADER_CANDIDATES or text.endswith(":"):
                return True
        # 3+ columns with "feature" and "value" in first two cells
        if len(cells) >= 2:
            left = cells[0].lower()
            right = cells[1].lower()
            if ("feature" in left and "value" in right) or ("abbrev" in left) or ("short" in left):
                return True
        return False

    def extract_stream(self):
        """
        Flatten to a single list of rows.
        - 3-col rows => [feature, abbrev, value]
        - 2-col rows => [feature, value]
        Other widths are ignored.
        """
        out = []
        for tbl in self.tables:
            for row in tbl:
                cells = [(c or "").strip() for c in row]
                # skip header rows
                if self._is_header_row(cells):
                    continue

                # 2 or 3 columns
                if len(cells) >= 3 and cells[0] and cells[2]:
                    # 3 col（feature, abbrev, value）
                    out.append([cells[0], cells[1], cells[2]])
                elif len(cells) >= 2 and cells[0] and cells[1]:
                    # 2 cpl（feature, value）
                    out.append([cells[0], cells[1]])
                else:
                    continue
        return {"type": "mixed", "df": out}

    def extract_text(self):
        laparams = LAParams()
        return extract_text(self.pdf_path, laparams=laparams)

    def extract_part_number(self):
        """
        Try to find BERNSTEIN's 'Article number' (or 'Article no.') in full text.
        Fallback: return 'unknown'.
        """
        try:
            text = self.extract_text()
            m = re.search(r'(Article\s+(?:number|no\.?))[:：]?\s*([A-Za-z0-9-]+)', text, re.IGNORECASE)
            if m:
                return m.group(2)
        except Exception as e:
            print(f"Part number extraction failed: {e}")
        return "unknown"

    def extract_part_number(self):
        """
        Try to find BERNSTEIN's Article number / Article no. / Art.-No. / Bestell-Nr. in full text.
        Fallback: return 'unknown'.
        """
        try:
            text = self.extract_text()
            # common variants
            pat = re.compile(
                r'(Article\s*(?:number|no\.?)|Art\.\-?No\.?|Order\s*No\.?|Bestell\-?Nr\.)[:：]?\s*([A-Za-z0-9\-_/\.]+)',
                re.IGNORECASE
            )
            m = pat.search(text)
            if m:
                return m.group(2)
        except Exception as e:
            print(f"Part number extraction failed: {e}")
        return "unknown"


# Test and Print
def _clean(s): return ("" if s is None else str(s)).strip()

def _to_three_cols(rows):
    """Normalize mixed 2/3 col rows to 3 columns: [feature, symbol, value]."""
    out = []
    for r in rows:
        if len(r) >= 3:
            out.append([_clean(r[0]), _clean(r[1]), _clean(r[2])])
        elif len(r) == 2:
            out.append([_clean(r[0]), "", _clean(r[1])])
    return out

def _pp_three_cols(rows3):
    if not rows3:
        print("(no rows)")
        return
    w0 = max(len("Feature"), *(len(r[0]) for r in rows3))
    w1 = max(len("Symbol"),  *(len(r[1]) for r in rows3))
    w2 = max(len("Value"),   *(len(r[2]) for r in rows3))
    print(f"{'Feature'.ljust(w0)} | {'Symbol'.ljust(w1)} | {'Value'.ljust(w2)}")
    print(f"{'-'*w0}-+-{'-'*w1}-+-{'-'*w2}")
    for a,b,c in rows3:
        print(f"{a.ljust(w0)} | {b.ljust(w1)} | {c.ljust(w2)}")


if __name__ == "__main__":
    pdf_path = r"D:/xPPU_DT-main/AAScreation/1.create_aas_from_product_info/product_files/Bernstein/Bernstein OT18RT-DPTP-0100-CL Diffuse Reflection Sensor.pdf"
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]

    ext = PDFExtractorBernstein(pdf_path)
    ext.extract_tables_plumber()
    data = ext.extract_stream()

    part = ext.extract_part_number()
    print(f"\nArticle number: {part}\n")

    rows3 = _to_three_cols(data["df"])
    _pp_three_cols(rows3)