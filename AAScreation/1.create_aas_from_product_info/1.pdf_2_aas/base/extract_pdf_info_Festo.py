
#!/usr/bin/env python3.12.4
"""
Extracts tables and text from PDF documents using local libraries only.
Uses `pdfplumber` for table extraction and `pdfminer` for text extraction.
"""

import re
import csv
import sys
import pdfplumber
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams, LTTextContainer, LTChar, LTTextLine
from pdfminer.high_level import extract_pages

class PDFExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.tables = []

    def extract_tables_plumber(self):
        """Extract tables from all pages using pdfplumber."""
        self.tables = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for raw_table in tables:
                    clean_table = [row for row in raw_table if row and any(cell is not None and cell.strip() for cell in row)]
                    self.tables.append(clean_table)

    def extract_text(self):
        laparams = LAParams()
        text = extract_text(self.pdf_path, laparams=laparams)
        return text

    def extract_text_elements(self):
        laparams = LAParams()
        pages = extract_pages(self.pdf_path, laparams=laparams)
        elements = []
        for page_layout in pages:
            for element in page_layout:
                if isinstance(element, LTTextContainer):
                    elements.extend(element)
        return elements

    def extract_stream(self):
        all_data = []
        for table in self.tables:
            if len(table) > 0 and len(table[0]) == 2:
                header = table[0]
                if header[0].strip().lower() == 'Feature' and header[1].strip().lower() == 'Value':
                    table = table[1:]  # skip header
                all_data.extend(table)
            else:
                print(f"Skipped non-2-column table or empty table")
        return {"type": 1, "df": all_data}

    def extract_title_and_description(self):
        elements = self.extract_text_elements()
        title = ""
        description = ""
        title_font = None
        title_size = None
        lines = []
        title_found = False
        title_end_line_index = 0

        for line_index, element in enumerate(elements):
            if isinstance(element, LTTextLine):
                line_text = element.get_text().strip()
                lines.append(line_text)
                if not title_found:
                    for char in element:
                        if isinstance(char, LTChar):
                            if not title:
                                title += char.get_text()
                                title_font = char.fontname
                                title_size = char.size
                            else:
                                if char.fontname == title_font and char.size == title_size:
                                    title += char.get_text()
                                else:
                                    title_found = True
                                    title_end_line_index = line_index
                                    break
                else:
                    break

        if title_found:
            title = title.strip()

        description_lines = []
        current_font = None
        current_size = None
        for element in elements[title_end_line_index + 1:]:
            if isinstance(element, LTTextLine):
                line_text = element.get_text().strip()
                if not line_text:
                    break
                for char in element:
                    if isinstance(char, LTChar):
                        if current_font is None and current_size is None:
                            current_font = char.fontname
                            current_size = char.size
                        elif char.fontname != current_font or char.size != current_size:
                            break
                else:
                    description_lines.append(line_text)
                    continue
                break

        description = " ".join(description_lines).strip()
        return title, description

    def extract_part_number(self):
        try:
            full_text = self.extract_text()
            match = re.search(r'Part number[:：]?\s*(\d+)', full_text)
            if match:
                return match.group(1)
        except Exception as e:
            print(f"Could not extract part number: {e}")
        return "unknown"

def save_to_csv(title, description, tables, csv_path):
    with open(csv_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Title", title])
        writer.writerow(["Description", description])
        writer.writerow([])
        for idx, table in enumerate(tables):
            writer.writerow([f"Table {idx + 1}"])
            for row in table:
                writer.writerow(row)
            writer.writerow([])

def _clean_cell(s):
    return re.sub(r"\s+", " ", "" if s is None else str(s)).strip()

def _pretty_print_feature_value(rows):
    """
    Print a 2-column table to terminal with header 'Feature | Value'.
    'rows' is a list like [[Feature, Value], ...]
    """
    header = ["Feature", "Value"]
    # width calculation
    w0 = max(len(_clean_cell(r[0] if len(r) > 0 else "")) for r in rows) if rows else 0
    w1 = max(len(_clean_cell(r[1] if len(r) > 1 else "")) for r in rows) if rows else 0
    w0 = max(w0, len(header[0]))
    w1 = max(w1, len(header[1]))

    print(f"{header[0].ljust(w0)} | {header[1].ljust(w1)}")
    print(f"{'-'*w0}-+-{'-'*w1}")
    for r in rows:
        f = _clean_cell(r[0] if len(r) > 0 else "")
        v = _clean_cell(r[1] if len(r) > 1 else "")
        print(f"{f.ljust(w0)} | {v.ljust(w1)}")


if __name__ == "__main__":
    # Default demo path; you can pass a PDF path as the first CLI arg
    path = r"D:/xPPU_DT-main/AAScreation/1.create_aas_from_product_info/product_files/Festo/Festo ADVU-16-10-P-A Compact cylinder.pdf"
    if len(sys.argv) > 1:
        path = sys.argv[1]

    extractor = PDFExtractor(path)
    extractor.extract_tables_plumber()
    stream = extractor.extract_stream()
    rows = stream.get("df", [])

    pn = extractor.extract_part_number()
    print(f"\nPart number: {pn}\n")


    _pretty_print_feature_value(rows)