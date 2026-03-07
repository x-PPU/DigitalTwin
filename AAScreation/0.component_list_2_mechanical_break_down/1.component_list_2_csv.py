#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate Mechanical_break_down.csv from ComponentList1.xlsx.

Steps:
1) Read Excel from ./input/ComponentList1.xlsx
2) Validate required columns
3) Clean and normalize rows
4) Group by module and emit SMC/Entity/Reference/End blocks
5) Save CSV to ./output/Mechanical_break_down.csv
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd

base_dir = Path(__file__).resolve().parent
input_xlsx = base_dir / "input" / "ComponentList1.xlsx"
output_dir = base_dir / "output"
output_csv = output_dir / "Mechanical_break_down_base1.csv"

module_map = {
    "Stack": "Magazine",
    "Crane": "Crane",
    "Stampt": "Stamping_Device",
    "LSC": "Sorting_Conveyor",
}

required_cols = ["Module Name", "Manufacturer", "ModellNr.", "Subtype"]

def safe_str(x):
    """Return a trimmed string; empty string if value is NaN."""
    if pd.isna(x):
        return ""
    return str(x).strip()

def compose_idshort(row: pd.Series):
    """Compose idShort as 'Manufacturer ModellNr. Subtype' (skip empty parts)."""
    parts = [safe_str(row.get("Manufacturer")),
             safe_str(row.get("ModellNr.")),
             safe_str(row.get("Subtype"))]
    parts = [p for p in parts if p]
    return " ".join(parts)

def validate_columns(df: pd.DataFrame):
    """Ensure the Excel contains all required columns."""
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

def load_excel(path: Path):
    """Load the Excel file."""
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    # Let pandas auto-select engine
    return pd.read_excel(path)

def preprocess(df: pd.DataFrame):
    """Clean, trim, and forward-fill module names; drop pure headers."""
    # Drop all-empty rows and trim key columns
    df = df.dropna(how="all").reset_index(drop=True)

    for col in ["Module Name", "Manufacturer", "ModellNr.", "Subtype"]:
        df[col] = df[col].apply(safe_str)

    # Forward-fill empty module names with the last seen non-empty name
    df["Module Name"] = df["Module Name"].replace("", pd.NA).ffill()

    # Keep rows where at least Manufacturer or ModellNr. is non-empty
    df = df[(df["Manufacturer"] != "") | (df["ModellNr."] != "")].reset_index(drop=True)
    return df

def emit_row(typename: str,
             idshort: str = "",
             value: str = "",
             valuetype: str = "",
             category: str = "",
             desc_en: str = "",
             desc_de: str = "",
             semantic_id: str = ""):
    """Create a single output row with unified keys."""
    return {
        "typeName": typename,
        "idShort": idshort,
        "value": value,
        "valueType": valuetype,
        "category": category,
        "descriptionEN": desc_en,
        "descriptionDE": desc_de,
        "semanticId": semantic_id,
    }

def build_output_rows(df: pd.DataFrame):
    """Build the Mechanical_break_down rows from the cleaned dataframe."""
    rows = []

    for src_module, smc_name in module_map.items():
        # SMC start
        rows.append(emit_row("SubmodelElementCollection", smc_name))

        # Filter parts under this module (case-insensitive match)
        sub = df[df["Module Name"].str.lower() == src_module.lower()]
        for _, r in sub.iterrows():
            idshort = compose_idshort(r)
            if not idshort:
                continue

            rows.append(emit_row("Entity", idshort))
            rows.append(emit_row("ReferenceElement", "Reference"))
            rows.append(emit_row("End-Entity"))

        # SMC end
        rows.append(emit_row("End-SubmodelElementCollection"))

    return rows

def write_csv(rows, path: Path):
    """Save rows to CSV with the specified column order."""
    cols = ["typeName", "idShort", "value", "valueType", "category",
            "descriptionEN", "descriptionDE", "semanticId"]
    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False, encoding="utf-8-sig")

def main():
    df = load_excel(input_xlsx)
    validate_columns(df)
    df = preprocess(df)
    rows = build_output_rows(df)
    write_csv(rows, output_csv)


if __name__ == "__main__":
    main()
