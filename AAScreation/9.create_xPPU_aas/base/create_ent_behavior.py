from basyx.aas import model
from basyx.aas.adapter import aasx
from basyx.aas.util.identification import *
from basyx.aas.model import LangStringSet
from basyx.aas.model.base import PreferredNameTypeIEC61360, DefinitionTypeIEC61360
from basyx.aas.model import MultiLanguageTextType, LangStringSet, DefinitionTypeIEC61360
from base.eClass import MapEClass  
from basyx.aas.model import DataSpecificationIEC61360, DataTypeIEC61360
from basyx.aas.model import MultiLanguageTextType
from basyx.aas.model import (
    ConceptDescription,
    EmbeddedDataSpecification,
    ExternalReference,
    Key,
    KeyTypes,
    MultiLanguageTextType,
    Reference,
    DataSpecificationContent,
)

class ent_behavior:
    def __init__(self):
        self.eclass_instance = MapEClass()  

    def get_kind(self, kind):
        if kind == 'I':
            return model.ModellingKind.INSTANCE
        elif kind == 'T':
            return model.ModellingKind.TEMPLATE
        return None

    def get_kind_asset(self, kind):
        if kind == 'I':
            return model.AssetKind.INSTANCE
        elif kind == 'T':
            return model.AssetKind.TYPE
        return model.AssetKind.NOT_APPLICABLE 

    def create_iri(self, obj_store, id_http, type_):
        generator = NamespaceIRIGenerator(id_http, obj_store)
        id_ = generator.generate_id()
        if type_ == 'submodel':
            obj_store.add(model.Submodel(id_))
        return obj_store, id_

    def get_iri_and_unit(self, id_short):
        unit, iri_prop, descr = self.eclass_instance.get_IrdiPR_unit_descr(id_short)
        return iri_prop 

    def create_aas(self, id_short, id_aas, asset, derived_from):
        aas = model.AssetAdministrationShell(
            id_short=id_short,
            id_=id_aas,
            asset_information=asset,
            derived_from=derived_from
        )
        return id_aas, aas

    def create_aas_rand_iri(self, obj_store, id_short, aas_name, asset, derived_from):
        obj_store, id_aas = self.create_iri(obj_store, 'https://' + aas_name + '.com/ids/aas/', 'aas')
        id_aas, aas = self.create_aas(id_short, id_aas, asset, derived_from)
        obj_store.add(aas)
        return obj_store, id_aas, aas

    def create_asset_information(self, id_, kind):
        return model.AssetInformation(
            asset_kind=self.get_kind_asset(kind),
            global_asset_id=model.Identifier(id_)
        )

    def create_asset_information_rand_iri(self, obj_store, asset_name, kind):
        obj_store, id_asset = self.create_iri(obj_store, 'https://' + asset_name + '.com/ids/asset/', 'asset')
        asset_information = self.create_asset_information(id_asset, kind)
        return obj_store, asset_information
    

    def create_SM(self, id_SM, submodel_elements, semantic_id, id_short, kind):
        if semantic_id:
            semantic_id_ref = semantic_id  # 已经是 Reference 对象
        else:
            iri_prop = self.get_iri_and_unit(id_short)
            semantic_id_ref = model.ExternalReference([
                model.Key(type_=model.KeyTypes.GLOBAL_REFERENCE, value=iri_prop)
            ])

        SM = model.Submodel(
            id_=id_SM,
            submodel_element=submodel_elements,
            id_short=id_short,
            semantic_id=semantic_id_ref,
            kind=self.get_kind(kind),
        )
        return SM


    def create_SM_rand_iri(self, obj_store, id_short, SM_name, submodel_elements, semantic_id, kind):
        obj_store, id_SM = self.create_iri(obj_store, 'https://' + SM_name + '.com/ids/sm/', 'submodel')
        SM = self.create_SM(id_SM, submodel_elements, semantic_id, id_short, kind)
        return obj_store, SM


    def create_SMC(self, id_short, value, category, description, semantic_id, supplemental_semantic_id):
        SMC = model.SubmodelElementCollection(
            id_short=id_short,
            value=value,
            category=category,
            description=description,
            semantic_id=semantic_id,
            supplemental_semantic_id=supplemental_semantic_id
        )
        return SMC

    def create_Prop(self, id_short, value_type, value, category, description, semantic_id, supplemental_semantic_id):
        Prop = model.Property(
            id_short=id_short,
            value_type=value_type,
            value=value,
            category=category,
            description=description,
            semantic_id=semantic_id,
            supplemental_semantic_id=supplemental_semantic_id
        )
        return Prop

    def create_Rel(self, id_short, description, first_value_keys, second_value_keys, category, semantic_id, supplemental_semantic_id):
        Rel = model.RelationshipElement(
            id_short=id_short,
            description=description,
            first=model.ModelReference(
                type_=model.KeyTypes.GLOBAL_REFERENCE,
                key=first_value_keys
            ),
            second=model.ModelReference(
                type_=model.KeyTypes.GLOBAL_REFERENCE,
                key=second_value_keys
            ),
            category=category,
            semantic_id=semantic_id,
            supplemental_semantic_id=supplemental_semantic_id
        )
        return Rel

    def create_Ref(self, id_short, value, category, description, semantic_id, supplemental_semantic_id):

        Ref = model.ReferenceElement(
            id_short=id_short,
            value=value,
            category=category,
            description=description,
            semantic_id=semantic_id,
            supplemental_semantic_id=supplemental_semantic_id
        )
        return Ref
    
    def create_CD(self, id_short, id_, category, description):
        if isinstance(description, str):
            description = description.strip()
            if description:
                parts = [description[i:i+1028] for i in range(0, len(description), 1028)]
                description_dict = {'en': '\n'.join(parts)}
            else:
                description_dict = None
        elif isinstance(description, dict):
            description_dict = {}
            for lang, text in description.items():
                text = text.strip()
                if text:
                    parts = [text[i:i+1028] for i in range(0, len(text), 1028)]
                    description_dict[lang] = '\n'.join(parts)
            if not description_dict:
                description_dict = None
        else:
            description_dict = None

        data_spec_content = DataSpecificationIEC61360(
            preferred_name=PreferredNameTypeIEC61360({'en': id_short}),
            data_type=DataTypeIEC61360.STRING  
        )

        embedded_data_spec = EmbeddedDataSpecification(
            data_specification=ExternalReference((
                Key(type_=KeyTypes.GLOBAL_REFERENCE, value="https://mediatum.ub.tum.de/doc/1468863/1468863.pdf"),
                Key(type_=KeyTypes.GLOBAL_REFERENCE, value="https://github.com/x-PPU/Models/blob/master/Papyrus%20-Scenario_14.zip")
            )),
            data_specification_content=data_spec_content
        )

        CD = ConceptDescription(
            id_short=id_short,
            id_=id_,
            category=category,
            description=MultiLanguageTextType(description_dict) if description_dict else None,
            embedded_data_specifications=[embedded_data_spec]
        )

        return CD


    def create_obj_store(self, aas, asset, submodels):
        object_list = [aas]
        for sm in submodels:
            aas.submodel.add(model.ModelReference.from_referable(sm))
            object_list.append(sm)
        object_store = model.DictObjectStore(object_list)
        return object_store

    def write_aas(self, outfile, id_aas, object_store, file_store):
        with aasx.AASXWriter(outfile) as writer:
            print("Writing AASX file with the following descriptions:")
            for obj in object_store:
                if hasattr(obj, 'description'):
                    print(f"{obj.id_short}: {obj.description}")
            writer.write_aas(
                aas_ids=id_aas,
                object_store=object_store,
                file_store=file_store
            )

    def create_description(self, description_text):
        if description_text:
            return MultiLanguageTextType({'en': description_text})
        return None