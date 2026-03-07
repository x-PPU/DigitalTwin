#!/usr/bin/env python3.10.15
# -*- coding: utf-8 -*-

"""
Behavior Submodel Updater (class-based)

Reads CSVs, creates Behavior submodel elements (with Concept Descriptions when applicable),
and appends them into existing submodels, then writes an updated AASX.
"""

import os
import csv
import re
from basyx.aas import model
from basyx.aas.adapter.aasx import AASXReader, AASXWriter, DictSupplementaryFileContainer
from basyx.aas.model import (
    DictObjectStore, Submodel, Key, KeyTypes, ModelReference, AssetAdministrationShell,
    ExternalReference, ConceptDescription, SubmodelElementCollection
)
from base.create_ent_behavior import ent_behavior
from base.eClass import MapEClass


BEHAVIOR_SUBMODEL_ID = "https://Behavior.com/ids/sm/0000"   


def sanitize_id_short(id_short: str) -> str:
    """Replace non-alphanum with underscores; ensure leading letter."""
    if not id_short:
        return "default"
    s = re.sub(r'[^a-zA-Z0-9_]', '_', id_short)
    if not s or not s[0].isalpha():
        s = 'default' + s
    return s  # added default prefix for duplicate idShort


class AASXIO:
    def __init__(self, aasx_in, aasx_out):
        self.aasx_in = aasx_in
        self.aasx_out = aasx_out
        self.object_store = None
        self.file_store = None

    def load(self):
        self.object_store = DictObjectStore()
        self.file_store = DictSupplementaryFileContainer()
        with AASXReader(self.aasx_in) as reader:
            reader.read_into(self.object_store, self.file_store)

    def save(self):
        aas_ids = [aas.id for aas in self.object_store if isinstance(aas, AssetAdministrationShell)]
        with AASXWriter(self.aasx_out) as writer:
            writer.write_aas(aas_ids=aas_ids, object_store=self.object_store, file_store=self.file_store)

    def find_submodel(self, id_short):
        for obj in self.object_store:
            if isinstance(obj, Submodel) and obj.id_short == id_short:
                return obj
        return None


class ConceptDescriptionManager:
    """
    Build ConceptDescriptions from CSV and add them to the object store.
    Exposes a mapping: concept_id (xmi:id) -> ConceptDescription object.
    """
    def __init__(self, io):
        self.io = io
        self.ent = ent_behavior()
        self.map = {}

    def load_from_csv(self, csv_file_path):
        # every scenario reloads its own CD set, reusing existing IDs to avoid KeyError
        self.map.clear()
        if not (csv_file_path and os.path.isfile(csv_file_path)):
            print("Warning: ConceptDescription CSV not found:", csv_file_path)
            return self.map

        # collect existing CDs by ID
        existing_cd_by_id = {}
        for obj in self.io.object_store:
            if isinstance(obj, ConceptDescription):
                existing_cd_by_id[obj.id] = obj

        with open(csv_file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for line_number, row in enumerate(reader, start=2):
                id_short = (row.get('name') or '').strip()
                concept_id = (row.get('xmi:id') or '').strip()
                description = (row.get('description') or '').strip()

                if not id_short:
                    print("Warning: ConceptDescription missing 'name' at line %d" % line_number)
                    continue
                if not concept_id:
                    print("Warning: ConceptDescription missing 'xmi:id' at line %d" % line_number)
                    continue
                if not id_short or not id_short[0].isalpha():
                    id_short = "Default_" + (id_short or "CD")

                if concept_id in existing_cd_by_id:
                    cd = existing_cd_by_id[concept_id]
                else:
                    cd = self.ent.create_CD(id_short, concept_id, 'CONCEPT_DESCRIPTION', description)
                    self.io.object_store.add(cd)
                    existing_cd_by_id[concept_id] = cd

                self.map[concept_id] = cd

        return self.map

    def get(self, concept_id):
        return self.map.get(concept_id)


class BehaviorReferenceResolver:
    """
    Resolve a ModelReference path to an element inside the Behavior submodel
    by scanning a CSV's rows and reconstructing the ancestor stack (SMC/Entity).

    """
    def __init__(self, behavior_submodel_id, root_smc_id_short=None):
        self.behavior_submodel_id = behavior_submodel_id
        self.root_smc_id_short = root_smc_id_short  # e.g., "Scenario_13"

    def create_reference_from_csv(self, target_semantic_id, rows):
        hierarchy = self._find_hierarchy(rows, target_semantic_id)
        if not hierarchy:
            return None

        keys = [Key(type_=KeyTypes.SUBMODEL, value=self.behavior_submodel_id)]
        # for reference within Behavior submodel add SMC Scenario_X
        if self.root_smc_id_short:
            keys.append(Key(type_=KeyTypes.SUBMODEL_ELEMENT_COLLECTION, value=self.root_smc_id_short))

        for id_short, element_type in hierarchy:
            if element_type == "SubmodelElementCollection":
                keys.append(Key(type_=KeyTypes.SUBMODEL_ELEMENT_COLLECTION, value=id_short))
            elif element_type == "Property":
                keys.append(Key(type_=KeyTypes.PROPERTY, value=id_short))
            elif element_type == "Entity":
                keys.append(Key(type_=KeyTypes.ENTITY, value=id_short))
            elif element_type == "ReferenceElement":
                keys.append(Key(type_=KeyTypes.REFERENCE_ELEMENT, value=id_short))
        return ModelReference(key=tuple(keys), type_=Submodel)

    def _find_hierarchy(self, rows, target_semantic_id, visited=None):
        if visited is None:
            visited = set()

        stack = []
        for row in rows:
            t = (row.get('typeName') or '').strip()
            sem = (row.get('Reference') or '').strip()

            # Pop on end-markers
            if t.startswith('End-') and stack:
                stack.pop()
                continue

            # Push containers
            if t in ("SubmodelElementCollection", "Entity"):
                cur_id_short = (row.get('idShort') or '').strip()
                stack.append((cur_id_short, t))

            # If this row is the target
            if sem and sem == target_semantic_id and sem not in visited:
                visited.add(sem)
                cur_id_short = (row.get('idShort') or '').strip()
                return stack + [(cur_id_short, t)]

        print("Warning: Could not find target semantic ID '%s' in CSV." % target_semantic_id)
        return []


class BehaviorCSVBuilder:
    """
    Parse one Behavior CSV and build submodel elements:
      - SubmodelElementCollection
      - Property
      - ReferenceElement
      - RelationshipElement (first_value / second_value)
    Assign semanticId: Prefer ConceptDescription (by Reference column), fallback to Global IRI from ent_behavior.get_iri_and_unit().
    """
    def __init__(self, io, cd_manager, resolver):
        self.io = io
        self.cd = cd_manager
        self.resolver = resolver
        self.ent = ent_behavior()
        self.eclass = MapEClass()

    def _add_unique(self, parent_smc, element):
        """
        Add element into parent_smc.value ensuring id_short uniqueness.
        If duplicated, prefix with 'None1_', 'None2_', ... before original id_short.
        """
        desired = element.id_short or "default"
        existing = {e.id_short for e in parent_smc.value}

        if desired in existing:
            n = 1
            candidate = f"None{n}_{desired}"
            while candidate in existing:
                n += 1
                candidate = f"None{n}_{desired}"
            element.id_short = candidate

        parent_smc.value.add(element)

    def from_csv(self, csv_file_path):
        elements = []
        stack_smc = []

        with open(csv_file_path, mode='r', newline='', encoding='utf-8') as f:
            reader = list(csv.DictReader(f, delimiter=','))

        if not reader:
            return elements

        expected = ['typeName', 'idShort', 'value', 'valueType',
                    'category', 'descriptionEN', 'descriptionDE', 'semanticId', 'Reference']
        for col in expected:
            if col not in reader[0]:
                print("Warning: column '%s' missing in %s. " % (col, os.path.basename(csv_file_path)))

        is_behavior_csv = 'second_value' in reader[0]

        for line_no, row in enumerate(reader, start=2):
            try:
                t = (row.get('typeName') or '').strip()
                id_short = sanitize_id_short(row.get('idShort') or '')
                category = row.get('category') or None
                # ent_behavior.create_description() -> MultiLanguageTextType
                desc = self.ent.create_description(row.get('descriptionEN'))

                iri_prop = self.ent.get_iri_and_unit(id_short)

                # Build semanticId + supplementalSemanticId
                ref_field = (row.get('Reference') or '').strip()
                if ref_field and self.cd.get(ref_field):
                    cd_obj = self.cd.get(ref_field)
                    semantic_id_ref = ModelReference(
                        key=(Key(type_=KeyTypes.CONCEPT_DESCRIPTION, value=cd_obj.id),),
                        type_=ConceptDescription
                    )
                    supplemental_semantic_id = [
                        ExternalReference((Key(type_=KeyTypes.GLOBAL_REFERENCE, value=iri_prop),))
                    ]
                else:
                    semantic_id_ref = ExternalReference((Key(type_=KeyTypes.GLOBAL_REFERENCE, value=iri_prop),))
                    supplemental_semantic_id = []

                if t == "SubmodelElementCollection":
                    smc = self.ent.create_SMC(
                        id_short=id_short, value=[], category=category, description=desc,
                        semantic_id=semantic_id_ref, supplemental_semantic_id=supplemental_semantic_id
                    )
                    if stack_smc:
                        self._add_unique(stack_smc[-1], smc)
                    else:
                        elements.append(smc)
                    stack_smc.append(smc)

                elif t == "Property":
                    value_type_str = (row.get('valueType') or 'string').strip().lower()
                    raw = (row.get('value') or '').strip()
                    if value_type_str == 'boolean':
                        value_type = bool
                        value = raw.lower() in ('true', '1', 'yes')
                    elif value_type_str in ('int', 'integer'):
                        value_type = int
                        value = int(raw) if raw else 0
                    else:
                        value_type = str
                        value = raw

                    prop = self.ent.create_Prop(
                        id_short=id_short, value=value, value_type=value_type, category=category,
                        description=desc, semantic_id=semantic_id_ref, supplemental_semantic_id=supplemental_semantic_id
                    )
                    if stack_smc:
                        self._add_unique(stack_smc[-1], prop)
                    else:
                        elements.append(prop)

                elif t == "ReferenceElement":
                    target_sem_id = (row.get('value') or '').strip()
                    if not target_sem_id:
                        print("WARN: %s:%d ReferenceElement with empty 'value'; skipped."
                              % (os.path.basename(csv_file_path), line_no))
                        continue

                    ref_value = self.resolver.create_reference_from_csv(target_sem_id, reader)
                    if not ref_value:
                        continue

                    ref_el = self.ent.create_Ref(
                        id_short=id_short, value=ref_value, category=category,
                        description=desc, semantic_id=semantic_id_ref, supplemental_semantic_id=supplemental_semantic_id
                    )
                    if stack_smc:
                        self._add_unique(stack_smc[-1], ref_el)
                    else:
                        elements.append(ref_el)

                elif t == "RelationshipElement":
                    first_sem = (row.get('value') or '').strip()
                    second_sem = (row.get('second_value') or '').strip() if is_behavior_csv else None
                    if first_sem and second_sem:
                        first_ref = self.resolver.create_reference_from_csv(first_sem, reader)
                        second_ref = self.resolver.create_reference_from_csv(second_sem, reader)
                        if first_ref and second_ref:
                            rel = self.ent.create_Rel(
                                id_short=id_short,
                                first_value_keys=first_ref.key,
                                second_value_keys=second_ref.key,
                                description=desc,
                                category=category,
                                semantic_id=semantic_id_ref,
                                supplemental_semantic_id=supplemental_semantic_id
                            )
                            if stack_smc:
                                self._add_unique(stack_smc[-1], rel)
                            else:
                                elements.append(rel)

                elif t.startswith("End-"):
                    if t == "End-SubmodelElementCollection" and stack_smc:
                        stack_smc.pop()

                # ignore other types for Behavior CSV

            except Exception as e:
                print("Error processing CSV '%s', line %d, idShort='%s': %s"
                      % (csv_file_path, line_no, row.get('idShort'), e))
                raise

        return elements


class BehaviorUpdater:
    """
    Orchestrate: load AASX - per Scenario:
      - load ConceptDescriptions_ScXX
      - ensure SMC 'Scenario_XX' under Submodel 'Behavior'
      - add elements from Behavior1_ScXX.csv / Behavior2_ScXX.csv into that SMC
      - save AASX
    """
    def __init__(self, aasx_in, behavior_submodel_name, scenarios, aasx_out, behavior_submodel_id=BEHAVIOR_SUBMODEL_ID):
        """
        scenarios: list of dicts, e.g.
          {
            "name": "Scenario_13",
            "cd":   "output/ConceptDescription_Sc13.csv",
            "csvs": ["output/Behavior1_Sc13.csv", "output/Behavior2_Sc13.csv"]
          }
        """
        self.io = AASXIO(aasx_in, aasx_out)
        self.behavior_submodel_name = behavior_submodel_name
        self.scenarios = scenarios
        self.behavior_submodel_id = behavior_submodel_id

        self.cd_manager = ConceptDescriptionManager(self.io)
        self.builder = None

    def _ensure_smc(self, submodel_obj: Submodel, smc_id_short: str) -> SubmodelElementCollection:
        # if not exist, create SMC under submodel_obj
        for sme in list(submodel_obj.submodel_element):  # submodel_element: set-like
            if isinstance(sme, SubmodelElementCollection) and sme.id_short == smc_id_short:
                return sme
        ent = ent_behavior()
        smc = ent.create_SMC(
            id_short=smc_id_short,
            value=[],
            category=None,
            description=None,
            semantic_id=None,
            supplemental_semantic_id=[]  
        )
        submodel_obj.submodel_element.add(smc)
        return smc

    def _add_unique_to_smc(self, smc, element):
        """
        Add element into Scenario_X SMC with uniqueness guarantee on id_short.
        If duplicated, prefix with 'None1_', 'None2_', ... before original id_short.
        """
        desired = element.id_short or "default"
        existing = {e.id_short for e in smc.value}

        if desired in existing:
            n = 1
            candidate = f"None{n}_{desired}"
            while candidate in existing:
                n += 1
                candidate = f"None{n}_{desired}"
            element.id_short = candidate

        smc.value.add(element)

    def run(self):
        self.io.load()

        behavior_sm = self.io.find_submodel(self.behavior_submodel_name)
        if behavior_sm is None:
            raise ValueError("Submodel '%s' not found in the object store." % self.behavior_submodel_name)

        for sc in self.scenarios:
            sc_name = sc["name"]               
            cd_csv = sc.get("cd")
            csv_list = sc.get("csvs", [])

            print("\n Updating %s :" % sc_name)

            # 1) load ConceptDescriptions_ScXX.csv
            self.cd_manager.load_from_csv(cd_csv)

            # 2) ensure Scenario_X SMC in Behavior submodel
            scenario_smc = self._ensure_smc(behavior_sm, sc_name)

            # 3) create builder + resolver  for this scenario
            resolver = BehaviorReferenceResolver(self.behavior_submodel_id, root_smc_id_short=sc_name)
            self.builder = BehaviorCSVBuilder(self.io, self.cd_manager, resolver)

            # 4) read Behavior1/2_ScXX.csv and add elements into Scenario_X SMC
            total = 0
            for csv_path in csv_list:
                if not (csv_path and os.path.isfile(csv_path)):
                    print("WARN: Behavior CSV not found:", csv_path)
                    continue
                elems = self.builder.from_csv(csv_path)
                for el in elems:
                    self._add_unique_to_smc(scenario_smc, el)
                total += len(elems)

            print("INFO: Added %d element(s) into SMC '%s'." % (total, sc_name))

        self.io.save()



if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))

    base_aasx = os.path.join(current_dir, "output", "xPPU_5.aasx")
    output_aasx = os.path.join(current_dir, "output", "xPPU_6.aasx")

    csv_root = os.path.join(current_dir, "csv")

    scenarios = [
        {
            "name": "Scenario_13",
            "cd":   os.path.join(csv_root, "ConceptDescription_Sc13.csv"),
            "csvs": [
                os.path.join(csv_root, "Behavior1_Sc13.csv"),
                os.path.join(csv_root, "Behavior2_Sc13.csv"),
            ],
        },
        {
            "name": "Scenario_14",
            "cd":   os.path.join(csv_root, "ConceptDescription_Sc14.csv"),
            "csvs": [
                os.path.join(csv_root, "Behavior1_Sc14.csv"),
                os.path.join(csv_root, "Behavior2_Sc14.csv"),
            ],
        },
        {
            "name": "Scenario_15",
            "cd":   os.path.join(csv_root, "ConceptDescription_Sc15.csv"),
            "csvs": [
                os.path.join(csv_root, "Behavior1_Sc15.csv"),
                os.path.join(csv_root, "Behavior2_Sc15.csv"),
            ],
        },
    ]

    updater = BehaviorUpdater(
        aasx_in=base_aasx,
        behavior_submodel_name="Behavior",   
        scenarios=scenarios,
        aasx_out=output_aasx,
        behavior_submodel_id=BEHAVIOR_SUBMODEL_ID
    )
    updater.run()

