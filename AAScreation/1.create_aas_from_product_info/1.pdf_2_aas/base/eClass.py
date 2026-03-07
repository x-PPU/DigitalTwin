import os
import csv
import pandas as pd
import numpy as np
import enchant


class MapEClass():
    def __init__(self): 
        pass

    def extract_unit(self, sent):
        """
        Don't extract unit, just return original string as-is.
        Ensures that AAS value matches PDF table exactly.
        """
        return sent.strip(), None

    def get_classes(self):
        classes_ = ['Supplier', 'IdCC', 'Identifier', 'VersionNumber', 'VersionDate', 'RevisionNumber', 'CodedName',
                    'PreferredName', 'Definition', 'ISOLanguageCode', 'ISOCountryCode', 'Note', 'Remark', 'Level',
                    'MKSubclass', 'MKKeyword', 'IrdiCC']
        current_dir = os.path.dirname(os.path.abspath(__file__)) 
        file_path = os.path.join(current_dir, "eClass11_0_CC_en.csv") 
        file = open(file_path, encoding='utf-8')
        csvreader = csv.reader(file)
        next(csvreader)
        units = []
        for row in csvreader:
            row_con = ''
            for i in range(len(row)):
                if i != 0:
                    row_con += ',' + row[i]
                else:
                    row_con += row[i]
            row = [row_con]
            for r in row:
                cell = r.split(";")
                units.append(cell)
        file.close()
        class_list = pd.DataFrame(units, columns=classes_)
        return class_list

    def get_properties(self): 
        properties_class = ['Supplier', 'IdPR', 'Identifier', 'VersionNumber', 'VersionDate', 'RevisionNumber',
                            'PreferredName', 'ShortName', 'Definition', 'SourceOfDefinition', 'Note', 'Remark',
                            'PreferredSymbol', 'IrdiUN', 'ISOLanguageCode', 'ISOCountryCode', 'Category',
                            'AttributeType', 'DefinitionClass', 'DataType', 'IrdiPR', 'CurrencyAlphaCode']

        current_dir = os.path.dirname(os.path.abspath(__file__)) 
        file_path = os.path.join(current_dir, "eClass11_0_PR_en.csv") 
        file = open(file_path, encoding='utf-8') 
        csvreader = csv.reader(file)
        next(csvreader)
        properties = []
        for row in csvreader:
            row_con = ''
            for i in range(len(row)):
                if i != 0:
                    row_con += ',' + row[i]
                else:
                    row_con += row[i]
            row = [row_con]
            for r in row:
                cell = r.split(";")
                properties.append(cell)
        file.close()
        property_list = pd.DataFrame(properties, columns=properties_class)
        return property_list

    def get_IrdiCC_descr(self, class_name):
        # get IrdiCC for a class
        classes = self.get_classes()
        index_similar_name = []
        levenshtein_distance = []

        for ind in classes.index:
            # if class name is exactly in eClass
            if class_name.lower() == classes['PreferredName'][ind].lower():
                IrdiCC = classes['IrdiCC'][ind]
                descr = [str(classes['PreferredName'][ind]), str(classes['Definition'][ind])]
                return IrdiCC, descr

            # fuzzy match
            if class_name.lower() in classes['PreferredName'][ind].lower():
                index_similar_name.append(ind)

        for ind in index_similar_name:
            levenshtein_distance.append(enchant.utils.levenshtein(class_name, classes['PreferredName'][ind]))

        if levenshtein_distance:
            index_name_found = index_similar_name[np.argmin(levenshtein_distance)]
            IrdiCC = classes['IrdiCC'][index_name_found]
            descr = [str(classes['PreferredName'][index_name_found]), str(classes['Definition'][index_name_found])]
            return IrdiCC, descr
        else:
            return "0000", "No semantic ID is found, please add it manually."

    def get_IrdiPR_unit_descr(self, prop_name):
        """
        Get IRDI property ID and preferred unit from eClass based on property name.
        Used for semantic ID even if unit is not applied to the AAS value.
        """
        properties = self.get_properties()
        units = self.get_units()

        index_similar_name = []
        levenshtein_distance = []
        unit = ''
        descr = []

        for ind in properties.index:
            if prop_name.lower() == properties['PreferredName'][ind].lower():
                IrdiUN, IrdiPR = properties['IrdiUN'][ind], properties['IrdiPR'][ind]
                for i in units.index:
                    if IrdiUN == units['IrdiUN'][i]:
                        unit = units['PreferredName'][i]
                        descr = [str(properties['PreferredName'][i]), str(properties['Definition'][i]), unit]
                        return unit, IrdiPR, descr
            if prop_name.lower() in properties['PreferredName'][ind].lower():
                index_similar_name.append(ind)

        for ind in index_similar_name:
            levenshtein_distance.append(enchant.utils.levenshtein(prop_name, properties['PreferredName'][ind]))

        if levenshtein_distance:
            index_name_found = index_similar_name[np.argmin(levenshtein_distance)]
            IrdiUN, IrdiPR = properties['IrdiUN'][index_name_found], properties['IrdiPR'][index_name_found]
            for i in units.index:
                if IrdiUN == units['IrdiUN'][i]:
                    unit = units['PreferredName'][i]
            descr = [str(properties['PreferredName'][index_name_found]),
                     str(properties['Definition'][index_name_found]), unit]
            return unit, IrdiPR, descr
        else:
            return None, "0000", "No semantic ID is found, please add it manually."

    def get_units(self):
        unit_classes = ['PreferredName', 'ShortName', 'Definition', 'Source', 'Comment', 'SINotation', 'SIName',
                        'DINNotation', 'ECEName', 'ECECode', 'NISTName', 'IECClassification', 'IrdiUN',
                        'NameOfDedicatedQuantity']
        current_dir = os.path.dirname(os.path.abspath(__file__)) 
        file_path = os.path.join(current_dir, "eClass11_0_UN_en.csv") 
        file = open(file_path, encoding='utf-8')
        csvreader = csv.reader(file)
        next(csvreader)
        units = []
        for row in csvreader:
            row_con = ''
            for i in range(len(row)):
                if i != 0:
                    row_con += ',' + row[i]
                else:
                    row_con += row[i]
            row = [row_con]
            for r in row:
                cell = r.split(";")
                units.append(cell)
        file.close()
        unit_list = pd.DataFrame(units, columns=unit_classes)
        return unit_list
