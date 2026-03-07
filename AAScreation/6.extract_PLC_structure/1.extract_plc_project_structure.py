# -*- coding: utf-8 -*-
"""
TwinCAT To SMC CSV exporter (class-based, documented)

What it does
------------
1) Discover all *.tsproj under a given base directory.
2) From each tsproj, read referenced *.plcproj files.
3) For each plcproj, reproduce a project-like SMC structure:
     PLC
       <ProjectName>
            ProjectName_Project
                External Types   (placeholder SMC)
                References       (from plcproj)
                DUTs             (from plcproj Compile Include paths)
                GVLs             (TcGVL + TcPOU under /GVLs in plcproj)
                POUs             (keep folders like 00_.../01_... from plcproj)
                PlcTask          (if PlcTask.TcTTO appears in plcproj)
            ProjectName_Instance (placeholder SMC)
                Only for Resi4MPM_Lib / xPPU_Lib]
                    Additional SMCs built purely from folder/file names,
                    skipping _Libraries and _CompileInfo

Notes
-----
- idShort is sanitized: remove outer brackets, drop file extension, keep letters/digits/_ only.
- Natural sort (00_..., 01_...) is used to keep TwinCAT-like ordering.
- CSV header is: ["typeName","idShort","value","valueType","category","descriptionEN","descriptionDE","semanticId"]
"""

import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Tuple, Iterable



def natsort_key(text):
    """Return a key that makes strings sort in a human/natural way: 2 < 10, 01 < 02, etc."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def local_name(tag):
    """Strip XML namespace from a tag name."""
    return tag.split('}', 1)[-1]


def strip_outer_brackets(s):
    """If the whole string is wrapped by (), [] or {}, remove the outer pair."""
    s = s.strip()
    if len(s) >= 2:
        pairs = {"(": ")", "[": "]", "{": "}"}
        if s[0] in pairs and s[-1] == pairs[s[0]]:
            return s[1:-1].strip()
    return s


def sanitize_idshort(s):
    """ Sanitize an idShort """
    p = Path(strip_outer_brackets(s))
    core = p.stem.strip()
    core = re.sub(r"[^\w]", "_", core)
    return core or "item"



class SmcWriter:
    """Collects SMC rows and writes them as a CSV."""
    def __init__(self):
        self.csv_header = [
            "typeName", "idShort", "value", "valueType",
            "category", "descriptionEN", "descriptionDE", "semanticId"
        ]
        self.rows = [self.csv_header]

    def _row(self,                
             type_name,
             id_short,
             value = "",
             value_type = "",
             category = "",
             description_en = "",
             description_de = "",
             semantic_id = ""):
        return [type_name, id_short, value, value_type,
                category, description_en, description_de, semantic_id]

    def start(self, id_short):
        self.rows.append(self._row("SubmodelElementCollection", sanitize_idshort(id_short)))

    def end(self):
        self.rows.append(self._row("End-SubmodelElementCollection", ""))

    def write(self, dest):
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(self.rows)        


class TwinCATParser:
    """Static helpers to read *.tsproj and *.plcproj contents."""

    # File suffix filters
    gvl_file_suffixes = {".TcGVL", ".TcPOU"}       # allow TcPOU inside GVLs (xPPU_Container case)
    pou_file_suffixes = {".TcPOU"}
    dut_file_suffixes = {".TcDUT"}

    # TwinCAT source-like suffixes for library tree completion
    tc_src_exts = {
        ".TcPOU", ".TcDUT", ".TcGVL", ".TcIO", ".TcAction", ".TcTask",
        ".TcTTO", ".TcPlcObject", ".TcVISU"
    }

    def find_tsproj_files(base_dir):
        """Recursively find all *.tsproj files under base_dir."""
        return sorted(base_dir.rglob("*.tsproj"))

    def parse_tsproj_for_plcprojs(tsproj):
        """
        From a *.tsproj file, collect referenced *.plcproj paths (relative to the tsproj).
        """
        try:
            root = ET.parse(tsproj).getroot()
        except Exception:
            return []
        plcprojs: List[Path] = []
        for el in root.iter():
            if local_name(el.tag) == "Project" and "PrjFilePath" in el.attrib:
                plcprojs.append((tsproj.parent / el.attrib["PrjFilePath"]).resolve())
        return plcprojs

    def parse_plcproj(plcproj):
        """
        Parse a *.plcproj to obtain:
        - files: 'Compile Include' values (raw relative paths) to reconstruct DUTs/GVLs/POUs/PlcTask
        - refs : Reference/PlaceholderReference names
        """
        result = {"files": [], "refs": []}
        try:
            root = ET.parse(plcproj).getroot()
        except Exception:
            return result

        # Collect 'Compile Include'
        for el in root.iter():
            if local_name(el.tag) == "Compile" and "Include" in el.attrib:
                inc = el.attrib["Include"].replace("/", "\\")
                result["files"].append(inc)

        # Collect references
        refs = []
        for el in root.iter():
            ln = local_name(el.tag)
            if ln in ("Reference", "PlaceholderReference"):
                inc = el.attrib.get("Include")
                if inc:
                    refs.append(inc)

        # Sort: put Tc2_*/Tc3_* after custom libs (e.g., [Resi4MPM], [xPPU])
        def ref_key(x):
            name = strip_outer_brackets(x)
            return ((1, name.lower()) if name.startswith(("Tc2_", "Tc3_")) else (0, name.lower()))

        result["refs"] = sorted(refs, key=ref_key)
        return result



class TwinCATSmcExporter:
    """
    - discovers projects
    - emits SMC rows for each project
    - supplements library projects (Resi4MPM_Lib / xPPU_Lib) using folder/file names
    """

    def __init__(self, base_dir: Path, output_csv: Path):
        self.base_dir = base_dir
        self.output_csv = output_csv
        self.writer = SmcWriter()

        # Desired order for well-known projects
        self.project_order = ["ReferenceImplementation", "Resi4MPM_Lib", "xPPU_Lib"]

        # Which directories to skip when walking library trees
        self.exclude_dirs = {"_Libraries", "_CompileInfo"}

        # Library roots used ONLY for "filename-based" completion
        self.supplement_roots = {
            "Resi4MPM_Lib": self.base_dir / "Resi_Lib" / "Resi4MPM_Lib",
            "xPPU_Lib": self.base_dir / "xPPU_Lib" / "xPPU_Lib",
        }

    def generate(self):
        """Entry point: build rows and write the CSV."""
        self.writer.start("PLC")

        # Discover all projects (tsproj → plcproj)
        plcproj_map: Dict[str, Path] = {}
        for ts in TwinCATParser.find_tsproj_files(self.base_dir):
            for pp in TwinCATParser.parse_tsproj_for_plcprojs(ts):
                if pp.exists():
                    plcproj_map[pp.parent.name] = pp

        # Emit in desired order first, then any leftovers
        for name in self.project_order:
            if name in plcproj_map:
                self._emit_project(name, plcproj_map[name])

        for name, pp in sorted(plcproj_map.items(), key=lambda kv: kv[0].lower()):
            if name not in self.project_order:
                self._emit_project(name, pp)

        self.writer.end()  # </PLC>
        self.writer.write(self.output_csv)


    def _emit_project(self, proj_name, plcproj):
        """Emit one project's SMC blocks based on its plcproj + (optional) library supplement."""
        info = TwinCATParser.parse_plcproj(plcproj)

        self.writer.start(proj_name)

        # 1) <ProjectName>_Project
        self.writer.start(f"{proj_name}_Project")

        # 1.1 External Types (placeholder, as requested)
        self.writer.start("External Types")
        self.writer.end()

        # 1.2 References (flat list from plcproj)
        self.writer.start("References")
        for r in info["refs"]:
            self.writer.start(strip_outer_brackets(r))
            self.writer.end()
        self.writer.end()

        # 1.3 Reconstruct DUTs / GVLs / POUs / PlcTask from Compile Includes
        self._emit_from_compile_includes(info["files"])

        # 1.4 Supplement (only for specific libraries) by folder/file names
        if proj_name in self.supplement_roots:
            self._emit_library_supplement(self.supplement_roots[proj_name])

        self.writer.end()  # </ProjectName_Project>

        # 2) <ProjectName>_Instance (placeholder)
        self.writer.start(f"{proj_name}_Instance")
        self.writer.end()

        self.writer.end()  # </ProjectName>

    def _emit_from_compile_includes(self, includes):
        """ Recreate DUTs, GVLs, POUs and PlcTask solely from plcproj 'Compile Include' entries.  """
        dut_items = []
        gvl_items = []
        pou_folders = {}
        has_plctask = False

        for inc in includes:
            parts = Path(inc).parts
            if len(parts) == 1:
                # e.g., PlcTask.TcTTO
                if parts[0].lower().endswith(".tctto"):
                    has_plctask = True
                continue

            top = parts[0]
            fname = Path(parts[-1])
            ext = fname.suffix

            if top == "DUTs" and ext in TwinCATParser.dut_file_suffixes:
                dut_items.append(fname.stem)

            elif top == "GVLs" and ext in TwinCATParser.gvl_file_suffixes:
                gvl_items.append(fname.stem)

            elif top == "POUs" and ext in TwinCATParser.pou_file_suffixes:
                folder = parts[1] if len(parts) >= 3 else ""
                pou_folders.setdefault(folder, []).append(fname.stem)

        # DUTs
        if dut_items:
            self.writer.start("DUTs")
            for name in sorted(set(dut_items), key=natsort_key):
                self.writer.start(name)
                self.writer.end()
            self.writer.end()

        # GVLs (include TcGVL + TcPOU inside /GVLs)
        if gvl_items:
            self.writer.start("GVLs")
            for name in sorted(set(gvl_items), key=natsort_key):
                self.writer.start(name)
                self.writer.end()
            self.writer.end()

        # POUs (keep second-level folder split like 00_..., 01_...)
        if pou_folders:
            self.writer.start("POUs")
            for folder in sorted(pou_folders.keys(), key=natsort_key):
                if folder:
                    self.writer.start(folder)
                for name in sorted(set(pou_folders[folder]), key=natsort_key):
                    self.writer.start(name)
                    self.writer.end()
                if folder:
                    self.writer.end()
            self.writer.end()

        # PlcTask
        if has_plctask:
            self.writer.start("PlcTask")
            self.writer.end()

    def _emit_library_supplement(self, lib_root):
        """
        For Resi4MPM_Lib and xPPU_Lib only:
        Build additional SMC blocks by walking the library folder tree,
        skipping `_Libraries` and `_CompileInfo`. We output:
          - each top-level folder as an SMC, then recurse
          - each TwinCAT source file as a leaf SMC (with filename stem)
        """
        if not lib_root.exists():
            return

        # walk entries at the library root
        for entry in sorted(lib_root.iterdir(), key=lambda p: natsort_key(p.name)):
            if entry.name in self.exclude_dirs:
                continue

            if entry.is_dir():
                self.writer.start(entry.name)
                self._emit_dir_tree(entry)
                self.writer.end()

            elif entry.is_file() and entry.suffix in TwinCATParser.tc_src_exts:
                self.writer.start(entry.stem)
                self.writer.end()

    def _emit_dir_tree(self, directory):
        """Recursive helper used by _emit_library_supplement()."""
        # subfolders first
        subdirs = [d for d in directory.iterdir()
                   if d.is_dir() and d.name not in self.exclude_dirs]
        for d in sorted(subdirs, key=lambda p: natsort_key(p.name)):
            self.writer.start(d.name)
            self._emit_dir_tree(d)
            self.writer.end()

        # then files
        files = [f for f in directory.iterdir()
                 if f.is_file() and f.suffix in TwinCATParser.tc_src_exts]
        for f in sorted(files, key=lambda p: natsort_key(p.name)):
            self.writer.start(f.stem)
            self.writer.end()



if __name__ == "__main__":
    base_dir = Path(__file__).parent / "plc-referenceimplementation" # base_dir = Path(__file__).parent / "plc-referenceimplementation-main" 

    output_csv = Path(__file__).parent / "PLC_base1.csv" # output_csv = Path(__file__).parent / "PLC_base1.csv"

    exporter = TwinCATSmcExporter(base_dir=base_dir, output_csv=output_csv)
    exporter.generate()
    print(f" CSV created in: {output_csv}")
