
"""
This script reads all Entity idShorts from a Mechanical_break_down.csv file
and searches for files with the same stem name under a given
product_files directory.

print
1. idShorts from the CSV that have no matching file in the directory.
2. File stems in the directory that were not matched by any idShort.
"""

from __future__ import annotations
from pathlib import Path
import pandas as pd
import re
from collections import defaultdict


base_dir = Path(__file__).resolve().parent

input_dir = base_dir / "input"
output_dir = base_dir / "output"
product_files_dir = base_dir.parent / "1.create_aas_from_product_info" / "product_files"

csv_path = output_dir / "Mechanical_break_down_manual.csv"
search_root = product_files_dir


def norm(s: str):
    """Normalize """
    s = s.strip().lower()
    s = re.sub(r"[._]+", ".", s)
    s = re.sub(r"[\s_\-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s

def load_idshorts(path: Path):
    """Load unique idShorts from the CSV file where typeName == "Entity". Returns a list of idShort strings."""
    df = pd.read_csv(path, encoding="utf-8-sig")
    ents = df[df["typeName"].astype(str).str.strip().str.lower() == "entity"]["idShort"]
    seen, out = set(), []
    for x in ents:
        s = str(x).strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out

def index_file_stems(root: Path):
    """
    Build an index of all file stems in the directory.
    The result is a dictionary
    """
    stem_map = defaultdict(set)
    for p in root.rglob("*"):
        if p.is_file():
            stem_map[norm(p.stem)].add(p.stem)
    return stem_map

def main():
    """
    Main routine:
    1. Load idShorts from the CSV.
    2. Index file stems under product_files.
    3. Report idShorts that are missing files.
    4. Report file stems that are unmatched by any idShort.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")
    if not search_root.exists():
        raise FileNotFoundError(f"Search root not found: {search_root}")

    idshorts = load_idshorts(csv_path)
    stem_map = index_file_stems(search_root)
    all_norm_stems = set(stem_map.keys())

    missing_idshorts = []
    matched_norm_stems = set()

    # Match idShorts against normalized file stems
    for name in idshorts:
        n = norm(name)
        n_compact = n.replace(" ", "")

        hit_key = None
        if n in all_norm_stems:
            hit_key = n
        elif n_compact in all_norm_stems:
            hit_key = n_compact

        if hit_key is not None:
            matched_norm_stems.add(hit_key)
        else:
            missing_idshorts.append(name)

    # --- Print missing idShorts ---
    if missing_idshorts:
        missing_sorted = sorted(missing_idshorts, key=str.casefold)
        print("Missing files for the following idShorts (alphabetical):")
        for m in missing_sorted:
            print(f" - {m}")
        print(f"\nTotal missing: {len(missing_sorted)} (searched under: {search_root})")
    else:
        print("All Entity idShorts have a matching file in product_files.")

    # --- Print unmatched file stems ---
    unmatched_norm_stems = all_norm_stems - matched_norm_stems

    if unmatched_norm_stems:
        # Pick a representative original stem for each normalized stem
        representative_original_stems = [
            sorted(stem_map[norm_stem], key=str.casefold)[0] for norm_stem in unmatched_norm_stems
        ]
        rep_sorted = sorted(representative_original_stems, key=str.casefold)

        print("\nFile stems in product_files not matched by any idShort (alphabetical):")
        for s in rep_sorted:
            print(f" - {s}")
        print(f"\nTotal unmatched file stems: {len(rep_sorted)} (from: {search_root})")
    else:
        print("\nAll file stems in product_files were matched by some idShort.")

if __name__ == "__main__":
    main()
