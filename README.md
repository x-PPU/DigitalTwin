# xPPU Digital Twin
To implement and evaluate the proposed DT-architecture, we utilize the xPPU, a laboratory plant for the domain of production systems in automation engineering. In this work, Scenario 14 is applied, which involves the automated sorting of workpieces via a coordinated sequence of the stack, crane, and ramp modules. The DT for this scenario is implemented as a synchronized virtual mirror for real-time process monitoring.


## System Architecture
The comprehensive system architecture follows a modular design centered on the AAS as the primary semantic orchestrator. This architecture is operationalized through three integrated modules: first, the systematic creation of AAS instances to semantically normalize heterogeneous engineering artifacts and operational telemetry; second, the deployment of an AASX server coupled with a high-fidelity 3D visualization in Unity for immersive real-time monitoring; and third, the implementation of a tiered communication framework designed to ensure deterministic synchronization between the physical asset, its AAS representation within the server, and the virtual 3D counterpart. The overall architecture is illustrated below.

<img width="2066" height="1002" alt="System_architecture_of_the_digital_twin" src="https://github.com/user-attachments/assets/0e811307-4453-40d3-8362-53917b44d9bb" />

Click [here](/Detailed%20Introduction.pptx) to see the detailed introduction. 
For a quick overview of the methods and examples, see the [images](/Detailed%20Images).

## Live Demo
https://github.com/user-attachments/assets/2f8956ff-1f03-4d0b-8a62-20e0b19cea47




# How to Start
## Prerequisites

- Windows 11
- Python 3.8 and 3.12.7
- TwinCAT 3 environment (for physical device connection and pyads communication)
- Unity 6 or newer (for running and modifying the visualization scene)


## Introduction

AAS Creation (AAScreation/):

1. Uses the Basyx Python SDK to generate a standardized AAS model of the xPPU based on engineering and operational data files, producing an .aasx package.

TwinCAT Data Bridge (Workstation TwinCAT/):

1. Runs on an Workstation. It reads real-time data from a TwinCAT PLC via device notifications using the pyads library. Install the required Python library on the Workstation:
```bash
pip install pyads==1.3.0
```

2. Broadcasts the acquired data to network clients (e.g., PC, Unity) in real-time via WebSocket.

Data Processing & Server (PC unity and aasx server/):

1. Data Reception & Processing: Receives real-time data via WebSocket, performs necessary cleaning, transformation, or logic.

2. AASX Server Update: Pushes processed data to a running AASX server via its HTTP REST API, synchronizing the digital twin model state with the physical world.

Unity Visualization (within PC unity and aasx server/ or separate project)

1. The Unity client connects to the Data Bridge's WebSocket server.

2. Maps incoming real-time data to events in the virtual scene, driving object movement, state changes (color, display values), and 3D visual updates.

  **Note:** The WebSocket communication functionality is based on the [NativeWebSocket](https://github.com/endel/NativeWebSocket) library, which is already integrated into the [Unity project](/PC%20unity%20and%20aasx%20server/Simulation%20Unity/xPPU_Unity.7z)'s `Plugins/` folder. No additional installation is required.



## Installation & Running
Install Python Dependencies:
```bash
pip install -r requirements.txt
```

Install with conda (** special package **): ** [pythonocc-core](https://github.com/tpaviot/pythonocc-core) **
Refer to the following repository for installation instructions:  
```bash
conda create --name=pyoccenv python=3.10
conda activate pyoccenv
conda install -c conda-forge pythonocc-core=7.8.1
```

The installation follows the [Video Guide](https://analysissitus.org/forum/index.php?threads/pythonocc-getting-started-guide.19/#post-349).
At the time of installation, `pythonocc-core` only supported Python 3.8–3.9 and did not support Python 3.12. Therefore, Python 3.8 is included in the prerequisites.





## AASX Server Install
Please refer to [Eclipse AASX Server](https://github.com/eclipse-aaspe/server)  for different installation methods.

Docker Compose is recommended. Create a `docker-compose.yaml` file with the following content:
```bash
services:
  aasx-server:
    container_name: aasx-server
    image: docker.io/adminshellio/aasx-server-blazor-for-demo:v2024-05-08.alpha
    restart: unless-stopped
    ports:
      - 5001:5001
    environment:
      - Kestrel__Endpoints__Http__Url=http://*:5001
    volumes:
      - ./aasxs:/AasxServerBlazor/aasxs
    #command: --with-db --no-security --external-blazor http://localhost:5001
    command: --no-security --data-path /AasxServerBlazor/aasxs --external-blazor http://localhost:5001
```
Then, start the server with:
```bash
docker-compose up -d
```
The server UI and API will be available at http://localhost:5001.

Tip: Place the generated .aasx files in the local ./aasxs directory, and they will be automatically loaded by the server.





## Contact
Jiayang Li, Email: li.jiayang@myyahoo.com




