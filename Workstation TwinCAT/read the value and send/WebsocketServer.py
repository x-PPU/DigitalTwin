import pyads
import asyncio
import websockets
import time
import json
import csv
import os
import threading
from ctypes import sizeof


# TwinCAT PLC AMS ID and port
PLC_AMS_ID = '192.168.82.13.1.1'
PLC_PORT = 851

# WebSocket configuration
WS_HOST = "192.168.82.3"  # IPC / PC IP
WS_PORT = 8765

# List of PLC variables (current code subscribes as BOOL)
var_list = [
    'MAIN.m_container.m_crane.m_PresenceSensorAtConveyor.DI_WPDetected',
    'MAIN.m_container.m_crane.m_PresenceSensorAtStack.DI_WPDetected',
    'MAIN.m_container.m_crane.m_PresenceSensorAtStamp.DI_WPDetected',
    'MAIN.m_container.m_crane.Motor.AI_Position',
    'MAIN.m_container.m_crane.Motor.AI_Speed',
    'MAIN.m_container.m_crane.Motor.DO_TurnClockwise',
    'MAIN.m_container.m_crane.Motor.DO_TurnCounterclockwise',
    'MAIN.m_container.m_crane.o_MonostableCylinder.AI_FlowPressure',
    'MAIN.m_container.m_crane.o_MonostableCylinder.AI_PositionTransmitter',
    'MAIN.m_container.m_crane.o_MonostableCylinder.AI_PressureSensor',
    'MAIN.m_container.m_crane.o_MonostableCylinder.DI_BoundaryFlowPressure',
    'MAIN.m_container.m_crane.o_MonostableCylinder.DI_BoundaryPressure',
    'MAIN.m_container.m_crane.o_MonostableCylinder.DI_Extended',
    'MAIN.m_container.m_crane.o_MonostableCylinder.DI_Retracted',
    'MAIN.m_container.m_crane.o_MonostableCylinder.DO_Extend',
    'MAIN.m_container.m_crane.o_VacuumGripper.DI_TakenIn',
    'MAIN.m_container.m_crane.o_VacuumGripper.DO_VacuumOn',
    'MAIN.m_container.m_crane.o_VacuumGripper.VacuumHit',
    'MAIN.m_container.m_LSC.m_inductiveSensorMid.DI_WPMetallic',
    'MAIN.m_container.m_LSC.m_inductiveSensorStart.DI_WPMetallic',
    'MAIN.m_container.m_LSC.m_opticalSensorEnd.DI_WPLight',
    'MAIN.m_container.m_LSC.m_opticalSensorMid.DI_WPLight',
    'MAIN.m_container.m_LSC.m_opticalSensorStart.DI_WPLight',
    'MAIN.m_container.m_LSC.m_presenceSensorStart.DI_WPDetected',
    'MAIN.m_container.m_LSC.m_rampEnd.m_presenceSensorRampFull.DI_WPDetected',
    'MAIN.m_container.m_LSC.m_rampMiddle.m_presenceSensorRampFull.DI_WPDetected',
    'MAIN.m_container.m_LSC.m_rampPusherMid.AI_FlowPressure',
    'MAIN.m_container.m_LSC.m_rampPusherMid.AI_PositionTransmitter',
    'MAIN.m_container.m_LSC.m_rampPusherMid.AI_PressureSensor',
    'MAIN.m_container.m_LSC.m_rampPusherMid.DI_BoundaryFlowPressure',
    'MAIN.m_container.m_LSC.m_rampPusherMid.DI_BoundaryPressure',
    'MAIN.m_container.m_LSC.m_rampPusherMid.DI_Extended',
    'MAIN.m_container.m_LSC.m_rampPusherMid.DI_Retracted',
    'MAIN.m_container.m_LSC.m_rampPusherMid.DO_Extend',
    'MAIN.m_container.m_LSC.m_rampPusherStart.AI_FlowPressure',
    'MAIN.m_container.m_LSC.m_rampPusherStart.AI_PositionTransmitter',
    'MAIN.m_container.m_LSC.m_rampPusherStart.AI_PressureSensor',
    'MAIN.m_container.m_LSC.m_rampPusherStart.DI_BoundaryFlowPressure',
    'MAIN.m_container.m_LSC.m_rampPusherStart.DI_BoundaryPressure',
    'MAIN.m_container.m_LSC.m_rampPusherStart.DI_Extended',
    'MAIN.m_container.m_LSC.m_rampPusherStart.DI_Retracted',
    'MAIN.m_container.m_LSC.m_rampPusherStart.DO_Extend',
    'MAIN.m_container.m_LSC.m_rampStart.m_presenceSensorRampFull.DI_WPDetected',
    'MAIN.m_container.m_LSC.m_Switch.DI_BoundaryPressure',
    'MAIN.m_container.m_LSC.m_Switch.DI_Extended',
    'MAIN.m_container.m_LSC.m_Switch.DI_Retracted',
    'MAIN.m_container.m_LSC.m_Switch.DO_Extend',
    'MAIN.m_container.m_LSC.Motor.AI_Position',
    'MAIN.m_container.m_LSC.Motor.AI_Speed',
    'MAIN.m_container.m_LSC.Motor.DO_TurnClockwise',
    'MAIN.m_container.m_LSC.Motor.DO_TurnCounterclockwise',
    'MAIN.m_container.m_PAC.m_PresencesensorEnd.DI_WPDetected',
    'MAIN.m_container.m_PAC.m_PresencesensorStart.DI_WPDetected',
    'MAIN.m_container.m_PAC.m_Switch.DI_BoundaryPressure',
    'MAIN.m_container.m_PAC.m_Switch.DI_Extended',
    'MAIN.m_container.m_PAC.m_Switch.DI_Retracted',
    'MAIN.m_container.m_PAC.m_Switch.DO_Extend',
    'MAIN.m_container.m_PAC.Motor.AI_Position',
    'MAIN.m_container.m_PAC.Motor.AI_Speed',
    'MAIN.m_container.m_PAC.Motor.DO_TurnClockwise',
    'MAIN.m_container.m_PAC.Motor.DO_TurnCounterclockwise',
    'MAIN.m_container.m_PicAlpha.m_PresenceSensorPosition1.DI_WPDetected',
    'MAIN.m_container.m_PicAlpha.m_PresenceSensorPosition2.DI_WPDetected',
    'MAIN.m_container.m_PicAlpha.m_PresenceSensorPosition3.DI_WPDetected',
    'MAIN.m_container.m_PicAlpha.m_PresenceSensorPosition4.DI_WPDetected',
    'MAIN.m_container.m_PicAlpha.Motor.AI_Position',
    'MAIN.m_container.m_PicAlpha.Motor.AI_Speed',
    'MAIN.m_container.m_PicAlpha.Motor.DO_TurnClockwise',
    'MAIN.m_container.m_PicAlpha.Motor.DO_TurnCounterclockwise',
    'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.AI_FlowPressure',
    'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.AI_PositionTransmitter',
    'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.AI_PressureSensor',
    'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.DI_BoundaryFlowPressure',
    'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.DI_BoundaryPressure',
    'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.DI_Extended',
    'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.DI_Retracted',
    'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.DO_Extend',
    'MAIN.m_container.m_PicAlpha.o_VacuumGripper.DI_TakenIn',
    'MAIN.m_container.m_PicAlpha.o_VacuumGripper.DO_VacuumOn',
    'MAIN.m_container.m_PicAlpha.o_VacuumGripper.VacuumHit',
    'MAIN.m_container.m_RFC.m_PresencesensorEnd.DI_WPDetected',
    'MAIN.m_container.m_RFC.m_PresencesensorStart.DI_WPDetected',
    'MAIN.m_container.m_RFC.m_Switch.DI_BoundaryPressure',
    'MAIN.m_container.m_RFC.m_Switch.DI_Extended',
    'MAIN.m_container.m_RFC.m_Switch.DI_Retracted',
    'MAIN.m_container.m_RFC.m_Switch.DO_Extend',
    'MAIN.m_container.m_RFC.Motor.AI_Position',
    'MAIN.m_container.m_RFC.Motor.AI_Speed',
    'MAIN.m_container.m_RFC.Motor.DO_TurnClockwise',
    'MAIN.m_container.m_RFC.Motor.DO_TurnCounterclockwise',
    'MAIN.m_container.m_SSC.m_Inductivesensor.DI_WPMetallic',
    'MAIN.m_container.m_SSC.m_Opticalsensor.DI_WPLight',
    'MAIN.m_container.m_SSC.m_PresencesensorEnd.DI_WPDetected',
    'MAIN.m_container.m_SSC.m_PresencesensorStart.DI_WPDetected',
    'MAIN.m_container.m_SSC.m_Ramp.m_presenceSensorRampFull.DI_WPDetected',
    'MAIN.m_container.m_SSC.m_Switch.DI_BoundaryPressure',
    'MAIN.m_container.m_SSC.m_Switch.DI_Extended',
    'MAIN.m_container.m_SSC.m_Switch.DI_Retracted',
    'MAIN.m_container.m_SSC.m_Switch.DO_Extend',
    'MAIN.m_container.m_SSC.Motor.AI_Position',
    'MAIN.m_container.m_SSC.Motor.AI_Speed',
    'MAIN.m_container.m_SSC.Motor.DO_TurnClockwise',
    'MAIN.m_container.m_SSC.Motor.DO_TurnCounterclockwise',
    'MAIN.m_container.m_stack.m_Inductivesensor.DI_WPMetallic',
    'MAIN.m_container.m_stack.m_Opticalsensor.DI_WPLight',
    'MAIN.m_container.m_stack.m_Presencesensor.DI_WPDetected',
    'MAIN.m_container.m_stack.m_Weightsensor.AI_WPWeight',
    'MAIN.m_container.m_stack.o_slidingCylinder.AI_FlowPressure',
    'MAIN.m_container.m_stack.o_slidingCylinder.AI_PositionTransmitter',
    'MAIN.m_container.m_stack.o_slidingCylinder.AI_PressureSensor',
    'MAIN.m_container.m_stack.o_slidingCylinder.DI_BoundaryFlowPressure',
    'MAIN.m_container.m_stack.o_slidingCylinder.DI_BoundaryPressure',
    'MAIN.m_container.m_stack.o_slidingCylinder.DI_Extended',
    'MAIN.m_container.m_stack.o_slidingCylinder.DI_Retracted',
    'MAIN.m_container.m_stack.o_slidingCylinder.DO_Extend',
    'MAIN.m_container.m_stamp.m_presenceSensor.DI_WPDetected',
    'MAIN.m_container.m_stamp.m_pressureSensor.AI_CurrentPressure',
    'MAIN.m_container.m_stamp.m_pressureValve.AO_SetPressure',
    'MAIN.m_container.m_stamp.m_slidingCylinder.AI_FlowPressure',
    'MAIN.m_container.m_stamp.m_slidingCylinder.AI_PositionTransmitter',
    'MAIN.m_container.m_stamp.m_slidingCylinder.AI_PressureSensor',
    'MAIN.m_container.m_stamp.m_slidingCylinder.DI_BoundaryFlowPressure',
    'MAIN.m_container.m_stamp.m_slidingCylinder.DI_BoundaryPressure',
    'MAIN.m_container.m_stamp.m_slidingCylinder.DI_Extended',
    'MAIN.m_container.m_stamp.m_slidingCylinder.DI_Retracted',
    'MAIN.m_container.m_stamp.m_slidingCylinder.DO_Extend',
    'MAIN.m_container.m_stamp.m_slidingCylinder.DO_Retract',
    'MAIN.m_container.m_stamp.m_stampingCylinder.AI_FlowPressure',
    'MAIN.m_container.m_stamp.m_stampingCylinder.AI_PositionTransmitter',
    'MAIN.m_container.m_stamp.m_stampingCylinder.AI_PressureSensor',
    'MAIN.m_container.m_stamp.m_stampingCylinder.DI_BoundaryFlowPressure',
    'MAIN.m_container.m_stamp.m_stampingCylinder.DI_BoundaryPressure',
    'MAIN.m_container.m_stamp.m_stampingCylinder.DI_Extended',
    'MAIN.m_container.m_stamp.m_stampingCylinder.DI_Retracted',
    'MAIN.m_container.m_stamp.m_stampingCylinder.DO_Extend',
]
# WARNING:
# Currently all variables are parsed as BOOL. If some variables are REAL/INT (e.g., AI_Position/AI_Speed),
# Should map them to correct pyads PLC types; otherwise parsing and notification length are wrong.
tags = {var: pyads.PLCTYPE_BOOL for var in var_list}

plc = None
notification_handles = {}
connected_clients = set()
main_loop = None
global_seq = 0

# CSV logging (IPC side) 
rows = []
rows_lock = threading.Lock()

# seq - > row index in CSV, to update rows in place if same variable changes again before CSV save
seq_to_row_index = {}
seq_map_lock = threading.Lock()

def make_csv_path():
    ts = time.strftime("%Y%m%d_%H%M%S")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, f"ipc_ads_log_{ts}.csv")

CSV_PATH = make_csv_path()


def save_csv():
    fieldnames = ["var_name", "value", "seq", "t0_ns", "t_return_ns"]

    with rows_lock:
        data = list(rows)

    try:
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in data:
                for k in fieldnames:
                    r.setdefault(k, "")
                w.writerow(r)
        print(f"[CSV SAVED] {len(data)} rows -> {CSV_PATH}")
    except Exception as e:
        print(f"[CSV SAVE ERROR] {e}")



def connect_plc():
    global plc
    plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
    plc.open()
    print("Successfully connected to PLC")

def plc_callback(notification, data):
    notification_id = notification.contents.hNotification
    var_name = next((k for k, v in notification_handles.items() if v[0] == notification_id), None)
    if var_name is None:
        print(f"Unknown notification ID: {notification_id}")
        return

    try:
        value = plc.parse_notification(notification, tags[var_name])[2]
    except Exception as e:
        print(f"parse_notification error for {var_name}: {e}")
        return

    # timestamp on IPC when ADS notification callback runs
    t0_ns = time.time_ns()

    # seq + log: make it atomic
    global global_seq
    with rows_lock:
        global_seq += 1
        seq = global_seq
        row_index = len(rows)
        rows.append({
            "var_name": var_name,
            "value": bool(value),
            "seq": seq,
            "t0_ns": t0_ns,
            "t_return_ns": ""   # wait to return 
        })
    # print(f"[SEND] seq={seq} row_index={row_index} var={var_name} t0_ns={t0_ns}")

    # create mapping for seq -> row index, to update rows in place if same variable changes again before CSV save
    with seq_map_lock:
        seq_to_row_index[seq] = row_index

    payload = {
        "type": "plc_change",
        "var": var_name,
        "value": bool(value),
        "seq": seq,
        "t0_ns": t0_ns
    }

    msg = json.dumps(payload, separators=(",", ":"))

    if main_loop:
        asyncio.run_coroutine_threadsafe(broadcast_ws_message(msg), main_loop)


def subscribe_plc_variables():
    attr = pyads.NotificationAttrib(
        length=sizeof(pyads.PLCTYPE_BOOL),
        trans_mode=pyads.ADSTRANS_SERVERONCHA,
        max_delay=0.001,
        cycle_time=0.001
    )
    attr._attrib.dwChangeFilter = 1

    for var in var_list:
        try:
            notification_handle, user_handle = plc.add_device_notification(var, attr, plc_callback)
            notification_handles[var] = (notification_handle, user_handle)
            print(f"Subscribed: {var}")
        except Exception as e:
            print(f"Subscription failed {var}: {e}")

def handle_return_message(message: str):
    """
    Handle return message from frontend, to update CSV with return timestamp.
    """
    try:
        data = json.loads(message)
    except Exception:
        return

    if data.get("type") != "plc_change_return":
        return

    try:
        seq = int(data.get("seq"))
    except Exception:
        return

    t_return_ns = time.time_ns()
    # print(f"return: seq={seq} t_return_ns={t_return_ns}")

    with seq_map_lock:
        idx = seq_to_row_index.get(seq)

    if idx is None:
        # print(f"[RETURN] seq={seq} idx=None (not found)")
        return

    with rows_lock:
        if 0 <= idx < len(rows):
            rows[idx]["t_return_ns"] = t_return_ns




async def websocket_server(websocket):
    connected_clients.add(websocket)
    print(f"Client connected: {websocket.remote_address}")
    try:
        async for message in websocket:
            handle_return_message(message)
    except websockets.exceptions.ConnectionClosed:
        print(f"Client disconnected: {websocket.remote_address}")
    finally:
        connected_clients.discard(websocket)

async def broadcast_ws_message(message: str):
    if not connected_clients:
        return
    dead = []
    for ws in list(connected_clients):
        try:
            await ws.send(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connected_clients.discard(ws)

async def run_websocket_server():
    async with websockets.serve(websocket_server, WS_HOST, WS_PORT):
        print(f"WebSocket server running: ws://{WS_HOST}:{WS_PORT}")
        await asyncio.Future()

async def shutdown():
    print("Shutting down WebSocket server...")
    for ws in list(connected_clients):
        try:
            await ws.close()
        except Exception:
            pass
    cleanup()

def cleanup():
    # unsubscribe PLC notifications
    for var, (notification_handle, user_handle) in notification_handles.items():
        try:
            plc.del_device_notification(notification_handle, user_handle)
            print(f"Unsubscribed: {var}")
        except Exception:
            pass
    try:
        plc.close()
    except Exception:
        pass
    print("PLC connection closed.")

    # always save CSV at end
    save_csv()

async def main():
    global main_loop
    main_loop = asyncio.get_running_loop()
    connect_plc()
    subscribe_plc_variables()

    try:
        await run_websocket_server()
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Ctrl+C -> run shutdown -> cleanup -> save csv
        asyncio.run(shutdown())