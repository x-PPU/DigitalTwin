#/usr/bin/env python3

"""
Insert ReferenceElement rows into ALL child-level items under:
  ReferenceImplementation_Instance / PlcTask_Outputs
  ReferenceImplementation_Instance / PlcTask_Inputs

Rule:
- If an item's descriptionEN matches a row in Operational_Data.csv,
  insert a child row:
    typeName=ReferenceElement
    idShort=Reference
    value=<that row's idShort>
    semanticId=0173-1#01-AGW586#00
- Skip if an identical Reference row already exists.

"""

import csv
from pathlib import Path
import sys


def read_csv_any(path: Path):
    """Read CSV with delimiter sniffing (comma/semicolon/tab) and BOM tolerance."""
    text = path.read_text(encoding="utf-8-sig")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t"])
    except Exception:
        dialect = csv.get_dialect("excel")
    return list(csv.reader(text.splitlines(), dialect))


def write_csv(path: Path, rows):
    """Write rows to CSV file with UTF-8 encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)


def normalize_string(s):
    """Normalize string for comparison: strip and convert to lowercase."""
    return (s or "").strip().lower()


def build_description_to_idshort(op_rows):
    """
    Build mapping from descriptionEN to idShort from Operational_Data.csv.
    
    Args:
        op_rows: Rows from Operational_Data.csv
        
    Returns:
        Dictionary mapping descriptionEN to idShort
    """
    if not op_rows:
        return {}
    
    # Create case-insensitive header mapping
    header = [col.strip() for col in op_rows[0]]
    header_map = {normalize_string(col): idx for idx, col in enumerate(header)}
    
    if "descriptionen" not in header_map or "idshort" not in header_map:
        raise RuntimeError("Operational_Data.csv must contain headers 'descriptionEN' and 'idShort'.")
    
    desc_idx = header_map["descriptionen"]
    id_idx = header_map["idshort"]
    
    # Build mapping dictionary
    mapping = {}
    for row in op_rows[1:]:
        if len(row) <= max(desc_idx, id_idx):
            continue
        description = (row[desc_idx] or "").strip()
        id_short = (row[id_idx] or "").strip()
        if description and id_short:
            mapping[description] = id_short
            
    return mapping


class SmcCsvEditor:
    """Editor for SMC (SubmodelElementCollection) CSV files."""
    
    def __init__(self, rows):
        if not rows:
            raise RuntimeError("Empty CSV.")
        
        self.header = rows[0]
        self.rows = rows
        
        # Validate header structure
        has_type_name = len(self.header) >= 1 and normalize_string(self.header[0]) == "typename"
        has_id_short = len(self.header) >= 2 and normalize_string(self.header[1]) == "idshort"
        
        if not (has_type_name and has_id_short):
            raise RuntimeError("SMC CSV header mismatch (need first two columns: typeName, idShort).")

    def _is_collection_start(self, row):
        """Check if row starts a SubmodelElementCollection."""
        return len(row) >= 1 and row[0] == "SubmodelElementCollection"

    def _is_collection_end(self, row):
        """Check if row ends a SubmodelElementCollection."""
        return len(row) >= 1 and row[0] == "End-SubmodelElementCollection"

    def _get_id_short(self, row):
        """Extract idShort from row."""
        return row[1].strip() if len(row) >= 2 else ""

    def find_collection_range(self, target_id_short):
        """
        Find the range of a collection by its idShort.
        
        Returns:
            Tuple of (start_index, end_index) inclusive
        """
        start_index = None
        
        # Find collection start
        for idx, row in enumerate(self.rows):
            if self._is_collection_start(row) and self._get_id_short(row) == target_id_short:
                start_index = idx
                break
                
        if start_index is None:
            raise ValueError(f"Collection '{target_id_short}' not found.")
        
        # Find collection end by tracking nesting depth
        depth = 0
        for end_index in range(start_index, len(self.rows)):
            if self._is_collection_start(self.rows[end_index]):
                depth += 1
            elif self._is_collection_end(self.rows[end_index]):
                depth -= 1
                
            if depth == 0:
                return start_index, end_index
                
        raise RuntimeError(f"Unbalanced SMC starting at row {start_index}.")

    def find_direct_child_range(self, parent_start, parent_end, child_id_short):
        """Find a direct child collection by idShort within parent range."""
        idx = parent_start + 1
        depth = 0
        
        while idx < parent_end:
            row = self.rows[idx]
            
            if self._is_collection_start(row):
                if depth == 0:
                    # Found potential direct child
                    child_start = idx
                    child_depth = 1
                    child_end = idx + 1
                    
                    # Find child end
                    while child_end < parent_end and child_depth > 0:
                        if self._is_collection_start(self.rows[child_end]):
                            child_depth += 1
                        elif self._is_collection_end(self.rows[child_end]):
                            child_depth -= 1
                        child_end += 1
                    
                    if self._get_id_short(self.rows[child_start]) == child_id_short:
                        return child_start, child_end - 1
                        
                    idx = child_end
                    continue
                    
                depth += 1
            elif self._is_collection_end(row):
                depth -= 1
                
            idx += 1
            
        return None

    def list_direct_children(self, parent_start, parent_end):
        """List all direct children ranges within parent collection."""
        children = []
        idx = parent_start + 1
        depth = 0
        
        while idx < parent_end:
            row = self.rows[idx]
            
            if self._is_collection_start(row):
                if depth == 0:
                    # Found direct child
                    child_start = idx
                    child_depth = 1
                    child_end = idx + 1
                    
                    # Find child end
                    while child_end < parent_end and child_depth > 0:
                        if self._is_collection_start(self.rows[child_end]):
                            child_depth += 1
                        elif self._is_collection_end(self.rows[child_end]):
                            child_depth -= 1
                        child_end += 1
                    
                    children.append((child_start, child_end - 1))
                    idx = child_end
                    continue
                    
                depth += 1
            elif self._is_collection_end(row):
                depth -= 1
                
            idx += 1
            
        return children

    def get_description_en(self, row):
        """Extract descriptionEN from row (column index 5)."""
        return row[5].strip() if len(row) > 5 and row[5] else ""

    def _create_reference_row(self, value_id_short):
        """Create a ReferenceElement row with the given value."""
        num_columns = max(8, len(self.header))
        row = [""] * num_columns
        row[0] = "ReferenceElement"
        row[1] = "Reference"
        row[2] = value_id_short
        row[7] = "0173-1#01-AGW586#00"
        return row[:num_columns]

    def has_identical_reference(self, item_start, item_end, value_id_short):
        """Check if item already contains an identical ReferenceElement."""
        idx = item_start + 1
        
        while idx < item_end:
            row = self.rows[idx]
            
            if (len(row) >= 3 and row[0] == "ReferenceElement" and 
                row[1] == "Reference" and row[2] == value_id_short):
                return True
                
            if self._is_collection_start(row):
                # Skip nested collections
                depth = 1
                next_idx = idx + 1
                
                while next_idx < item_end and depth > 0:
                    if self._is_collection_start(self.rows[next_idx]):
                        depth += 1
                    elif self._is_collection_end(self.rows[next_idx]):
                        depth -= 1
                    next_idx += 1
                    
                idx = next_idx
                continue
                
            idx += 1
            
        return False

    def insert_reference_element(self, item_start, item_end, value_id_short):
        """Insert ReferenceElement as first child if not already present."""
        if self.has_identical_reference(item_start, item_end, value_id_short):
            return 0
            
        reference_row = self._create_reference_row(value_id_short)
        self.rows.insert(item_start + 1, reference_row)
        return 1


def process_files(input_csv_path: Path, operational_data_path: Path, output_path: Path):
    """Main processing function."""
    # Read input files
    smc_rows = read_csv_any(input_csv_path)
    op_rows = read_csv_any(operational_data_path)
    
    # Build description to idShort mapping
    description_to_id = build_description_to_idshort(op_rows)
    
    # Initialize CSV editor
    smc_editor = SmcCsvEditor(smc_rows)
    
    # Find ReferenceImplementation_Instance collection
    instance_start, instance_end = smc_editor.find_collection_range(
        "ReferenceImplementation_Instance"
    )
    
    # Find PlcTask groups (support both spellings)
    plc_groups = []
    group_names = [
        ("PlcTask_Outputs", "PlcTask Outputs"),
        ("PlcTask_Inputs", "PlcTask Inputs")
    ]
    
    for standard_name, alt_name in group_names:
        # Try standard name first, then alternative
        for name in [standard_name, alt_name]:
            range_ = smc_editor.find_direct_child_range(instance_start, instance_end, name)
            if range_:
                plc_groups.append((standard_name, range_))
                break
    
    # Process all first-level children in each group
    inserted_count = 0
    
    for group_name, (group_start, group_end) in plc_groups:
        children = smc_editor.list_direct_children(group_start, group_end)
        
        # Process from bottom to top to avoid index shifts
        for child_start, child_end in reversed(children):
            description_en = smc_editor.get_description_en(smc_editor.rows[child_start])
            
            if not description_en:
                continue
                
            value_id_short = description_to_id.get(description_en)
            
            if not value_id_short:
                continue
                
            inserted_count += smc_editor.insert_reference_element(
                child_start, child_end, value_id_short
            )
    
    # Write output
    write_csv(output_path, smc_editor.rows)
    print(f"Inserted {inserted_count} reference rows into {output_path}")


def main(argv):
    script_dir = Path(__file__).parent.resolve()

    default_input_csv = script_dir / "PLC_base5.csv"
    default_operational_data = script_dir / "Operational_Data.csv"
    default_output = script_dir / "PLC_base6.csv"

    # Parse command line arguments
    input_csv_path = Path(argv[0]).resolve() if len(argv) >= 1 else default_input_csv
    operational_data_path = Path(argv[1]).resolve() if len(argv) >= 2 else default_operational_data
    output_path = Path(argv[2]).resolve() if len(argv) >= 3 else default_output
    
    # Run processing
    process_files(input_csv_path, operational_data_path, output_path)


if __name__ == "__main__":
    main(sys.argv[1:])