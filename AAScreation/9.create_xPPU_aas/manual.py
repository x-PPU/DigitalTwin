#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import re
from typing import Tuple

from basyx.aas import model
from basyx.aas.adapter.aasx import AASXReader, AASXWriter, DictSupplementaryFileContainer
from basyx.aas.model import DictObjectStore, AssetAdministrationShell, Submodel


current_dir = os.path.dirname(os.path.abspath(__file__))
aasx_in  = os.path.join(current_dir, "output", "xPPU_7.aasx")
aasx_out = os.path.join(current_dir, "output", "xPPU_7_manual.aasx")



SMC_MAP = {
    # Only rename SMC idShort exactly equal to this key
    "PPU_2ubIBHQEeaen93uATCTQQ": "PPU",
}

AAS_IDSHORT_MAP = {
    "Phonix_Contact_DIKD_1": "Phonix_Contact_DIKD_1_5_Terminal_Block_Load_Cell_Connection",
}

def _get_container(sm):
    """Return the top-level submodel element container across basyx versions."""
    return getattr(sm, "submodel_element", None) or getattr(sm, "submodel_elements", None) or []


def _walk_sm_elements(sm):
    """Depth-first traversal over all SubmodelElements (SMC/Entity/others)."""
    top = _get_container(sm)
    stack = [(top, e) for e in list(top)]
    while stack:
        parent, cur = stack.pop()
        yield parent, cur
        if isinstance(cur, model.SubmodelElementCollection):
            for child in list(cur.value):
                stack.append((cur.value, child))
        elif isinstance(cur, model.Entity):
            for child in list(cur.statement):
                stack.append((cur.statement, child))


def _titlecase_token(token: str) -> str:
    """Title-case a token; also handle inner hyphen parts (e.g., 'double_reflection' / 'm18x0-75')."""
    parts = token.split("-")
    def tc(w: str) -> str:
        if not w:
            return w
        # keep digits/letters; just uppercase first letter, lowercase the rest
        return w[:1].upper() + w[1:].lower()
    return "-".join(tc(p) for p in parts)


def _titlecase_suffix_after_model(idshort: str) -> str:
    """
    Split by '_' and find the last token containing a digit ⇒ treat as end of model.
    Title-case tokens after that point, then rejoin with '_'.
    If no token contains a digit, keep original (保守处理，避免误改型号).
    """
    if not idshort:
        return idshort
    tokens = idshort.split("_")
    # serch for last token containing a digit
    last_model_idx = -1
    for i, tk in enumerate(tokens):
        if re.search(r"\d", tk):
            last_model_idx = i
    if last_model_idx < 0 or last_model_idx + 1 >= len(tokens):
        # if no digit found, or no tail to title-case, keep original
        return idshort
    head = tokens[: last_model_idx + 1]
    tail = tokens[last_model_idx + 1 :]
    tail_tc = [_titlecase_token(t) for t in tail]
    return "_".join(head + tail_tc)


def _maybe_rename_aas_idshort(aas: AssetAdministrationShell) -> bool:
    """
    Auto-format AAS.id_short: first apply exact mapping if present; otherwise
    title-case the words AFTER the model part. Never touch AAS.id.
    """
    cur = getattr(aas, "id_short", None)
    if not cur:
        return False

    # NEW: exact rename takes precedence and preserves intended casing
    if cur in AAS_IDSHORT_MAP:
        new_val = AAS_IDSHORT_MAP[cur]
        if new_val != cur:
            setattr(aas, "id_short", new_val)
            return True
        return False

    # Fallback: original Title-Case tail logic
    new_val = _titlecase_suffix_after_model(cur)
    if new_val != cur:
        setattr(aas, "id_short", new_val)
        return True
    return False



def _maybe_rename_smc_idshort(sme: model.SubmodelElement) -> bool:
    """Rename SMC.id_short using SMC_MAP; ignore other SME types."""
    if not isinstance(sme, model.SubmodelElementCollection):
        return False
    cur = getattr(sme, "id_short", None)
    if cur and cur in SMC_MAP:
        setattr(sme, "id_short", SMC_MAP[cur])
        return True
    return False


def process_one_file(inp: str, outp: str) -> Tuple[int, int]:
    """
    Process a single AASX file.
    Returns (changed_aas_count, changed_smc_count).
    """
    objs = DictObjectStore()
    files = DictSupplementaryFileContainer()

    if not os.path.isfile(inp):
        raise FileNotFoundError(f"Input AASX not found: {inp}")

    with AASXReader(inp) as reader:
        _ = reader.get_core_properties()
        reader.read_into(objs, files)

    changed_aas = 0
    changed_smc = 0

    # Rename/format AAS.id_short (auto Title-Case tail)
    for obj in objs:
        if isinstance(obj, AssetAdministrationShell):
            if _maybe_rename_aas_idshort(obj):
                changed_aas += 1

    # Rename SMC.id_short inside every submodel (only per SMC_MAP)
    for obj in objs:
        if isinstance(obj, Submodel):
            for _parent, elm in _walk_sm_elements(obj):
                if _maybe_rename_smc_idshort(elm):
                    changed_smc += 1

    if (changed_aas + changed_smc) == 0:
        print("[NO CHANGE] Nothing to update.")
        return 0, 0

    os.makedirs(os.path.dirname(outp), exist_ok=True)

    # Repack to output AASX (keep original AAS.id to preserve references)
    store_out = DictObjectStore()
    aas_ids = []
    for obj in objs:
        store_out.add(obj)
        if isinstance(obj, AssetAdministrationShell):
            aas_ids.append(obj.id)

    with AASXWriter(outp) as writer:
        writer.write_aas(aas_ids, store_out, files)

    return changed_aas, changed_smc


def main():
    try:
        aas_cnt, smc_cnt = process_one_file(aasx_in, aasx_out)
        print(f"Summary: AAS.idShort_changed={aas_cnt}, SMC.idShort_changed={smc_cnt}")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
