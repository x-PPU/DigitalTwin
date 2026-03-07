#!/usr/bin/env python3.12.4
"""
This script extracts tables from a PDF and converts them into a two-column format.

The `PDFExtractor` class provides methods to:
- Extract tables from a PDF using Camelot.
- Extract text elements and titles from the PDF.
- Convert four-column tables into a two-column format.

Suitable for Balluff company product PDF documents.

The `main` function processes the PDF and prints the resulting tables.
"""
import re
import sys
import camelot
from pdfminer.high_level import extract_text, extract_pages
from pdfminer.layout import LAParams, LTTextContainer, LTTextLine, LTChar
import pandas as pd

class PDFExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.tables = []

    def extract_tables_camelot(self, pages='all', outpath=""):
        """
        This function extracts tables from a PDF using camelot.
        @param outpath: output path
        @param pages: pages of the pdf
        @return: a list of tables
        """
        if pages == 'all':
            p = 'all'
        else:
            p = f"{pages[0]}-{pages[1]}"
        tables = camelot.read_pdf(self.pdf_path, flavor='stream', pages=p)
        for i in range(tables.n):
            self.tables.append(tables[i])
        self.num_tables = tables.n
        if outpath:
            tables.export(outpath)
        return self.tables

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
            df = table.df

            if df.shape[1] == 4:
                data = df.values.tolist()
                all_data.extend(data)

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

        # Extract lines and title
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

        # Extract description starting from the line after the title
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

    def convert_table_to_two_columns(self, df):
        """
        Convert a 4-column DataFrame into a 2-column DataFrame by merging columns.
        The content of columns 2 and 3 is placed after the content of columns 0 and 1.
        """
        # Split the DataFrame into two parts: first half and second half
        first_half = df.iloc[:, :2]
        second_half = df.iloc[:, 2:4]
        
        # Drop any rows that are completely empty in both halves
        second_half = second_half.dropna(how='all').reset_index(drop=True)
        first_half = first_half.dropna(how='all').reset_index(drop=True)
        
        # Concatenate the two parts vertically, ignoring the original index
        combined = pd.concat([first_half, second_half], ignore_index=True)
        
        return combined

    def convert_all_tables_to_two_columns(self):
        """
        Convert all 4-column tables to 2-column tables.
        """
        converted_tables = []
        for table in self.tables:
            df = table.df  # Extract the DataFrame from the camelot Table object
            if df.shape[1] == 4:
                converted_df = self.convert_table_to_two_columns(df)
                converted_tables.append(converted_df)
        return converted_tables

    def extract_order_code(self):
        """
        Extract 'Order Code' (best-effort). Returns 'unknown' if not found.
        """
        try:
            txt = self.extract_text()
            # e.g. "Order Code: BCS0055"
            m = re.search(r'Order\s*Code[:：]?\s*([A-Za-z0-9._/\-]+)', txt, re.IGNORECASE)
            if m:
                return m.group(1)
        except Exception:
            pass
        return "unknown"
    

# Test and Print
def _clean(s):
    return ("" if s is None else str(s)).strip()

def _normalize_rows_to_two_cols(rows):
    """
    Ensure every row has exactly two strings.
    If there are more than 2 cells, merge the extras into the 2nd column.
    """
    fixed = []
    for r in rows:
        if isinstance(r, (list, tuple)):
            if len(r) >= 2:
                first = _clean(r[0])
                second = " | ".join(_clean(x) for x in r[1:])
                fixed.append([first, second])
            elif len(r) == 1:
                fixed.append([_clean(r[0]), ""])
        else:
            fixed.append([_clean(r), ""])
    return fixed

def _pretty_print_two_col(rows):
    rows2 = _normalize_rows_to_two_cols(rows)
    if not rows2:
        print("(no rows)")
        return
    w0 = max(len(rows2[0][0]), *(len(r[0]) for r in rows2))
    w1 = max(len("Value"), *(len(r[1]) for r in rows2))
    w0 = max(w0, len("Feature"))
    print(f"{'Feature'.ljust(w0)} | {'Value'.ljust(w1)}")
    print(f"{'-'*w0}-+-{'-'*w1}")
    for a, b in rows2:
        print(f"{a.ljust(w0)} | {b.ljust(w1)}")


if __name__ == "__main__":
    # Default demo path; you can pass a path as the first CLI arg
    pdf_path = r"D:/xPPU_DT-main/AAScreation/1.create_aas_from_product_info/product_files/Balluff/Balluff BUS M18K0-XAER-040-S92K Ultrasonic Sensor.pdf"
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]

    ext = PDFExtractor(pdf_path)
    ext.extract_tables_camelot(pages='all')
    order_code = ext.extract_order_code()
    print(f"\nOrder Code: {order_code}\n")

    # Build a single 2-col view for terminal
    two_col_tables = ext.convert_all_tables_to_two_columns()
    merged_rows = []
    for df in two_col_tables:
        if df.shape[1] >= 2:
            merged_rows.extend(df.iloc[:, :2].values.tolist())

    _pretty_print_two_col(merged_rows)

