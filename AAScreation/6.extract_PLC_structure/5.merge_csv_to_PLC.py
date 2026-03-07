#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Merge two SMC-CSV files (same header) and fix idShort values.

- Append csv_in2 BELOW csv_in1 (keep the header from csv_in1; skip csv_in2 header)
- For each non-empty idShort, if it does not start with a letter [A-Za-z],
  change it to "None" + original (but do not double-prefix if it already
  starts with "None").

Defaults:
  csv_in1 = ./PLC_base3.csv
  csv_in2 = ./IO_smc.csv
  csv_out = ./PLC.csv
"""

import csv
import re
import sys
from pathlib import Path


def read_rows(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def write_rows(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)


def pad_or_trim(row, ncols):
    # Ensure row has exactly ncols elements
    if len(row) < ncols:
        return row + [""] * (ncols - len(row))
    if len(row) > ncols:
        return row[:ncols]
    return row


def merge_and_fix(csv_in1: Path, csv_in2: Path, csv_out: Path):
    rows1 = read_rows(csv_in1)
    rows2 = read_rows(csv_in2)

    if not rows1:
        raise RuntimeError(f"Empty CSV: {csv_in1}")
    if not rows2:
        raise RuntimeError(f"Empty CSV: {csv_in2}")

    header = rows1[0]
    ncols = len(header)

    # Basic header check (same column names)
    if rows2[0] != header:
        # If headers differ only by BOM/whitespace, you can relax this as needed
        raise RuntimeError("Headers differ between the two CSV files.")

    # Build merged rows: header + rows1(body) + rows2(body)
    out_rows = [header]
    out_rows += [pad_or_trim(r, ncols) for r in rows1[1:]]
    out_rows += [pad_or_trim(r, ncols) for r in rows2[1:]]

    # Find idShort column index
    try:
        id_idx = header.index("idShort")
    except ValueError:
        raise RuntimeError("Header does not contain 'idShort' column.")

    # Fix idShort: non-empty & not starting with letter -> prefix 'None'
    for i in range(1, len(out_rows)):
        val = out_rows[i][id_idx].strip()
        if not val:
            continue
        # Starts with ASCII letter?
        if not re.match(r"[A-Za-z]", val[0]):
            # Avoid double 'None' if re-running
            if not val.startswith("None"):
                out_rows[i][id_idx] = "None" + val
            else:
                out_rows[i][id_idx] = val  # already has 'None'
        else:
            out_rows[i][id_idx] = val  # normalize whitespace

    write_rows(csv_out, out_rows)
    print(f"Merged {len(rows1)-1} + {len(rows2)-1} rows to {csv_out}")


def main(argv):
    script_dir = Path(__file__).parent.resolve()
    default_in1 = script_dir / "PLC_base3.csv"
    default_in2 = script_dir / "IO_smc.csv"
    default_out = script_dir / "PLC_base5.csv"

    csv_in1 = Path(argv[0]).resolve() if len(argv) >= 1 else default_in1
    csv_in2 = Path(argv[1]).resolve() if len(argv) >= 2 else default_in2
    csv_out = Path(argv[2]).resolve() if len(argv) >= 3 else default_out

    merge_and_fix(csv_in1, csv_in2, csv_out)


if __name__ == "__main__":
    main(sys.argv[1:])
