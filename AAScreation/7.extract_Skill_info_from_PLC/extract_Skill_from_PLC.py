#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
TwinCAT POU to Skills CSV Converter

This script analyzes TwinCAT .TcPOU files to extract skills from methods and actions,
then exports them to a structured CSV format compatible with AAS (Asset Administration Shell).

The pipeline:
1. Parses TwinCAT POU XML files to find methods (METH_*) and actions (ACT_*)
2. Extracts top-level statements while ignoring control structures
3. Converts method/action calls to skill references
4. Extracts property assignments as conditions
5. Exports hierarchical CSV with skills and their call dependencies

Input: Directory containing .TcPOU files
Output: Skill.csv with AAS-compatible structure
"""

import re
import csv
from pathlib import Path
import xml.etree.ElementTree as ET


class TwinCatRegexPatterns:
    """Regular expressions for parsing TwinCAT Structured Text code."""
    
    def __init__(self):
        # Comment patterns
        self.block_comment = re.compile(r"\(\*.*?\*\)", re.DOTALL)
        self.line_comment = re.compile(r"//.*?$", re.MULTILINE)

        # Assignment patterns: variable := value;
        self.assignment_statement = re.compile(
            r"^\s*(?P<lhs>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s*:=\s*(?P<rhs>[^;]+?)\s*;?$"
        )
        self.boolean_value = re.compile(r"^(?:TRUE|FALSE|0|1)$", re.IGNORECASE)

        # Method/Action call patterns
        self.method_call_with_receiver = re.compile(
            r"\b(?P<receiver>[A-Za-z_]\w*)(?:\^\.)?(?:\.[A-Za-z_]\w*(?:\^\.)?)*\."
            r"(?P<method_name>(?:ACT|METH)_[A-Za-z_]\w*)\s*\(\s*\)\s*;",
            re.IGNORECASE,
        )
        self.bare_method_call = re.compile(
            r"\b(?P<method_name>(?:ACT|METH)_[A-Za-z_]\w*)\s*\(\s*\)\s*;", 
            re.IGNORECASE
        )

        # Control structure patterns (for filtering out nested code)
        self.if_then = re.compile(r"\bIF\b.*\bTHEN\b", re.IGNORECASE)
        self.elsif_then = re.compile(r"\bELSIF\b.*\bTHEN\b", re.IGNORECASE)
        self.else_statement = re.compile(r"^\s*ELSE\b", re.IGNORECASE)
        self.end_if = re.compile(r"^\s*END_IF\b", re.IGNORECASE)

        self.case_of = re.compile(r"\bCASE\b.*\bOF\b", re.IGNORECASE)
        self.end_case = re.compile(r"^\s*END_CASE\b", re.IGNORECASE)

        self.for_loop = re.compile(r"\bFOR\b.*\bDO\b", re.IGNORECASE)
        self.end_for = re.compile(r"^\s*END_FOR\b", re.IGNORECASE)

        self.while_loop = re.compile(r"\bWHILE\b.*\bDO\b", re.IGNORECASE)
        self.end_while = re.compile(r"^\s*END_WHILE\b", re.IGNORECASE)

        self.repeat_loop = re.compile(r"^\s*REPEAT\b", re.IGNORECASE)
        self.until_end_repeat = re.compile(r"\bUNTIL\b.*\bEND_REPEAT\b", re.IGNORECASE)

        # Declaration patterns
        self.simple_declaration = re.compile(
            r"^\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*)\s*;", 
            re.MULTILINE
        )
        self.pointer_declaration = re.compile(
            r"^\s*([A-Za-z_]\w*)\s*:\s*(?:POINTER\s+TO|REFERENCE\s+TO)\s*([A-Za-z_]\w*)\s*;",
            re.IGNORECASE | re.MULTILINE,
        )
        self.function_block_header = re.compile(
            r"\bFUNCTION_BLOCK\b\s+(?:ABSTRACT\s+)?([A-Za-z_]\w*)", 
            re.IGNORECASE
        )


class FileUtilities:
    """File I/O operations, text processing, and XML helper methods."""
    
    def __init__(self, regex_patterns):
        self.regex = regex_patterns

    def read_file_with_fallback_encodings(self, file_path):
        """
        Read text file trying multiple encodings to handle various file formats.
        
        Args:
            file_path: Path to the file to read
            
        Returns:
            str: File content as string
        """
        encodings = ("utf-8", "utf-8-sig", "utf-16-le", "utf-16", "cp1252", "latin-1")
        path = Path(file_path)
        
        for encoding in encodings:
            try:
                return path.read_text(encoding=encoding)
            except (UnicodeDecodeError, UnicodeError, OSError):
                continue
                
        # Final fallback: read as bytes and decode with error handling
        return path.read_bytes().decode("utf-8", errors="ignore")

    def remove_comments(self, code_text):
        """
        Remove both block comments (* ... *) and line comments (// ...) from code.
        
        Args:
            code_text: Structured Text code as string
            
        Returns:
            str: Code with comments removed
        """
        if not code_text:
            return ""
            
        # Remove block comments first
        code_no_block = self.regex.block_comment.sub("", code_text)
        # Then remove line comments
        code_clean = self.regex.line_comment.sub("", code_no_block)
        
        return code_clean

    def extract_function_block_name(self, xml_root, fallback_name):
        """
        Extract function block name from XML structure or use filename as fallback.
        
        Args:
            xml_root: Parsed XML root element
            fallback_name: Name to use if extraction fails
            
        Returns:
            str: Function block name
        """
        # Try to get name from POU element
        pou_element = xml_root.find(".//POU")
        if pou_element is not None:
            name = pou_element.get("Name") or pou_element.get("name")
            if name:
                return name
                
        # Try to extract from declaration section
        declaration_element = xml_root.find(".//Declaration")
        if declaration_element is not None:
            declaration_text = "".join(declaration_element.itertext())
            match = self.regex.function_block_header.search(declaration_text)
            if match:
                return match.group(1)
                
        return fallback_name

    def get_declaration_section(self, xml_root):
        """
        Extract the declaration section text from XML.
        
        Args:
            xml_root: Parsed XML root element
            
        Returns:
            str: Declaration section content
        """
        declaration_element = xml_root.find(".//Declaration")
        return "".join(declaration_element.itertext()) if declaration_element is not None else ""


class PouXmlParser:
    """Parses TwinCAT POU XML files to extract methods, actions, and variable declarations."""
    
    def __init__(self, regex_patterns, file_utils):
        self.regex = regex_patterns
        self.file_utils = file_utils

    def build_variable_type_map(self, declaration_text):
        """
        Parse declaration text to create {variable_name: type_name} mapping.
        
        Args:
            declaration_text: Raw declaration section text
            
        Returns:
            dict: Mapping of variable names to their types
        """
        clean_text = self.file_utils.remove_comments(declaration_text or "")
        type_map = {}
        
        # Parse simple variable declarations: var_name : type;
        for match in self.regex.simple_declaration.finditer(clean_text):
            var_name, type_name = match.group(1), match.group(2)
            type_map[var_name] = type_name
            
        # Parse pointer/reference declarations: var_name : POINTER TO type;
        for match in self.regex.pointer_declaration.finditer(clean_text):
            var_name, type_name = match.group(1), match.group(2)
            type_map[var_name] = type_name
            
        return type_map

    def iterate_methods_and_actions(self, xml_root):
        """
        Generator that yields all methods (METH_*) and actions (ACT_*) from XML.
        
        Args:
            xml_root: Parsed XML root element
            
        Yields:
            tuple: (method_name, method_code)
        """
        for element in xml_root.iter():
            tag_name = element.tag.split("}")[-1].lower()  # Handle namespaced XML
            
            if tag_name not in ("method", "action"):
                continue
                
            method_name = element.get("Name") or element.get("name") or ""
            
            # Only process methods and actions with specific prefixes
            if not (method_name.startswith("ACT_") or method_name.startswith("METH_")):
                continue
                
            # Extract all ST (Structured Text) code from the method
            code_sections = []
            for st_element in element.iter():
                if st_element.tag.split("}")[-1].lower() == "st":
                    code_sections.append("".join(st_element.itertext()))
                    
            method_code = "\n".join(code_sections)
            yield method_name, method_code


class StructuredTextAnalyzer:
    """Analyzes Structured Text code to extract skills, properties, and references."""
    
    def __init__(self, regex_patterns, file_utils):
        self.regex = regex_patterns
        self.file_utils = file_utils

    def convert_to_skill_name(self, method_name):
        """
        Convert ACT_* or METH_* method names to Skill_* format.
        
        Args:
            method_name: Original method/action name
            
        Returns:
            str: Skill name in standardized format
        """
        if method_name.startswith("ACT_"):
            return "Skill_" + method_name[4:]
        if method_name.startswith("METH_"):
            return "Skill_" + method_name[5:]
        return method_name

    def extract_top_level_statements(self, st_code):
        """
        Extract top-level statements while ignoring nested control structures.
        
        Args:
            st_code: Structured Text code as string
            
        Returns:
            list: List of top-level statements
        """
        clean_code = self.file_utils.remove_comments(st_code)
        statements = []
        nesting_depth = 0
        
        for raw_line in clean_code.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # Check for control structure openings (increase nesting depth)
            if (self.regex.if_then.search(line) or 
                self.regex.case_of.search(line) or
                self.regex.for_loop.search(line) or 
                self.regex.while_loop.search(line) or
                self.regex.repeat_loop.search(line)):
                nesting_depth += 1
                continue

            # Check for control structure closings (decrease nesting depth)
            if (self.regex.end_if.search(line) or 
                self.regex.end_case.search(line) or
                self.regex.end_for.search(line) or 
                self.regex.end_while.search(line) or
                self.regex.until_end_repeat.search(line) or 
                self.regex.else_statement.search(line) or 
                self.regex.elsif_then.search(line)):
                
                # Only decrease depth for proper end statements
                if (self.regex.end_if.search(line) or 
                    self.regex.end_case.search(line) or
                    self.regex.end_for.search(line) or 
                    self.regex.end_while.search(line) or
                    self.regex.until_end_repeat.search(line)):
                    nesting_depth = max(0, nesting_depth - 1)
                continue

            # Skip statements inside control structures
            if nesting_depth > 0:
                continue

            # Split compound statements (multiple statements per line)
            statement_parts = [part for part in re.split(r";\s*", line) if part != ""]
            for part in statement_parts:
                statement = part.strip()
                if not statement.endswith(";"):
                    statement += ";"
                statements.append(statement)
                
        return statements

    def extract_call_target(self, statement, current_function_block, variable_types):
        """
        Extract skill call target from a statement.
        
        Args:
            statement: Single ST statement
            current_function_block: Name of the current function block
            variable_types: Map of variable names to types
            
        Returns:
            str or None: Call target in "Type.Skill_Name" format or None if not a call
        """
        # Check for method calls with receiver: receiver.METH_Name();
        match_with_receiver = self.regex.method_call_with_receiver.search(statement)
        if match_with_receiver:
            receiver_var = match_with_receiver.group("receiver")
            method_name = match_with_receiver.group("method_name")
            
            # Determine the type of the receiver
            receiver_type = variable_types.get(receiver_var) or receiver_var
            skill_name = self.convert_to_skill_name(method_name)
            
            return receiver_type + "." + skill_name

        # Check for bare method calls: METH_Name();
        match_bare = self.regex.bare_method_call.search(statement)
        if match_bare:
            method_name = match_bare.group("method_name")
            skill_name = self.convert_to_skill_name(method_name)
            return current_function_block + "." + skill_name
            
        return None

    def analyze_skill_content(self, st_code, current_function_block, variable_types):
        """
        Analyze ST code to extract skill components.
        
        Args:
            st_code: Structured Text code for a method/action
            current_function_block: Name of the containing function block
            variable_types: Map of variable names to types
            
        Returns:
            tuple: (skill_calls, properties, boolean_references)
        """
        skill_calls = []
        properties = []
        boolean_references = []
        
        if not st_code:
            return skill_calls, properties, boolean_references

        for statement in self.extract_top_level_statements(st_code):
            # Check for assignments: variable := value;
            assignment_match = self.regex.assignment_statement.match(statement)
            if assignment_match:
                left_hand_side = assignment_match.group("lhs").strip()
                right_hand_side = assignment_match.group("rhs").strip()
                full_lhs = current_function_block + "." + left_hand_side

                properties.append((full_lhs, right_hand_side))   
                # Track boolean assignments separately for references
                if self.regex.boolean_value.match(right_hand_side):
                    root_prefix = full_lhs.split('.')[0] 
                    boolean_references.append(root_prefix)                             
                                
                continue

            # Check for method/action calls
            call_target = self.extract_call_target(statement, current_function_block, variable_types)
            if call_target:
                skill_calls.append(call_target)

        # Remove duplicates while preserving order
        def remove_duplicates(items):
            seen = set()
            unique_items = []
            for item in items:
                if item not in seen:
                    unique_items.append(item)
                    seen.add(item)
            return unique_items

        return (
            remove_duplicates(skill_calls),
            remove_duplicates(properties),
            remove_duplicates(boolean_references)
        )


class CsvExporter:
    """Exports extracted skills to AAS-compatible CSV format."""
    
    def __init__(self, output_csv_path):
        self.output_path = output_csv_path

    def write_skills_to_csv(self, function_blocks_data):
        """
        Write all function blocks and their skills to CSV file.
        
        Args:
            function_blocks_data: List of (fb_name, skill_rows) tuples
        """
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with self.output_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            # Write AAS-compatible header
            writer.writerow([
                "typeName", "idShort", "value", "valueType",
                "category", "descriptionEN", "descriptionDE", "semanticId"
            ])

            for function_block_name, skill_rows in function_blocks_data:
                if not skill_rows:
                    continue
                    
                # Open function block collection
                writer.writerow(["SubmodelElementCollection", function_block_name, "", "", "", "", "", ""])
                
                # Write all skills for this function block
                for row in skill_rows:
                    writer.writerow(row)
                    
                # Close function block collection
                writer.writerow(["End-SubmodelElementCollection", "", "", "", "", "", "", ""])


class SkillsExtractionPipeline:
    """Main pipeline that coordinates POU analysis and CSV export."""
    
    def __init__(self, tc_pou_directory, output_csv_path):
        self.tc_root = Path(tc_pou_directory)
        self.output_csv = Path(output_csv_path)
        
        # Initialize components
        self.regex_patterns = TwinCatRegexPatterns()
        self.file_utils = FileUtilities(self.regex_patterns)
        self.pou_parser = PouXmlParser(self.regex_patterns, self.file_utils)
        self.st_analyzer = StructuredTextAnalyzer(self.regex_patterns, self.file_utils)
        self.csv_exporter = CsvExporter(self.output_csv)

    def execute(self):
        """Execute the complete skills extraction pipeline."""
        if not self.tc_root.exists():
            print("ERROR: TwinCAT POU directory not found:", self.tc_root)
            return

        function_blocks_with_skills = []  # List of (fb_name, skill_rows) tuples

        # Find all .TcPOU files in directory tree
        pou_files = sorted(self.tc_root.rglob("*.TcPOU"))
        
        for pou_file in pou_files:
            try:
                # Parse XML file
                xml_content = self.file_utils.read_file_with_fallback_encodings(pou_file)
                xml_root = ET.fromstring(xml_content)
            except ET.ParseError as e:
                print("WARN: XML parsing failed for:", pou_file, "(", e, ")")
                continue
            except Exception as e:
                print("WARN: Failed to process:", pou_file, "(", e, ")")
                continue

            # Extract function block information
            function_block_name = self.file_utils.extract_function_block_name(xml_root, pou_file.stem)
            declaration_text = self.file_utils.get_declaration_section(xml_root)
            variable_type_map = self.pou_parser.build_variable_type_map(declaration_text)

            skill_rows_for_fb = []  # All CSV rows for this function block

            # Process each method and action
            for method_name, method_code in self.pou_parser.iterate_methods_and_actions(xml_root):
                skill_name = self.st_analyzer.convert_to_skill_name(method_name)
                
                # Analyze the method code
                skill_calls, properties, boolean_refs = self.st_analyzer.analyze_skill_content(
                    method_code, function_block_name, variable_type_map
                )

                # Skip empty skills (no calls, properties, or references)
                if not skill_calls and not properties and not boolean_refs:
                    continue

                # Build CSV rows for this skill
                skill_rows = []
                
                # Open skill collection
                full_skill_name = f"{function_block_name}.{skill_name}"
                skill_rows.append(["SubmodelElementCollection", full_skill_name, "", "", "", "", "", ""])

                # Add call references
                for call_target in skill_calls:
                    skill_rows.append(["ReferenceElement", "Call", call_target, "", "", "", "", ""])

                # Add condition block if there are properties or boolean references
                if properties or boolean_refs:
                    skill_rows.append(["SubmodelElementCollection", "Precondition", "", "", "", "", "", ""])
                    
                    # Add properties
                    for lhs, rhs in properties:
                        # Determine value type
                        value_type = "bool" if rhs.strip().upper() in ("TRUE", "FALSE") else ""
                        skill_rows.append(["Property", lhs, rhs, value_type, "", "", "", ""])
                    
                    # Add boolean references as calls
                    seen = set()
                    unique_prefixes = []
                    for p in boolean_refs:
                        if p not in seen:
                            seen.add(p)
                            unique_prefixes.append(p)

                    for prefix in unique_prefixes:
                        skill_rows.append(["ReferenceElement", "Call", prefix, "", "", "", "", ""])
                    skill_rows.append(["End-SubmodelElementCollection", "", "", "", "", "", "", ""])

                # Close skill collection
                skill_rows.append(["End-SubmodelElementCollection", "", "", "", "", "", "", ""])
                
                skill_rows_for_fb.extend(skill_rows)

            # Only include function blocks that have skills
            if skill_rows_for_fb:
                function_blocks_with_skills.append((function_block_name, skill_rows_for_fb))

        # Export to CSV
        self.csv_exporter.write_skills_to_csv(function_blocks_with_skills)
        print("SUCCESS: Skills CSV saved io:", self.output_csv)

BASE_DIR = Path(__file__).resolve().parent
TC_POU_DIRECTORY = BASE_DIR / "plc-referenceimplementation" / "xPPU_Lib" / "xPPU_Lib" / "05_HardwareControl"
OUTPUT_CSV_PATH = BASE_DIR / "Skill.csv"

if __name__ == "__main__":
    pipeline = SkillsExtractionPipeline(TC_POU_DIRECTORY, OUTPUT_CSV_PATH)
    pipeline.execute()