#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
The datasheet of Bernstein OT18RT-DPTP-0100-CL is not available online.
Create AAS from manual table (Bernstein OT18RT-DPTP-0100-CL) based on Page 50 of Bernstein.pdf

"""

import os
import re
from basyx.aas import model
from basyx.aas.adapter import aasx
from base.create_ent import ent
from base.eClass import MapEClass


class AasFromBernsteinManual:
    """Class for creating AAS from manual table data"""
    
    def __init__(self, rows, title, filename, mpn):
        self.rows = rows
        self.title = title
        self.filename = filename
        self.mpn = mpn
        
        self.ent_instance = ent()
        self.obj_store = model.DictObjectStore()
        self.file_store = aasx.DictSupplementaryFileContainer()
        self.eclass_instance = MapEClass()
        
        self._initialize_aas_structure()

    def _initialize_aas_structure(self):
        """Initialize basic AAS structure"""
        asset_name = self._replace_str(self.title)
        
        # Create asset information
        self.obj_store, self.asset_information = self.ent_instance.create_asset_information_rand_iri(
            self.obj_store, asset_name, 'I'
        )

        # Create AAS
        id_short = self._replace_str(self.title)
        self.obj_store, self.id_aas, self.aas = self.ent_instance.create_aas_rand_iri(
            self.obj_store, id_short, 'bernstein', self.asset_information, None
        )

        # Create TechnicalData submodel
        sm_semantic_id = f"https://technicaldata.com/ids/sm/{self._replace_str(self.mpn)}"
        self.obj_store, self.submodel = self.ent_instance.create_SM_rand_iri(
            self.obj_store, 'TechnicalData', 'TechnicalData', [], sm_semantic_id, 'I'
        )

        # Add PartNr property
        self._add_part_number_property()
        self.aas.submodel.add(model.ModelReference.from_referable(self.submodel))

    def _add_part_number_property(self):
        """Add part number property"""
        pn_prop = self.ent_instance.create_Prop(
            "PartNr", model.datatypes.String, str(self.mpn), 
            None, None, "https://example.com/semanticId/PartNr"
        )
        self.submodel.submodel_element.add(pn_prop)

    def _replace_str(self, string):
        """Clean string for ID generation"""
        if not string:
            return "unknown"
            
        replacements = {
            'ä': 'ae', 'Ä': 'Ae', 'ö': 'oe', 'Ö': 'Oe', 'ü': 'ue', 'Ü': 'Ue',
            '°C': 'degreeCelsius', 'Ω': 'ohm', 'µ': 'micro', '�': '',
            ' ': '_', '-': '_', '.': '_', '/': '_', '#': '_', '%': 'percentage', 
            '±': 'plus_minus', '+': '_', '[': '', ']': '', '(': '', ')': '', 
            ',': '', '&': 'and', '@': 'at', '!': '', ':': '_', ';': '_', 
            '"': '', "'": '', '~': '', '<': '', '>': '', '|': '_', '\\': '_', 
            '^': '_', '`': '', '=': '_'
        }
        
        for word, replacement in replacements.items():
            string = string.replace(word, replacement)
            
        string = re.sub(r'[^a-zA-Z0-9_]', '', string)
        return 'ID_' + string if not string[0].isalpha() else string

    def _generate_incremental_id_short(self, base_id_short, existing_ids):
        """Generate incremental ID short"""
        if base_id_short not in existing_ids:
            return base_id_short
            
        max_index = 0
        for existing_id in existing_ids:
            if existing_id.startswith(base_id_short + "_"):
                try:
                    idx = int(existing_id.split("_")[-1])
                    max_index = max(max_index, idx)
                except ValueError:
                    continue
                    
        return f"{base_id_short}_{max_index + 1}"

    def create_data_sheet(self):
        """Create datasheet file element"""
        try:
            if not os.path.isfile(self.filename):
                return None
                
            mime_type = "application/pdf"
            base_name = os.path.basename(self.filename)
            name_no_ext = os.path.splitext(base_name)[0]
            clean_name = self._replace_str(name_no_ext)
            file_path = f"/aasx/datasheet/{clean_name}.pdf"
            
            file_element = self.ent_instance.create_File(
                self.file_store, self.filename, file_path, 
                "DataSheet", mime_type, None, None
            )
            
            if file_element:
                self.submodel.submodel_element.add(file_element)
                return file_element
                
        except Exception as e:
            print(f"Error creating datasheet: {e}")
            
        return None

    def _add_property(self, id_short, value, feature):
        """Add property to submodel"""
        value_text = "" if value is None else str(value)
        _, iri_prop, _ = self.eclass_instance.get_IrdiPR_unit_descr(feature)
        
        if not iri_prop or iri_prop == "0000":
            iri_prop = f"https://example.com/semanticId/{self._replace_str(feature)}"
            
        prop = self.ent_instance.create_Prop(
            id_short, model.datatypes.String, value_text, 
            None, None, iri_prop
        )
        self.submodel.submodel_element.add(prop)

    def create_aas_from_manual_rows(self):
        """Create AAS from manual table data"""
        existing_ids = []
        
        for feature, value in self.rows:
            base_id = self._replace_str(feature)
            id_short = self._generate_incremental_id_short(base_id, existing_ids)
            existing_ids.append(id_short)
            
            self._add_property(id_short, value, feature)

        # Add datasheet file
        if self.create_data_sheet():
            print("File element created successfully")
        else:
            print("File element creation failed")

    def save_aas(self, output_file):
        """Save AAS to file"""
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            object_store = model.DictObjectStore([self.submodel, self.aas])
            
            with aasx.AASXWriter(output_file) as writer:
                writer.write_aas(
                    aas_ids=[self.id_aas],
                    object_store=object_store,
                    file_store=self.file_store
                )
                
            return True
            
        except Exception as e:
            print(f"Failed to save AASX file: {e}")
            return False


def main():
    """Main function"""
    # Configuration
    manufacturer = "Bernstein"
    mpn = "OT18RT-DPTP-0100-CL"
    type_name = "Diffuse Reflection Sensor"
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    title = f"{manufacturer} {mpn} {type_name}"
    output_file = os.path.join(base_dir, "output","Bernstein", f"{title}.aasx")
    pdf_file = os.path.join(base_dir, "Bernstein.pdf")
    
    # Manual table data
    table_rows = [
        ("Rated operating voltage", "10 - 36 VDC"),
        ("Rated operating current", "200 mA"),
        ("Switching frequency", "500 Hz"),
        ("Short circuit-protection", "Cyclic"),
        ("Function/operating voltage indicator", "LED"),
        ("Sensitivity adjustable", ""),
        ("Teach-in", ""),
        ("Timer function", ""),
        ("Diagnostic function", ""),
        ("Type of light", "IR 880 nm"),
        ("Ambient temperature (min/max)", "-20 °C / +70 °C"),
        ("Protection class IP", "IP67"),
        ("Enclosure material", "PBT, black"),
        ("Connection", "M12 x 1"),
    ]
    
    

    
    # Create and process AAS
    builder = AasFromBernsteinManual(table_rows, title, pdf_file, mpn)
    builder.create_aas_from_manual_rows()
    
    # Save results
    if builder.save_aas(output_file):
        print("AAS creation completed!")
    else:
        print("\nAAS creation failed!")


if __name__ == '__main__':
    main()