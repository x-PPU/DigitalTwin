#!/usr/bin/env python3.10.15
"""
This script extracts OPC Read and Write Item IDs from Simulink models and saves them to CSV files.

Process overview:
- Searches for Simulink (.slx) files in the "simulation_info_2_csv/model" directory and its subdirectories.
- Executes MATLAB scripts in each subdirectory (if available) to set up the environment.
- Loads each model and identifies OPC Read and Write blocks by their mask type.
- Extracts the Item IDs from these blocks.
- Saves the extracted Item IDs along with their block paths into separate CSV files for OPC Read and Write blocks.
- Utilizes MATLAB Engine API to interact with Simulink.
"""

import matlab.engine
import os
import glob
import pandas as pd

def extract_opc_item_ids():
    """
    Main function that processes Simulink models to extract OPC Read and Write Item IDs.
    """
    # Get the directory of the current script
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    # Define the directory where the Simulink model files are located
    model_dir = os.path.join(current_script_dir, "model")
    
    # Start MATLAB Engine to interact with MATLAB/Simulink
    eng = matlab.engine.start_matlab()

    # Retrieve all subdirectories within the model directory
    model_subdirs = [
        os.path.join(model_dir, d) 
        for d in os.listdir(model_dir) 
        if os.path.isdir(os.path.join(model_dir, d))
    ]

    # Process each subdirectory containing Simulink models
    for subdir in model_subdirs:
        # Use the subdirectory name as a base name for output files
        model_base_name = os.path.basename(subdir)
        # Find all .slx files in the current subdirectory
        slx_files = glob.glob(os.path.join(subdir, "*.slx"))

        # If no .slx files are found, skip this subdirectory
        if not slx_files:
            print(f"No .slx files found in {subdir}. Skipping.")
            continue

        # Process the first .slx file found in the subdirectory
        model_path = slx_files[0]
        model_name = os.path.splitext(os.path.basename(model_path))[0]
        # Define output CSV file paths for OPC Write and Read blocks
        output_write_csv_path = os.path.join(current_script_dir, "4.opcID", f"opc_write_item_ids_{model_base_name}.csv")
        output_read_csv_path = os.path.join(current_script_dir, "4.opcID", f"opc_read_item_ids_{model_base_name}.csv")
        
        print(f"Running model: {model_name} in folder: {model_base_name}")

        # Add the current subdirectory to MATLAB's search path
        eng.addpath(subdir, nargout=0)

        # Execute any MATLAB scripts (.m files) in the subdirectory to initialize variables, if available
        m_files = glob.glob(os.path.join(subdir, "*.m"))
        if m_files:
            for m_file in m_files:
                script_name = os.path.splitext(os.path.basename(m_file))[0]
                try:
                    eng.eval(script_name, nargout=0)
                    print(f"Executed MATLAB script: {script_name}.m")
                except Exception as e:
                    print(f"Error executing MATLAB script {script_name}.m: {e}")
        else:
            print(f"No MATLAB script found in {subdir}. Proceeding without initializing variables.")

        try:
            # Load the Simulink model in MATLAB
            eng.load_system(model_name, nargout=0)

            # Find OPC Read blocks by searching for blocks with the mask type 'OPC Read'
            opc_read_blocks = eng.find_system(model_name,
                                              'FollowLinks', 'on',
                                              'LookUnderMasks', 'all',
                                              'MaskType', 'OPC Read')
            # Find OPC Write blocks by searching for blocks with the mask type 'OPC Write'
            opc_write_blocks = eng.find_system(model_name,
                                               'FollowLinks', 'on',
                                               'LookUnderMasks', 'all',
                                               'MaskType', 'OPC Write')

            # If no OPC blocks are found, skip CSV generation for this model
            if len(opc_read_blocks) == 0 and len(opc_write_blocks) == 0:
                print(f"No OPC Read or Write blocks found in {model_name}. Skipping CSV generation.")
                continue

            # Process OPC Read blocks if they exist
            if opc_read_blocks:
                print(f"Found {len(opc_read_blocks)} OPC Read blocks in the model.")
                opc_read_item_ids_list = []
                # Extract the 'itemids' parameter from each OPC Read block
                for block in opc_read_blocks:
                    item_ids = eng.get_param(block, 'itemids')
                    # Process the string to extract individual item IDs (removing braces and splitting by semicolon)
                    item_ids = [s.strip() for s in item_ids.strip('{}').split(';')]
                    opc_read_item_ids_list.append({
                        'BlockPath': block,
                        'ItemIDs': item_ids
                    })

                # Flatten the data into a list of dictionaries for CSV export
                read_data = []
                for item in opc_read_item_ids_list:
                    block_path = item['BlockPath']
                    for item_id in item['ItemIDs']:
                        read_data.append({
                            'BlockPath': block_path,
                            'ItemID': item_id
                        })

                # Convert the data into a pandas DataFrame and save as CSV
                read_df = pd.DataFrame(read_data)
                read_df.to_csv(output_read_csv_path, index=False)
                print(f"OPC Read Item IDs saved to {output_read_csv_path}")

            # Process OPC Write blocks if they exist
            if opc_write_blocks:
                print(f"Found {len(opc_write_blocks)} OPC Write blocks in the model.")
                opc_write_item_ids_list = []
                # Extract the 'itemids' parameter from each OPC Write block
                for block in opc_write_blocks:
                    item_ids = eng.get_param(block, 'itemids')
                    # Process the string to extract individual item IDs
                    item_ids = [s.strip() for s in item_ids.strip('{}').split(';')]
                    opc_write_item_ids_list.append({
                        'BlockPath': block,
                        'ItemIDs': item_ids
                    })

                # Flatten the data into a list of dictionaries for CSV export
                write_data = []
                for item in opc_write_item_ids_list:
                    block_path = item['BlockPath']
                    for item_id in item['ItemIDs']:
                        write_data.append({
                            'BlockPath': block_path,
                            'ItemID': item_id
                        })

                # Convert the data into a pandas DataFrame and save as CSV
                write_df = pd.DataFrame(write_data)
                write_df.to_csv(output_write_csv_path, index=False)
                print(f"OPC Write Item IDs saved to {output_write_csv_path}")

        except Exception as e:
            print(f"Error extracting OPC Item IDs from {model_name}: {e}")
        
        finally:
            # Attempt to close the loaded Simulink model to free up resources
            try:
                eng.close_system(model_name, nargout=0)
            except:
                pass
            # Remove the subdirectory from MATLAB's search path
            eng.rmpath(subdir, nargout=0)

    # Quit the MATLAB engine after processing all models
    eng.quit()

if __name__ == "__main__":
    extract_opc_item_ids()
