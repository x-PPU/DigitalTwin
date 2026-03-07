#/usr/bin/env python3
# coding: utf-8 -*-

"""
Append TwinCAT actions discovered in TcPOU files to an existing SMC CSV tree.

Overview
--------
- Scan a directory tree for *.TcPOU files and collect Action nodes whose
  Name ends with "_active". The original Action name is kept as the node label.
- Load an existing SMC CSV (rows are only "SubmodelElementCollection" and
  "End-SubmodelElementCollection"), build an in-memory tree, and append actions
  under each "01_SequenceControl" / <POU node> if that POU node already exists.
- Duplicates are avoided by comparing sanitized idShorts.

"""

import csv
import sys
import re
import xml.etree.ElementTree as ET
from pathlib import Path



CSV_HEADER = [
    "typeName", "idShort", "value", "valueType",
    "category", "descriptionEN", "descriptionDE", "semanticId"
]

def sanitize(text):
    """
    Sanitize a string for SMC idShort:
    """
    s = (text or "").strip()
    s = re.sub(r"[^\w]", "_", s).strip("_")
    return s or "item"


def strip_ns(tag):
    """Strip an XML namespace from a tag name, if present."""
    return tag.split("}", 1)[-1] if isinstance(tag, str) else tag


def read_csv_rows(path):
    """Load all CSV rows with UTF-8."""
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def write_csv_rows(path, rows):
    """Write all CSV rows using UTF-8."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)

class ActionFinder:
    """
    Collect actions from TcPOU files.
    """

    def __init__(self, root_dir):
        self.root_dir = Path(root_dir)

    def extract(self):
        result = {}

        for file in sorted(self.root_dir.rglob("*.TcPOU")):
            try:
                root = ET.parse(file).getroot()
            except Exception:
                # Malformed or unreadable file: skip silently
                continue

            # Prefer POU/@Name if available; fall back to file stem
            pou_name = file.stem
            pou_el = root.find(".//POU")
            if pou_el is not None and pou_el.get("Name"):
                pou_name = pou_el.get("Name")

            bucket = result.setdefault(pou_name, [])
            seen = {sanitize(a) for a in bucket}

            # collect all Action/Name
            for node in root.iter():
                if strip_ns(node.tag) != "Action":
                    continue
                nm = (node.get("Name") or "").strip()
                if not nm:
                    continue
                sid = sanitize(nm)
                if sid in seen:
                    continue
                bucket.append(nm)
                seen.add(sid)

        # Remove POU entries that ended up empty
        return {k: v for k, v in result.items() if v}


class SMCNode:
    def __init__(self, id_short):
        self.id_short = id_short
        self.children = []

    def find_child(self, name):
        """Find a direct child by sanitized idShort; return None if not found."""
        tgt = sanitize(name)
        for c in self.children:
            if sanitize(c.id_short) == tgt:
                return c
        return None


class SMCTree:
    """
    Build a minimal SMC tree from CSV and serialize it back to CSV.
    """

    def __init__(self):
        self.roots = []

    def load_from_csv(self, csv_path):
        rows = read_csv_rows(csv_path)
        if not rows or rows[0][:2] != CSV_HEADER[:2]:
            raise RuntimeError(f"CSV header not recognized: {csv_path}")

        self.roots = []
        stack = []

        for row in rows[1:]:
            if self._is_start(row):
                node = SMCNode(row[1])
                if stack:
                    stack[-1].children.append(node)
                else:
                    self.roots.append(node)
                stack.append(node)
            elif self._is_end(row):
                if stack:
                    stack.pop()

    def to_csv_rows(self):
        out = [CSV_HEADER]

        def emit(node):
            out.append([
                "SubmodelElementCollection",
                sanitize(node.id_short),
                "", "", "", "", "", ""
            ])
            for c in node.children:
                emit(c)
            out.append(["End-SubmodelElementCollection", "", "", "", "", "", "", ""])

        for r in self.roots:
            emit(r)
        return out

    def find_all(self, name):
        """Find all nodes (any depth) whose sanitized idShort matches `name`."""
        target = sanitize(name)
        hits = []

        def dfs(n):
            if sanitize(n.id_short) == target:
                hits.append(n)
            for c in n.children:
                dfs(c)

        for r in self.roots:
            dfs(r)
        return hits

    def insert_actions_under_sequence_control(self, actions_by_pou):
        """
        For each '01_SequenceControl' node:
          - Find an existing POU child (e.g. 'xPPU_Crane').
          - Append actions under that child, skipping duplicates.
        Returns the number of actions actually inserted.
        """
        inserted = 0
        anchors = self.find_all("01_SequenceControl")

        for anchor in anchors:
            for pou_name, actions in actions_by_pou.items():
                pou_node = anchor.find_child(pou_name)
                if pou_node is None:
                    continue
                existing = {sanitize(c.id_short) for c in pou_node.children}
                for act in actions:
                    sid = sanitize(act)
                    if sid in existing:
                        continue
                    pou_node.children.append(SMCNode(act))
                    existing.add(sid)
                    inserted += 1

        return inserted

    def _is_start(self, row):
        return len(row) >= 2 and row[0] == "SubmodelElementCollection"

    def _is_end(self, row):
        return len(row) >= 1 and row[0] == "End-SubmodelElementCollection"


class AppendActionsApp:
    """
    Steps:
      1. Extracts actions from TcPOU files.
      2. Loads an SMC CSV into a tree.
      3. Appends actions under '01_SequenceControl' / existing POU nodes.
      4. Writes the updated CSV.
    """

    def __init__(self, tcpou_dir, csv_in, csv_out):
        self.tcpou_dir = Path(tcpou_dir)
        self.csv_in = Path(csv_in)
        self.csv_out = Path(csv_out)

    def run(self):
        if not self.tcpou_dir.exists():
            raise FileNotFoundError(f"TcPOU directory not found: {self.tcpou_dir}")
        if not self.csv_in.exists():
            raise FileNotFoundError(f"CSV not found: {self.csv_in}")

        actions = ActionFinder(self.tcpou_dir).extract()

        tree = SMCTree()
        tree.load_from_csv(self.csv_in)
        added = tree.insert_actions_under_sequence_control(actions)

        write_csv_rows(self.csv_out, tree.to_csv_rows())
        print(f"Done. Inserted {added} actions into:", self.csv_out)



def main(argv):
    script_dir = Path(__file__).parent.resolve()
    default_tcpou_dir = (
        script_dir / "plc-referenceimplementation" /
        "ReferenceImplementation" / "POUs" / "01_SequenceControl"
    )
    default_csv_in  = script_dir / "PLC_base1.csv"
    default_csv_out = script_dir / "PLC_base2.csv"


    # Optional positional args: [TcPOU root] [input CSV] [output CSV]
    tcpou_dir = Path(argv[0]).resolve() if len(argv) >= 1 else default_tcpou_dir
    csv_in    = Path(argv[1]).resolve() if len(argv) >= 2 else default_csv_in
    csv_out   = Path(argv[2]).resolve() if len(argv) >= 3 else default_csv_out

    AppendActionsApp(tcpou_dir, csv_in, csv_out).run()


if __name__ == "__main__":
    main(sys.argv[1:])
