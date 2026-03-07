#!/usr/bin/env python3.10.15
# -*- coding: utf-8 -*-

"""
AASX Skill/PLC/Process Update with:
- 2-pass Reference resolution (first create placeholders, then backfill),
- Duplicate idShort auto-rename for ReferenceElement (Call -> CallNone1/2/... within same parent),
- Extended resolver (with normalization, case-insensitive, dotted-path tolerant):
  * http(s):// => AAS global id
  * else idShort exact OR normalized (lowercase + non-alnum -> '_' + collapse '_')
  * descriptionEN (lowercased) when allowed
  * dotted paths like 'Switch.Skill_Extend' -> match idShort 'Switch_Skill_Extend'
    or nested path Switch -> (Skill_Extend | Switch_Skill_Extend)

Priority by context:
  PLC:      Operational_Data (id/desc) -> PLC (id/desc)
  Skill:    PLC (id/desc) -> Skill (id only)
  Process:  PLC (id/desc) -> Skill (id/desc) -> Operational_Data (id/desc) -> Process (id/desc)
"""

import os
import re
import csv
from pathlib import Path

from basyx.aas import model
from basyx.aas.model import (
    DictObjectStore, Submodel, AssetAdministrationShell,
    Key, KeyTypes, ModelReference, EntityType, LangStringSet
)
from basyx.aas.adapter.aasx import AASXReader, AASXWriter, DictSupplementaryFileContainer

from base.create_ent import ent
from base.eClass import MapEClass


class AASXIO:
    """Handles AASX file operations - loading, saving, and submodel retrieval."""
    
    def __init__(self, aasx_in, aasx_out):
        self.aasx_in = aasx_in
        self.aasx_out = aasx_out
        self.object_store = None
        self.file_store = None

    def load(self):
        """Load AASX file into object and file stores."""
        self.object_store = DictObjectStore()
        self.file_store = DictSupplementaryFileContainer()
        with AASXReader(self.aasx_in) as reader:
            reader.read_into(self.object_store, self.file_store)

    def save(self):
        """Save object and file stores to AASX file."""
        aas_ids = [aas.id for aas in self.object_store if isinstance(aas, AssetAdministrationShell)]
        with AASXWriter(self.aasx_out) as writer:
            writer.write_aas(aas_ids=aas_ids, object_store=self.object_store, file_store=self.file_store)

    def find_submodel(self, id_short):
        """Find submodel by id_short."""
        for obj in self.object_store:
            if isinstance(obj, Submodel) and obj.id_short == id_short:
                return obj
        return None


class ReferenceResolver:
    """Handles resolution of references with advanced matching strategies."""
    
    def __init__(self, io: AASXIO):
        self.io = io
        self._norm_rx = re.compile(r'[^a-z0-9_]+')

    def _norm(self, s: str) -> str:
        """Normalize text: lowercase + non-alnum->'_' + collapse '_' + trim '_'"""
        s = (s or "").strip().lower()
        s = self._norm_rx.sub('_', s)
        s = re.sub(r'_+', '_', s).strip('_')
        return s

    def looks_like_aas_id(self, s: str) -> bool:
        """Check if string looks like an AAS global identifier (starts with http/https)."""
        return bool(re.match(r'^(?:https?://)', (s or '').strip(), flags=re.IGNORECASE))

    def build_aas_reference(self, aas_id: str) -> ModelReference:
        """Build ModelReference for AAS global identifier."""
        return ModelReference(
            key=(Key(type_=KeyTypes.ASSET_ADMINISTRATION_SHELL, value=aas_id),),
            type_=AssetAdministrationShell
        )

    def _walk_elements(self, parent_iter):
        """Walk through all elements in hierarchical structure."""
        stack = []
        for se in parent_iter:
            stack.append(([], se))
        while stack:
            path, cur = stack.pop()
            yield (path, cur)
            if isinstance(cur, model.SubmodelElementCollection):
                for child in cur.value:
                    stack.append((path + [cur], child))
            elif isinstance(cur, model.Entity):
                for stmt in cur.statement:
                    stack.append((path + [cur], stmt))

    def _children(self, elem):
        """Get child elements based on element type."""
        if isinstance(elem, model.SubmodelElementCollection):
            return list(elem.value)
        if isinstance(elem, model.Entity):
            return list(elem.statement)
        return []

    def _get_desc_en_text(self, desc) -> str | None:
        """Extract English description text from LangStringSet or string."""
        if isinstance(desc, LangStringSet):
            if 'en' in desc and desc['en']:
                return str(next(iter(desc['en']))).strip().lower()
            for _lang, vals in desc.items():
                for v in vals:
                    s = str(v).strip().lower()
                    if s:
                        return s
        elif isinstance(desc, str):
            return desc.strip().lower() or None
        return None

    def _index_paths(self, submodel: Submodel):
        """Build indexes for element lookup by id_short and description."""
        idx_id, idx_id_norm, idx_desc = {}, {}, {}
        if submodel is None:
            return idx_id, idx_id_norm, idx_desc
            
        for path, elem in self._walk_elements(submodel.submodel_element):
            full_path = path + [elem]
            if getattr(elem, "id_short", None):
                k = elem.id_short
                idx_id.setdefault(k, []).append(full_path)
                idx_id_norm.setdefault(self._norm(k), []).append(full_path)
            desc_txt = self._get_desc_en_text(getattr(elem, "description", None))
            if desc_txt:
                idx_desc.setdefault(desc_txt, []).append(full_path)
        return idx_id, idx_id_norm, idx_desc

    def _build_reference(self, submodel: Submodel, path):
        """Build ModelReference from submodel and element path."""
        if submodel is None or not path:
            return None
        keys = [Key(type_=KeyTypes.SUBMODEL, value=submodel.id)]
        for e in path:
            keys.append(Key(type_=self._keytype_of(e), value=e.id_short))
        return ModelReference(key=tuple(keys), type_=Submodel)

    def _keytype_of(self, elem):
        """Determine KeyTypes for different AAS element types."""
        if isinstance(elem, model.SubmodelElementCollection):
            return KeyTypes.SUBMODEL_ELEMENT_COLLECTION
        if isinstance(elem, model.Property):
            return KeyTypes.PROPERTY
        if isinstance(elem, model.ReferenceElement):
            return KeyTypes.REFERENCE_ELEMENT
        if isinstance(elem, model.Entity):
            return KeyTypes.ENTITY
        if isinstance(elem, model.File):
            return KeyTypes.FILE
        if hasattr(model, "Capability") and isinstance(elem, model.Capability):
            return KeyTypes.CAPABILITY
        return KeyTypes.SUBMODEL_ELEMENT

    def _find_by_dotted_path(self, sm: Submodel, target: str):
        """
        Resolve dotted paths like 'A.B.C' to either:
        - Element with idShort 'A_B_C' (underscored join)
        - Nested path A -> (B or 'A_B') -> (C or 'A_B_C')
        """
        if sm is None:
            return None
        tokens = [t for t in target.split('.') if t]
        if not tokens:
            return None

        idx_id, idx_id_norm, _ = self._index_paths(sm)

        # 1) Direct underscored match
        underscored = "_".join(tokens)
        paths = idx_id.get(underscored, []) or idx_id_norm.get(self._norm(underscored), [])
        if paths:
            return self._build_reference(sm, paths[0])

        # 2) Nested DFS using normalized comparisons
        def dfs_at(elems, depth, path_acc):
            if depth >= len(tokens):
                return None
            want = tokens[depth]
            joined = "_".join(tokens[:depth+1])
            want_n = self._norm(want)
            joined_n = self._norm(joined)

            for el in elems:
                eid = getattr(el, "id_short", None)
                if not eid:
                    continue
                e_n = self._norm(eid)
                if e_n in (want_n, joined_n):
                    if depth == len(tokens) - 1:
                        return path_acc + [el]
                    child_elems = self._children(el)
                    found = dfs_at(child_elems, depth + 1, path_acc + [el])
                    if found:
                        return found
            return None

        root_elems = list(sm.submodel_element)
        found_path = dfs_at(root_elems, 0, [])
        if found_path:
            return self._build_reference(sm, found_path)
        return None

    def _resolve_in_submodel(self, sm: Submodel, target: str, allow_desc: bool):
        """Resolve target within a specific submodel."""
        if sm is None:
            return None

        # Try dotted path resolution first
        if '.' in target:
            ref = self._find_by_dotted_path(sm, target)
            if ref is not None:
                return ref

        idx_id, idx_id_norm, idx_desc = self._index_paths(sm)

        # 1) Exact idShort match
        paths = idx_id.get(target, [])
        if paths:
            return self._build_reference(sm, paths[0])

        # 2) Normalized idShort match
        norm_t = self._norm(target)
        paths = idx_id_norm.get(norm_t, [])
        if paths:
            return self._build_reference(sm, paths[0])

        # 3) Description match (if allowed)
        if allow_desc:
            t = (target or "").strip().lower()
            paths = idx_desc.get(t, [])
            if paths:
                return self._build_reference(sm, paths[0])

        # 4) Fallback for dotted text
        if '.' in target:
            underscored = target.replace('.', '_')
            paths = idx_id.get(underscored, [])
            if paths:
                return self._build_reference(sm, paths[0])
            paths = idx_id_norm.get(self._norm(underscored), [])
            if paths:
                return self._build_reference(sm, paths[0])

        return None

    def resolve_extended(self, raw_target: str, context_sm_name: str):
        """
        Resolve reference using context-specific search order.
        
        Search strategies by context:
        - PLC: Operational_Data -> PLC
        - Skill: PLC -> Skill (id only)
        - Process: PLC -> Skill -> Operational_Data -> Process
        """
        skill = self.io.find_submodel("Skill")
        plc   = self.io.find_submodel("PLC")
        proc  = self.io.find_submodel("Process")
        oper  = self.io.find_submodel("Operational_Data")

        # Define search order based on context
        if context_sm_name == "PLC":
            order = [(oper, True), (plc, True)]
        elif context_sm_name == "Skill":
            order = [(plc, True), (skill, False)]   # Skill自身仅 idShort
        elif context_sm_name == "Process":
            order = [(plc, True), (skill, True), (oper, True), (proc, True)]
        else:
            order = [(plc, True), (skill, True), (oper, True), (proc, True)]

        for sm, allow_desc in order:
            ref = self._resolve_in_submodel(sm, raw_target, allow_desc)
            if ref is not None:
                return ref
        return None


class CSVElementBuilder:
    """Builds AAS elements from CSV data with hierarchical structure."""
    
    BASE_REQUIRED_COLS = ["typeName", "idShort"]

    def __init__(self, io, ent_creator, eclass_mapper, resolver: ReferenceResolver):
        self.io = io
        self.ent = ent_creator
        self.eclass = eclass_mapper
        self.resolver = resolver

    def from_path(self, path_like, target_submodel):
        """Process CSV file or directory and return elements with pending references."""
        out_elements = []
        out_pending  = []   # (ref_el, raw_target, context_sm, csv_name, line_no, ref_id_short)
        
        for csv_file in self._list_csvs(path_like):
            elems, pend = self._from_file(csv_file, target_submodel)
            out_elements.extend(elems)
            out_pending.extend(pend)
            
        return out_elements, out_pending

    def _dedupe_idshort_for_ref(self, desired: str, parent_smc: model.SubmodelElementCollection | None, root_list: list | None):
        """Ensure unique idShort for ReferenceElements within scope."""
        def exists_in_container(name: str) -> bool:
            if parent_smc is not None:
                return any(getattr(e, "id_short", None) == name for e in parent_smc.value)
            if root_list is not None:
                return any(getattr(e, "id_short", None) == name for e in root_list)
            return False

        if not exists_in_container(desired):
            return desired

        i = 1
        while True:
            candidate = f"{desired}None{i}"
            if not exists_in_container(candidate):
                return candidate
            i += 1

    def _from_file(self, csv_file: Path, target_submodel: str):
        """Process single CSV file and build hierarchical element structure."""
        results = []  # Root level elements
        pending = []  # Pending references for second pass
        
        # Stacks for maintaining hierarchy
        smc_stack = []  # SubmodelElementCollection stack
        ent_stack = []  # Entity stack

        with open(csv_file, mode="r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=",")
            if reader.fieldnames:
                reader.fieldnames = [h.lstrip('\ufeff').strip() for h in reader.fieldnames]

            hdr = reader.fieldnames or []
            missing = [c for c in self.BASE_REQUIRED_COLS if c not in hdr]
            if missing:
                print("[ERROR] CSV %s missing required columns %s. Got %s. Skipped."
                      % (csv_file.name, missing, hdr))
                return results, pending

            for line_no, row in enumerate(reader, start=2):
                try:
                    element_type = (row.get("typeName") or "").strip()
                    id_raw = (row.get("idShort") or "").strip()
                    id_short = self._sanitize_id_short(id_raw)
                    category = (row.get("category") or None)
                    desc = (row.get("descriptionEN") or "").strip() or None

                    # Handle end markers
                    if element_type.startswith("End-"):
                        if element_type == "End-SubmodelElementCollection" and smc_stack:
                            smc_stack.pop()
                        elif element_type == "End-Entity" and ent_stack:
                            ent_stack.pop()
                        continue

                    # Determine semanticId
                    semantic_id = (row.get("semanticId") or "").strip()
                    if not semantic_id:
                        try:
                            _, semantic_id, _ = self.eclass.get_IrdiPR_unit_descr(id_raw) if id_raw else (None, "0000", None)
                        except Exception:
                            semantic_id = "0000"

                    # Create element based on type
                    current_parent = smc_stack[-1] if smc_stack else None
                    root_list = None if smc_stack else results
                    
                    if element_type == "SubmodelElementCollection":
                        smc = self.ent.create_SMC(
                            id_short=id_short, value=[], category=category, 
                            description=desc, semantic_id=semantic_id
                        )
                        if current_parent:
                            current_parent.value.add(smc)
                        else:
                            results.append(smc)
                        smc_stack.append(smc)

                    elif element_type == "File":
                        file_path = (row.get("value") or "").strip()
                        if not file_path:
                            print("Warn: %s:%d File element without 'value' path. Skipped."
                                  % (csv_file.name, line_no))
                            continue
                        f_el = self.ent.create_File(
                            file_store=self.io.file_store,
                            file_path=file_path,
                            aasx_file_path="/aasx/files/%s" % id_short,
                            id_short=id_short,
                            mime_type="application/octet-stream",
                            category=category,
                            description=desc
                        )
                        if current_parent:
                            current_parent.value.add(f_el)
                        else:
                            results.append(f_el)

                    elif element_type == "Entity":
                        target_aas = next(
                            (aas for aas in self.io.object_store 
                             if isinstance(aas, AssetAdministrationShell) and aas.id_short == id_raw),
                            None
                        )
                        global_asset_id = target_aas.id if target_aas else None
                        ent_el = self.ent.create_Ent(
                            id_short=id_short, description=desc, category=category,
                            ent_type=EntityType.SELF_MANAGED_ENTITY, statement=[],
                            semantic_id=semantic_id, global_asset_id=global_asset_id
                        )
                        if current_parent:
                            current_parent.value.add(ent_el)
                        else:
                            results.append(ent_el)
                        ent_stack.append(ent_el)

                    elif element_type == "Property":
                        py_t, val = self._cast_property_value(row.get("valueType"), row.get("value"))
                        prop = self.ent.create_Prop(
                            id_short=id_short, value=val, value_type=py_t,
                            category=category, description=desc, semantic_id=semantic_id
                        )
                        if current_parent:
                            current_parent.value.add(prop)
                        else:
                            results.append(prop)

                    elif element_type == "Capability":
                        if hasattr(model, "Capability"):
                            cap = self.ent.create_Cap(
                                id_short=id_short, category=category, description=desc, semantic_id=semantic_id
                            )
                            if current_parent:
                                current_parent.value.add(cap)
                            else:
                                results.append(cap)
                        else:
                            print("Warn: %s:%d 'Capability' not supported by current basyx; skipped."
                                  % (csv_file.name, line_no))

                    elif element_type == "ReferenceElement":
                        raw_target = (row.get("value") or "").strip()
                        if not raw_target:
                            print("Warn: %s:%d ReferenceElement with empty 'value'; skipped."
                                  % (csv_file.name, line_no))
                            continue

                        # Resolve reference (may be None initially)
                        if self.resolver.looks_like_aas_id(raw_target):
                            ref_value = self.resolver.build_aas_reference(raw_target)
                        else:
                            ref_value = self.resolver.resolve_extended(raw_target, target_submodel)

                        # Ensure unique idShort for ReferenceElements
                        final_id = self._dedupe_idshort_for_ref(
                            id_short, parent_smc=current_parent, root_list=root_list
                        )
                        if final_id != id_short:
                            print(f"Info: {csv_file.name}:{line_no} Duplicate idShort '{id_short}' -> renamed to '{final_id}' in parent scope.")

                        # Create ReferenceElement (allow value=None for pending resolution)
                        try:
                            ref_el = self.ent.create_Ref(
                                id_short=final_id, value=ref_value,
                                category=category, description=desc, semantic_id=semantic_id
                            )
                        except Exception:
                            ref_el = model.ReferenceElement(
                                id_short=final_id, value=ref_value,
                                category=category, description=desc
                            )

                        if current_parent:
                            current_parent.value.add(ref_el)
                        else:
                            results.append(ref_el)

                        # Track for second-pass resolution if needed
                        if (not self.resolver.looks_like_aas_id(raw_target)) and (ref_value is None):
                            pending.append((ref_el, raw_target, target_submodel, csv_file.name, line_no, final_id))

                    else:
                        print("Warn: %s:%d Unsupported typeName='%s'. Skipped."
                              % (csv_file.name, line_no, element_type))

                except Exception as ex:
                    print("[ERROR] %s:%d idShort='%s'. Error: %s"
                          % (csv_file.name, line_no, row.get("idShort"), ex))
                    continue

        return results, pending

    def _list_csvs(self, path_like):
        """Find all CSV files in given path."""
        p = Path(path_like)
        if p.is_dir():
            files = sorted([c for c in p.glob("*.csv") if c.is_file()])
            if not files:
                print("Warn: Directory has no CSVs: %s" % p)
            return files
        if p.is_file() and p.suffix.lower() == ".csv":
            return [p]
        print("[ERROR] CSV path not found or not a CSV: %s" % path_like)
        return []

    def _sanitize_id_short(self, s):
        """Sanitize id_short to valid format."""
        if not s:
            return "default"
        s2 = re.sub(r"[^A-Za-z0-9_]", "_", s)
        if not s2 or not s2[0].isalpha():
            s2 = "default_" + s2
        return s2

    def _cast_property_value(self, value_type, raw):
        """Cast property value to appropriate type."""
        t = (value_type or "string").strip().lower()
        v = (raw or "").strip()
        map_t = {
            "string": str, "str": str, "text": str,
            "int": int, "integer": int, "dint": int, "udint": int, "uint": int, "word": int,
            "float": float, "double": float, "real": float, "lreal": float,
            "bool": bool, "boolean": bool,
        }
        py = map_t.get(t, str)

        def cast(value):
            if value == "":
                return None
            try:
                if py is int:
                    return int(value, 16) if re.match(r"^0x[0-9a-fA-F]+$", value) else int(value)
                if py is float:
                    return float(value.replace(",", "."))
                if py is bool:
                    return value.lower() in ("true", "1", "yes", "y", "ja")
                return value
            except Exception as ex:
                print("Warn: Property cast failed ('%s' as %s): %s. Set to None."
                      % (value, py.__name__, ex))
                return None

        return py, cast(v)


class AASXSkillPLCUpdater:
    """Main class orchestrating the AASX update pipeline."""
    
    def __init__(self, aasx_in, aasx_out, submodel_to_csv):
        self.io = AASXIO(aasx_in, aasx_out)
        self.submodel_to_csv = submodel_to_csv
        self.ent = ent()
        self.eclass = MapEClass()
        self.resolver = ReferenceResolver(self.io)
        self.builder = CSVElementBuilder(self.io, self.ent, self.eclass, self.resolver)
        self.pending_refs = []

    def run(self):
        """Execute the complete update pipeline with 2-pass resolution."""
        # Load existing AASX
        self.io.load()

        # First pass: Build all elements and collect pending references
        for subm_name, csv_path in self.submodel_to_csv.items():
            submodel = self.io.find_submodel(subm_name)
            if submodel is None:
                print("Warn: Submodel '%s' not found. Skip CSV: %s" % (subm_name, csv_path))
                continue

            elements, pend = self.builder.from_path(csv_path, subm_name)
            if not elements:
                print("No elements created for Submodel '%s' from '%s'." % (subm_name, csv_path))
                continue

            # Add root level elements to submodel
            for el in elements:
                submodel.submodel_element.add(el)

            self.pending_refs.extend(pend)
            print(" Added %d elements to Submodel '%s' from '%s'." %
                  (len(elements), subm_name, csv_path))

        # Second pass: Resolve pending references now that all elements are in store
        unresolved = self._resolve_pending_references()

        # Save updated AASX
        self.io.save()
        print("[OK] Wrote updated AASX -> %s" % self.io.aasx_out)

        # Report unresolved references
        if unresolved:
            print("==== Unresolved ReferenceElement (final) ====")
            print("Total:", len(unresolved))
            for rec in unresolved:
                ref_el, raw_target, context, csv_name, line_no, ref_id_short = rec
                print(f"- {csv_name}:{line_no}  idShort='{ref_id_short}'  value='{raw_target}'  (context={context})")
        else:
            print("All ReferenceElement targets resolved.")

    def _resolve_pending_references(self):
        """Resolve all pending references in second pass."""
        still_unresolved = []
        for ref_el, raw_target, context, csv_name, line_no, ref_id_short in self.pending_refs:
            if self.resolver.looks_like_aas_id(raw_target):
                continue  # Already handled
                
            ref_val = self.resolver.resolve_extended(raw_target, context)
            if ref_val is None:
                still_unresolved.append((ref_el, raw_target, context, csv_name, line_no, ref_id_short))
            else:
                ref_el.value = ref_val
                
        return still_unresolved

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))

    aasx_in  = os.path.join(current_dir, "output", "xPPU_6.aasx")
    aasx_out = os.path.join(current_dir, "output", "xPPU_7.aasx")

    csv_map = {
        "Process": os.path.join(current_dir, "csv", "Process.csv"),
        "Skill":   os.path.join(current_dir, "csv", "Skill.csv"),
        "PLC":     os.path.join(current_dir, "csv", "PLC.csv"),
    }

    updater = AASXSkillPLCUpdater(aasx_in, aasx_out, csv_map)
    updater.run()