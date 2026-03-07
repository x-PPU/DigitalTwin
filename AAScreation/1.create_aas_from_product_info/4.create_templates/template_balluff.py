#!/usr/bin/env python 3.10.15
import os
from pathlib import Path

from basyx.aas import model
from basyx.aas.adapter import aasx
from base.create_ent import ent
from base.eClass import MapEClass
from pathlib import Path
from basyx.aas.adapter.aasx import AASXWriter

ent_instance = ent()
eclass_instance = MapEClass()

def create_property(id_short, value, iri):
    return ent_instance.create_Prop(id_short, model.datatypes.String, value, 'PARAMETER', iri)

def get_iri_from_eclass(property_name):
    unit, iri, descr = eclass_instance.get_IrdiPR_unit_descr(property_name)
    return iri

# Create the Nameplate submodel
def create_nameplate_submodel(obj_store, file_store):
    submodel_elements = []
    id_short = 'Nameplate'
    semantic_id = 'https://admin-shell.io/zvei/nameplate/1/0/Nameplate'
    kind = 'I'
    obj_store, submodel = ent_instance.create_SM_rand_iri(obj_store, id_short, 'Nameplate', submodel_elements, semantic_id, kind)

    # Add properties
    properties = [
        ('ManufacturerTypName', None, '0173-1#02-AAW338#001'),
        ('ManufacturerProductFamily', None, '0173-1#02-AAU731#001'),
        ('SerialNumber', None, '0173-1#02-AAM556#002'),
        ('CountryOfOrigin', 'Germany', '0173-1#02-AAO841#001'),
        ('YearOfConstruction', None, '0173-1#02-AAP906#001')
    ]

    for id_short, value, iri in properties:
        prop_element = create_property(id_short, value, iri)
        submodel.submodel_element.add(prop_element)

    # Create SMC Address
    address_elements = [
        ('Department', 'R&D', '0173-1#02-AAO127#003'),
        ('Street', 'Balluffstraße 1', '0173-1#02-AAO128#002'),
        ('Zipcode', '73734', '0173-1#02-AAO129#002'),
        ('CityTown', 'Neuhausen a.d.F.', '0173-1#02-AAO132#002'),
        ('StateCounty', 'Baden-Württemberg', '0173-1#02-AAO133#002'),
        ('NationalCode', 'DE', '0173-1#02-AAO134#002'),
        ('AddressRemarks', 'Headquarters', '0173-1#02-AAO202#003'),
        ('AddressOfAdditionalLink', 'https://www.balluff.de/', '0173-1#02-AAQ326#002')
    ]

    phone_elements = [
        ('TelephoneNumber', '+49 7158 173-0', '0173-1#02-AAO136#002'),
        ('TypeOfTelephone', 'Office', '0173-1#02-AAO137#003')
    ]

    fax_elements = [
        ('FaxNumber', '+49 7158 5010', '0173-1#02-AAO195#002'),
        ('TypeOfFaxNumber', 'Office', '0173-1#02-AAO196#003')
    ]

    email_elements = [
        ('EmailAddress', 'balluff@balluff.de', '0173-1#02-AAO198#002'),
        ('TypeOfEmailAddress', 'Work', '0173-1#02-AAO199#003'),
    ]

    def create_elements(elements):
        return [create_property(id_short, value, iri) for id_short, value, iri in elements]

    phone_smc = ent_instance.create_SMC('Phone', create_elements(phone_elements), 'PARAMETER', '0173-1#02-AAQ833#005')
    fax_smc = ent_instance.create_SMC('Fax', create_elements(fax_elements), 'PARAMETER', '0173-1#02-AAQ834#005')
    email_smc = ent_instance.create_SMC('Email', create_elements(email_elements), 'PARAMETER', '0173-1#02-AAQ836#005')

    address_elements = create_elements(address_elements)
    address_elements.extend([phone_smc, fax_smc, email_smc])

    address_smc = ent_instance.create_SMC('Address', address_elements, 'PARAMETER', '0173-1#02-AAQ832#005')
    submodel.submodel_element.add(address_smc)

    # Create SMC Markings
    markings_elements = [
        ('MarkingName', 'Balluff', get_iri_from_eclass('MarkingName')),
        ('MarkingAdditionalText', None, get_iri_from_eclass('MarkingAdditionalText'))
    ]

    # Use a temporary file path or replace with an existing file path
    temp_marking_file_path = Path(os.path.join(current_dir, 'logo', 'ManufacturerLogoBalluff.jpg'))
    if not os.path.exists(temp_marking_file_path):
        with open(temp_marking_file_path, 'wb') as f:
            f.write(b'This is a temporary marking file.')

    marking_file = ent_instance.create_File(
        file_store=file_store,
        file_path=temp_marking_file_path,
        aasx_file_path='/aasx/Logo/ManufacturerLogoBalluff.jpg',
        id_short='MarkingFile',
        mime_type='image/jpeg',
        category='PARAMETER'
    )

    markings_elements = create_elements(markings_elements)
    markings_elements.append(marking_file)
    markings_smc = ent_instance.create_SMC('Markings', markings_elements, 'PARAMETER', get_iri_from_eclass('Markings'))
    submodel.submodel_element.add(markings_smc)

    # Create SMC AssetSpecificProperties
    asset_specific_properties_smc = ent_instance.create_SMC('AssetSpecificProperties', [], 'PARAMETER', get_iri_from_eclass('AssetSpecificProperties'))

    # Create GuidelineSpecificProperties SMC
    guideline_specific_properties_elements = [
        ('GuidelineForConformityDeclaration', None, get_iri_from_eclass('GuidelineForConformityDeclaration'))
    ]
    guideline_specific_properties_smc = ent_instance.create_SMC('GuidelineSpecificProperties', create_elements(guideline_specific_properties_elements), 'PARAMETER', 'https://admin-shell.io/zvei/nameplate/1/0/Nameplate/AssetSpecificProperties/GuidelineSpecificProperties')
    asset_specific_properties_smc.value.add(guideline_specific_properties_smc)  # Use add method
    submodel.submodel_element.add(asset_specific_properties_smc)

    return obj_store, submodel

# Create the GeneralInformation submodel
def create_general_information_submodel(obj_store, file_store):
    submodel_elements = []
    id_short = 'GeneralInformation'
    semantic_id = 'https://admin-shell.io/sandbox/SG2/GeneralInformation/1/1n'
    kind = 'I'
    obj_store, submodel = ent_instance.create_SM_rand_iri(obj_store, id_short, 'GeneralInformation', submodel_elements, semantic_id, kind)

    # Use eClass to get IRI for GlobalTradeItemNumber
    global_trade_item_number_iri = get_iri_from_eclass('GlobalTradeItemNumber')

    properties = [
        ('ManufacturerName', 'Balluff GmbH', '0173-1#02-AAO677#002'),    
        ('ManufacturerProductDescription', None, '0173-1#02-AAU734#001'),
        ('ManufacturingProductNumber', None, '0173-1#02-AAO676#003'),
        ('ManufacturerOrderCode', None, '0173-1#02-AAW338#001'),
        ('GlobalTradeItemNumber', None, global_trade_item_number_iri)
    ]

    for id_short, value, iri in properties:
        prop_element = create_property(id_short, value, iri)
        submodel.submodel_element.add(prop_element)

    # Use a temporary file path or replace with an existing file path
    temp_logo_file_path = Path(os.path.join(current_dir, 'logo', 'ManufacturerLogoBalluff.jpg'))
    if not os.path.exists(temp_logo_file_path):
        with open(temp_logo_file_path, 'wb') as f:
            f.write(b'This is a temporary manufacturer logo.')

    temp_image_file_path = Path(os.path.join(current_dir, 'logo', 'ProductImage.png'))
    if not os.path.exists(temp_image_file_path):
        with open(temp_image_file_path, 'wb') as f:
            f.write(b'This is a temporary product image.')

    logo_file = ent_instance.create_File(
        file_store=file_store,
        file_path=temp_logo_file_path,
        aasx_file_path='/aasx/Logo/ManufacturerLogoBalluff.jpg',
        id_short='ManufacturerLogo',
        mime_type='image/jpeg',
        category='PARAMETER'
    )

    image_file = ent_instance.create_File(
        file_store=file_store,
        file_path=temp_image_file_path,
        aasx_file_path='/aasx/ProductImage/ProductImage.png',
        id_short='ProductImage',
        mime_type='image/png',
        category='PARAMETER'
    )

    submodel.submodel_element.add(logo_file)
    submodel.submodel_element.add(image_file)

    return obj_store, submodel

def create_product_classifications_submodel(obj_store):
    submodel_elements = []
    id_short = 'ProductClassifications'
    semantic_id = 'https://admin-shell.io/sandbox/SG2/ProductClassifications/1/1'
    kind = 'I'
    obj_store, submodel = ent_instance.create_SM_rand_iri(obj_store, id_short, 'ProductClassifications', submodel_elements, semantic_id, kind)

    classification_elements = [
        ('ProductClassificationSystem', 'eClass', get_iri_from_eclass('ProductClassificationSystem')),
        ('ClassificationSystemVersion', '11', get_iri_from_eclass('ClassificationSystemVersion')),
        ('ProductClassId', None, get_iri_from_eclass('ProductClassId'))
    ]

    def create_elements(elements):
        return [create_property(id_short, value, iri) for id_short, value, iri in elements]

    classification_smc = ent_instance.create_SMC('ProductClassificationItem', create_elements(classification_elements), 'PARAMETER', get_iri_from_eclass('ProductClassificationItem'))
    submodel.submodel_element.add(classification_smc)

    return obj_store, submodel

def create_further_information_submodel(obj_store):
    submodel_elements = []
    id_short = 'FurtherInformation'
    semantic_id = 'https://admin-shell.io/sandbox/SG2/FurtherInformation/1/1'
    kind = 'I'
    obj_store, submodel = ent_instance.create_SM_rand_iri(obj_store, id_short, 'FurtherInformation', submodel_elements, semantic_id, kind)

    additional_info = [
        ('TextStatement', None, get_iri_from_eclass('TextStatement')),
        ('ValidDate', None, get_iri_from_eclass('ValidDate'))
    ]

    for id_short, value, iri in additional_info:
        prop_element = create_property(id_short, value, iri)
        submodel.submodel_element.add(prop_element)

    return obj_store, submodel

def create_Capability_submodel(obj_store):
    submodel_elements = []
    id_short = 'Capability'
    semantic_id = get_iri_from_eclass('Capability')
    kind = 'I'
    obj_store, submodel = ent_instance.create_SM_rand_iri(obj_store, id_short, 'Capability', submodel_elements, semantic_id, kind)

    # Create a Capability
    id_short = 'Capability'
    category = 'PARAMETER'
    description = None
    semantic_id = get_iri_from_eclass('Capability')
    capability_element = ent_instance.create_Cap(id_short, category, description, semantic_id)

    # Add the Capability element to the submodel
    submodel.submodel_element.add(capability_element)

    return obj_store, submodel


def create_aasx_with_submodels(output_filename_aasx):
    # Create object and file stores
    obj_store = model.DictObjectStore()
    file_store = aasx.DictSupplementaryFileContainer()

    # Create asset information
    asset_name = 'Template'
    obj_store, asset_information = ent_instance.create_asset_information_rand_iri(obj_store, asset_name, 'I')

    # Create AAS
    id_short = 'Template'
    aas_name = 'Template'
    obj_store, id_aas, aas = ent_instance.create_aas_rand_iri(obj_store, id_short, aas_name, asset_information, None)

    # Create submodels
    obj_store, submodel_nameplate = create_nameplate_submodel(obj_store, file_store)
    obj_store, submodel_general_information = create_general_information_submodel(obj_store, file_store)
    obj_store, submodel_product_classifications = create_product_classifications_submodel(obj_store)
    obj_store, submodel_further_information = create_further_information_submodel(obj_store)
    
    # Create the Capability submodel
    obj_store, submodel_Capability = create_Capability_submodel(obj_store)

    # Add submodels to AAS
    aas.submodel.add(model.ModelReference.from_referable(submodel_nameplate))
    aas.submodel.add(model.ModelReference.from_referable(submodel_general_information))
    aas.submodel.add(model.ModelReference.from_referable(submodel_product_classifications))
    aas.submodel.add(model.ModelReference.from_referable(submodel_further_information))
    aas.submodel.add(model.ModelReference.from_referable(submodel_Capability))  # Add this line

    # Create object store
    object_store = ent_instance.create_obj_store(aas, asset_information, [submodel_nameplate, submodel_general_information, submodel_product_classifications, submodel_further_information, submodel_Capability])  # Include submodel_Capability

    # Write AASX file
    with AASXWriter(output_filename_aasx) as writer:
        writer.write_aas(
            aas_ids=[id_aas],
            object_store=object_store,
            file_store=file_store
        )

if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = Path(os.path.join(current_dir, 'output'))
    output_filename_aasx = output_dir / 'Template_balluff.aasx'
    create_aasx_with_submodels(output_filename_aasx)