#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
This script augments a Process_list.txt file with mapped PLC signals.

1 Parse TwinCAT .tsproj to build a module to signals index (based on MAIN.m_container.* variables).
2 Parse the process text blocks:
   - Map "SMC VAR" tokens (e.g., Crane_AtStack) to specific I/O signals by heuristics.
   - Map "SMC Call Skill" lines by extracting a component from skill names and
     matching against the module's signal paths. Motor-like endings (forward, backward, stop,
     clockwise, counterclockwise) are normalized to 'Motor'. Some skills are hard-routed:
     MonostableCylinder_Skill_* to MonostableCylinder, VacuumGripper_Skill_* to VacuumGripper.
3 Output formatting per process:
   - A single "-SMC Control Variable:" block that contains:
       a) "-SMC Condition Variable" with:
          - Standard VAR mappings: "      -Ref <Token>: <SignalPath>"
          - Special subsections if needed.
       b) Embedded skill sections:
                "     -SMC SkillX [and SkillY] Variable:"



"""

from pathlib import Path
from collections import defaultdict, deque
import xml.etree.ElementTree as ET
import csv
import re
import sys


def w(buf, s=""):
    buf.append(s + "\r\n")


def local_name(tag):
    return tag.split("}", 1)[-1] if isinstance(tag, str) else tag


def first_child_text(elem, lname):
    for c in list(elem):
        if isinstance(c.tag, str) and local_name(c.tag) == lname and c.text:
            return c.text.strip()
    return None


class Config:
    """
    Central configuration and small utilities.
    """
    def __init__(self):
        self.eol = "\r\n"
        self.container_prefix = "MAIN.m_container."
        self.group_outputs = "PlcTask Outputs"
        self.group_inputs = "PlcTask Inputs"

        self.component_aliases = {
            "conveyor": ["Motor"],
            "picalphaconveyor": ["Motor"],
            "largesortingconveyor": ["Motor"],
            "refeedingconveyor": ["Motor"],
            "smallsortingconveyor": ["Motor"],
            "ramppusher": ["rampPusherStart", "rampPusherMid"],
            "ramp1pusher": ["rampPusherStart"],
            "ramp2pusher": ["rampPusherMid"],
            "monostablecylinder": ["MonostableCylinder", "rampPusherStart", "rampPusherMid"],
        }

        self.module_aliases = {
            "largesortingconveyor": "lsc",
            "smallsortingconveyor": "ssc",
            "refeedingconveyor": "rfc",
            "picalphaconveyor": "picalpha",
            "picalpha": "picalpha",
            "pickalpha": "picalpha",
            "pickalphaconveyor": "picalpha",
        }

        self.proc_re = re.compile(r"^\s*-SMC Process (?P<name>[A-Za-z_]\w*)", re.M)
        self.group_re = re.compile(r"^SMC\s+(?P<group>[A-Za-z][^\r\n]*)\s*$", re.M)
        self.var_section_start = re.compile(r"^\s*-SMC VAR:\s*$", re.M)
        self.call_skill_section = re.compile(r"^\s*-SMC Call Skill:\s*$", re.M)
        self.any_section_header = re.compile(r"^\s*-SMC [A-Z_]+", re.M)
        self.ref_skill_line = re.compile(r"^\s*-\s*Ref\s+Skill(?P<num>\d+)?\s*:\s+(?P<skill>[A-Za-z_][\w]*)", re.M)
        self.token_re = re.compile(r"\b([A-Z][A-Za-z0-9]+_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)?)\b")

    def normalize_module_segment(self, seg):
        s = seg
        for pre in ("m_", "o_", "i_", "q_", "g_", "p_"):
            if s.startswith(pre):
                s = s[len(pre):]
                break
        return s

    def normalize_process_module(self, group_name):
        head = group_name.strip().split()[0]
        head = re.split(r'[_\-]', head, 1)[0]
        head = head.lower()
        return self.module_aliases.get(head, head)

    def module_alias(self, name_lc):
        return self.module_aliases.get(name_lc, name_lc)

    def expand_component_candidates(self, component):
        key = component.lower()
        if key in self.component_aliases:
            return sorted({key, *[v.lower() for v in self.component_aliases[key]]})
        for k, vals in self.component_aliases.items():
            if key == k.lower():
                return sorted({key, *[v.lower() for v in vals]})
        return [key]


class ProjectIndex:
    """
    Parse .tsproj and build:
      - module_index: {module_lower: [full_signal_paths...]}
      - all_signals_flat: set of all full signal paths
    """
    def __init__(self, cfg, tsproj_path):
        self.cfg = cfg
        self.tsproj_path = tsproj_path
        self.module_index = {}
        self.all_signals_flat = set()

    def _extract_plctask_vars(self):
        root = ET.parse(self.tsproj_path).getroot()
        data = {self.cfg.group_outputs: [], self.cfg.group_inputs: []}
        for el in root.iter():
            if not isinstance(el.tag, str) or local_name(el.tag) != "Vars":
                continue
            gname = first_child_text(el, "Name")
            if gname in data:
                for v in el.findall("./{*}Var"):
                    nm = first_child_text(v, "Name")
                    if nm:
                        data[gname].append(nm)
        return data

    def build(self):
        groups = self._extract_plctask_vars()
        all_signals = groups.get(self.cfg.group_outputs, []) + groups.get(self.cfg.group_inputs, [])
        grouped = defaultdict(list)
        flat = set()
        for name in all_signals:
            if not name.startswith(self.cfg.container_prefix):
                continue
            flat.add(name)
            rest = name[len(self.cfg.container_prefix):]
            seg = rest.split(".", 1)[0] if "." in rest else rest
            module = self.cfg.normalize_module_segment(seg).lower()
            grouped[module].append(name)
        self.module_index = {k: sorted(v) for k, v in grouped.items()}
        self.all_signals_flat = flat
        return self.module_index, self.all_signals_flat


class ProcessParser:
    """
    Parse the Process_list.txt into per-process blocks with group, name, VAR chunk and skills.
    """
    def __init__(self, cfg):
        self.cfg = cfg

    def parse(self, text):
        res = []
        for gmatch in self.cfg.group_re.finditer(text):
            gblock_end = self.cfg.group_re.search(text, gmatch.end())
            gblock = text[gmatch.start():(gblock_end.start() if gblock_end else len(text))]
            group_name = gmatch.group("group").strip()

            for pm in self.cfg.proc_re.finditer(gblock):
                pnext = self.cfg.proc_re.search(gblock, pm.end())
                block = gblock[pm.start():(pnext.start() if pnext else len(gblock))]
                name = pm.group("name")

                vs = self.cfg.var_section_start.search(block)
                var_block = ""
                if vs:
                    sh = self.cfg.any_section_header.search(block, vs.end())
                    var_block = block[vs.end():(sh.start() if sh else len(block))]

                cs = self.cfg.call_skill_section.search(block)
                skills = []
                if cs:
                    sh2 = self.cfg.any_section_header.search(block, cs.end())
                    chunk = block[cs.end():(sh2.start() if sh2 else len(block))]
                    for m in self.cfg.ref_skill_line.finditer(chunk):
                        num = m.group("num")
                        lbl = f"Skill{num}" if num else "Skill"
                        sid = m.group("skill")
                        skills.append((lbl, sid))

                res.append({
                    "group": group_name,
                    "name":  name,
                    "block": block,
                    "var_block": var_block,
                    "call_skills": skills,
                })
        return res


class VarMapper:
    """
    Heuristics for mapping VAR tokens to signal paths.
    Also provides the special collectors.
    """
    def __init__(self, cfg, module_index):
        self.cfg = cfg
        self.module_index = module_index

    def find_best_wpdetected(self, module_signals):
        cand_presence = [s for s in module_signals if ("Presence" in s or "presence" in s) and s.endswith("DI_WPDetected")]
        if cand_presence:
            return sorted(cand_presence)[0]
        cand_any = [s for s in module_signals if s.endswith("DI_WPDetected")]
        return sorted(cand_any)[0] if cand_any else None

    def find_keywords(self, module_signals, keywords, must_end=None):
        cand = []
        for s in module_signals:
            if all(k.lower() in s.lower() for k in keywords):
                if must_end and not s.endswith(must_end):
                    continue
                cand.append(s)
        return sorted(cand)[0] if cand else None

    def map_token(self, token):
        try:
            mod_raw, suffix = token.split("_", 1)
        except ValueError:
            return token, None

        module = mod_raw.lower()
        signals = self.module_index.get(module, [])
        if not signals:
            return token, None

        sfx = suffix.lower()

        if sfx == "workpieceavailable":
            return token, self.find_best_wpdetected(signals)

        if sfx in ("cylinderextended", "cylinder_retracted", "cylinderretracted"):
            want = "DI_Extended" if "extended" in sfx else "DI_Retracted"
            sig = self.find_keywords(signals, ["MonostableCylinder"], want)
            return (token, sig) if sig else (token, None)

        if sfx == "holdingworkpiece":
            sig = self.find_keywords(signals, ["VacuumGripper"], "DI_TakenIn")
            return (token, sig) if sig else (token, None)

        if module == "crane" and sfx.startswith("at"):
            place_alias = {
                "atstack":    "PresenceSensorAtStack",
                "atstamp":    "PresenceSensorAtStamp",
                "atlsc":      "PresenceSensorAtConveyor",
                "atconveyor": "PresenceSensorAtConveyor",
            }
            target = place_alias.get(sfx)
            if target:
                sig = self.find_keywords(signals, [target], "DI_WPDetected")
                if sig:
                    return token, sig
            return token, self.find_best_wpdetected(signals)

        if module == "crane" and sfx == "cylinderretracted":
            sig = self.find_keywords(signals, ["MonostableCylinder"], "DI_Retracted")
            return (token, sig) if sig else (token, None)

        if module == "lsc" and sfx in ("wpatrampstart", "wpatrampmiddle", "wpatrampend"):
            target_map = {
                "wpatrampstart":  ["rampStart",  "presenceSensorRampFull"],
                "wpatrampmiddle": ["rampMiddle", "presenceSensorRampFull"],
                "wpatrampend":    ["rampEnd",    "presenceSensorRampFull"],
            }
            keys = target_map[sfx]
            sig = self.find_keywords(signals, keys, "DI_WPDetected")
            return (token, sig) if sig else (token, None)

        if module == "lsc" and sfx in ("workpieceatentry", "wpatentry"):
            sig = self.find_keywords(signals, ["presenceSensorStart"], "DI_WPDetected")
            if not sig:
                sig = self.find_best_wpdetected(signals)
            return (token, sig) if sig else (token, None)

        if module == "pac" and sfx in ("wpatstart", "wpatend"):
            key = "PresencesensorStart" if sfx == "wpatstart" else "PresencesensorEnd"
            sig = self.find_keywords(signals, [key], "DI_WPDetected")
            return (token, sig) if sig else (token, None)

        if module == "rfc" and sfx == "wpatend":
            sig = self.find_keywords(signals, ["PresencesensorEnd"], "DI_WPDetected")
            return (token, sig) if sig else (token, None)

        if module == "ssc" and sfx in ("wpatstart", "wpatend"):
            key = "PresencesensorStart" if sfx == "wpatstart" else "PresencesensorEnd"
            sig = self.find_keywords(signals, [key], "DI_WPDetected")
            return (token, sig) if sig else (token, None)

        if module == "picalpha" and sfx.startswith("atpos"):
            n = sfx.replace("atpos", "")
            if n in {"1", "2", "3", "4"}:
                key = "PresenceSensorPosition{}".format(n)
                sig = self.find_keywords(signals, [key], "DI_WPDetected")
                return (token, sig) if sig else (token, None)

        if module == "picalpha" and sfx in ("cylinderextended", "cylinderretracted"):
            want = "DI_Extended" if "extended" in sfx else "DI_Retracted"
            sig = self.find_keywords(signals, ["MonostableCylinder"], want)
            return (token, sig) if sig else (token, None)

        if module == "picalpha" and sfx == "holdingworkpiece":
            sig = self.find_keywords(signals, ["VacuumGripper"], "DI_TakenIn")
            return (token, sig) if sig else (token, None)

        if module == "stamp" and sfx in ("wpatstamp", "workpieceatstamp"):
            sig = self.find_keywords(signals, ["presenceSensor"], "DI_WPDetected")
            if not sig:
                sig = self.find_best_wpdetected(signals)
            return (token, sig) if sig else (token, None)

        return token, None

    def _all_signals_lower_map(self):
        m = {}
        for lst in self.module_index.values():
            for s in lst:
                m[s.lower()] = s
        return m

    def _resolve_existing(self, desired_list):
        m = self._all_signals_lower_map()
        res = []
        for d in desired_list:
            hit = m.get(d.lower())
            if hit:
                res.append(hit)
        return res

    def collect_stack_producttype(self):
        desired = [
            # only exists Stack_ProductType = 0, and EProductTypes means none(no workpiece)
            "MAIN.m_container.m_stack.m_Presencesensor.DI_WPDetected",
        ]
        return self._resolve_existing(desired)

    def collect_stamp_producttype(self):
        desired = [
            # because only exists Stamp_ProductType = 0,
            "MAIN.m_container.m_stamp.m_presenceSensor.DI_WPDetected",
        ]
        return self._resolve_existing(desired)

    def collect_stamp_workpiecestate(self):
        desired = [
            # Stamp_WorkpieceState = 2: none := 0, unpressed := 1, pressed := 2
            "MAIN.m_container.m_stamp.m_stampingCylinder.DI_Extended",
        ]
        return self._resolve_existing(desired)

    def collect_lsc_producttype(self):
        desired = [
            # LSC_ProductType = 0,4 (and >=0 not used). none := 0, unknown := 1, white := 2, black := 3, metal := 4
            "MAIN.m_container.m_LSC.m_inductiveSensorStart.DI_WPMetallic",
            "MAIN.m_container.m_LSC.m_presenceSensorStart.DI_WPDetected",
        ]
        return self._resolve_existing(desired)

    def lsc_producttype_signal_for_value(self, value):
        if value == 4:
            desired = [
                "MAIN.m_container.m_LSC.m_inductiveSensorStart.DI_WPMetallic",
            ]
        elif value == 0:
            desired = [
                "MAIN.m_container.m_LSC.m_presenceSensorStart.DI_WPDetected",
            ]
        else:
            desired = []
        return self._resolve_existing(desired)

    def collect_ssc_producttype_1(self):
        desired = [
            # SSC_ProductType_1 = 0
            "MAIN.m_container.m_SSC.m_PresencesensorStart.DI_WPDetected",
        ]
        return self._resolve_existing(desired)

    def collect_ssc_producttype_2(self):
        desired = [
            # SSC_ProductType_2 = 0
            "MAIN.m_container.m_SSC.m_PresencesensorEnd.DI_WPDetected",
        ]
        return self._resolve_existing(desired)

    def collect_lsc_rampendWPcount(self):
        desired = [
            "MAIN.m_container.m_LSC.m_rampEnd.m_presenceSensorRampFull.DI_WPDetected",
        ]
        return self._resolve_existing(desired)

    def collect_pac_WPnumber(self):
        desired = [
            # PAC_WPNumber < 3, use switch DI_Extended instead of ultrasonic sensor.
            "MAIN.m_container.m_LSC.m_Switch.DI_Extended",
        ]
        return self._resolve_existing(desired)

    def special_sections(self):
        # LSC_ProductType is handled specially in Augmenter.augment()
        return {
            "Stack_ProductType": self.collect_stack_producttype,
            "Stamp_ProductType": self.collect_stamp_producttype,
            "Stamp_WorkpieceState": self.collect_stamp_workpiecestate,
            "SSC_ProductType_1": self.collect_ssc_producttype_1,
            "SSC_ProductType_2": self.collect_ssc_producttype_2,
            "LSC_RampEndWPCount": self.collect_lsc_rampendWPcount,  # SM process not use, but keep for possible future use
        }


class SkillMapper:
    """
    Resolve skill name to component candidates and match signals for a module.
    """
    def __init__(self, cfg, module_index):
        self.cfg = cfg
        self.module_index = module_index

    def extract_component_from_skill(self, skill_name):
        s = skill_name.strip()

        if s.startswith("MonostableCylinder_Skill_"):
            return "MonostableCylinder"
        if s.startswith("VacuumGripper_Skill_"):
            return "VacuumGripper"

        motor_verbs = ('backward', 'forward', 'stop', 'clockwise', 'counterclockwise')
        if s.lower().endswith(motor_verbs):
            return "Motor"

        action_words = {'extend', 'retract', 'intake', 'release', 'on', 'off', 'start', 'stop'}

        def looks_like_action(token):
            t = token.lower()
            if t in action_words:
                return True
            if t.endswith("on") or t.endswith("off"):
                return True
            if "hit" in t:
                return True
            return False

        if "_Skill_" in s:
            before, _, after = s.partition("_Skill_")
            if after:
                comp = after.split("_", 1)[0]
                if comp and not looks_like_action(comp):
                    return comp
            if before:
                return before

        if "_" in s:
            return s.split("_")[0]
        if "." in s:
            return s.split(".", 1)[0]
        return s

    def parse_signal_path(self, signal):
        if not signal.startswith(self.cfg.container_prefix):
            return "", ""
        rest = signal[len(self.cfg.container_prefix):]
        parts = rest.split('.')
        if len(parts) < 2:
            return "", ""
        module_part = parts[0]
        module_prefixes = ['m_', 'o_', 'i_', 'q_', 'g_', 'p_']
        module = module_part
        for prefix in module_prefixes:
            if module.lower().startswith(prefix):
                module = module[len(prefix):]
                break
        component_part = parts[1]
        component = component_part
        for prefix in module_prefixes:
            if component.lower().startswith(prefix):
                component = component[len(prefix):]
                break
        return module.lower(), component.lower()

    def guess_module_from_skill(self, skill_name):
        s = skill_name.strip()
        if "_Skill_" in s:
            mod = s.split("_Skill_")[0]
        else:
            mod = s.split(".", 1)[0]
        if not mod:
            return None
        mod = mod.split("_", 1)[0].lower()
        return self.cfg.module_alias(mod)

    def find_signals_for_skill(self, process_module, skill_name):
        component = self.extract_component_from_skill(skill_name)

        module_lower = process_module.lower()
        module_signals = self.module_index.get(module_lower, [])

        if not module_signals:
            alt = self.guess_module_from_skill(skill_name)
            if alt and alt in self.module_index:
                module_lower = alt
                module_signals = self.module_index[alt]

        if not module_signals:
            return []

        matched = []
        target_module_lower = module_lower
        candidates = self.cfg.expand_component_candidates(component)

        for signal in module_signals:
            sig_module, sig_component = self.parse_signal_path(signal)
            if not sig_module or not sig_component:
                continue

            module_match = (sig_module == target_module_lower)
            component_match = (sig_component in candidates)

            if module_match and component_match:
                matched.append(signal)
                continue

            module_contains = (target_module_lower in sig_module)
            component_contains = any(c in sig_component for c in candidates)

            if module_contains and component_contains:
                matched.append(signal)

        return sorted(matched)


class Augmenter:
    """
    Orchestrates parsing, mapping, and writing output.
    """
    def __init__(self, cfg, tsproj_path, process_txt_path):
        self.cfg = cfg
        self.tsproj_path = tsproj_path
        self.process_txt_path = process_txt_path

        self.project_index = None
        self.module_index = {}
        self.all_signals_flat = set()

        self.unmapped_tokens = set()
        self.used_signals = set()
        self.failed_skills = []

    def load_index(self):
        self.project_index = ProjectIndex(self.cfg, self.tsproj_path)
        self.module_index, self.all_signals_flat = self.project_index.build()

    def augment(self):
        raw = self.process_txt_path.read_text(encoding="utf-8", errors="ignore")

        parser = ProcessParser(self.cfg)
        processes = parser.parse(raw)

        var_mapper = VarMapper(self.cfg, self.module_index)
        skill_mapper = SkillMapper(self.cfg, self.module_index)
        special_sections = var_mapper.special_sections()

        out_lines = []
        cursor = 0

        for proc in processes:
            block = proc["block"]
            blk_start = raw.find(block, cursor)
            if blk_start < 0:
                continue
            blk_end = blk_start + len(block)

            out_lines.append(raw[cursor:blk_end])
            if not out_lines[-1].endswith(("\n", "\r")):
                w(out_lines, "")

            tokens = sorted(set(self.cfg.token_re.findall(proc["var_block"] or "")))
            mapped_pairs = []

            for tk in tokens:
                tkn, path = var_mapper.map_token(tk)
                if path:
                    mapped_pairs.append((tkn, path))
                    self.used_signals.add(path)
                else:
                    self.unmapped_tokens.add(tkn)

            process_module = self.cfg.normalize_process_module(proc["group"])
            skill_sets = []
            for lbl, skill_id in proc["call_skills"]:
                signals = skill_mapper.find_signals_for_skill(process_module, skill_id)
                self.used_signals.update(signals)
                skill_sets.append((frozenset([lbl]), frozenset(signals)))
                if not signals:
                    self.failed_skills.append((proc["name"], lbl, skill_id))

            merged = []
            for labels, sigs in skill_sets:
                merged_any = False
                for i, (mlabels, msigs) in enumerate(merged):
                    if msigs == sigs:
                        merged[i] = (mlabels | labels, msigs)
                        merged_any = True
                        break
                if not merged_any:
                    merged.append((labels, sigs))
            merged = [(labels, sigs) for (labels, sigs) in merged if sigs]

            if mapped_pairs or tokens or merged:
                w(out_lines, "    -SMC Control Variable:")

                if mapped_pairs or tokens:
                    w(out_lines, "     -SMC Condition Variable")
                    seen_paths = set()
                    for tkn, path in mapped_pairs:
                        if path not in seen_paths:
                            w(out_lines, f"      -Ref {tkn}: {path}")
                            seen_paths.add(path)

                    # --- custom handling for LSC_ProductType ---
                    if "LSC_ProductType" in tokens:
                        var_text = proc["var_block"] or ""
                        has_4 = re.search(r"\bLSC_ProductType\s*=\s*4\b", var_text)
                        has_0 = re.search(r"\bLSC_ProductType\s*=\s*0(?:\.0)?\b", var_text)

                        if has_4 and has_0:
                            paths = var_mapper.collect_lsc_producttype()
                            if paths:
                                w(out_lines, "      -SMC LSC_ProductType")
                                for i, p in enumerate(paths, 1):
                                    w(out_lines, f"       -Ref LSC_ProductType_{i}: {p}")
                                    self.used_signals.add(p)
                                if "LSC_ProductType" in self.unmapped_tokens:
                                    self.unmapped_tokens.discard("LSC_ProductType")

                        elif has_4:
                            paths = var_mapper.lsc_producttype_signal_for_value(4)
                            if paths:
                                p = paths[0]
                                w(out_lines, f"      -Ref LSC_ProductType: {p}")
                                self.used_signals.add(p)
                                if "LSC_ProductType" in self.unmapped_tokens:
                                    self.unmapped_tokens.discard("LSC_ProductType")

                        elif has_0:
                            paths = var_mapper.lsc_producttype_signal_for_value(0)
                            if paths:
                                p = paths[0]
                                w(out_lines, f"      -Ref LSC_ProductType: {p}")
                                self.used_signals.add(p)
                                if "LSC_ProductType" in self.unmapped_tokens:
                                    self.unmapped_tokens.discard("LSC_ProductType")

                        else:
                            paths = var_mapper.collect_lsc_producttype()
                            if paths:
                                w(out_lines, "      -SMC LSC_ProductType")
                                for i, p in enumerate(paths, 1):
                                    w(out_lines, f"       -Ref LSC_ProductType_{i}: {p}")
                                    self.used_signals.add(p)
                                if "LSC_ProductType" in self.unmapped_tokens:
                                    self.unmapped_tokens.discard("LSC_ProductType")

                    # --- other special sections (Stack, Stamp, SSC_ProductType_1/2, PAC_WPNumber, ...) ---
                    for special_token, collector in special_sections.items():
                        if special_token in tokens:
                            paths = collector()
                            if paths:
                                # if only one signal, write as single Ref line
                                if special_token in (
                                    "Stack_ProductType",
                                    "Stamp_ProductType",
                                    "SSC_ProductType_1",
                                    "SSC_ProductType_2",
                                ) and len(paths) == 1:
                                    p = paths[0]
                                    w(out_lines, f"      -Ref {special_token}: {p}")
                                    self.used_signals.add(p)
                                    if special_token in self.unmapped_tokens:
                                        self.unmapped_tokens.discard(special_token)
                                else:
                                    w(out_lines, f"      -SMC {special_token}")
                                    for i, p in enumerate(paths, 1):
                                        w(out_lines, f"       -Ref {special_token}_{i}: {p}")
                                        self.used_signals.add(p)
                                    if special_token in self.unmapped_tokens:
                                        self.unmapped_tokens.discard(special_token)

                if merged:
                    for labels, sigs in merged:
                        labs_sorted = sorted(labels, key=lambda s: int(re.sub(r"\D", "", s) or "0"))
                        if len(labs_sorted) > 1:
                            title = f"     -SMC {' and '.join(labs_sorted)} Variable:"
                        else:
                            title = f"     -SMC {labs_sorted[0]} Variable:"
                        w(out_lines, title)
                        for idx, p in enumerate(sorted(sigs), 1):
                            w(out_lines, f"      -Ref  Variable{idx}: {p}")

                w(out_lines)

            cursor = blk_end

        out_lines.append(raw[cursor:])
        return "".join(out_lines).replace("\r\n", "\n").replace("\r", "\n").replace("\n", self.cfg.eol)

    def print_three_sections(self):
        print("\n Unmapped tokens: {}".format(len(self.unmapped_tokens)))
        for tk in sorted(self.unmapped_tokens):
            print("  - {}".format(tk))

        print("\n Ref Skill produced NO signals: {} skills".format(len(self.failed_skills)))
        for proc_name, lbl, skill_id in self.failed_skills:
            print("  - [{}] {}: {}".format(proc_name, lbl, skill_id))

        idx = ProjectIndex(self.cfg, self.tsproj_path)
        module_index, all_signals_flat = idx.build()
        unused = sorted(all_signals_flat - self.used_signals)
        print("\n Unused PlcTask signals:")
        if unused:
            groups = defaultdict(list)
            for s in unused:
                rest = s[len(self.cfg.container_prefix):]
                seg = rest.split(".", 1)[0] if "." in rest else rest
                mod = self.cfg.normalize_module_segment(seg).lower()
                groups[mod].append(s)
            for mod in sorted(groups.keys()):
                items = sorted(groups[mod])
                print("\n-  [{}] ({})  -".format(mod, len(items)))
                for i, nm in enumerate(items, 1):
                    print("   {}. {}".format(i, nm))


def find_tsproj(base_dir):
    cands = list(base_dir.rglob("*.tsproj"))
    if not cands:
        cands = list(base_dir.rglob("*.tsproj.bak"))
    return cands[0] if cands else None


def main(argv):
    script_dir = Path(__file__).parent.resolve()
    default_process_txt = script_dir / "output" / "Process_list.txt"
    default_project_dir = script_dir / "plc-referenceimplementation"
    default_skill_csv   = script_dir / "check" / "Skill.csv"

    in_txt  = Path(argv[0]).resolve() if len(argv) >= 1 else default_process_txt
    tsproj  = Path(argv[1]).resolve() if len(argv) >= 2 else (find_tsproj(default_project_dir) or Path())
    skill_c = Path(argv[2]).resolve() if len(argv) >= 3 else default_skill_csv

    if not in_txt.exists():
        print("ERROR: Process_list.txt not found:\n  {}".format(in_txt))
        sys.exit(1)
    if not tsproj or not tsproj.exists():
        print("ERROR: .tsproj/.tsproj.bak not found under:\n  {}".format(default_project_dir))
        print("Tip: python augment_process_signals_from_text.py <Process_list.txt> <project.tsproj> [Skill.csv]")
        sys.exit(2)

    cfg = Config()
    aug = Augmenter(cfg, tsproj, in_txt)
    aug.load_index()
    final_text = aug.augment()

    out_path = in_txt.parent / "Process_list_with_signals.txt"
    out_path.write_text(final_text, encoding="utf-8")

    aug.print_three_sections()


if __name__ == "__main__":
    main(sys.argv[1:])
