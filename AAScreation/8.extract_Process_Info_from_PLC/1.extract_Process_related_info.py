#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PLC Function Block Parser and SMC Documentation Generator

Parses TwinCAT .TcPOU files, extracts FB definitions, variables, properties (GET),
and methods, formats them to SMC text, and adds a "Call Skill" section that lists
unique METH/ACT calls across the FB and its inheritance chain, resolving receivers
(e.g., m_ptrCrane^, o_VacuumGripper) to their declared types (Crane, VacuumGripper).
"""

from pathlib import Path
import re
import xml.etree.ElementTree as ET
from collections import defaultdict


class Config:
    base = Path(__file__).resolve().parent
    project_root = base / "plc-referenceimplementation"
    output_dir = base / "output"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "Process_list.txt"

    group_parent_levels = 1
    step_logic_label = "logic"


class RegexPatterns:
    num_pattern = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    
    # FB header
    fb_header = re.compile(
        r"\bFUNCTION_BLOCK\b\s+(?:ABSTRACT\s+)?(?P<name>[A-Za-z_]\w*)"
        r"(?:\s+EXTENDS\s+(?P<base>[A-Za-z_]\w*))?",
        re.IGNORECASE | re.DOTALL,
    )

    # VAR blocks
    var_input_block = re.compile(
        r"(?im)^[ \t]*VAR_INPUT(?:\s+(?:RETAIN|CONSTANT|PERSISTENT))?\s*\r?\n(.*?)(?=^[ \t]*END_VAR\s*$)",
        re.DOTALL | re.MULTILINE,
    )
    var_output_block = re.compile(
        r"(?im)^[ \t]*VAR_OUTPUT(?:\s+(?:RETAIN|CONSTANT|PERSISTENT))?\s*\r?\n(.*?)(?=^[ \t]*END_VAR\s*$)",
        re.DOTALL | re.MULTILINE,
    )
    var_inout_block = re.compile(
        r"(?im)^[ \t]*VAR_IN_OUT(?:\s+(?:RETAIN|CONSTANT|PERSISTENT))?\s*\r?\n(.*?)(?=^[ \t]*END_VAR\s*$)",
        re.DOTALL | re.MULTILINE,
    )
    var_block = re.compile(
        r"(?im)^[ \t]*VAR(?!_INPUT|_OUTPUT|_IN_OUT)(?:\s+(?:RETAIN|CONSTANT|PERSISTENT))?\s*\r?\n(.*?)(?=^[ \t]*END_VAR\s*$)",
        re.DOTALL | re.MULTILINE,
    )

    # Comments and declaration CDATA
    block_comment = re.compile(r"\(\*.*?\*\)", re.DOTALL)
    decl_cdata = re.compile(
        r"<Declaration>\s*<!\[CDATA\[(.*?)\]\]>\s*</Declaration>",
        re.IGNORECASE | re.DOTALL,
    )

    # Comparison and boolean expressions (for pretty VAR printing)
    num_pattern = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
    comparison_expression = re.compile(
        rf"""^\s*(?P<lhs>[A-Za-z_]\w*)\s*:\s*ComparisonExpression\(
            \s*(?P<procvar>EProcessVariables\.[A-Za-z_]\w*)\s*,\s*
            EComparisonType\.(?P<cmp>[A-Za-z_]+)\s*,\s*
            EDataType\.(?P<dtype>binary|numeric|text)\s*,\s*
            (?P<bool>TRUE|FALSE|True|False)\s*,\s*
            (?P<num>{num_pattern})\s*,\s*
            '(?P<txt>[^']*)'\s*,\s*
            (?P<enabled>TRUE|FALSE|True|False)\s*
            \)\s*;?\s*$""",
        re.IGNORECASE | re.VERBOSE,
    )
    boolean_expression = re.compile(
        r"""^\s*(?P<lhs>[A-Za-z_]\w*)\s*:\s*BoolExpression\(
            \s*(?P<left>[^,]+?)\s*,\s*
            EBoolOperation\.(?P<op>[A-Za-z_]+)\s*,\s*
            (?P<right>[^)]+?)\s*
            \)\s*;?\s*$""",
        re.IGNORECASE | re.VERBOSE,
    )

    # ValueExpression(name: ValueExpression(EDataType.binary/numeric/text, BOOL, NUM, 'TXT', ENABLED))
    value_expression = re.compile(
        rf"""^\s*(?P<lhs>[A-Za-z_]\w*)\s*:\s*ValueExpression\(
            \s*EDataType\.(?P<dtype>binary|numeric|text)\s*,\s*
            (?P<bool>TRUE|FALSE|True|False)\s*,\s*
            (?P<num>{num_pattern})\s*,\s*
            '(?P<txt>[^']*)'\s*,\s*
            (?P<enabled>TRUE|FALSE|True|False)
            \)\s*;?\s*$""",
        re.IGNORECASE | re.VERBOSE,
    )
    
    # Control structure
    control_line = re.compile(
        r"^\s*(IF\b.*\bTHEN|ELSIF\b.*\bTHEN|ELSE\b|END_IF\b|"
        r"CASE\b.*\bOF\b|END_CASE\b|"
        r"FOR\b.*\bDO\b|END_FOR\b|"
        r"WHILE\b.*\bDO\b|END_WHILE\b|"
        r"REPEAT\b|UNTIL\b.*\bEND_REPEAT\b)\s*$",
        re.IGNORECASE,
    )
    case_mstep_start = re.compile(r"^\s*CASE\s+m_step\s+OF\s*$", re.IGNORECASE)
    case_start_any = re.compile(r"^\s*CASE\s+(?P<var>[A-Za-z_]\w*)\s+OF\s*$", re.IGNORECASE)
    case_label = re.compile(r"^\s*(\d+)\s*:\s*(?://\s*(.+?)\s*)?;?\s*$", re.IGNORECASE)

    # Block boundaries
    re_if_then = re.compile(r"^\s*IF\b.*\bTHEN\b", re.IGNORECASE)
    re_end_if = re.compile(r"^\s*END_IF\b", re.IGNORECASE)
    re_case_of = re.compile(r"^\s*CASE\b.*\bOF\b", re.IGNORECASE)
    re_end_case = re.compile(r"^\s*END_CASE\b", re.IGNORECASE)
    re_for_do = re.compile(r"^\s*FOR\b.*\bDO\b", re.IGNORECASE)
    re_end_for = re.compile(r"^\s*END_FOR\b", re.IGNORECASE)
    re_while_do = re.compile(r"^\s*WHILE\b.*\bDO\b", re.IGNORECASE)
    re_end_while = re.compile(r"^\s*END_WHILE\b", re.IGNORECASE)
    re_repeat = re.compile(r"^\s*REPEAT\b", re.IGNORECASE)
    re_until_endrep = re.compile(r"^\s*UNTIL\b.*\bEND_REPEAT\b", re.IGNORECASE)
    re_else_like = re.compile(r"^\s*(ELSIF\b.*\bTHEN\b|ELSE\b)\s*$", re.IGNORECASE)

    # Method/Action call like: m_ptrCrane^.METH_CarrierStop();  o_VacuumGripper.METH_Release();
    meth_call = re.compile(
        r"""
        (?:                                   # optional receiver (may end with ^)
            (?P<recv>[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*(?:\^)?)\s*\.
        )?
        \s*(?P<prefix>METH|ACT)_(?P<name>[A-Za-z_]\w*)\s*\(
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    # "name: TYPE;"  "name: POINTER TO Crane;"
    var_decl_kv = re.compile(
        r"^\s*(?P<name>[A-Za-z_]\w*)\s*:\s*(?P<typ>[^;]+?)\s*;\s*$", re.IGNORECASE
    )
    ptr_or_ref_to = re.compile(
        r"(?:POINTER\s+TO|REFERENCE\s+TO)\s+([A-Za-z_]\w*)", re.IGNORECASE
    )


class PLCUtilities:
    def __init__(self, regex_patterns):
        self.regex = regex_patterns

    def is_control_line(self, text):
        return bool(self.regex.control_line.match(text.strip()))

    def is_comment_only(self, text):
        return text.strip().startswith("//")

    def read_text_with_fallback_encoding(self, file_path):
        for encoding in ("utf-8-sig", "utf-16-le", "utf-16", "cp1252", "latin-1"):
            try:
                return file_path.read_text(encoding=encoding)
            except Exception:
                pass
        return file_path.read_bytes().decode("utf-8", errors="ignore")

    def extract_declaration_from_xml(self, file_path):
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            for element in root.iter():
                if element.tag.split("}")[-1].lower() == "declaration":
                    return "".join(element.itertext())
        except Exception:
            pass
        raw_text = self.read_text_with_fallback_encoding(file_path)
        match = self.regex.decl_cdata.search(raw_text)
        return match.group(1) if match else None

    def extract_function_block_info(self, declaration_text):
        if not declaration_text:
            return None, None
        match = self.regex.fb_header.search(declaration_text)
        if not match:
            return None, None
        return match.group("name"), match.group("base")

    def get_parent_directory_label(self, directory_path, levels):
        parts, current = [], directory_path
        for _ in range(levels):
            parts.append(current.name)
            current = current.parent
        return "/".join(reversed(parts))

    def split_variable_declarations(self, var_block_text):
        text_without_comments = self.regex.block_comment.sub("", var_block_text)
        lines = []
        for raw_line in text_without_comments.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            lines.append(stripped)
        items, current = [], ""
        for line in lines:
            current = (current + " " + line).strip() if current else line
            if current.endswith(";"):
                items.append(current)
                current = ""
        if current:
            items.append(current)
        return items

    def extract_variable_key(self, declaration_item):
        match = re.match(r"\s*([A-Za-z_]\w*)\s*:", declaration_item)
        return match.group(1) if match else declaration_item.strip()

    def normalize_var_type(self, typ: str) -> str:
        if not typ:
            return ""
        typ = typ.strip()
        m = self.regex.ptr_or_ref_to.search(typ)
        if m:
            return m.group(1)
        m2 = re.search(r"ARRAY\s*\[[^\]]+\]\s*OF\s*([A-Za-z_]\w*)", typ, re.IGNORECASE)
        if m2:
            return m2.group(1)
        m3 = re.match(r"([A-Za-z_]\w*)", typ)
        return m3.group(1) if m3 else typ

    def collect_var_types_from_decls(self, decl_items):
        out = {}
        for it in decl_items:
            m = self.regex.var_decl_kv.match(it)
            if not m:
                continue
            name = m.group("name")
            typ = self.normalize_var_type(m.group("typ"))
            if name and typ:
                out[name] = typ
        return out


class StructuredTextParser:
    def __init__(self, config, regex_patterns, utilities):
        self.config = config
        self.regex = regex_patterns
        self.utils = utilities

    def parse_variable_items(self, raw_items):
        comparison_operators = {
            "equals": "=", "not_equals": "!=", "greater": ">",
            "greater_eq": ">=", "less": "<", "less_eq": "<=",
        }
        expressions, other_items = {}, []
        for item in raw_items:
            match = self.regex.comparison_expression.match(item)
            if match:
                name = match.group("lhs")
                variable = match.group("procvar").split(".")[-1]
                operator = comparison_operators.get(match.group("cmp").lower(), match.group("cmp"))
                data_type = match.group("dtype").lower()
                enabled = match.group("enabled").upper()
                if data_type == "binary":
                    value = match.group("bool").upper()
                elif data_type == "numeric":
                    value = match.group("num")
                else:
                    value = f"'{match.group('txt')}'"
                expression = f"{variable} {operator} {value}"
                if enabled == "FALSE":
                    expression += "  (disabled)"
                expressions[name] = expression
                continue

            match = self.regex.boolean_expression.match(item)
            if match:
                boolean_operators = {"and_op": "AND", "or_op": "OR", "xor_op": "XOR"}
                name = match.group("lhs")
                left_operand = match.group("left").strip()
                right_operand = match.group("right").strip()
                operator = boolean_operators.get(match.group("op").lower(), match.group("op"))
                expression = f"({left_operand}) {operator} ({right_operand})"
                expressions[name] = expression
                continue

            match = self.regex.value_expression.match(item)
            if match:
                name = match.group("lhs")
                dtype = match.group("dtype").lower()
                enabled = match.group("enabled").upper()
                if dtype == "binary":
                    value = match.group("bool").upper()
                elif dtype == "numeric":
                    value = match.group("num")
                else:  # text
                    value = f"'{match.group('txt')}'"
                expression = f"{value}"
                if enabled == "FALSE":
                    expression += "  (disabled)"
                expressions[name] = expression
                continue

            other_items.append(item)
        return expressions, other_items

    def resolve_expression_dependencies(self, expressions):
        memo = {}
        name_patterns = {name: re.compile(rf"\b{re.escape(name)}\b") for name in expressions.keys()}

        def resolve_expression(name, call_stack):
            if name in memo:
                return memo[name]
            if name not in expressions:
                return name
            if name in call_stack:
                return expressions[name]
            call_stack.add(name)
            expression = expressions[name]
            for dependency, pattern in name_patterns.items():
                if dependency == name:
                    continue
                if pattern.search(expression):
                    expression = pattern.sub(
                        lambda _: f"({resolve_expression(dependency, call_stack)})", expression
                    )
            call_stack.remove(name)
            memo[name] = expression
            return expression

        return {name: resolve_expression(name, set()) for name in expressions.keys()}

    def identify_top_level_expressions(self, expressions):
        referenced = set()
        for name, expression in expressions.items():
            for other_name in expressions.keys():
                if other_name == name:
                    continue
                if re.search(rf"\b{re.escape(other_name)}\b", expression):
                    referenced.add(other_name)
        priority_names = ["m_precondition", "m_postcondition", "precondition", "postcondition"]
        top_level = [n for n in expressions.keys() if n not in referenced]
        return sorted(
            top_level,
            key=lambda n: (priority_names.index(n) if n in priority_names else len(priority_names), n.lower()),
        )

    def prettify_variable_declaration(self, declaration_item):
        match = self.regex.comparison_expression.match(declaration_item)
        if match:
            comparison_operators = {
                "equals": "=", "not_equals": "!=", "greater": ">",
                "greater_eq": ">=", "less": "<", "less_eq": "<=",
            }
            variable = match.group("procvar").split(".")[-1]
            operator = comparison_operators.get(match.group("cmp").lower(), match.group("cmp"))
            data_type = match.group("dtype").lower()
            enabled = match.group("enabled").upper()
            if data_type == "binary":
                value = match.group("bool").upper()
            elif data_type == "numeric":
                value = match.group("num")
            else:
                value = f"'{match.group('txt')}'"
            pretty_expression = f"{variable} {operator} {value}"
            if enabled == "FALSE":
                pretty_expression += "  (disabled)"
            return f"{match.group('lhs')}: {pretty_expression};"

        match = self.regex.boolean_expression.match(declaration_item)
        if match:
            boolean_operators = {"and_op": "AND", "or_op": "OR", "xor_op": "XOR"}
            left_operand = match.group("left").strip()
            right_operand = match.group("right").strip()
            operator = boolean_operators.get(match.group("op").lower(), match.group("op"))
            return f"{match.group('lhs')}: ({left_operand}) {operator} ({right_operand});"


        match = self.regex.value_expression.match(declaration_item)
        if match:
            dtype = match.group("dtype").lower()
            enabled = match.group("enabled").upper()
            if dtype == "binary":
                value = match.group("bool").upper()
            elif dtype == "numeric":
                value = match.group("num")
            else:
                value = f"'{match.group('txt')}'"
            pretty = value + ("  (disabled)" if enabled == "FALSE" else "")
            return f"{match.group('lhs')}: {pretty};"


        return declaration_item

    def extract_implementation_lines(self, xml_node):
        lines = []
        for child in xml_node.iter():
            tag = child.tag.split("}")[-1].lower()
            if tag == "st":
                text_content = "".join(child.itertext())
                if not text_content:
                    continue
                text_content = self.regex.block_comment.sub("", text_content)
                for line in text_content.splitlines():
                    stripped = line.rstrip()
                    if not stripped.strip():
                        continue
                    if self.utils.is_comment_only(stripped):
                        continue
                    if self.utils.is_control_line(stripped) or stripped.endswith(";"):
                        lines.append(stripped)
                    else:
                        lines.append(stripped + ";")
        deduplicated = []
        for line in lines:
            if not deduplicated or deduplicated[-1] != line:
                deduplicated.append(line)
        return deduplicated

    def format_case_mstep_block(self, logic_lines):
        output_lines = []
        if not logic_lines or not self.regex.case_mstep_start.match(logic_lines[0].strip()):
            return output_lines

        index = 1
        while index < len(logic_lines):
            line = logic_lines[index].strip()
            if line.upper() == "END_CASE":
                break

            label_match = self.regex.case_label.match(line)
            if not label_match:
                index += 1
                continue

            step_number = label_match.group(1)
            comment = (label_match.group(2) or "").strip()
            title = f"step {step_number}" + (f" {comment}" if comment else "") + ":"
            output_lines.append("      " + title)

            index += 1
            branch_lines = []
            while index < len(logic_lines):
                raw_line = logic_lines[index]
                stripped_line = raw_line.strip()
                if stripped_line.upper() == "END_CASE" or self.regex.case_label.match(stripped_line):
                    break
                branch_lines.append(raw_line.rstrip("\n"))
                index += 1

            branch_index = 0
            logic_counter = 0
            while branch_index < len(branch_lines):
                raw_branch_line = branch_lines[branch_index]
                stripped_branch = raw_branch_line.strip()
                if not stripped_branch or self.utils.is_comment_only(stripped_branch):
                    branch_index += 1
                    continue

                is_if_start = self.regex.re_if_then.match(stripped_branch)
                is_case_start = self.regex.re_case_of.match(stripped_branch)
                is_for_start = self.regex.re_for_do.match(stripped_branch)
                is_while_start = self.regex.re_while_do.match(stripped_branch)
                is_repeat_start = self.regex.re_repeat.match(stripped_branch)

                if is_if_start or is_case_start or is_for_start or is_while_start or is_repeat_start:
                    block_lines, nesting_level = [], 0
                    while branch_index < len(branch_lines):
                        current_line = branch_lines[branch_index]
                        current_stripped = current_line.strip()

                        if (
                            self.regex.re_if_then.match(current_stripped)
                            or self.regex.re_case_of.match(current_stripped)
                            or self.regex.re_for_do.match(current_stripped)
                            or self.regex.re_while_do.match(current_stripped)
                            or self.regex.re_repeat.match(current_stripped)
                        ):
                            nesting_level += 1

                        block_lines.append(current_line)

                        if (
                            self.regex.re_end_if.match(current_stripped)
                            or self.regex.re_end_case.match(current_stripped)
                            or self.regex.re_end_for.match(current_stripped)
                            or self.regex.re_end_while.match(current_stripped)
                            or self.regex.re_until_endrep.match(current_stripped)
                        ):
                            nesting_level -= 1
                            if nesting_level == 0:
                                branch_index += 1
                                break
                        branch_index += 1

                    logic_counter += 1
                    output_lines.append(f"        {self.config.step_logic_label} {logic_counter}:")
                    for block_line in block_lines:
                        if self.utils.is_comment_only(block_line):
                            continue
                        output_lines.append("          " + block_line.strip())
                    continue

                output_lines.append("        " + stripped_branch)
                branch_index += 1

        return output_lines

    def format_case_generic_block(self, logic_lines):
        output_lines = []
        case_start_match = self.regex.case_start_any.match(logic_lines[0].strip()) if logic_lines else None
        if not case_start_match:
            return output_lines

        output_lines.append("      CASE:")
        index = 1
        while index < len(logic_lines):
            line_raw = logic_lines[index]
            line = line_raw.strip()
            if line.upper() == "END_CASE":
                break

            label_match = self.regex.case_label.match(line)
            if not label_match:
                index += 1
                continue

            case_label = label_match.group(1)
            output_lines.append(f"        CASE {case_label}:")
            index += 1

            branch_lines = []
            while index < len(logic_lines):
                raw_line = logic_lines[index]
                stripped = raw_line.strip()
                if stripped.upper() == "END_CASE" or self.regex.case_label.match(stripped):
                    break
                branch_lines.append(raw_line.rstrip("\n"))
                index += 1

            branch_index, logic_counter = 0, 0
            while branch_index < len(branch_lines):
                raw_branch_line = branch_lines[branch_index]
                stripped_branch = raw_branch_line.strip()
                if not stripped_branch or self.utils.is_comment_only(stripped_branch):
                    branch_index += 1
                    continue

                is_if_start = self.regex.re_if_then.match(stripped_branch)
                is_case_start = self.regex.re_case_of.match(stripped_branch)
                is_for_start = self.regex.re_for_do.match(stripped_branch)
                is_while_start = self.regex.re_while_do.match(stripped_branch)
                is_repeat_start = self.regex.re_repeat.match(stripped_branch)

                if is_if_start or is_case_start or is_for_start or is_while_start or is_repeat_start:
                    block_lines, nesting_level = [], 0
                    while branch_index < len(branch_lines):
                        current_line = branch_lines[branch_index]
                        current_stripped = current_line.strip()

                        if (
                            self.regex.re_if_then.match(current_stripped)
                            or self.regex.re_case_of.match(current_stripped)
                            or self.regex.re_for_do.match(current_stripped)
                            or self.regex.re_while_do.match(current_stripped)
                            or self.regex.re_repeat.match(current_stripped)
                        ):
                            nesting_level += 1

                        block_lines.append(current_line)

                        if (
                            self.regex.re_end_if.match(current_stripped)
                            or self.regex.re_end_case.match(current_stripped)
                            or self.regex.re_end_for.match(current_stripped)
                            or self.regex.re_end_while.match(current_stripped)
                            or self.regex.re_until_endrep.match(current_stripped)
                        ):
                            nesting_level -= 1
                            if nesting_level == 0:
                                branch_index += 1
                                break
                        branch_index += 1

                    logic_counter += 1
                    output_lines.append(f"          {self.config.step_logic_label} {logic_counter}:")
                    for block_line in block_lines:
                        if self.utils.is_comment_only(block_line):
                            continue
                        output_lines.append("            " + block_line.strip())
                    continue

                output_lines.append("          " + stripped_branch)
                branch_index += 1

        return output_lines

    def format_method_to_normalized_text(self, method_name, implementation_lines):
        filtered_lines = [line for line in implementation_lines if not self.utils.is_comment_only(line)]

        control_start_index = None
        for i, line in enumerate(filtered_lines):
            if self.utils.is_control_line(line):
                control_start_index = i
                break
        pre_control_lines = filtered_lines if control_start_index is None else filtered_lines[:control_start_index]
        logic_lines = [] if control_start_index is None else filtered_lines[control_start_index:]

        buffer = [f"{method_name}:"]
        for line in pre_control_lines:
            buffer.append("      " + line)

        if logic_lines:
            first_logic_line = logic_lines[0].strip()
            if self.regex.case_mstep_start.match(first_logic_line):
                buffer.extend(self.format_case_mstep_block(logic_lines))
            elif self.regex.case_start_any.match(first_logic_line):
                buffer.extend(self.format_case_generic_block(logic_lines))
            else:
                buffer.append("      logic:")
                for line in logic_lines:
                    buffer.append("        " + line)

        return "\n".join(buffer)


class POUIndexer:
    def __init__(self, config, regex_patterns, utilities, st_parser):
        self.config = config
        self.regex = regex_patterns
        self.utils = utilities
        self.st_parser = st_parser

    def collect_all_function_blocks(self):
        if not self.config.project_root.exists():
            raise SystemExit(f"ERROR: Project root not found: {self.config.project_root}")

        control_dirs = [d for d in self.config.project_root.rglob("03_ControlPrimitives") if d.is_dir()]
        if not control_dirs:
            raise SystemExit(f"ERROR: No '03_ControlPrimitives' folder found under {self.config.project_root}")

        function_block_index = {}
        for control_dir in control_dirs:
            pou_files = list(control_dir.rglob("*.TcPOU"))
            print(f"Scanning {control_dir} -> {len(pou_files)} TcPOU files")

            for pou_file in pou_files:
                declaration_text = self.utils.extract_declaration_from_xml(pou_file) or self.utils.read_text_with_fallback_encoding(pou_file)
                declaration_no_comments = self.regex.block_comment.sub("", declaration_text or "")
                fb_name, base_name = self.utils.extract_function_block_info(declaration_no_comments)
                if not fb_name:
                    continue

                input_vars, output_vars, inout_vars = [], [], []
                for match in self.regex.var_input_block.finditer(declaration_no_comments):
                    input_vars.extend(self.utils.split_variable_declarations(match.group(1)))
                for match in self.regex.var_output_block.finditer(declaration_no_comments):
                    output_vars.extend(self.utils.split_variable_declarations(match.group(1)))
                for match in self.regex.var_inout_block.finditer(declaration_no_comments):
                    inout_vars.extend(self.utils.split_variable_declarations(match.group(1)))

                internal_vars_raw = []
                for match in self.regex.var_block.finditer(declaration_no_comments):
                    internal_vars_raw.extend(self.utils.split_variable_declarations(match.group(1)))

                expressions, other_vars = self.st_parser.parse_variable_items(internal_vars_raw)
                if expressions:
                    resolved_expressions = self.st_parser.resolve_expression_dependencies(expressions)
                    top_level_names = self.st_parser.identify_top_level_expressions(expressions)
                    pretty_expressions = [f"{name}: {resolved_expressions[name]};" for name in top_level_names]
                else:
                    pretty_expressions = []

                properties, methods = self._extract_properties_and_methods(pou_file)
                parent_label = self.utils.get_parent_directory_label(pou_file.parent, self.config.group_parent_levels)

                var_types = {}
                var_types.update(self.utils.collect_var_types_from_decls(input_vars))
                var_types.update(self.utils.collect_var_types_from_decls(output_vars))
                var_types.update(self.utils.collect_var_types_from_decls(inout_vars))
                var_types.update(self.utils.collect_var_types_from_decls(other_vars))

                function_block_index[fb_name] = {
                    "base": base_name,
                    "label": parent_label,
                    "sections": {
                        "VAR_INPUT": [self.st_parser.prettify_variable_declaration(item) for item in input_vars],
                        "VAR_OUTPUT": [self.st_parser.prettify_variable_declaration(item) for item in output_vars],
                        "VAR_IN_OUT": [self.st_parser.prettify_variable_declaration(item) for item in inout_vars],
                        "VAR": [item for item in (other_vars + pretty_expressions) if item.strip()],
                    },
                    "properties": properties,
                    "methods": methods,
                    "var_types": var_types,
                }

        print(f" function blocks indexed: {len(function_block_index)}")
        return function_block_index

    def _extract_properties_and_methods(self, pou_file_path):
        properties_map, methods_map = {}, {}
        try:
            tree = ET.parse(pou_file_path)
            root = tree.getroot()
            for element in root.iter():
                tag = element.tag.split("}")[-1].lower()
                if tag == "property":
                    property_name = element.attrib.get("Name") or element.attrib.get("name") or "Property"
                    for child in element:
                        child_tag = child.tag.split("}")[-1].lower()
                        if child_tag == "get":
                            impl_lines = self.st_parser.extract_implementation_lines(child)
                            if not impl_lines:
                                continue
                            cleaned = []
                            for ln in impl_lines:
                                s = ln.strip()
                                if not s or re.match(r"^(VAR|END_VAR)\b", s, re.IGNORECASE):
                                    continue
                                if not s.endswith(";"):
                                    s += ";"
                                cleaned.append(s)
                            if cleaned:
                                properties_map[property_name] = cleaned
                elif tag == "method":
                    method_name = element.attrib.get("Name") or element.attrib.get("name") or "Method"
                    implementation_lines = self.st_parser.extract_implementation_lines(element)
                    if implementation_lines:
                        methods_map[method_name] = implementation_lines
        except Exception:
            pass

        return properties_map, methods_map


class FunctionBlockMerger:
    def __init__(self, function_block_index, utilities):
        self.index = function_block_index
        self.utils = utilities
        self.cache = {}

    def merge_inheritance_chain(self, function_block_name):
        if function_block_name in self.cache:
            return self.cache[function_block_name]

        if function_block_name not in self.index:
            self.cache[function_block_name] = {
                "inheritance_chain": [],
                "sections": {s: [] for s in ["VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR"]},
                "properties": {},
                "methods": {},
                "var_types": {},
            }
            return self.cache[function_block_name]

        current_data = self.index[function_block_name]
        base_name = current_data["base"]

        if base_name:
            base_merged = self.merge_inheritance_chain(base_name)
            inheritance_chain = base_merged["inheritance_chain"] + [base_name]
            merged_sections = {s: list(base_merged["sections"][s]) for s in base_merged["sections"]}
            merged_properties = dict(base_merged["properties"])
            merged_methods = dict(base_merged["methods"])
            merged_var_types = dict(base_merged.get("var_types", {}))
        else:
            inheritance_chain = []
            merged_sections = {s: [] for s in ["VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR"]}
            merged_properties, merged_methods = {}, {}
            merged_var_types = {}

        # child overrides
        for section in ["VAR_INPUT", "VAR_OUTPUT", "VAR_IN_OUT", "VAR"]:
            variables_by_key = {self.utils.extract_variable_key(decl): decl for decl in merged_sections[section]}
            for declaration in current_data["sections"][section]:
                variables_by_key[self.utils.extract_variable_key(declaration)] = declaration
            merged_sections[section] = list(variables_by_key.values())

        merged_properties.update(current_data["properties"])
        merged_methods.update(current_data["methods"])
        merged_var_types.update(current_data.get("var_types", {}))

        result = {
            "inheritance_chain": inheritance_chain,
            "sections": merged_sections,
            "properties": merged_properties,
            "methods": merged_methods,
            "var_types": merged_var_types,
        }
        self.cache[function_block_name] = result
        return result


class SMCDocumentationGenerator:
    def __init__(self, config, regex_patterns, utilities):
        self.config = config
        self.regex = regex_patterns
        self.utils = utilities

    def emit_section_to_smc(self, output_lines, section_title, items, base_indent):
        if not items:
            return
        indent = " " * base_indent
        output_lines.append(f"{indent}-SMC {section_title}:")
        for item in items:
            stripped = item.strip()
            if not stripped or self.utils.is_comment_only(stripped):
                continue
            output_lines.append(f"{indent}  -Prop {stripped}")

    def format_method_to_smc(self, method_name, formatted_method_block, base_indent):
        step_title_pattern = re.compile(r"^step\s+\d+(?:\s+.*)?:$", re.IGNORECASE)
        logic_header_pattern = re.compile(r"^logic(?:\s+\d+)?:$", re.IGNORECASE)
        case_block_pattern = re.compile(r"^CASE:$", re.IGNORECASE)
        case_number_pattern = re.compile(r"^CASE\s+\d+:$", re.IGNORECASE)

        output_lines = []
        method_indent = " " * base_indent
        smc_section_indent = " " * (base_indent + 2)
        case_child_indent = " " * (base_indent + 4)
        property_default_indent = " " * (base_indent + 4)
        property_in_case_indent = " " * (base_indent + 6)
        code_default_indent = " " * (base_indent + 8)
        code_in_case_indent = " " * (base_indent + 10)

        output_lines.append(f"{method_indent}-SMC {method_name}:")
        if not formatted_method_block:
            return output_lines

        lines = formatted_method_block.splitlines()
        body_lines = lines[1:] if lines and lines[0].strip().endswith(":") else lines

        in_logic_block = False
        logic_indent_level = 0
        nesting_level = 0
        in_case_child_block = False

        for raw_line in body_lines:
            if not raw_line.strip() or self.utils.is_comment_only(raw_line):
                continue

            line_text = raw_line.rstrip("\n")
            stripped_text = line_text.strip()
            leading_space_count = len(line_text) - len(line_text.lstrip(" "))

            if step_title_pattern.match(stripped_text):
                output_lines.append(f"{smc_section_indent}-SMC {stripped_text[:-1]}:")
                in_logic_block = False
                nesting_level = 0
                in_case_child_block = False
                continue

            if case_block_pattern.match(stripped_text):
                output_lines.append(f"{smc_section_indent}-SMC CASE:")
                in_logic_block = False
                nesting_level = 0
                in_case_child_block = False
                continue

            if case_number_pattern.match(stripped_text):
                output_lines.append(f"{case_child_indent}-SMC {stripped_text[:-1]}:")
                in_logic_block = False
                nesting_level = 0
                in_case_child_block = True
                continue

            if logic_header_pattern.match(stripped_text):
                if in_case_child_block:
                    output_lines.append(f"{property_in_case_indent}-Prop {stripped_text}")
                else:
                    output_lines.append(f"{property_default_indent}-Prop {stripped_text}")
                in_logic_block = True
                logic_indent_level = leading_space_count
                nesting_level = 0
                continue

            if in_logic_block:
                is_control_start = (
                    self.regex.re_if_then.match(stripped_text)
                    or self.regex.re_case_of.match(stripped_text)
                    or self.regex.re_for_do.match(stripped_text)
                    or self.regex.re_while_do.match(stripped_text)
                    or self.regex.re_repeat.match(stripped_text)
                )
                if is_control_start:
                    nesting_level += 1
                    output_lines.append((code_in_case_indent if in_case_child_block else code_default_indent) + stripped_text)
                    continue

                is_control_end = (
                    self.regex.re_end_if.match(stripped_text)
                    or self.regex.re_end_case.match(stripped_text)
                    or self.regex.re_end_for.match(stripped_text)
                    or self.regex.re_end_while.match(stripped_text)
                    or self.regex.re_until_endrep.match(stripped_text)
                )
                if is_control_end:
                    output_lines.append((code_in_case_indent if in_case_child_block else code_default_indent) + stripped_text)
                    nesting_level = max(0, nesting_level - 1)
                    continue

                if self.regex.re_else_like.match(stripped_text):
                    output_lines.append((code_in_case_indent if in_case_child_block else code_default_indent) + stripped_text)
                    continue

                if nesting_level > 0 and leading_space_count > logic_indent_level:
                    output_lines.append((code_in_case_indent if in_case_child_block else code_default_indent) + stripped_text)
                    continue
                else:
                    in_logic_block = False
                    nesting_level = 0

            output_lines.append((property_in_case_indent if in_case_child_block else property_default_indent) + f"-Prop {stripped_text}")

        return output_lines

    def emit_properties_to_smc(self, output_lines, properties_map, base_indent):
        if not properties_map:
            return
        indent = " " * base_indent
        output_lines.append(f"{indent}-SMC Property:")
        for pname in sorted(properties_map.keys(), key=str.lower):
            for line in properties_map[pname]:
                output_lines.append(f"{indent}  -Prop {line}")

    def _strip_prefixes(self, name: str) -> str:
        if not name:
            return name
        s = name.rstrip("^")
        if s.lower().startswith("m_ptr"):
            s = s[5:]
        for pre in ("m_", "i_", "q_", "o_", "g_", "p_"):
            if s.startswith(pre):
                s = s[len(pre):]
                break
        return s

    def _resolve_receiver_class(self, recv_chain: str, var_types: dict) -> str:
        if not recv_chain:
            return ""
        token = recv_chain.strip().split(".")[-1].rstrip("^")
        if not token:
            return ""
        typ = var_types.get(token, "")
        if typ:
            return typ
        stripped = self._strip_prefixes(token)
        typ2 = var_types.get(stripped, "")
        if typ2:
            return typ2
        return stripped or token

    def collect_called_skills(self, methods_map: dict, var_types: dict, regex) -> list[str]:
        found = set()
        for _, impl_lines in methods_map.items():
            for line in impl_lines:
                for mt in regex.meth_call.finditer(line):
                    recv_raw = (mt.group("recv") or "").strip()
                    cls = self._resolve_receiver_class(recv_raw, var_types)
                    pref = mt.group("prefix").upper()
                    nm = mt.group("name")
                    if cls:
                        found.add(f"{cls}.{pref}_{nm}")
                    else:
                        found.add(f"{pref}_{nm}")
        return sorted(found, key=str.lower)


    def emit_called_skills(self, output_lines, called: list[str], base_indent: int):
        """
        make 'Class.METH_Name' / 'Class.ACT_Name' into 'Class_Skill_Name' output。
        if no class, make 'METH_Name' / 'ACT_Name' into 'Skill_Name'.
        """
        if not called:
            return

        def to_skill(sig: str) -> str:
            m = re.match(r"^(?P<cls>[A-Za-z_]\w*)\.(?P<prefix>METH|ACT)_(?P<name>[A-Za-z_]\w*)$", sig, re.IGNORECASE)
            if m:
                return f"{m.group('cls')}_Skill_{m.group('name')}"
            m2 = re.match(r"^(?P<prefix>METH|ACT)_(?P<name>[A-Za-z_]\w*)$", sig, re.IGNORECASE)
            if m2:
                return f"Skill_{m2.group('name')}"
            return sig.replace(".", "_").replace("METH_", "Skill_").replace("ACT_", "Skill_")

        indent = " " * base_indent
        output_lines.append(f"{indent}-SMC Call Skill:")
        for i, sig in enumerate(called, 1):
            output_lines.append(f"{indent}  -Ref Skill{i}: {to_skill(sig)}")


def main():
    regex_patterns = RegexPatterns()
    utilities = PLCUtilities(regex_patterns)
    st_parser = StructuredTextParser(Config, regex_patterns, utilities)
    indexer = POUIndexer(Config, regex_patterns, utilities, st_parser)

    function_block_index = indexer.collect_all_function_blocks()

    grouped_blocks = defaultdict(list)
    for fb_name, info in function_block_index.items():
        grouped_blocks[info["label"]].append(fb_name)

    merger = FunctionBlockMerger(function_block_index, utilities)
    documentation_generator = SMCDocumentationGenerator(Config, regex_patterns, utilities)

    output_lines = []
    for group_label in sorted(grouped_blocks.keys()):
        output_lines.append(f"SMC {group_label}")
        for fb_name in sorted(grouped_blocks[group_label], key=str.lower):
            merged_data = merger.merge_inheritance_chain(fb_name)

            output_lines.append(f"  -SMC Process {fb_name}")

            base_class = function_block_index.get(fb_name, {}).get("base")
            if base_class:
                output_lines.append(f"    -Ref Extends: {base_class}")

            internal_vars = sorted(merged_data["sections"]["VAR"])
            documentation_generator.emit_section_to_smc(output_lines, "VAR", internal_vars, base_indent=4)

            documentation_generator.emit_properties_to_smc(
                output_lines, merged_data["properties"], base_indent=4
            )

            if merged_data["methods"]:
                output_lines.append("    -SMC METHODS:")
                for method_name in sorted(merged_data["methods"].keys(), key=str.lower):
                    formatted_block = st_parser.format_method_to_normalized_text(
                        method_name, merged_data["methods"][method_name]
                    )
                    method_lines = documentation_generator.format_method_to_smc(
                        method_name, formatted_block, base_indent=6
                    )
                    output_lines.extend(method_lines)

            called = documentation_generator.collect_called_skills(
                merged_data["methods"], merged_data.get("var_types", {}), regex_patterns
            )
            documentation_generator.emit_called_skills(output_lines, called, base_indent=4)

            output_lines.append("")
        output_lines.append("")

    Config.output_file.write_text("\n".join(output_lines), encoding="utf-8")
    print(f"SUCCESS, file saved in {Config.output_file}")


if __name__ == "__main__":
    main()
