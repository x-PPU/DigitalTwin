import csv
import os
import re
import xml.etree.ElementTree as ET

regex_specials = set(r".*+?[]()^$|\\")  


def looks_like_regex(pattern):
    """Return True if the pattern contains regex-special characters."""
    if not pattern:
        return False
    return any(c in regex_specials for c in pattern)


def sanitize_id_short(s):
    """
    Make idShort AAS-friendly:
    - Keep letters, digits, underscores; replace others with '_'
    - If first char is not a letter, prefix with 'a_'
    """
    s = re.sub(r"[^A-Za-z0-9_]", "_", s or "")
    if not s or not s[0].isalpha():
        s = "a_" + s
    return s

class TypeMapper:
    """Map PLC primitive types to output CSV valueType and produce sensible defaults."""

    def __init__(self):
        self.plc_to_value_type = {
            "BOOL": "boolean",
            "INT": "int", "DINT": "int", "UINT": "int", "UDINT": "int",
            "STRING": "string",
        }

    def default_value(self, value_type):
        """Return a default value for an output valueType."""
        if value_type == "boolean":
            return "FALSE"
        if value_type in ("float", "int"):
            return "0"
        return ""

    def from_plc_or_name(self, full_name, plc_type):
        """
        Infer (valueType, defaultValue) by PLC type first, then name heuristic (AI/AO/DI/DO), else string.
        """
        if plc_type:
            vt = self.plc_to_value_type.get(plc_type.strip().upper())
            if vt:
                return vt, self.default_value(vt)

        # Name heuristics
        if re.search(r"\.(AI|AO)_", full_name):
            return "float", "0"
        if re.search(r"\.(DI|DO)_", full_name):
            return "boolean", "FALSE"

        return "string", ""


class ManualRuleRouter:
    """
    Manual routing and type overrides.

    Rules structure (per section 'Sensors'/'Actuators'):
      - item can be a plain string: exact match - route only
      - or a dict: {"pattern": <str or regex>, "valueType": "...", "value": "..."} -- route + override type/value
    """

    def __init__(self, rules):
        # expect {"Sensors": [...], "Actuators": [...]}
        self.rules = rules or {"Sensors": [], "Actuators": []}

    def route(self, full_name):
        """
        Return (section, (valueType, value) or None) if matched, else (None, None).
        """
        for section in ("Sensors", "Actuators"):
            for entry in self.rules.get(section, []):
                if isinstance(entry, str):
                    if full_name == entry:
                        return section, None
                elif isinstance(entry, dict):
                    pat = entry.get("pattern", "")
                    if not pat:
                        continue
                    matched = re.search(pat, full_name) is not None if looks_like_regex(pat) else (full_name == pat)
                    if matched:
                        vt = entry.get("valueType")
                        val = entry.get("value")
                        return section, (vt, val) if (vt is not None or val is not None) else None
        return None, None


class AASDataBuilder:
    """
    Accumulates rows for the output CSV and provides helpers to add / locate sections.

    Row schema:
        ["typeName", "idShort", "value", "valueType", "category", "descriptionEN", "descriptionDE", "semanticId"]
    """

    def __init__(self):
        self.rows = []
        self._init_header_and_status()

    def _init_header_and_status(self):
        # header
        self.rows.append([
            "typeName","idShort","value","valueType","category",
            "descriptionEN","descriptionDE","semanticId"
        ])

        # smc Status
        self.rows.append(["SubmodelElementCollection", "Status", "", "", "", "", "", ""])

        # ├─ smc Automode
        self.rows.append(["SubmodelElementCollection", "Automode", "", "", "", "", "", ""])
        # │   └─ smc buttonManager
        self.rows.append(["SubmodelElementCollection", "buttonManager", "", "", "", "", "", ""])
        self.rows.append(["End-SubmodelElementCollection", "", "", "", "", "", "", ""])   
        self.rows.append(["End-SubmodelElementCollection", "", "", "", "", "", "", ""])   

        # ├─ smc ManualMode
        self.rows.append(["SubmodelElementCollection", "ManualMode", "", "", "", "", "", ""])
        # │   ├─ properties
        self.rows.append(["Property", "Port",  "851",               "string", "", "", "", ""])
        self.rows.append(["Property", "AMSID", "192.168.82.13.1.1", "string", "", "", "", ""])
        # │   └─ smc buttonManager
        self.rows.append(["SubmodelElementCollection", "buttonManager", "", "", "", "", "", ""])
        self.rows.append(["End-SubmodelElementCollection", "", "", "", "", "", "", ""])   
        self.rows.append(["End-SubmodelElementCollection", "", "", "", "", "", "", ""])  

        # end Status
        self.rows.append(["End-SubmodelElementCollection", "", "", "", "", "", "", ""])


    def _find_smc_index(self, idshort):
        """Find the index of the SMC row by idShort. Return -1 if not found."""
        for i, r in enumerate(self.rows):
            if r[0] == "SubmodelElementCollection" and r[1] == idshort:
                return i
        return -1

    def _find_bounds(self, start_idx):
        """Find the [start, end] indices of a SMC block."""
        depth = 0
        for j in range(start_idx + 1, len(self.rows)):
            t = self.rows[j][0]
            if t == "SubmodelElementCollection":
                depth += 1
            elif t == "End-SubmodelElementCollection":
                if depth == 0:
                    return start_idx, j
                depth -= 1
        return start_idx, len(self.rows) - 1

    def add_smc(self, idshort, parent=None):
        """
        Add SMC with optional parent.
        If parent is None, append at root. Else, append just before parent's closing end.
        """
        if parent is None:
            self.rows.append(["SubmodelElementCollection", idshort, "", "", "", "", "", ""])
            return

        parent_idx = self._find_smc_index(parent)
        if parent_idx == -1:
            # if parent absent, create at root then continue
            self.add_smc(parent)
            parent_idx = self._find_smc_index(parent)

        _, p_end = self._find_bounds(parent_idx)
        self.rows.insert(p_end, ["SubmodelElementCollection", idshort, "", "", "", "", "", ""])

    def end_smc(self):
        """Append an End-SubmodelElementCollection row."""
        self.rows.append(["End-SubmodelElementCollection", "", "", "", "", "", "", ""])

    def ensure_root_sections(self):
        """Ensure top-level 'Sensors' and 'Actuators' SMCs exist."""
        if self._find_smc_index("Sensors") == -1:
            self.add_smc("Sensors")
            self.end_smc()
        if self._find_smc_index("Actuators") == -1:
            self.add_smc("Actuators")
            self.end_smc()

    def ensure_module_under(self, section, module):
        """Ensure 'module' SMC exists directly under 'section' SMC."""
        sec_idx = self._find_smc_index(section)
        if sec_idx == -1:
            self.add_smc(section)
            self.end_smc()
            sec_idx = self._find_smc_index(section)

        s_start, s_end = self._find_bounds(sec_idx)

        # look for module inside section
        i = s_start + 1
        while i < s_end:
            if self.rows[i][0] == "SubmodelElementCollection" and self.rows[i][1] == module:
                return
            i += 1

        # not found , insert at section end
        self.rows.insert(s_end, ["SubmodelElementCollection", module, "", "", "", "", "", ""])
        self.rows.insert(s_end + 1, ["End-SubmodelElementCollection", "", "", "", "", "", "", ""])


    def _insert_property_at_smc_end(self, smc_idx, prop_row):
        """Insert property just before the closing 'End-SubmodelElementCollection' of an SMC."""
        _, end_idx = self._find_bounds(smc_idx)
        self.rows.insert(end_idx, prop_row)

    def add_property(self, idshort, value, value_type, description="", parent=None):
        """Add a Property under the given parent SMC (or root if None)."""
        prop = ["Property", idshort, value, value_type, "", description, "", ""]
        if parent is None:
            self.rows.append(prop)
            return
        parent_idx = self._find_smc_index(parent)
        if parent_idx == -1:
            self.add_smc(parent)
            self.end_smc()
            parent_idx = self._find_smc_index(parent)
        self._insert_property_at_smc_end(parent_idx, prop)

    def remove_faults_block(self):
        """Remove existing FaultsAndAlarms SMC if present (to avoid duplicates)."""
        idx = self._find_smc_index("FaultsAndAlarms")
        if idx == -1:
            return
        start, end = self._find_bounds(idx)
        del self.rows[start:end + 1]

    def add_faults_with_pairs(self, pairs, value_type):
        """
        Add FaultsAndAlarms/Alarms with entries from pairs (key, text).
        value_type: output valueType for all alarm properties (e.g., 'bool').
        """
        self.add_smc("FaultsAndAlarms")
        self.add_smc("Alarms", parent="FaultsAndAlarms")
        for key, text in pairs:
            pid = sanitize_id_short(key)
            self.add_property(pid, text, value_type, description="", parent="Alarms")
        self.end_smc()  
        self.end_smc()  


class SymbolProcessor:
    """
    Parse symbol names and insert into AASDataBuilder according to rules.

    - MAIN.m_buttonManager. - Status.(Automode/ManualMode).buttonManager
    - MAIN.m_container. - Sensors/Actuators - <Module>
    """

    def __init__(self, builder, router, typemapper):
        self.b = builder
        self.router = router
        self.typemapper = typemapper
        self.unknown_container = []

        self.module_map = {
            "stack": "Stack",
            "crane": "Crane",
            "stamp": "Stamp",
            "LSC": "LSC",
            "PAC": "PAC",
            "PicAlpha": "PicAlpha",
            "RFC": "RFC",
            "SSC": "SSC",
        }

    def idshort_from_container(self, full_name):
        """
        Generate a compact idShort from 'MAIN.m_container....' by removing prefixes up to the first dot
        and dropping left parts of 'xxx_yyy' to keep the suffix token.
        """
        m = re.search(r"MAIN\.m_container\.(.+)", full_name)
        if not m:
            return "Unknown"
        parts = m.group(1).split(".")
        cleaned = []
        for part in parts:
            if "_" in part:
                part = part.split("_")[-1]
            cleaned.append(part)
        return "".join(cleaned)

    def idshort_from_button(self, full_name):
        """Generate idShort for button manager items by stripping 'DI_' and commas."""
        m = re.search(r"MAIN\.m_buttonManager\.(.+)", full_name)
        if not m:
            return "Unknown"
        return m.group(1).replace(",", "").replace("DI_", "")

    def detect_module(self, full_name):
        m = re.search(r"MAIN\.m_container\.(m_[A-Za-z0-9]+)", full_name)
        if not m:
            return None
        base = m.group(1)[2:]  
        return self.module_map.get(base, base[:1].upper() + base[1:])

    def process(self, full_name, plc_type, name_for_match=None):
        name_for_match = (name_for_match or full_name)  
        full_name = (full_name or "").strip().lstrip("'")
        if not full_name.startswith("MAIN."):
            return

        if full_name.startswith("MAIN.m_buttonManager."):
            is_auto = ("DI_AutomaticSwitch_" in full_name) or re.search(r"\bAutomaticSwitch\b", name_for_match or "")
            mode = "Automode" if is_auto else "ManualMode"
            self._process_button_with_mode(full_name, mode)
            return


        if full_name.startswith("MAIN.m_container."):
            self._process_container(full_name, plc_type, name_for_match=name_for_match)
            return

    def _process_button_with_mode(self, full_name, mode):
        id_short = self.idshort_from_button(full_name)

        # search Automode / ManualMode SMC
        mode_idx = self.b._find_smc_index(mode)
        if mode_idx == -1:
            return

        m_start, m_end = self.b._find_bounds(mode_idx)
        btn_idx = -1
        for i in range(m_start + 1, m_end):
            if self.b.rows[i][0] == "SubmodelElementCollection" and self.b.rows[i][1] == "buttonManager":
                btn_idx = i
                break

        if btn_idx == -1:
            self.b.add_smc("buttonManager", parent=mode)
            m_start, m_end = self.b._find_bounds(mode_idx)
            for i in range(m_start + 1, m_end):
                if self.b.rows[i][0] == "SubmodelElementCollection" and self.b.rows[i][1] == "buttonManager":
                    btn_idx = i
                    break
            if btn_idx == -1:
                return
            
        _, btn_end = self.b._find_bounds(btn_idx)
        self.b.rows.insert(btn_end, ["Property", id_short, "FALSE", "boolean", "", full_name, "", ""])


    def _process_container(self, full_name, plc_type, name_for_match=None):
        """Route container signals into Sensors/Actuators → Module. Apply manual overrides and type inference."""
        name_for_match = name_for_match or full_name

        module = self.detect_module(full_name)
        if not module:
            return

        # 先手动规则（对 name_for_match）
        section, override = self.router.route(name_for_match)

        # 再按名称启发式（对 name_for_match）
        if section is None:
            if re.search(r"\.(DO|AO)_", name_for_match):
                section = "Actuators"
            elif re.search(r"\.(DI|AI)_", name_for_match):
                section = "Sensors"

        # 仍未判定则默认 Sensors，并记录
        if section is None:
            print("[WARN] MAIN.m_container.* without AI/AO/DI/DO and no manual rule: " + full_name)
            self.unknown_container.append(full_name)
            section = "Sensors"

        # 类型与默认值（手动覆盖 > CSV 基础类型 > 名称启发式）
        if override is not None:
            vt, val = override
            if not vt:
                vt, _ = self.typemapper.from_plc_or_name(full_name, plc_type)
            if val is None or val == "":
                val = self.typemapper.default_value(vt)
            value_type, value = vt, val
        else:
            value_type, value = self.typemapper.from_plc_or_name(full_name, plc_type)

        # 生成 idShort 并插入到正确的 section/module 下
        id_short = self.idshort_from_container(full_name)
        self.b.ensure_root_sections()
        self.b.ensure_module_under(section, module)

        # ✅ 只在目标 section 范围内寻找 module，避免命中另一个 section 的同名模块
        sec_idx = self.b._find_smc_index(section)
        if sec_idx == -1:
            return
        s_start, s_end = self.b._find_bounds(sec_idx)

        mod_idx = -1
        for i in range(s_start + 1, s_end):
            if self.b.rows[i][0] == "SubmodelElementCollection" and self.b.rows[i][1] == module:
                mod_idx = i
                break
        if mod_idx == -1:
            return

        _, mod_end = self.b._find_bounds(mod_idx)
        self.b.rows.insert(mod_end, ["Property", id_short, value, value_type, "", full_name, "", ""])


class CsvSymbolReader:
    def __init__(self, csv_path, processor):
        self.csv_path = csv_path
        self.processor = processor
        self.name_candidates = ("Full-Name", "Full_Name", "FullName", "Name", "FullNamePath")
        self.type_candidates = ("Base-Type", "Data-Type", "Type", "Datatype", "IEC_Type")
        self.short_candidates = ("IdShort", "ShortName", "Index-Short", "IndexShort", "idShort")

    def run(self):
        try:
            with open(self.csv_path, "r", encoding="utf-8-sig", newline="") as f:
                dict_reader = csv.DictReader(f)
                headers = [h.lstrip("\ufeff").strip() for h in (dict_reader.fieldnames or [])]

                name_col  = self._first_present(headers, self.name_candidates)
                type_col  = self._first_present(headers, self.type_candidates)
                short_col = self._first_present(headers, self.short_candidates)  

                if name_col is None:
                    f.seek(0)
                    row_reader = csv.reader(f)
                    next(row_reader, None)
                    for row in row_reader:
                        if not row:
                            continue
                        full_name = row[0]
                        plc_type  = row[1] if len(row) > 1 else None
                        short_raw = None  #
                        self.processor.process(full_name, plc_type, name_for_match=short_raw)  # ✨
                else:
                    f.seek(0)
                    dict_reader = csv.DictReader(f)
                    dict_reader.fieldnames = [h.lstrip("\ufeff").strip() for h in (dict_reader.fieldnames or [])]
                    for row in dict_reader:
                        full_name = (row.get(name_col) or "").strip()
                        if not full_name:
                            continue
                        plc_type  = (row.get(type_col)  or "").strip() if type_col  else None
                        short_raw = (row.get(short_col) or "").strip() if short_col else None
                        self.processor.process(full_name, plc_type, name_for_match=short_raw)  # ✨
        except FileNotFoundError:
            print("ERROR: Symbols CSV not found: " + self.csv_path)
        except Exception as e:
            print("ERROR: Failed to read CSV: " + str(e))
    def _first_present(self, headers, candidates): 
        for c in candidates: 
            if c in headers: 
                return c 
        return None

class TcPouAlarmExtracter:
    """
    Parse FC_InitAlarmTexts.TcPOU to extract alarm key/text pairs.

    Pattern matched in ST code:
        HMI_Texts.AlarmTexts[EAlarms.KEY] := 'TEXT';
    """

    def __init__(self, pou_path):
        self.pou_path = pou_path
        self.pattern = re.compile(r"HMI_Texts\.AlarmTexts\[EAlarms\.([A-Za-z0-9_]+)\]\s*:=\s*'([^']*)';")

    def parse(self):
        """Return a de-duplicated list of (key, text) pairs; keep first occurrence per key."""
        if not os.path.isfile(self.pou_path):
            print("[WARN] TcPOU file not found: " + self.pou_path)
            return []

        st_code = self._extract_st()
        pairs = self.pattern.findall(st_code or "")
        seen, out = set(), []
        for k, v in pairs:
            if k not in seen:
                out.append((k, v))
                seen.add(k)
        return out

    def _extract_st(self):
        """Extract ST block text from the TcPOU file; fallback to regex if XML parser fails."""
        try:
            tree = ET.parse(self.pou_path)
            root = tree.getroot()
            st_nodes = root.findall(".//ST")
            if not st_nodes:
                return ""
            return st_nodes[0].text or ""
        except Exception:
            with open(self.pou_path, "r", encoding="utf-8") as f:
                content = f.read()
            m = re.search(r"<ST><!\[CDATA\[(.*?)\]\]></ST>", content, re.S)
            return m.group(1) if m else ""


class OperationalDataBuilder:
    """
      1 Read symbols CSV - build Sensors/Actuators modules with properties
      2 Parse TcPOU - build FaultsAndAlarms/Alarms
      3 Write output CSV
    """

    def __init__(self, csv_path, tc_pou_path, output_csv_path, manual_rules, alarm_value_type="bool"):
        self.csv_path = csv_path
        self.tc_pou_path = tc_pou_path
        self.output_csv_path = output_csv_path
        self.alarm_value_type = alarm_value_type

        self.builder = AASDataBuilder()
        self.router = ManualRuleRouter(manual_rules)
        self.typemapper = TypeMapper()
        self.processor = SymbolProcessor(self.builder, self.router, self.typemapper)

    def build(self):
        """Run the full pipeline and write the CSV."""
        # 1) CSV symbols
        CsvSymbolReader(self.csv_path, self.processor).run()

        # 2) Faults/Alarms from TcPOU
        self.builder.remove_faults_block()
        pairs = TcPouAlarmExtracter(self.tc_pou_path).parse()
        if pairs:
            self.builder.add_faults_with_pairs(pairs, value_type=self.alarm_value_type)
        else:
            # Insert empty skeleton if no alarms found
            self.builder.add_smc("FaultsAndAlarms")
            self.builder.add_smc("Alarms", parent="FaultsAndAlarms")
            self.builder.end_smc()
            self.builder.end_smc()

        # 3) Write CSV
        os.makedirs(os.path.dirname(self.output_csv_path), exist_ok=True)
        with open(self.output_csv_path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(self.builder.rows)

        # 4) Report unknown container signals (if any)
        if self.processor.unknown_container:
            print("\n[SUMMARY] m_container signals WITHOUT AI/AO/DI/DO and no manual rule:")
            for s in self.processor.unknown_container:
                print(" -", s)


manual_rules = {
    "Sensors": [
    ],
    "Actuators": [
        {"pattern": "MAIN.m_container.m_crane.o_VacuumGripper.VacuumHit", "valueType": "boolean", "value": "FALSE"},
        {"pattern": "MAIN.m_container.m_PicAlpha.o_VacuumGripper.VacuumHit", "valueType": "boolean", "value": "FALSE"},
    ],
}


if __name__ == "__main__":
    # All paths are defined at the end as requested.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_csv = os.path.join(script_dir, "input", "plc_symbols.csv")
    output_csv = os.path.join(script_dir, "output", "Operational_Data.csv")
    tc_pou = os.path.join(
        script_dir,
        "plc-referenceimplementation",
        "ReferenceImplementation",
        "POUs",
        "98_Utility",
        "FC_InitAlarmTexts.TcPOU",
    )

    OperationalDataBuilder(
        csv_path=input_csv,
        tc_pou_path=tc_pou,
        output_csv_path=output_csv,
        manual_rules=manual_rules,
        alarm_value_type="bool",  
    ).build()
