#!/usr/bin/env python3.10.15
"""
This script updates a template CSV file by inserting data from various source files into specific locations.

Process overview:
- Reads the base template from “1.template/Template_modify.csv”.
- Finds metadata, chart data, and OPC item ID files in their respective directories.
- For each model, it:
  - Inserts 'ModelFileInfo' data from metadata into the appropriate location in the template.
  - Adds 'Solver' data from metadata into the template.
  - Updates simulation time ('SimTime') in the template.
  - Inserts state data ('Input' and 'Output') from chart data.
  - Integrates OPC Read and Write item IDs from their respective files into the template.
- Saves the updated template as a new CSV file in the '5.update' directory.
"""

import pandas as pd
import os
import glob

def insert_metadata(new_template_df, metadata_file):
    """
    Inserts metadata from the metadata_file into the template DataFrame.
    
    This function processes two sections:
      - ModelFileInfo: Data from the start of the metadata file until (but not including) 'SolverType'.
      - Solver: Data from 'SolverType' to 'FixedStepSize'.
    
    It also updates the simulation time ('SimTime') using the 'StopTime' value.
    
    :param new_template_df: The template DataFrame to be updated.
    :param metadata_file: The metadata CSV file path.
    :return: Updated template DataFrame.
    """
    model_metadata_df = pd.read_csv(metadata_file, dtype=str)
    
    # --- Process ModelFileInfo section ---
    # Find the index of the row where 'idShort' equals 'SolverType'
    solver_type_indices = model_metadata_df.index[model_metadata_df['idShort'] == 'SolverType'].tolist()
    if solver_type_indices:
        solver_type_index = solver_type_indices[0]
    else:
        print(f"Warning: 'SolverType' not found in {metadata_file}.")
        solver_type_index = len(model_metadata_df)
    
    # All rows before 'SolverType' are considered ModelFileInfo
    model_file_info_rows = model_metadata_df.iloc[0:solver_type_index].copy()
    # Set typeName to 'Property' for these rows
    model_file_info_rows['typeName'] = 'Property'
    # Ensure missing columns exist and rename 'Value' to 'value'
    for col in ['valueType', 'category', 'descriptionEN', 'descriptionDE', 'semanticId']:
        if col not in model_file_info_rows.columns:
            model_file_info_rows[col] = ''
    model_file_info_rows.rename(columns={'Value': 'value'}, inplace=True)
    model_file_info_rows = model_file_info_rows[['typeName', 'idShort', 'value', 'valueType', 'category', 'descriptionEN', 'descriptionDE', 'semanticId']]
    
    # Find insertion location for ModelFileInfo in the template
    mfi_indices = new_template_df.index[new_template_df['idShort'] == 'ModelFileInfo'].tolist()
    if not mfi_indices:
        print("Error: 'ModelFileInfo' not found in template.")
        return new_template_df
    mfi_index = mfi_indices[0]
    # Find the corresponding end marker after ModelFileInfo
    end_mfi_indices = new_template_df.index[(new_template_df['typeName'] == 'End-SubmodelElementCollection') & (new_template_df.index > mfi_index)].tolist()
    if not end_mfi_indices:
        print("Error: 'End-SubmodelElementCollection' after 'ModelFileInfo' not found in template.")
        return new_template_df
    end_mfi_index = end_mfi_indices[0]
    # Insert the ModelFileInfo rows between the marker and the next section
    before_mfi = new_template_df.iloc[:mfi_index+1]
    after_mfi = new_template_df.iloc[end_mfi_index:]
    new_template_df = pd.concat([before_mfi, model_file_info_rows, after_mfi], ignore_index=True)
    
    # --- Process Solver section ---
    # Determine the range for solver information: from 'SolverType' to 'FixedStepSize'
    fixed_step_size_indices = model_metadata_df.index[model_metadata_df['idShort'] == 'FixedStepSize'].tolist()
    if fixed_step_size_indices:
        fixed_step_size_index = fixed_step_size_indices[0]
    else:
        print(f"Warning: 'FixedStepSize' not found in {metadata_file}.")
        fixed_step_size_index = len(model_metadata_df) - 1

    solver_rows = model_metadata_df.iloc[solver_type_index:fixed_step_size_index+1].copy()
    solver_rows['typeName'] = 'Property'
    for col in ['valueType', 'category', 'descriptionEN', 'descriptionDE', 'semanticId']:
        if col not in solver_rows.columns:
            solver_rows[col] = ''
    solver_rows.rename(columns={'Value': 'value'}, inplace=True)
    solver_rows = solver_rows[['typeName', 'idShort', 'value', 'valueType', 'category', 'descriptionEN', 'descriptionDE', 'semanticId']]
    
    solver_indices = new_template_df.index[new_template_df['idShort'] == 'Solver'].tolist()
    if not solver_indices:
        print("Error: 'Solver' not found in template.")
        return new_template_df
    solver_index = solver_indices[0]
    end_solver_indices = new_template_df.index[(new_template_df['typeName'] == 'End-SubmodelElementCollection') & (new_template_df.index > solver_index)].tolist()
    if not end_solver_indices:
        print("Error: 'End-SubmodelElementCollection' after 'Solver' not found in template.")
        return new_template_df
    end_solver_index = end_solver_indices[0]
    
    before_solver = new_template_df.iloc[:solver_index+1]
    after_solver = new_template_df.iloc[end_solver_index:]
    new_template_df = pd.concat([before_solver, solver_rows, after_solver], ignore_index=True)
    
    # --- Update Simulation Time ---
    stop_time_row = model_metadata_df[model_metadata_df['idShort'] == 'StopTime']
    if not stop_time_row.empty:
        stop_time_value = stop_time_row.iloc[0]['Value']
        sim_time_indices = new_template_df.index[new_template_df['idShort'] == 'SimTime'].tolist()
        if sim_time_indices:
            sim_time_index = sim_time_indices[0]
            new_template_df.at[sim_time_index, 'value'] = stop_time_value
        else:
            print("Error: 'SimTime' not found in template.")
    else:
        print(f"Warning: 'StopTime' not found in {metadata_file}.")

    return new_template_df

def insert_chartdata(new_template_df, chartdata_file):
    """
    Inserts state (chart) data from the chartdata_file into the template DataFrame.
    
    For each scope type ('Input' and 'Output'), this function creates new rows from the chart data.
    The 'Input' data is inserted at the location of the 'Input' marker and 'Output' data is inserted at the 'results' marker.
    
    :param new_template_df: The template DataFrame to update.
    :param chartdata_file: The chart data CSV file path.
    :return: Updated template DataFrame.
    """
    stateflow_data_df = pd.read_csv(chartdata_file, dtype=str)
    
    for scope_type in ['Input', 'Output']:
        scoped_data_df = stateflow_data_df[stateflow_data_df['Scope'] == scope_type]
        if scoped_data_df.empty:
            print(f"No '{scope_type}' data found in chart data for the model.")
            continue

        new_rows = []
        # Create a row for each entry in the scoped data
        for _, row in scoped_data_df.iterrows():
            new_row = {
                'typeName': 'Property',
                'idShort': row['Name'],  
                'value': '',  
                'valueType': row['DataType'], 
                'category': '',
                'descriptionEN': f"{row['Scope']}{row['Port']}", 
                'descriptionDE': '',
                'semanticId': ''
            }
            new_rows.append(new_row)

        insert_df = pd.DataFrame(new_rows)
        # Ensure the new DataFrame follows the same column order as the template
        insert_df = insert_df[new_template_df.columns]

        # Decide the target insertion point based on the scope type
        if scope_type == 'Input':
            target_idShort = 'Input'
        elif scope_type == 'Output':
            target_idShort = 'results'
        else:
            continue 

        target_indices = new_template_df.index[new_template_df['idShort'] == target_idShort].tolist()
        if not target_indices:
            print(f"Error: '{target_idShort}' not found in template.")
            continue
        target_index = target_indices[0]
        # Find the end marker after the target insertion point
        end_target_indices = new_template_df.index[
            (new_template_df['typeName'] == 'End-SubmodelElementCollection') & (new_template_df.index > target_index)
        ].tolist()
        if not end_target_indices:
            print(f"Error: 'End-SubmodelElementCollection' after '{target_idShort}' not found in template.")
            continue
        end_target_index = end_target_indices[0]

        before_target = new_template_df.iloc[:target_index+1]
        after_target = new_template_df.iloc[end_target_index:]
        new_template_df = pd.concat([before_target, insert_df, after_target], ignore_index=True)
    
    return new_template_df

def insert_opc_data(new_template_df, opc_file, target_marker):
    """
    Inserts OPC item IDs into the template DataFrame.
    
    This function reads an OPC CSV file (either for OPC Read or OPC Write), creates new rows for each block
    and its item IDs, and inserts them at the specified target marker ('Input' for OPC Read or 'results' for OPC Write).
    
    :param new_template_df: The template DataFrame to update.
    :param opc_file: The CSV file path for OPC data.
    :param target_marker: The idShort marker indicating where to insert the OPC data.
    :return: Updated template DataFrame.
    """
    opc_df = pd.read_csv(opc_file, dtype=str)
    opc_new_rows = []

    # Process each row in the OPC CSV file
    for _, row in opc_df.iterrows():
        block_path = row['BlockPath']
        item_id = row['ItemID']
        # Extract a short name from the block path (using the last segment)
        idShort = block_path.split('/')[-1]
  
        # Create a collection row for the block
        opc_new_rows.append({
            'typeName': 'SubmodelElementCollection',
            'idShort': idShort,
            'value': '',
            'valueType': '',
            'category': '',
            'descriptionEN': '',
            'descriptionDE': '',
            'semanticId': ''
        })
        # Split item IDs if they are comma-separated and create a row for each item
        item_ids = item_id.split(',')
        for item in item_ids:
            item = item.strip()
            opc_new_rows.append({
                'typeName': 'Property',
                'idShort': item,
                'value': '',
                'valueType': '',
                'category': '',
                'descriptionEN': '',
                'descriptionDE': '',
                'semanticId': ''
            })
        # Append an end marker row after each block's items
        opc_new_rows.append({
            'typeName': 'End-SubmodelElementCollection',
            'idShort': '',
            'value': '',
            'valueType': '',
            'category': '',
            'descriptionEN': '',
            'descriptionDE': '',
            'semanticId': ''
        })
    
    # Create a DataFrame from the new rows and align its columns with the template
    opc_insert_df = pd.DataFrame(opc_new_rows)
    opc_insert_df = opc_insert_df[new_template_df.columns]

    # Find target insertion location in the template
    target_indices = new_template_df.index[new_template_df['idShort'] == target_marker].tolist()
    if not target_indices:
        print(f"Error: '{target_marker}' not found in template.")
        return new_template_df
    target_index = target_indices[0]
    end_target_indices = new_template_df.index[
        (new_template_df['typeName'] == 'End-SubmodelElementCollection') & (new_template_df.index > target_index)
    ].tolist()
    if not end_target_indices:
        print(f"Error: 'End-SubmodelElementCollection' after '{target_marker}' not found in template.")
        return new_template_df
    end_target_index = end_target_indices[0]

    before_target = new_template_df.iloc[:target_index+1]
    after_target = new_template_df.iloc[end_target_index:]
    new_template_df = pd.concat([before_target, opc_insert_df, after_target], ignore_index=True)

    return new_template_df

def fill_template():
    """
    Main function that updates the template CSV file by inserting data from metadata, chart data,
    and OPC item ID files into their designated sections, then saves the updated template.
    """
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    template_csv_path = os.path.join(current_script_dir, '1.template', 'Template_modify.csv')
    
    # Find available metadata and chart data files (by model)
    metadata_files = glob.glob(os.path.join(current_script_dir, '2.metadata', 'metadata_*.csv'))
    chartdata_files = glob.glob(os.path.join(current_script_dir, '3.chartdata', 'chartdata_*.csv'))

    metadata_models = set(os.path.basename(f)[len('metadata_'):-len('.csv')] for f in metadata_files)
    chartdata_models = set(os.path.basename(f)[len('chartdata_'):-len('.csv')] for f in chartdata_files)
    all_models = metadata_models.union(chartdata_models)

    # Process each model found in the metadata or chart data directories
    for model_base_name in all_models:
        metadata_file = os.path.join(current_script_dir, '2.metadata', f'metadata_{model_base_name}.csv')
        chartdata_file = os.path.join(current_script_dir, '3.chartdata', f'chartdata_{model_base_name}.csv')
        opc_write_file = os.path.join(current_script_dir, '4.opcID', f'opc_write_item_ids_{model_base_name}.csv')
        opc_read_file = os.path.join(current_script_dir, '4.opcID', f'opc_read_item_ids_{model_base_name}.csv')
        output_csv_path = os.path.join(current_script_dir, '5.update', f'{model_base_name}.csv')

        # Read the base template CSV and make a working copy
        template_df = pd.read_csv(template_csv_path, dtype=str)
        new_template_df = template_df.copy()

        # Insert metadata if available
        if os.path.exists(metadata_file):
            new_template_df = insert_metadata(new_template_df, metadata_file)
        else:
            print(f"Metadata file not found for model {model_base_name}. Skipping metadata processing.")

        # Insert chart data if available
        if os.path.exists(chartdata_file):
            new_template_df = insert_chartdata(new_template_df, chartdata_file)
        else:
            print(f"Chart data file not found for model {model_base_name}. Skipping chart data processing.")

        # Insert OPC Read data if available (target marker: 'Input')
        if os.path.exists(opc_read_file):
            new_template_df = insert_opc_data(new_template_df, opc_read_file, target_marker='Input')
        else:
            print(f"OPC Read Item IDs file not found for model {model_base_name}. Skipping OPC Read processing.")

        # Insert OPC Write data if available (target marker: 'results')
        if os.path.exists(opc_write_file):
            new_template_df = insert_opc_data(new_template_df, opc_write_file, target_marker='results')
        else:
            print(f"OPC Write Item IDs file not found for model {model_base_name}. Skipping OPC Write processing.")

        # Save the updated template to the output directory
        os.makedirs(os.path.join(current_script_dir, '5.update'), exist_ok=True)
        new_template_df.to_csv(output_csv_path, index=False)
        print(f"Updated template for model {model_base_name} saved to {output_csv_path}")

if __name__ == '__main__':
    fill_template()
