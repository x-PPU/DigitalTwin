#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Merge product AASX with templates, patch IDs from PartNr or a manual map,
fill ManufacturingProductNumber & ManufacturerTypName parsed from file name,
update Capability description ( match on ManufacturerTypName),
and update ProductClassId using a manual map(eClass cant find 0000)) and eClass fallback.

"""

import io
import os
import re

from basyx.aas import model  
from basyx.aas.adapter.aasx import AASXReader, AASXWriter, DictSupplementaryFileContainer
from basyx.aas.model import DictObjectStore, AssetAdministrationShell, Submodel
from basyx.aas.model.base import ModelReference
from basyx.aas.model import MultiLanguageTextType

from base.create_ent import ent
from base.eClass import MapEClass




# Supplier: template file name under 4.create_templates/output
supplier_template = {
    "balluff":           "Template_balluff.aasx",
    "bernstein":         "Template_bernstein.aasx",
    "contelec":          "Template_contelec.aasx",
    "festo":             "Template_festo.aasx",
    "hbm":               "Template_hbm.aasx",
    "ott":               "Template_ott.aasx",
    "phoenix contact":   "Template_phoenix_contact.aasx",
    "phoenix_contact":   "Template_phoenix_contact.aasx",
    "phoenix":           "Template_phoenix_contact.aasx",
    "phonix":            "Template_phoenix_contact.aasx",
    "siemens":           "Template_siemens.aasx",
}

# File name: suffix that replaces  "0000" in AAS/SM IDs 
id_suffix_map = {
    "Contelec GL60 Angel sensor": "GL60",
    "Festo CPV10-M1H-5JS-M7 Solenoid valve": "161415",
    "HBM PW6DC3MR 3kg Weight sensor": "PW6DC3MR",
    "HBM RM4220 Measuring amplifier": "RM4220",
    "Ott XDS 035 005-03 Motor": "00503-03",
    "Phonix Contact DIKD 1.5 Terminal block & Load cell connection": "DIKD1.5",
    "Siemens 6GT2821-2AC32 RFID read & write head": "6GT2821-2AC32",
}

# ManufacturerTypName: Eenglish description for Capability
cap_desc_map = {
    "angel sensor": "Detects specific positional or angular changes for precise alignment or movement control.",
    "blanking plate": "Covers unused ports or openings to maintain system integrity and safety.",
    "capacitive sensor": "Senses objects or materials based on changes in capacitance, even through non-metallic surfaces.",
    "compact cylinder": "Provides linear motion in tight spaces with efficient pneumatic actuation.",
    "cylinder": "Converts compressed air into linear mechanical motion for automation tasks.",
    "flat cylinder": "Offers low-profile linear motion ideal for space-constrained applications.",
    "flow sensor": "Measures the rate of fluid or gas flow for monitoring and control.",
    "inductive position transmitter": "Transmits precise position data using inductive sensing technology.",
    "inductive proximity switch": "Detects metallic objects without physical contact for automation and safety.",
    "inductive sensor": "Identifies metal targets via electromagnetic fields for non-contact detection.",
    "micro switch": "Offers quick-response switching for control and safety applications.",
    "motor": "Converts electrical energy into mechanical motion for driving systems.",
    "optical sensor": "Detects objects or changes using light, ideal for fast and precise sensing.",
    "diffuse reflection sensor": "Detects objects based on reflected light, Measures distance to target surface.",
    "pressure gauge": "Displays real-time pressure levels for monitoring and diagnostics.",
    "pressure sensor": "Measures fluid or gas pressure and converts it into an electrical signal.",
    "proximity sensor": "Detects nearby objects without physical contact, enhancing automation and safety.",
    "rfid read & write head": "Reads and writes data to RFID tags for tracking and identification.",
    "solenoid valve": "Controls fluid or gas flow using electromagnetic actuation.",
    "terminal block & load cell connection": "Provides secure electrical connections and interfaces for load cells.",
    "toothed belt axis": "Enables synchronized linear motion with high precision and repeatability.",
    "ultrasonic sensor": "Measures distance or detects objects using high-frequency sound waves.",
    "vacuum cup": "Grips and holds objects using vacuum suction, ideal for pick-and-place systems.",
    "vacuum generator": "Creates vacuum pressure for suction-based handling systems.",
    "valve terminal": "Integrates multiple valves for centralized pneumatic control.",
    "weight sensor": "Measures weight or force, often using strain gauge technology.",
    "measuring amplifier": "Amplifies and conditions weak sensor signals to ensure accurate and reliable data acquisition.",
}

# ManufacturerTypName: ProductClassId (eClass IRDI,manual search https://eclass.eu/eclass-standard/content-suche)
IRDI_map = {
    "proximity sensor": "0173-1#01-AKH677#016",
    "inductive sensor": "0173-1#01-AKH677#016",
    "capacitive sensor": "0173-1#01-AGZ377#017",
    "valve terminal": "	0173-1#01-AAT325#015",   
    "angel sensor": "0173-1#01-AFV538#003",
    "inductive position transmitter": "	0173-1#01-AKH677#016",
    "micro switch": "	0173-1#01-AGK360#001",
    "flat cylinder": "	0173-1#01-AGU428#001",
    "toothed belt axis": "0173-1#01-AKH707#016",
    "weight sensor": "0173-1#01-AJZ033#018",
    "measuring amplifier": "0173-1#01-AKH676#015",
    "vacuum cup": "	0173-1#01-AGV426#001",
    "Terminal block & Load cell connection": "0173-1#01-AAR770#015", # need manual moedification
    "RFID read & write head": "0173-1#01-AGZ438#014", # need manual moedification
    "Diffuse Reflection Sensor": "0173-1#01-AGZ394#017", # need manual moedification
}


# 1 Paths
current_dir = os.path.dirname(os.path.abspath(__file__))              
work_root   = os.path.abspath(os.path.join(current_dir, os.pardir))    
AAS_root       = os.path.join(work_root, "3.aasx_merge", "output")
template_root  = os.path.join(work_root, "4.create_templates", "output")
out_root       = os.path.join(current_dir, "output1")
os.makedirs(out_root, exist_ok=True)



# 2 normalization, traversal, description handling
class AASUtils:
    """
    Helper methods used throughout the pipeline.
    Kept as instance methods (no staticmethod) as requested.
    """

    def norm_spaces(self, s):
        """Collapse multiple whitespaces to one and trim."""
        return re.sub(r"\s+", " ", (s or "").strip())

    def norm_id(self, s):
        """Lowercase, trim, and remove '_' and '-' for tolerant idShort comparisons."""
        return re.sub(r"[_\-]+", "", (s or "").strip().lower())

    def is_sm_technicaldata(self, sm):
        """Check if a Submodel is the 'TechnicalData' (tolerant to underscores)."""
        return self.norm_id(getattr(sm, "id_short", "")) in {"technicaldata", "technical_data"}

    def is_sm_nameplate(self, sm):
        """Check if a Submodel is the 'Nameplate'."""
        return self.norm_id(getattr(sm, "id_short", "")) == "nameplate"

    def get_sm_container(self, sm):
        """
        Get the container that holds Submodel elements, compatible with different basyx versions:
        - submodel_element
        - submodel_elements
        - or an empty list if neither exists
        """
        return getattr(sm, "submodel_element", None) or getattr(sm, "submodel_elements", None) or []

    def walk_sm(self, sm):
        """
        Depth-first traversal of a Submodel.
        Yields tuples (parent_container, element) so that the caller can remove an element easily.
        """
        top = self.get_sm_container(sm)
        stack = [(top, e) for e in list(top)]
        while stack:
            parent_cont, cur = stack.pop()
            yield parent_cont, cur
            if isinstance(cur, model.SubmodelElementCollection):
                for child in list(cur.value):
                    stack.append((cur.value, child))
            elif isinstance(cur, model.Entity):
                for child in list(cur.statement):
                    stack.append((cur.statement, child))

    def set_description_en(self, elem, text, ent_factory):
        """
        Ensure elem.description is a MultiLanguageTextType and set English text.
        Using create_ent.create_description to create the right object if missing.
        """
        if not text:
            return False
        try:
            cur = getattr(elem, "description", None)
            if isinstance(cur, MultiLanguageTextType):
                cur["en"] = text
            else:
                elem.description = ent_factory.create_description(text)
            return True
        except Exception:
            try:
                elem.description = MultiLanguageTextType({'en': text})
                return True
            except Exception:
                return False



# 3 AASX I/O and template merging
class AASXIO:
    """
    Read/write AASX files and merge a product AASX with a supplier template AASX.
    """

    def read_aasx(self, path):
        objects = DictObjectStore()
        files = DictSupplementaryFileContainer()
        with AASXReader(path) as reader:
            _ = reader.get_core_properties()
            reader.read_into(objects, files)
        return objects, files

    def write_aasx(self, out_path, aas, submodels, files):
        with AASXWriter(out_path) as writer:
            store = DictObjectStore()
            store.add(aas)
            for sm in submodels:
                store.add(sm)
            writer.write_aas([aas.id], store, files)

    def _guess_content_type_by_ext(self, path):
        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mapping = {
            "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "bmp": "image/bmp", "svg": "image/svg+xml",
            "txt": "text/plain", "csv": "text/csv", "json": "application/json",
            "xml": "application/xml", "html": "text/html",
            "pdf": "application/pdf", "stp": "model/step", "step": "model/step",
            "stl": "model/stl", "igs": "model/iges", "iges": "model/iges",
            "gltf": "model/gltf+json", "glb": "model/gltf-binary",
            "zip": "application/zip", "gz": "application/gzip",
        }
        return mapping.get(ext, "application/octet-stream")

    def _clean_content_type(self, raw, path):
        ct = (raw or "").strip()
        if ";" in ct:
            ct = ct.split(";", 1)[0].strip()
        if not ct or ("/" not in ct) or (" " in ct):
            ct = self._guess_content_type_by_ext(path)
        return ct

    def _merge_files(self, files_prod, files_tmpl):
        merged = DictSupplementaryFileContainer()
        added = set()
        for fp in files_prod:
            data = files_prod._store[files_prod.get_sha256(fp)]
            ct = self._clean_content_type(files_prod.get_content_type(fp), fp)
            merged.add_file(fp, io.BytesIO(data), ct)
            added.add(fp)
        for fp in files_tmpl:
            if fp in added:
                continue
            data = files_tmpl._store[files_tmpl.get_sha256(fp)]
            ct = self._clean_content_type(files_tmpl.get_content_type(fp), fp)
            merged.add_file(fp, io.BytesIO(data), ct)
            added.add(fp)
        return merged

    def merge_product_with_template(self, product_path, template_path):
        """
        Load product and template AASX, merge submodels (no duplicates by id),
        keep the AAS from product and append missing template submodels.
        """
        objs_prod, files_prod = self.read_aasx(product_path)
        objs_tmpl, files_tmpl = self.read_aasx(template_path)

        aas = None
        merged_submodels = []
        seen_ids = set()

        for obj in objs_prod:
            if isinstance(obj, AssetAdministrationShell):
                aas = obj
                for sm_ref in obj.submodel:
                    sm = sm_ref.resolve(objs_prod)
                    if isinstance(sm, Submodel) and sm.id not in seen_ids:
                        merged_submodels.append(sm)
                        seen_ids.add(sm.id)
                break

        if aas is None:
            raise RuntimeError("No AssetAdministrationShell in {}".format(product_path))

        for obj in objs_tmpl:
            if isinstance(obj, Submodel) and obj.id not in seen_ids:
                merged_submodels.append(obj)
                seen_ids.add(obj.id)
                aas.submodel.add(ModelReference.from_referable(obj))

        merged_files = self._merge_files(files_prod, files_tmpl)
        return aas, merged_submodels, merged_files



# 4 Parse Supplier / ManufacturingProductNumber / type name from file name
class FilenameParser:
    """
    Parse:
    - Supplier (prefix)
    - ManufacturingProductNumber (MPN)
    - ManufacturerTypName (type name)
    from a file name like: "Festo DSNU-16-60-P-A Cylinder.aasx".
    """

    def __init__(self, utils):
        self.utils = utils
        self._alpha_regex = re.compile(r"^[A-Za-z]+$")

    def _remove_vendor_prefix_tokens(self, base_name):
        tokens = base_name.split()
        if not tokens:
            return [], ""
        lower = [t.lower() for t in tokens]

        best_n = 0
        best_vendor = ""
        for key in sorted(supplier_template.keys(), key=lambda k: -len(k)):
            kt = key.split()
            n = len(kt)
            if n <= len(tokens) and lower[:n] == [x.lower() for x in kt]:
                best_n = n
                best_vendor = " ".join(tokens[:n])
                break

        if best_n == 0:
            best_n = 1
            best_vendor = tokens[0]
        return tokens[best_n:], best_vendor

    def _is_alpha(self, t):
        return bool(self._alpha_regex.fullmatch(t))

    def _has_digit(self, t):
        return any(ch.isdigit() for ch in t)

    def split_mpn_and_typename(self, base_name):
        """
        Rules:
        - Remove supplier prefix (supports multi-word vendors).
        - Scan left-to-right for first alphabetic token such that the token after it
          is also alphabetic or '&', and there is at least one digit on its left.
          Left side becomes MPN, right side becomes TypeName.
        - Fallbacks:
          * Use trailing continuous alphabetic segment as TypeName if possible.
          * Otherwise, take first token as MPN and the rest as TypeName.
        Returns  supplier, mpn, typename).
        """
        tokens_after_vendor, supplier = self._remove_vendor_prefix_tokens(base_name)
        t = tokens_after_vendor
        n = len(t)
        if n == 0:
            return supplier, "", ""

        for i in range(1, n):
            if self._is_alpha(t[i]) and (i == n - 1 or self._is_alpha(t[i + 1]) or t[i + 1] == "&"):
                if any(self._has_digit(x) for x in t[:i]):
                    mpn = " ".join(t[:i]).strip()
                    typ = " ".join(t[i:]).strip()
                    if mpn:
                        return supplier, mpn, typ

        last_alpha_start = None
        for i in range(n - 1, -1, -1):
            if self._is_alpha(t[i]):
                last_alpha_start = i
            else:
                break
        if last_alpha_start is not None and any(self._has_digit(x) for x in t[:last_alpha_start]):
            return supplier, " ".join(t[:last_alpha_start]).strip(), " ".join(t[last_alpha_start:]).strip()

        if n >= 2:
            return supplier, t[0], " ".join(t[1:]).strip()
        else:
            return supplier, t[0], ""

    def detect_vendor(self, filename):
        """
        Robust supplier detection based on longest matching prefix using supplier_template keys.
        """
        base = os.path.splitext(os.path.basename(filename))[0].lower()
        base = self.utils.norm_spaces(re.sub(r"[_\-]+", " ", base))
        for key in sorted(supplier_template.keys(), key=lambda k: -len(k)):
            k = self.utils.norm_spaces(key)
            if base.startswith(k + " ") or base == k:
                return key
        return None


# 5 ID patching and PartNr handling
class IdPatcher:
    """
    Replace trailing "0000" with a chosen suffix across AAS and Submodels.
    Also extract PartNr from the TechnicalData submodel and write SerialNumber.
    """

    def __init__(self, utils):
        self.utils = utils

    def sanitize_suffix(self, s):
        s = (s or "").strip()
        s = s.replace(" ", "_")
        s = re.sub(r"[#?/:]+", "_", s)
        return s

    def replace_trailing_0000(self, identifier, suffix):
        if identifier and identifier.endswith("0000"):
            return identifier[:-4] + suffix
        return identifier

    def patch_ids(self, aas, submodels, chosen_suffix):
        if not chosen_suffix:
            return False
        suffix = self.sanitize_suffix(chosen_suffix)
        changed = False

        if str(aas.id).endswith("0000"):
            aas.id = self.replace_trailing_0000(str(aas.id), suffix)
            changed = True

        for sm in submodels:
            if str(sm.id).endswith("0000"):
                sm.id = self.replace_trailing_0000(str(sm.id), suffix)
                changed = True

        if changed:
            # Rebuild AAS.submodel references to keep referential integrity
            try:
                aas.submodel.clear()
            except AttributeError:
                for ref in list(aas.submodel):
                    try:
                        aas.submodel.remove(ref)
                    except Exception:
                        pass
            for sm in submodels:
                aas.submodel.add(ModelReference.from_referable(sm))
        return changed

    def find_partnr_in_technicaldata_and_remove(self, submodels):
        """
        Recursively locate PartNr/PartNo/PartNumber Property inside TechnicalData only.
        Remove it once found and return its value as string.
        """
        for sm in submodels:
            if not self.utils.is_sm_technicaldata(sm):
                continue
            for parent, elm in self.utils.walk_sm(sm):
                ids = self.utils.norm_id(getattr(elm, "id_short", None))
                if ids in {"partnr", "partno", "partnumber"}:
                    val = getattr(elm, "value", None)
                    if val is None:
                        continue
                    val = str(val).strip()
                    try:
                        parent.remove(elm)
                    except Exception:
                        pass
                    return val
        return None

    def update_serialnumber_from_partnr(self, submodels, partnr_val):
        """
        If Nameplate.SerialNumber exists, set its value to the PartNr value.
        """
        if not partnr_val:
            return False
        for sm in submodels:
            if not self.utils.is_sm_nameplate(sm):
                continue
            for _, elm in self.utils.walk_sm(sm):
                if self.utils.norm_id(getattr(elm, "id_short", None)) == "serialnumber":
                    try:
                        setattr(elm, "value", str(partnr_val))
                        return True
                    except Exception:
                        pass
        return False

    def pick_number_from_code_map(self, filename):
        """
        Try to pick a manual suffix from id_suffix_map by exact file base name or tolerant prefix.
        """
        base = os.path.splitext(os.path.basename(filename))[0]
        if base in id_suffix_map:
            return id_suffix_map[base]
        norm = re.sub(r"[_\-]+", " ", base.lower()).strip()
        for k, v in id_suffix_map.items():
            kk = re.sub(r"[_\-]+", " ", k.lower()).strip()
            if norm.startswith(kk):
                return v
        return None



# 6 Update AAS elements (properties, capability description)
class AASUpdater:
    """
    Update property values from filename, and update Capability('Cap') description text.
    """

    def __init__(self, utils, ent_factory):
        self.utils = utils
        self.ent = ent_factory

    def update_properties_from_filename(self, submodels, mpn, typ):
        """
        Look for Property with idShort:
        - ManufacturingProductNumber
        - ManufacturerTypName
        If found, write the values parsed from filename. Does not create new elements.
        """
        changed = False
        targets = {
            "manufacturingproductnumber": mpn,
            "manufacturertypname": typ,
        }
        if not (mpn or typ):
            return False

        for sm in submodels:
            for _, elm in self.utils.walk_sm(sm):
                if isinstance(elm, model.Property):
                    key = self.utils.norm_id(getattr(elm, "id_short", None))
                    if key in targets and targets[key] is not None:
                        try:
                            elm.value = str(targets[key])
                            changed = True
                        except Exception:
                            pass
        return changed

    def update_capability_desc_from_typename(self, submodels, typename):
        """
        Case-insensitive match of ManufacturerTypName against cap_desc_map.
        If a description is found, write it into Capability elements:
        - Prefer Capability with idShort == 'Cap'
        - Fallback to all Capability elements if no 'Cap' exists
        Returns (found_in_map: bool, actually_updated: bool)
        """
        if not typename:
            return False, False
        key = self.utils.norm_spaces(typename).lower()
        desc = cap_desc_map.get(key)
        if not desc:
            return False, False

        updated = False
        targets = []

        # Prefer 'Cap'
        for sm in submodels:
            for _, elm in self.utils.walk_sm(sm):
                if hasattr(model, "Capability") and isinstance(elm, model.Capability):
                    if self.utils.norm_id(getattr(elm, "id_short", "")) == "cap":
                        targets.append(elm)

        # Fallback to all capabilities if 'Cap' not found
        if not targets:
            for sm in submodels:
                for _, elm in self.utils.walk_sm(sm):
                    if hasattr(model, "Capability") and isinstance(elm, model.Capability):
                        targets.append(elm)

        for cap in targets:
            if self.utils.set_description_en(cap, desc, self.ent):
                updated = True

        return True, updated


# 7 ProductClassId update (manual IRDI map first, then eClass)
class ProductClassUpdater:
    """
    Update ProductClassId Property values based on ManufacturerTypName.
    Priority:
      1) PRODUCT_CLASS_IRDI_MAP
      2) eClass best-effort match (MapEClass.get_IrdiCC_descr)
    If neither provides a meaningful IRDI, writes '0000'.
    """

    def __init__(self, utils, eclass):
        self.utils = utils
        self.eclass = eclass

    def update_from_typename(self, submodels, typename):
        """
        Return (found_meaningful_value, written_value).
        'found_meaningful_value' is False when '0000' is used.
        """
        if not typename:
            return False, "0000"

        key = self.utils.norm_spaces(typename).lower()
        irdi = IRDI_map.get(key)
        if not irdi:
            irdi, _ = self.eclass.get_IrdiCC_descr(typename.strip())
        if not irdi:
            irdi = "0000"

        wrote = False
        for sm in submodels:
            for _, elm in self.utils.walk_sm(sm):
                if isinstance(elm, model.Property) and self.utils.norm_id(getattr(elm, "id_short", "")) == "productclassid":
                    try:
                        elm.value = str(irdi)
                        wrote = True
                    except Exception:
                        pass
        return (irdi != "0000"), irdi if wrote else irdi

    def productclassid_is_0000(self, submodels):
        """
        Check whether any ProductClassId property is present and has value exactly '0000'.
        """
        for sm in submodels:
            for _, elm in self.utils.walk_sm(sm):
                if isinstance(elm, model.Property) and self.utils.norm_id(getattr(elm, "id_short", "")) == "productclassid":
                    if str(getattr(elm, "value", "")).strip() == "0000":
                        return True
        return False



# 8 Statistics container (no dataclass, as requested)
class Stats:
    def __init__(self):
        self.uniq_mpn = set()
        self.uniq_typ = set()
        self.missing_typnames = set()   # Typename not found in cap_desc_map
        self.cls_notfound_files = set() # Typename not found in manual map nor eClass
        self.pcid_0000_files = set()    # ProductClassId written/kept as '0000'
        self.aas_still_0000 = set()     # AAS.id still ending with '0000'



# 9 High-level coordinator, orchestration app
class AASUpdaterApp:
    """
    High-level coordinator that:
      - Detects supplier by filename and picks the right template
      - Merges product AASX with template AASX
      - Parses filename to fill MPN and TypeName
      - Updates Capability description
      - Updates ProductClassId (manual map to eClass)
      - Patches IDs from PartNr or manual suffix map
      - Writes output and prints summary
    """

    def __init__(self):
        self.utils = AASUtils()
        self.io = AASXIO()
        self.parser = FilenameParser(self.utils)
        self.idpatch = IdPatcher(self.utils)
        self.ent_factory = ent()
        self.eclass = MapEClass()
        self.updater = AASUpdater(self.utils, self.ent_factory)
        self.cls_updater = ProductClassUpdater(self.utils, self.eclass)

    def run(self):
        if not os.path.isdir(AAS_root):
            raise RuntimeError("AAS root not found: {}".format(AAS_root))
        if not os.path.isdir(template_root):
            raise RuntimeError("Template root not found: {}".format(template_root))
        os.makedirs(out_root, exist_ok=True)

        stats = Stats()

        for fname in os.listdir(AAS_root):
            if not fname.lower().endswith(".aasx"):
                continue

            product_path = os.path.join(AAS_root, fname)
            vendor_key = self.parser.detect_vendor(fname)
            if not vendor_key:
                print("[WARN] Unable to detect supplier for:", fname)
                continue

            tmpl_name = supplier_template[vendor_key]
            template_path = os.path.join(template_root, tmpl_name)
            if not os.path.isfile(template_path):
                print("[WARN] Template not found for {}: {}".format(vendor_key, template_path))
                continue

            out_path = os.path.join(out_root, fname)

            aas, submodels, merged_files = self.io.merge_product_with_template(product_path, template_path)

            # ---- Parse filename and update properties (MPN / TypeName) ----
            base_name = os.path.splitext(fname)[0]
            _, mpn, typname = self.parser.split_mpn_and_typename(base_name)
            if mpn:
                stats.uniq_mpn.add(mpn)
            if typname:
                stats.uniq_typ.add(typname)
            self.updater.update_properties_from_filename(submodels, mpn, typname)

            # ---- Capability description from TypeName ----
            found_desc, _ = self.updater.update_capability_desc_from_typename(submodels, typname)
            if typname and not found_desc:
                stats.missing_typnames.add(typname)

            # ---- ProductClassId from manual map or eClass ----
            found_cls, _written = self.cls_updater.update_from_typename(submodels, typname)
            if not found_cls:
                stats.cls_notfound_files.add(fname)
            if self.cls_updater.productclassid_is_0000(submodels):
                stats.pcid_0000_files.add(fname)

            # ---- Patch IDs if any ends with '0000' ----
            if str(aas.id).endswith("0000") or any(str(sm.id).endswith("0000") for sm in submodels):
                part_suffix = self.idpatch.find_partnr_in_technicaldata_and_remove(submodels)
                if part_suffix:
                    self.idpatch.update_serialnumber_from_partnr(submodels, part_suffix)
                    self.idpatch.patch_ids(aas, submodels, part_suffix)
                else:
                    mapped = self.idpatch.pick_number_from_code_map(fname)
                    if mapped:
                        self.idpatch.patch_ids(aas, submodels, mapped)

            # Write result file
            self.io.write_aasx(out_path, aas, submodels, merged_files)

            # Collect AAS.id still '0000'
            if str(aas.id).endswith("0000"):
                stats.aas_still_0000.add(fname)

        self._print_summary(stats)

    def _print_summary(self, s):
        if s.missing_typnames:
            print("\nWarn: ManufacturerTypName not found in cap_desc_map (case-insensitive):")
            for v in sorted(s.missing_typnames, key=lambda x: x.lower()):
                print(" -", v)

        if s.pcid_0000_files:
            print("\nWarn: Files where ProductClassId value == '0000':")
            for name in sorted(s.pcid_0000_files):
                print(" -", name)

        if s.aas_still_0000:
            print("\nWarn: Files whose AAS.id still ends with '0000' after merge:")
            for name in sorted(s.aas_still_0000):
                print(" -", name)
        else:
            print("\nWarn: No AAS.id still ends with '0000'.")



if __name__ == "__main__":
    AASUpdaterApp().run()
