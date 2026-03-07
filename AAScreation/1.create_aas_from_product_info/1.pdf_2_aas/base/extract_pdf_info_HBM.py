#!/usr/bin/env python3.12.4
"""
This script provides a `PDFExtractor` class for extracting and processing tabular data from product PDF files provided by hbm.
It supports a variety of extraction methods using the `camelot` and `pdfplumber` libraries, and includes functions to clean up 
and convert the extracted data into a structured two-column format. Suitable for complex table structures.

Key functionalities:
- Extract tables from PDF files using Camelot or PDFPlumber.
- Clean and transform table data, handling various formats including tables with different numbers of columns.
- Provide a method to extract table data as a stream, converting it into a standardized format.

Dependencies:
- `camelot`: For reading tables from PDFs.
- `pdfplumber`: For an alternative method to read tables from PDFs.
- `pdfminer`: For extracting text and analyzing PDF layouts.

Camelot requires Ghostscript to process PDF files. Ghostscript download:https://ghostscript.com/releases/gsdnld.html
"""

import camelot
import re
import pdfplumber
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams, LTTextContainer, LTChar, LTTextLine
from pdfminer.high_level import extract_pages

class PDFExtractor:
    def __init__(self, pdf_path):
        self.pdf_path = pdf_path
        self.tables = []

    def extract_tables_camelot(self, pages='all'):
        try:
            tables = camelot.read_pdf(self.pdf_path, flavor='lattice', pages=pages)
            if tables:
                for i in range(tables.n):
                    self.tables.append(tables[i])
                return self.tables
            else:
                raise ValueError("Camelot did not find any tables.")
        except Exception as e:
            print(f"Error using Camelot: {e}. Trying pdfplumber instead.")
            return self.extract_tables_pdfplumber()

    def extract_tables_pdfplumber(self, pages='all'):
        all_tables = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page_num in range(len(pdf.pages)):
                page = pdf.pages[page_num]
                table = page.extract_table()
                if table:
                    cleaned_table = self.clean_pdfplumber_data(table)
                    all_tables.append(cleaned_table)
                    self.tables.append(cleaned_table)
        return all_tables

    def extract_stream(self):
        """
        Extract and transform table data into a new two-column format.
        """
        all_data = []
        for table in self.tables:
            df = table.df if hasattr(table, 'df') else table  # Check if it is a DataFrame

            if isinstance(df, list):
                # If df is a list, process it directly
                for row in df:
                    # Clean or replace special characters
                    row = [re.sub(r'\(cid:\d+\)', '', cell) for cell in row]
                    
                    if len(row) == 4:
                        # Transform rows with 4 columns
                        new_row = [f"{row[0]} {row[1]}", f"{row[3]} {row[2]}"]
                        all_data.append(new_row)
                    elif len(row) == 10:
                        # Transform rows with 10 columns
                        new_row = [f"{row[0]} {row[1]}", f"{row[3]} {row[4]} {row[5]} {row[6]} {row[7]} {row[8]} {row[9]} {row[2]}"]
                        all_data.append(new_row)
                    elif len(row) == 3:
                        # Handle tables with three columns (from the original logic)
                        modified_row = [row[0], f"{row[2]} {row[1]}"]  # Append the unit to the value
                        all_data.append(modified_row)
                    elif len(row) == 2:
                        # Handle tables with two columns (from the original logic)
                        if row[0] in ['Feature'] and row[1] in ['Value']:
                            continue  # Skip the header row
                        all_data.append(row)
            else:
                # If df is a DataFrame, process the DataFrame
                df = df.loc[~df.iloc[:, 0].eq('').cumprod().astype(bool)]

                for row in df.values.tolist():
                    # Clean or replace special characters
                    row = [re.sub(r'\(cid:\d+\)', '', cell) for cell in row]
                    
                    if len(row) == 4:
                        # Transform rows with 4 columns
                        new_row = [f"{row[0]} {row[1]}", f"{row[3]} {row[2]}"]
                        all_data.append(new_row)
                    elif len(row) == 10:
                        # Transform rows with 10 columns
                        new_row = [f"{row[0]} {row[1]}", f"{row[3]} {row[4]} {row[5]} {row[6]} {row[7]} {row[8]} {row[9]} {row[2]}"]
                        all_data.append(new_row)
                    elif len(row) == 3:
                        # Handle tables with three columns (from the original logic)
                        modified_row = [row[0], f"{row[2]} {row[1]}"]  # Append the unit to the value
                        all_data.append(modified_row)
                    elif len(row) == 2:
                        # Handle tables with two columns (from the original logic)
                        if row[0] in ['Feature'] and row[1] in ['Value']:
                            continue  # Skip the header row
                        all_data.append(row)

        return all_data

    def clean_pdfplumber_data(self, data):
        cleaned_data = []
        for row in data:
            # Filter out rows with all None values
            if all(cell is None for cell in row):
                continue

            # Combine fragmented text cells into meaningful data
            combined_row = [cell if cell is not None else "" for cell in row]
            cleaned_data.append(combined_row)

        return cleaned_data