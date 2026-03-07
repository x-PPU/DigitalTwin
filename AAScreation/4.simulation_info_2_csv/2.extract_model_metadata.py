#!/usr/bin/env python3.10.15
"""
This script processes Simulink models in a specified directory, extracts metadata using MATLAB engine,
and saves the metadata to CSV files. It performs the following steps:
    
1. Locate .slx Simulink model files in subdirectories.
2. Execute any MATLAB (.m) scripts found in each subdirectory (to initialize model parameters).
3. Load each Simulink model and extract metadata such as creator, modification details, version, 
   solver settings, etc.
4. Save the extracted metadata into a CSV file within a results (metadata) directory.
   
Example MATLAB engine installation:
    cd "C:\Program Files\MATLAB\R2024b\extern\engines\python"
    python -m pip install matlabengine==24.2.1
"""

import matlab.engine
import csv
import os
import glob


def execute_matlab_scripts(subdir, eng):
    """
    Execute all MATLAB (.m) scripts found in the given subdirectory.
    
    :param subdir: Directory to search for MATLAB scripts.
    :param eng: MATLAB engine instance.
    """
    m_files = glob.glob(os.path.join(subdir, "*.m"))
    if m_files:
        for m_file in m_files:
            m_file_name = os.path.basename(m_file)
            script_name = os.path.splitext(m_file_name)[0]
            try:
                eng.eval(f"{script_name}", nargout=0)
                print(f"Executed MATLAB script: {m_file_name}")
            except Exception as e:
                print(f"Error executing MATLAB script {m_file_name}: {e}")
    else:
        print(f"No MATLAB script found in {subdir}. Running without initializing variables.")


def extract_metadata(model_base_name, eng):
    """
    Extract metadata parameters from a loaded Simulink model.
    
    :param model_base_name: Base name of the model (without extension).
    :param eng: MATLAB engine instance.
    :return: Dictionary containing metadata key-value pairs.
    """
    try:
        metadata = {
            "ModelName": model_base_name,
            "Creator": eng.get_param(model_base_name, 'Creator') or 'N/A',
            "LastModifiedBy": eng.get_param(model_base_name, 'ModifiedBy') or 'N/A',
            "CreatedOn": eng.get_param(model_base_name, 'Created') or 'N/A',
            "ModelVersion": eng.get_param(model_base_name, 'ModelVersion') or 'N/A',
            "Description": eng.get_param(model_base_name, 'Description') or 'N/A',
            "SolverType": eng.get_param(model_base_name, 'SolverType') or 'N/A',
            "SolverName": eng.get_param(model_base_name, 'Solver') or 'N/A',
            "FixedStepSize": eng.get_param(model_base_name, 'FixedStep') or 'N/A',
            "StopTime": eng.get_param(model_base_name, 'StopTime') or 'N/A',
        }
    except matlab.engine.MatlabExecutionError as e:
        print(f"Error extracting metadata from {model_base_name}: {e}")
        metadata = {
            "ModelName": model_base_name,
            "Creator": 'N/A',
            "LastModifiedBy": 'N/A',
            "CreatedOn": 'N/A',
            "ModelVersion": 'N/A',
            "Description": 'N/A',
            "SolverType": 'N/A',
            "SolverName": 'N/A',
            "FixedStepSize": 'N/A',
            "StopTime": 'N/A',
        }
    return metadata


def write_metadata_to_csv(csv_filename, metadata):
    """
    Write the metadata dictionary to a CSV file.
    
    :param csv_filename: Full path of the output CSV file.
    :param metadata: Dictionary containing metadata key-value pairs.
    """
    try:
        with open(csv_filename, mode='w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(["idShort", "Value"])
            for key, value in metadata.items():
                writer.writerow([key, value])
        print(f"Metadata for model saved to {csv_filename}")
    except Exception as e:
        print(f"Error writing CSV file {csv_filename}: {e}")


def process_model(model_path, subdir, current_script_dir, eng):
    """
    Process a single Simulink model: execute MATLAB scripts, load the model,
    extract metadata, update and close the model, and write metadata to CSV.
    
    :param model_path: Full path to the .slx model file.
    :param subdir: The directory containing the model.
    :param current_script_dir: Directory where the script is located (used for CSV output).
    :param eng: MATLAB engine instance.
    """
    model_name = os.path.basename(model_path)
    model_base_name = os.path.splitext(model_name)[0]  # e.g., Dynamik_3
    
    # Determine the CSV filename (output in a "metadata" folder)
    csv_dir = os.path.join(current_script_dir, "metadata")
    os.makedirs(csv_dir, exist_ok=True)
    csv_filename = os.path.join(csv_dir, f"metadata_{model_base_name}.csv")
    
    # Add the model's directory to the MATLAB path
    eng.addpath(subdir, nargout=0)
    
    # Execute any MATLAB scripts found in the subdirectory
    execute_matlab_scripts(subdir, eng)
    
    # Load the Simulink model system
    try:
        eng.load_system(model_path, nargout=0)
    except Exception as e:
        print(f"Error loading model {model_name}: {e}")
        eng.rmpath(subdir, nargout=0)
        return
    
    # Extract metadata using MATLAB get_param function
    metadata = extract_metadata(model_base_name, eng)
    
    # Update model to ensure parameters are current
    try:
        eng.set_param(model_base_name, 'SimulationCommand', 'update', nargout=0)
    except Exception as e:
        print(f"Error updating model {model_base_name}: {e}")
    
    # Close the loaded model
    try:
        eng.close_system(model_base_name, nargout=0)
    except Exception as e:
        print(f"Error closing model {model_base_name}: {e}")
    
    # Write the extracted metadata to a CSV file
    write_metadata_to_csv(csv_filename, metadata)
    
    # Remove the subdirectory from MATLAB path
    eng.rmpath(subdir, nargout=0)


def extract_model_metadata():
    """
    Main function to search for Simulink models, extract their metadata,
    and save the information to CSV files.
    """
    # Get the directory of the current script and the target "model" directory
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    model_dir = os.path.join(current_script_dir, "model")
    
    # Start the MATLAB engine
    eng = matlab.engine.start_matlab()
    
    # Get all subdirectories under the model directory
    model_subdirs = [
        os.path.join(model_dir, d) for d in os.listdir(model_dir)
        if os.path.isdir(os.path.join(model_dir, d))
    ]
    
    # Process each subdirectory for Simulink model files (.slx)
    for subdir in model_subdirs:
        slx_files = glob.glob(os.path.join(subdir, "*.slx"))
        if not slx_files:
            continue  # Skip subdirectories with no model files
        
        for model_path in slx_files:
            process_model(model_path, subdir, current_script_dir, eng)
    
    # Quit the MATLAB engine after processing all models
    eng.quit()


if __name__ == "__main__":
    extract_model_metadata()
