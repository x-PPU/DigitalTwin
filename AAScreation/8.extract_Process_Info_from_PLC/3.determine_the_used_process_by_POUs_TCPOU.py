#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Process TwinCAT POU analysis and SMC filtering for AAS export.

This script performs two main functions:
1. Scans TwinCAT .TcPOU files to analyze FB usage and EPrimitives references
2. Filters a human-readable SMC text file to export a hierarchical CSV 
   containing only processes referenced by those EPrimitives.

Input files (relative to script location):
- TcPOU root directory: ./plc-referenceimplementation/ReferenceImplementation/POUs/01_SequenceControl
- SMC text file: ./output/Process_list_with_signals.txt

Output:
- Filtered CSV: ./output/Process.csv

CSV structure follows AAS (Asset Administration Shell) format with columns:
["typeName","idShort","value","valueType","category","descriptionEN","descriptionDE","semanticId"]
"""

import argparse
import csv
import re
from pathlib import Path
import xml.etree.ElementTree as et


class TextFileReader:
    """Handles text file reading with multiple encoding fallbacks."""
    def read_text_any(self, file_path):
        encodings = ("utf-8", "utf-8-sig")
        path = Path(file_path)
        for encoding in encodings:
            try:
                return path.read_text(encoding=encoding)
            except (UnicodeDecodeError, UnicodeError):
                continue
        return path.read_bytes().decode("utf-8", errors="ignore")


class CodeCommentStripper:
    """Removes comments from Structured Text code."""
    def strip_comments(self, text):
        block_comment_pattern = re.compile(r"\(\*.*?\*\)", re.DOTALL)
        text = block_comment_pattern.sub("", text)
        line_comment_pattern = re.compile(r"//.*?$", re.MULTILINE)
        text = line_comment_pattern.sub("", text)
        return text


class TwinCatPouAnalyzer:
    """
    Analyzes TwinCAT POU files to extract EPrimitives usage and FB instances.
    
    Scans .TcPOU files in a directory structure and identifies:
    - EPrimitives references (EPrimitives.<ProcessName>)
    - Function block instances declared and called
    """
    def __init__(self, root_directory):
        self.root_dir = Path(root_directory)
        self.eprimitives_pattern = re.compile(r"\bEPrimitives\.([A-Za-z_]\w*)\b")
        self.variable_declaration_pattern = re.compile(r"^\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\s*;", re.MULTILINE)
        self.reader = TextFileReader()
        self.stripper = CodeCommentStripper()
        
    def _extract_pou_name(self, xml_root, fallback_name):
        """Extract POU name from XML, use filename as fallback."""
        pou_element = xml_root.find(".//POU")
        return pou_element.get("Name") if pou_element is not None else fallback_name

    def _extract_st_code(self, xml_root):
        """Extract all Structured Text code from XML."""
        code_sections = []
        for st_element in xml_root.findall(".//ST"):
            text_content = "".join(st_element.itertext()) if st_element is not None else ""
            if text_content:
                code_sections.append(text_content)
        return "\n".join(code_sections)

    def _extract_declaration_section(self, xml_root):
        """Extract variable declaration section from XML."""
        declaration_sections = []
        for decl_element in xml_root.findall(".//Declaration"):
            text_content = "".join(decl_element.itertext()) if decl_element is not None else ""
            if text_content:
                declaration_sections.append(text_content)
        return "\n".join(declaration_sections)

    def _parse_variable_declarations(self, declaration_text):
        """Parse declaration text to extract {variable_name: type_name} mapping."""
        variables = {}
        if not declaration_text:
            return variables
        clean_text = self.stripper.strip_comments(declaration_text)
       
        for match in self.variable_declaration_pattern.finditer(clean_text):
            var_name, type_name = match.group(1), match.group(2)
            variables[var_name] = type_name
            
        return variables

    def _detect_function_block_calls(self, st_code, variable_types):
        """Detect function block instances that are called in the code."""
        called_instances = set()
        if not st_code or not variable_types:
            return called_instances
            
        # Sort variable names by length (longest first) to avoid partial matches
        var_names = sorted(variable_types.keys(), key=len, reverse=True)
        if not var_names:
            return called_instances
            
        # Pattern to match variable calls: var_name(
        call_pattern = r"\b(?:%s)\s*\(" % "|".join(map(re.escape, var_names))
        call_regex = re.compile(call_pattern)
        
        for match in call_regex.finditer(st_code):
            call_span = st_code[match.start():match.end()]
            # Extract variable name before parentheses
            var_name = call_span.split("(")[0].strip().split()[-1]
            fb_type = variable_types.get(var_name)
            if fb_type:
                called_instances.add(fb_type)
                
        return called_instances

    def _analyze_pou_file(self, file_path):
        """
        Analyze a single .TcPOU file.
        Returns: (pou_name, eprimitives_set, invoked_fb_types_set)
        """
        xml_content = self.reader.read_text_any(file_path)

        # analyze XML content
        try:
            xml_root = et.fromstring(xml_content)
        except et.ParseError:
            xml_content_clean = xml_content.replace("&nbsp;", " ")
            xml_root = et.fromstring(xml_content_clean)

        # extract POU name and ST code
        pou_name = self._extract_pou_name(xml_root, file_path.stem)
        st_raw = self._extract_st_code(xml_root)
        st_code = self.stripper.strip_comments(st_raw)

        # EPrimitives references
        eprimitives_refs = {m.group(1) for m in self.eprimitives_pattern.finditer(st_code)}

        # variable declarations and FB calls
        declaration_text = self._extract_declaration_section(xml_root)
        variable_types = self._parse_variable_declarations(declaration_text)
        invoked_fbs = self._detect_function_block_calls(st_code, variable_types)

        return pou_name, eprimitives_refs, invoked_fbs


    def analyze_pou_directory(self):
        """
        Scan all .TcPOU files and analyze their content.
        
        Returns:
            dict: Mapping of POU names to sets of EPrimitive names
        """
        pou_files = sorted(self.root_dir.rglob("*.TcPOU"))
        if not pou_files:
            print(f"No .TcPOU files found in: {self.root_dir}")
            return {}

        pou_eprimitives_map = {}
        
        for file_path in pou_files:
            pou_name, eprimitives, invoked_fbs = self._analyze_pou_file(file_path)
            
            if not eprimitives and not invoked_fbs:
                continue
                
            # Print analysis results
            print(pou_name + ":")
            if eprimitives:
                print("  EPrimitives:", ", ".join(sorted(eprimitives)))
            if invoked_fbs:
                print("  FB instances:", ", ".join(sorted(invoked_fbs)))
            print()
            
            # Store for filtering
            if eprimitives:
                pou_eprimitives_map.setdefault(pou_name, set()).update(eprimitives)
                
        return pou_eprimitives_map


class SmcToCsvExporter:
    """
    Converts SMC text format to a filtered hierarchical CSV (AAS-compatible).

    Behavior highlights:
    - Filters processes based on EPrimitives referenced by analyzed POUs.
    - Preserves a hierarchical structure using SubmodelElementCollection rows.
    - Adds a special rule for ReferenceElement rows that appear under any
      "-SMC Control Variable:" scope (at any depth):
        * Put the original reference value into the 'descriptionEN' column.
        * Put a sanitized value (all dots replaced by underscores) into 'value'.
    """

    def __init__(self, smc_text_path, pou_eprimitives_map, output_csv_path):
        self.smc_text_path = Path(smc_text_path)
        self.pou_eprimitives_map = pou_eprimitives_map or {}
        self.output_csv_path = Path(output_csv_path)
        self.reader = TextFileReader()

        # Regular expressions for parsing SMC text structure
        self.smc_group_pattern = re.compile(r"^\s*(?:\ufeff)?SMC\s+(.+?)\s*$")
        self.smc_item_pattern = re.compile(r"^(?P<indent>\s*)-SMC\s+(.+?)\s*$")
        self.property_pattern = re.compile(r"^(?P<indent>\s*)-Prop\s+(.+?)\s*$")
        self.extends_reference_pattern = re.compile(r"^\s*-Ref\s+Extends:", re.IGNORECASE)
        self.ref_pattern = re.compile(r"^(?P<indent>\s*)-Ref\s+(?P<id>[^:]+?)\s*:\s*(?P<val>.+?)\s*$")

        # Control-structure markers (for logic compression)
        self.if_pattern = re.compile(r"^\s*IF\b.*\bTHEN\b", re.IGNORECASE)
        self.elsif_pattern = re.compile(r"^\s*ELSIF\b.*\bTHEN\b", re.IGNORECASE)
        self.else_pattern = re.compile(r"^\s*ELSE\b\s*;?$", re.IGNORECASE)
        self.endif_pattern = re.compile(r"^\s*END_IF\b\s*;?$", re.IGNORECASE)


    def _map_smc_group_to_pou(self, group_name):
        """
        Map an SMC group (top-level 'SMC <Group>') to the expected POU name.
        """
        group_clean = group_name.strip().lower()
        if group_clean in ("pickalpha", "picalpha"):
            return "xPPU_PicAlpha"
        if group_clean == "generic":
            return "xPPU_Automatic"
        return f"xPPU_{group_name}"

    def _parse_property_components(self, property_text):
        """
        Parse a '-Prop ...' body into (key, value) pairs, supporting forms:
          key := value;
          key : value;
          call();    ("call()", "")
        """
        text_clean = property_text.strip()

        # Assignment form
        if ":=" in text_clean:
            key_part, value_part = text_clean.split(":=", 1)
            return key_part.strip(), value_part.strip().rstrip(";")

        # Type declaration form
        if ":" in text_clean:
            key_part, value_part = text_clean.split(":", 1)
            return key_part.strip(), value_part.strip().rstrip(";")

        # Bare call ending with ';'
        if text_clean.endswith(";"):
            text_clean = text_clean[:-1].rstrip()

        return text_clean, ""

    def _ensure_statement_termination(self, code_line):
        """
        Ensure an ST statement ends with ';'.
        """
        line_clean = code_line.strip()
        return line_clean if line_clean.endswith(";") else (line_clean + ";")

    def _compress_logic_blocks(self, code_lines) :
        """
        Compress IF/ELSIF/ELSE/END_IF blocks so each branch with its body
        appears on a single line. If no control structures are present,
        return the original lines joined by newlines.
        """
        has_ctrl = any(
            self.if_pattern.search(line)
            or self.elsif_pattern.search(line)
            or self.else_pattern.search(line)
            or self.endif_pattern.search(line)
            for line in code_lines
        )
        if not has_ctrl:
            return "\n".join(code_lines).rstrip("\n")

        # Accumulate blocks as (header, [statements])
        structured_blocks: list[tuple[str, list[str]]] = []
        current_idx = -1

        for raw in code_lines:
            line = raw.strip()
            if not line:
                continue

            if (
                self.if_pattern.match(line)
                or self.elsif_pattern.match(line)
                or self.else_pattern.match(line)
                or self.endif_pattern.match(line)
            ):
                structured_blocks.append((line.rstrip(";"), []))
                current_idx = len(structured_blocks) - 1
                continue

            if current_idx >= 0:
                header, statements = structured_blocks[current_idx]
                statements.append(self._ensure_statement_termination(line))
                structured_blocks[current_idx] = (header, statements)
            else:
                # Orphan statement without a control-header
                structured_blocks.append((line, []))
                current_idx = len(structured_blocks) - 1

        # Build compressed string
        out_lines = []
        for header, statements in structured_blocks:
            if statements:
                out_lines.append(f"{header}  " + " ".join(statements))
            else:
                out_lines.append(header)
        return "\n".join(out_lines)


    def export_to_csv(self):
        """
        Read the SMC text, filter by POU EPrimitives, and write an AAS-style CSV.

        CSV columns:
          ["typeName","idShort","value","valueType",
           "category","descriptionEN","descriptionDE","semanticId"]
        """
        file_lines = self.reader.read_text_any(self.smc_text_path).splitlines()
        self.output_csv_path.parent.mkdir(parents=True, exist_ok=True)

        with self.output_csv_path.open("w", encoding="utf-8", newline="") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow([
                "typeName", "idShort", "value", "valueType",
                "category", "descriptionEN", "descriptionDE", "semanticId"
            ])

            # Stack for open collections to maintain proper closures.
            # Each entry is a triple: (indent_level, was_emitted, label)
            # - indent_level: indentation depth where the collection started
            # - was_emitted: whether we actually wrote a "SubmodelElementCollection" row
            # - label: the collection label (e.g., "Variable", "Variable", "Process Foo")
            collection_stack: list[tuple[int, bool, str | None]] = []

            def close_collections_to_level(target_indent: int):
                """
                Close all open collections at or above the given indentation level.
                """
                while collection_stack and collection_stack[-1][0] >= target_indent:
                    indent_level, was_emitted, _label = collection_stack.pop()
                    if was_emitted:
                        csv_writer.writerow([
                            "End-SubmodelElementCollection", "", "", "", "", "", "", ""
                        ])

            def inside_signal_scope():
                """
                Returns True if we are currently inside any emitted "-SMC Control Variable:" collection
                (at any depth).
                """
                for _indent, was_emitted, label in reversed(collection_stack):
                    if was_emitted and label and label.strip().lower() == "signal":
                        return True
                return False

            # State variables for group/process filtering and writing
            current_group = None
            current_group_pou = None
            allowed_processes: set[str] = set()
            group_collection_opened = False
            parsing_started = False
            should_emit_content = False

            # Logic block buffering state
            pending_logic_id: str | None = None
            pending_logic_lines: list[str] = []

            def flush_pending_logic_block():
                """
                If we were accumulating a logic block, emit it as a single Property row.
                """
                nonlocal pending_logic_id, pending_logic_lines
                if pending_logic_id is not None and should_emit_content:
                    compressed = self._compress_logic_blocks(pending_logic_lines)
                    csv_writer.writerow([
                        "Property", pending_logic_id, compressed, "", "", "", "", ""
                    ])
                pending_logic_id = None
                pending_logic_lines = []

            # Variable section state
            in_variable_section = False
            variable_section_indent = -1
            variable_properties: list[tuple[str, str]] = []
            precondition_properties: list[tuple[str, str]] = []
            postcondition_properties: list[tuple[str, str]] = []

            def reset_variable_section():
                """
                Reset the variable section capture state and buffers.
                """
                nonlocal in_variable_section, variable_section_indent
                nonlocal variable_properties, precondition_properties, postcondition_properties
                in_variable_section = False
                variable_section_indent = -1
                variable_properties, precondition_properties, postcondition_properties = [], [], []

            def emit_variable_subcollection(collection_name,
                                           properties_list):
                """
                Emit a SubmodelElementCollection with its property children.
                """
                if not properties_list or not should_emit_content:
                    return
                csv_writer.writerow(["SubmodelElementCollection", collection_name, "", "", "", "", "", ""])
                for key, value in properties_list:
                    csv_writer.writerow(["Property", key, value, "", "", "", "", ""])
                csv_writer.writerow(["End-SubmodelElementCollection", "", "", "", "", "", "", ""])

            def flush_variable_section(next_indent_level=None):
                """
                If we were inside a variable section, emit Variable/Precondition/Postcondition
                subcollections and then restore the stack/indent state.
                """
                if not in_variable_section:
                    return

                emit_variable_subcollection("Variable", variable_properties)
                emit_variable_subcollection("Precondition", precondition_properties)
                emit_variable_subcollection("Postcondition", postcondition_properties)

                # Remove placeholder entry if present at the section's indent
                if (
                    collection_stack
                    and collection_stack[-1][0] == variable_section_indent
                    and not collection_stack[-1][1]
                ):
                    collection_stack.pop()

                if next_indent_level is not None:
                    close_collections_to_level(next_indent_level)

                reset_variable_section()


            # Main line-by-line parsing loop
            for raw_line in file_lines:
                # Skip everything before the first group header
                if not parsing_started and not self.smc_group_pattern.match(raw_line):
                    continue

                # If a logic block is being accumulated, continue until a new item starts
                if pending_logic_id is not None:
                    if (
                        self.smc_item_pattern.match(raw_line)
                        or self.property_pattern.match(raw_line)
                        or self.smc_group_pattern.match(raw_line)
                    ):
                        flush_pending_logic_block()
                    else:
                        pending_logic_lines.append(raw_line)
                        continue

                # Group header: "SMC <Group>"
                group_match = self.smc_group_pattern.match(raw_line)
                if group_match:
                    parsing_started = True
                    flush_pending_logic_block()
                    flush_variable_section(next_indent_level=0)
                    close_collections_to_level(0)

                    current_group = group_match.group(1).strip()
                    current_group_pou = self._map_smc_group_to_pou(current_group)
                    allowed_processes = set(self.pou_eprimitives_map.get(current_group_pou, set()))
                    group_collection_opened = False
                    should_emit_content = False
                    continue

                # Ignore "Ref Extends: ..." lines
                if self.extends_reference_pattern.match(raw_line):
                    continue

                # SMC item line: "-SMC ..."
                smc_match = self.smc_item_pattern.match(raw_line)
                if smc_match:
                    indent_level = len(smc_match.group("indent"))
                    item_label = raw_line.strip()[5:].strip()  # remove "-SMC "
                    clean_label = item_label[:-1].strip() if item_label.endswith(":") else item_label

                    # Finish variable section when encountering a new SMC item
                    if in_variable_section:
                        flush_variable_section()

                    close_collections_to_level(indent_level)

                    # Process blocks are filtered by allowed_processes
                    if clean_label.lower().startswith("process "):
                        process_name = clean_label[8:].strip()
                        should_include = (current_group is not None) and (process_name in allowed_processes)
                        should_emit_content = should_include

                        # Open the group collection if needed
                        if should_emit_content and not group_collection_opened and current_group:
                            csv_writer.writerow([
                                "SubmodelElementCollection", current_group, "", "", "", "", "", ""
                            ])
                            collection_stack.append((0, True, current_group))
                            group_collection_opened = True

                        # Open the process collection (or push a placeholder to keep indentation)
                        if should_emit_content:
                            csv_writer.writerow([
                                "SubmodelElementCollection", f"Process {process_name}", "", "", "", "", "", ""
                            ])
                            collection_stack.append((indent_level, True, f"Process {process_name}"))
                        else:
                            collection_stack.append((indent_level, False, f"Process {process_name}"))
                        continue

                    # Variable section start
                    if clean_label.lower() == "var":
                        in_variable_section = True
                        variable_section_indent = indent_level
                        variable_properties, precondition_properties, postcondition_properties = [], [], []
                        # Push a non-emitted placeholder to maintain hierarchy
                        collection_stack.append((indent_level, False, None))
                        continue

                    # Any other SMC item (e.g., "Variable", "Methods", etc.)
                    if should_emit_content:
                        csv_writer.writerow([
                            "SubmodelElementCollection", clean_label, "", "", "", "", "", ""
                        ])
                        collection_stack.append((indent_level, True, clean_label))
                    else:
                        collection_stack.append((indent_level, False, clean_label))
                    continue

                # Reference line: "-Ref idShort: value"
                ref_match = self.ref_pattern.match(raw_line)
                if ref_match:
                    indent_level = len(ref_match.group("indent"))
                    id_short = ref_match.group("id").strip()
                    ref_value = ref_match.group("val").strip()

                    flush_pending_logic_block()

                    # If a new Ref begins while inside a variable section, finalize that section first
                    if in_variable_section:
                        flush_variable_section(next_indent_level=indent_level)

                    close_collections_to_level(indent_level)

                    if should_emit_content:
                        if inside_signal_scope():
                            # Special handling under any "-SMC Control Variable" scope
                            cleaned_value = ref_value.replace(".", "_")
                            csv_writer.writerow([
                                "ReferenceElement", id_short, cleaned_value, "", "",
                                ref_value,  # descriptionEN holds the original dotted value
                                "", ""      # descriptionDE, semanticId remain empty
                            ])
                        else:
                            # Default ReferenceElement behavior
                            csv_writer.writerow([
                                "ReferenceElement", id_short, ref_value, "", "", "", "", ""
                            ])
                    continue

                # Property line: "-Prop ..."
                prop_match = self.property_pattern.match(raw_line)
                if prop_match:
                    indent_level = len(prop_match.group("indent"))
                    property_body = raw_line.strip()[5:].strip()  # remove "-Prop "

                    # If within variable section, collect properties until indent decreases
                    if in_variable_section:
                        if indent_level > variable_section_indent:
                            key, value = self._parse_property_components(property_body)
                            key_lower = key.strip().lower()
                            if key_lower == "m_precondition":
                                precondition_properties.append((key, value))
                            elif key_lower == "m_postcondition":
                                postcondition_properties.append((key, value))
                            else:
                                variable_properties.append((key, value))
                            continue
                        else:
                            # Indentation decreased or equal: finalize variable section
                            flush_variable_section(next_indent_level=indent_level)
                            # Then continue as a normal property

                    close_collections_to_level(indent_level)

                    # Detect logic header like "LogicSomething:"
                    is_logic_header = property_body.endswith(":") and property_body.lower().startswith("logic")
                    if is_logic_header:
                        pending_logic_id = property_body[:-1].strip()
                        pending_logic_lines = []
                        continue

                    # Regular property outside of logic buffering
                    key, value = self._parse_property_components(property_body)
                    if should_emit_content:
                        csv_writer.writerow(["Property", key, value, "", "", "", "", ""])
                    continue

                # Any other line types are ignored

            # Final cleanup
            flush_pending_logic_block()
            flush_variable_section(next_indent_level=0)
            close_collections_to_level(0)


class ApplicationController:
    """Main application controller coordinating POU analysis and CSV export."""
    
    def __init__(self):
        script_directory = Path(__file__).parent.resolve()
        self.default_tc_root = (
            script_directory / 
            "plc-referenceimplementation" / 
            "ReferenceImplementation" / 
            "POUs" / 
            "01_SequenceControl"
        )
        self.default_smc_input = script_directory / "output" / "Process_list_with_signals.txt"
        self.default_csv_output = script_directory / "output" / "Process_base.csv"

    def execute(self):
        """Main execution method."""
        parser = argparse.ArgumentParser(
            description="Analyze TwinCAT POU files and export filtered SMC content to CSV"
        )
        parser.add_argument(
            "tc_root",
            nargs="?",
            type=Path,
            default=self.default_tc_root,
            help="Path to TwinCAT POU root directory (default: project relative path)",
        )
        parser.add_argument(
            "--in-smc",
            type=Path,
            default=self.default_smc_input,
            help="Path to SMC Process_list.txt input file",
        )
        parser.add_argument(
            "--out-csv", 
            type=Path,
            default=self.default_csv_output,
            help="Output CSV file path",
        )
        args = parser.parse_args()

        tc_root_path = args.tc_root.resolve()
        if not tc_root_path.exists():
            return

        # Analyze POU files
        analyzer = TwinCatPouAnalyzer(tc_root_path)
        pou_analysis_results = analyzer.analyze_pou_directory()

        # Check SMC input file
        smc_input_path = args.in_smc.resolve()
        if not smc_input_path.exists():
            return

        # Export filtered CSV
        csv_output_path = args.out_csv.resolve()
        exporter = SmcToCsvExporter(smc_input_path, pou_analysis_results, csv_output_path)
        exporter.export_to_csv()
        
        print(f"SUCCESS, CSV saved in: {csv_output_path}")


if __name__ == "__main__":
    ApplicationController().execute()