#!/usr/bin/env python3.10.15
"""
This script extracts metadata and chart data from Simulink Stateflow models and exports it to CSV files.

Process overview:
- Iterates through subdirectories in the "model" folder to locate Simulink (.slx) files.
- Executes MATLAB scripts (if available) in each subdirectory to initialize the environment.
- Loads the Simulink model, updates it, and then extracts Stateflow chart data using MATLAB commands.
- Extracted data includes variable names, ports, data types, and scopes.
- Saves the extracted chart data into CSV files in the "3.chartdata" folder.
- Uses MATLAB Engine API to interact with Simulink and Stateflow.
"""

import matlab.engine
import csv
import os
import glob
import math

def extract_stateflow_data():
    """
    Main function that coordinates the extraction of Stateflow chart data from Simulink models.
    It navigates through subdirectories, processes each model, and writes extracted data to CSV files.
    """
    # Determine the directory of the current script
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    # Define the directory containing the Simulink models
    model_dir = os.path.join(current_script_dir, "model")
    
    # Start MATLAB engine for interacting with MATLAB/Simulink environment
    eng = matlab.engine.start_matlab()
    
    # Get all subdirectories under the model directory
    model_subdirs = [
        os.path.join(model_dir, d) 
        for d in os.listdir(model_dir) 
        if os.path.isdir(os.path.join(model_dir, d))
    ]
    
    # Process each subdirectory
    for subdir in model_subdirs:
        # Use the subdirectory name as the model base name
        model_base_name = os.path.basename(subdir)
        # Find all .slx files in the subdirectory
        slx_files = glob.glob(os.path.join(subdir, "*.slx"))
    
        if not slx_files:
            print(f"No .slx files found in {subdir}. Skipping.")
            continue  # Skip if there are no Simulink files
    
        # Process each Simulink file found in the subdirectory
        for model_path in slx_files:
            model_name = os.path.basename(model_path)
            # Define the CSV file path for the chart data output
            csv_filename = os.path.join(current_script_dir, "3.chartdata", f"chartdata_{model_base_name}.csv")
            
            print(f"Processing model: {model_name} in folder: {model_base_name}")
    
            # Add the current subdirectory to the MATLAB path
            eng.addpath(subdir, nargout=0)
    
            # Look for MATLAB (.m) scripts in the subdirectory and execute them
            m_files = glob.glob(os.path.join(subdir, "*.m"))
            if m_files:
                for m_file in m_files:
                    m_file_name = os.path.basename(m_file)
                    script_name = os.path.splitext(m_file_name)[0]
                    try:
                        # Execute the MATLAB script to initialize any necessary variables or settings
                        eng.eval(f"{script_name}", nargout=0)
                        print(f"Executed MATLAB script: {m_file_name}")
                    except Exception as e:
                        print(f"Error executing MATLAB script {m_file_name}: {e}")
            else:
                print(f"No MATLAB script found in {subdir}. Proceeding without initializing variables.")
    
            # Load the Simulink model into MATLAB
            try:
                eng.load_system(model_path)
            except Exception as e:
                print(f"Error loading model {model_name}: {e}")
                continue  # Skip to the next file if loading fails
    
            # Update the model to ensure that all parameters and states are current
            try:
                eng.set_param(model_base_name, 'SimulationCommand', 'update', nargout=0)
            except Exception as e:
                print(f"Error updating model {model_base_name}: {e}")
    
            # Define a MATLAB script (as a multiline string) to extract Stateflow chart data.
            # The script collects data info for each chart variable (Name, Port, DataType, Scope)
            matlab_script = f'''
            data_info = struct('Name',{{}}, 'Port',{{}}, 'DataType',{{}}, 'Scope',{{}});
            rt = sfroot;
            m = rt.find('-isa', 'Simulink.BlockDiagram', 'Name', '{model_base_name}');
            charts = m.find('-isa', 'Stateflow.Chart');
            idx = 1;
            for c = 1:length(charts)
                chart = charts(c);
                data_elements = chart.find('-isa', 'Stateflow.Data');
                for d = 1:length(data_elements)
                    data = data_elements(d);
                    data_info(idx).Name = data.Name;
                    data_info(idx).Port = data.Port;
                    data_info(idx).DataType = data.DataType;
                    data_info(idx).Scope = data.Scope;
                    idx = idx + 1;
                end
            end
            data_info_struct = struct();
            data_info_struct.Name = {{data_info.Name}};
            data_info_struct.Port = [data_info.Port];
            data_info_struct.DataType = {{data_info.DataType}};
            data_info_struct.Scope = {{data_info.Scope}};
            assignin('base', 'data_info_struct', data_info_struct);
            '''
    
            try:
                # Execute the MATLAB script to populate the workspace variable 'data_info_struct'
                eng.eval(matlab_script, nargout=0)
                # Retrieve the extracted data from the MATLAB workspace
                data_info_struct = eng.workspace['data_info_struct']
    
                # Process the retrieved data: convert MATLAB arrays to Python lists.
                names = [str(n) for n in data_info_struct['Name']]
                ports = [int(p) if not math.isnan(p) else 'N/A' for p in data_info_struct['Port'][0]]
                dataTypes = [str(dt) for dt in data_info_struct['DataType']]
                scopes = [str(s) for s in data_info_struct['Scope']]
    
                # Combine the data into a list of dictionaries for each data entry
                chart_data_info = []
                for name, port, dataType, scope in zip(names, ports, dataTypes, scopes):
                    chart_data_info.append({
                        'Name': name,
                        'Port': port,
                        'DataType': dataType,
                        'Scope': scope
                    })
    
                # Write the chart data into a CSV file
                with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    # Write CSV header
                    writer.writerow(["Name", "Port", "DataType", "Scope"])
                    # Write each data row
                    for data_info in chart_data_info:
                        writer.writerow([data_info['Name'], data_info['Port'], data_info['DataType'], data_info['Scope']])
    
            except Exception as e:
                print(f"Error extracting Stateflow data from {model_name}: {e}")
    
            finally:
                # Close the Simulink model to free resources
                try:
                    eng.close_system(model_base_name, nargout=0)
                except Exception as e:
                    print(f"Error closing model {model_base_name}: {e}")
    
            # Remove the subdirectory from MATLAB's search path
            eng.rmpath(subdir, nargout=0)
    
    # Terminate the MATLAB engine session after processing all models
    eng.quit()


if __name__ == "__main__":
    extract_stateflow_data()
