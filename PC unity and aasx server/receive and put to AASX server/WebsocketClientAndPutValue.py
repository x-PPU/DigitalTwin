import asyncio
import websockets
import requests
import json
import time
import csv
import os

# WebSocket Server Info
WS_SERVER_IP = "192.168.82.3"  # WebSocket Server IP
WS_PORT = 8765
WS_URL = f"ws://{WS_SERVER_IP}:{WS_PORT}"

# Mapping from PLC variable names to readable names
VARIABLE_MAPPING = {
    'MAIN.m_container.m_stack.o_slidingCylinder.DI_Extended': 'stackslidingCylinderExtended',
    'MAIN.m_container.m_stack.o_slidingCylinder.DI_Retracted': 'stackslidingCylinderRetracted',
    'MAIN.m_container.m_stack.o_slidingCylinder.DO_Extend': 'stackslidingCylinderExtend',
    'MAIN.m_container.m_crane.o_MonostableCylinder.DI_Extended': 'craneMonostableCylinderExtended',
    'MAIN.m_container.m_crane.o_MonostableCylinder.DI_Retracted': 'craneMonostableCylinderRetracted',
    'MAIN.m_container.m_crane.o_MonostableCylinder.DO_Extend': 'craneMonostableCylinderExtend',
    'MAIN.m_container.m_crane.o_VacuumGripper.DI_TakenIn': 'craneVacuumGripperTakenIn',
    'MAIN.m_container.m_crane.m_PresenceSensorAtStack.DI_WPDetected': 'cranePresenceSensorAtStackWPDetected',
    'MAIN.m_container.m_crane.m_PresenceSensorAtConveyor.DI_WPDetected': 'cranePresenceSensorAtConveyorWPDetected',
    'MAIN.m_container.m_crane.m_PresenceSensorAtStamp.DI_WPDetected': 'cranePresenceSensorAtStampWPDetected',
    'MAIN.m_container.m_crane.Motor.DO_TurnClockwise': 'craneMotorTurnClockwise',
    'MAIN.m_container.m_crane.Motor.DO_TurnCounterclockwise': 'craneMotorTurnCounterclockwise',
    'MAIN.m_container.m_stamp.m_stampingCylinder.DI_Extended': 'stampstampingCylinderExtended',
    'MAIN.m_container.m_stamp.m_stampingCylinder.DO_Extend': 'stampstampingCylinderExtend',
    'MAIN.m_container.m_stamp.m_stampingCylinder.DI_Retracted': 'stampstampingCylinderRetracted',
    'MAIN.m_container.m_stamp.m_slidingCylinder.DI_Extended': 'stampslidingCylinderExtended',
    'MAIN.m_container.m_stamp.m_slidingCylinder.DI_Retracted': 'stampslidingCylinderRetracted',
    'MAIN.m_container.m_stamp.m_slidingCylinder.DO_Extend': 'stampslidingCylinderExtend',
    'MAIN.m_container.m_stamp.m_slidingCylinder.DO_Retract': 'stampslidingCylinderRetract',
    'MAIN.m_container.m_LSC.Motor.DO_TurnClockwise': 'LSCMotorTurnClockwise',
    'MAIN.m_container.m_LSC.m_rampPusherStart.DI_Retracted': 'LSCrampPusherStartRetracted',
    'MAIN.m_container.m_LSC.m_rampPusherMid.DI_Retracted': 'LSCrampPusherMidRetracted',
    'MAIN.m_container.m_LSC.m_rampPusherStart.DO_Extend': 'LSCrampPusherStartExtend',
    'MAIN.m_container.m_LSC.m_rampPusherMid.DO_Extend': 'LSCrampPusherMidExtend',
    'MAIN.m_container.m_LSC.m_Switch.DO_Extend': 'LSCSwitchExtend'
}

# Manually defined URLs for PUT requests
URLS = {
    "stackslidingCylinderExtended": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Stack.Sensors.stackslidingCylinderExtended",
    "stackslidingCylinderRetracted": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Stack.Sensors.stackslidingCylinderRetracted",
    "stackslidingCylinderExtend": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Stack.Actuators.stackslidingCylinderExtend",
    "craneMonostableCylinderRetracted": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Crane.Sensors.craneMonostableCylinderRetracted",
    "craneMonostableCylinderExtend": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Crane.Actuators.craneMonostableCylinderExtend",
    "craneMonostableCylinderExtended": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Crane.Sensors.craneMonostableCylinderExtended",
    "cranePresenceSensorAtStackWPDetected": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Crane.Sensors.cranePresenceSensorAtStackWPDetected",
    "cranePresenceSensorAtConveyorWPDetected": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Crane.Sensors.cranePresenceSensorAtConveyorWPDetected",
    "cranePresenceSensorAtStampWPDetected": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Crane.Sensors.cranePresenceSensorAtStampWPDetected",
    "craneMotorTurnClockwise": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Crane.Actuators.craneMotorTurnClockwise",
    "craneMotorTurnCounterclockwise": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Crane.Actuators.craneMotorTurnCounterclockwise",
    "craneVacuumGripperTakenIn": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Crane.Sensors.craneVacuumGripperTakenIn",
    "stampslidingCylinderRetracted": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Stamp.Sensors.stampslidingCylinderRetracted",
    "stampslidingCylinderExtended": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Stamp.Sensors.stampslidingCylinderExtended",
    "stampslidingCylinderRetract": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Stamp.Actuators.stampslidingCylinderRetract",
    "stampslidingCylinderExtend": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Stamp.Actuators.stampslidingCylinderExtend",
    "stampstampingCylinderRetracted": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Stamp.Sensors.stampstampingCylinderRetracted",
    "stampstampingCylinderExtended": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Stamp.Sensors.stampstampingCylinderExtended",
    "stampstampingCylinderExtend": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/Stamp.Actuators.stampstampingCylinderExtend",
    "LSCrampPusherStartRetracted": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/LSC.Sensors.LSCrampPusherStartRetracted",
    "LSCrampPusherMidRetracted": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/LSC.Sensors.LSCrampPusherMidRetracted",
    "LSCrampPusherStartExtend": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/LSC.Actuators.LSCrampPusherStartExtend",
    "LSCrampPusherMidExtend": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/LSC.Actuators.LSCrampPusherMidExtend",
    "LSCMotorTurnClockwise": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/LSC.Actuators.LSCMotorTurnClockwise",
    "LSCSwitchExtend": "http://localhost:5001/submodels/aHR0cHM6Ly9PcGVyYXRpb25hbF9EYXRhLmNvbS9pZHMvc20vMDAwMA/submodel-elements/LSC.Actuators.LSCSwitchExtend"
}

rows = []

def make_csv_filename():
    ts = time.strftime("%Y%m%d_%H%M%S")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, f"ws_put_log_{ts}.csv")

def save_csv(path: str):
    fieldnames = [
        "var_name",
        "value",
        "seq",
        "t0_ns",
        "t_receive_ns",
        "mapped_name",
        "t_req0_ns",
        "t_resp_ns",
        "http_status"
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            for k in fieldnames:
                row.setdefault(k, "")
            writer.writerow(row)
    print(f"[CSV SAVED] {len(rows)} rows -> {path}")

def do_put(url: str, payload: dict, timeout_s: float = 0.5):
    t_req0_ns = time.time_ns()
    try:
        response = requests.put(url, json=payload, timeout=timeout_s)
        t_resp_ns = time.time_ns()
        return t_req0_ns, t_resp_ns, response.status_code
    except Exception:
        return t_req0_ns, "", "EXCEPTION"

async def handle_message(websocket, message: str):
    try:
        data = json.loads(message)
    except Exception:
        return

    if data.get("type") != "plc_change":
        return

    # 1) if received a plc_change, record the receive timestamp immediately
    t_receive_ns = time.time_ns()

    # 2)  send back the same message with type "plc_change_return" for latency measurement 
    try:
        echo = dict(data)
        echo["type"] = "plc_change_return"
        await websocket.send(json.dumps(echo, separators=(",", ":")))
    except Exception:
        pass

    # 3) parse the message, do PUT request, and save all info in rows for later CSV output
    try:
        var_name = data["var"]
        value = bool(data["value"])
        seq = int(data["seq"])
        t0_ns = int(data["t0_ns"])
    except Exception:
        return

    mapped_name = VARIABLE_MAPPING.get(var_name, "")
    url = URLS.get(mapped_name, "")


    if not mapped_name or not url:
        # dont save csv, directly skip
        return
    payload_put = {
        "idShort": mapped_name,
        "valueType": "xs:boolean",
        "value": "true" if value else "false",
        "modelType": "Property"
    }

    t_req0_ns, t_resp_ns, http_status = do_put(url, payload_put, timeout_s=0.5)

    rows.append({
        "var_name": var_name,
        "value": value,
        "seq": seq,
        "t0_ns": t0_ns,
        "t_receive_ns": t_receive_ns,
        "mapped_name": mapped_name,
        "t_req0_ns": t_req0_ns,
        "t_resp_ns": t_resp_ns,
        "http_status": http_status
    })

async def receive_updates():
    print(f"Connecting to {WS_URL}")
    async with websockets.connect(WS_URL) as websocket:
        print("Connected.")
        async for message in websocket:
            await handle_message(websocket, message)

if __name__ == "__main__":
    output_csv = make_csv_filename()

    try:
        asyncio.run(receive_updates())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except websockets.exceptions.ConnectionClosed:
        print("\nWebSocket closed.")
    finally:
        save_csv(output_csv)