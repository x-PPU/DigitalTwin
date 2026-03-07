import pyads
import asyncio
import websockets
from datetime import datetime
from ctypes import sizeof

# TwinCAT PLC AMS ID and port
PLC_AMS_ID = '192.168.82.13.1.1'  
PLC_PORT = 851 

# WebSocket configuration
WS_HOST = "192.168.82.3"  # PC IP
WS_PORT = 8765

# List of PLC variables (all BOOL type)
var_list = [
    'MAIN.m_container.m_stack.o_slidingCylinder.DI_Extended',
    'MAIN.m_container.m_stack.o_slidingCylinder.DI_Retracted', 
    'MAIN.m_container.m_stack.o_slidingCylinder.DO_Extend',  
    'MAIN.m_container.m_crane.o_MonostableCylinder.DI_Extended', 
    'MAIN.m_container.m_crane.o_MonostableCylinder.DI_Retracted', 
    'MAIN.m_container.m_crane.o_MonostableCylinder.DO_Extend',
    'MAIN.m_container.m_crane.o_VacuumGripper.DI_TakenIn',
    'MAIN.m_container.m_crane.Motor.DO_TurnClockwise', 
    'MAIN.m_container.m_crane.Motor.DO_TurnCounterclockwise', 
    'MAIN.m_container.m_crane.m_PresenceSensorAtStack.DI_WPDetected',
    'MAIN.m_container.m_crane.m_PresenceSensorAtStamp.DI_WPDetected', 
    'MAIN.m_container.m_crane.m_PresenceSensorAtConveyor.DI_WPDetected', 
    'MAIN.m_container.m_stamp.m_slidingCylinder.DI_Extended',
    'MAIN.m_container.m_stamp.m_slidingCylinder.DI_Retracted',
    'MAIN.m_container.m_stamp.m_slidingCylinder.DO_Extend', 
    'MAIN.m_container.m_stamp.m_slidingCylinder.DO_Retract',
    'MAIN.m_container.m_stamp.m_stampingCylinder.DI_Extended',
    'MAIN.m_container.m_stamp.m_stampingCylinder.DI_Retracted',
    'MAIN.m_container.m_stamp.m_stampingCylinder.DO_Extend', 
    'MAIN.m_container.m_LSC.Motor.DO_TurnClockwise', 
    'MAIN.m_container.m_LSC.m_rampPusherStart.DI_Retracted',
    'MAIN.m_container.m_LSC.m_rampPusherStart.DO_Extend', 
    'MAIN.m_container.m_LSC.m_rampPusherMid.DI_Retracted',           
    'MAIN.m_container.m_LSC.m_rampPusherMid.DO_Extend',
    'MAIN.m_container.m_LSC.m_Switch.DO_Extend'
]

# Map variables to BOOL type
tags = {var: pyads.PLCTYPE_BOOL for var in var_list}

# Global variables
plc = None  
notification_handles = {}  
connected_clients = set()  
main_loop = None  # Store the main event loop

def connect_plc():
    """ Connect to TwinCAT PLC """
    global plc
    plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
    plc.open()
    print(" Successfully connected to PLC")

def plc_callback(notification, data):
    """ Handle PLC variable change event """
    notification_id = notification.contents.hNotification
    var_name = next((k for k, v in notification_handles.items() if v[0] == notification_id), None)

    if var_name is None:
        print(f" Unknown notification ID: {notification_id}")
        return

    value = plc.parse_notification(notification, tags[var_name])[2]
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  
    msg = f"[{timestamp}] {var_name} changed: {value}"
    
    print(msg)

    # Ensure the WebSocket message is sent in the main asyncio event loop
    if main_loop:
        asyncio.run_coroutine_threadsafe(broadcast_ws_message(msg), main_loop)
    else:
        print(" Error: Main event loop is not initialized.")

def subscribe_plc_variables():
    """ Subscribe to PLC variable changes """
    attr = pyads.NotificationAttrib(
        length=sizeof(pyads.PLCTYPE_BOOL), 
        trans_mode=pyads.ADSTRANS_SERVERONCHA,  
        max_delay=0.05,
        cycle_time=0.05
    )
    attr._attrib.dwChangeFilter = 1  

    for var in var_list:
        try:
            notification_handle, user_handle = plc.add_device_notification(var, attr, plc_callback)
            notification_handles[var] = (notification_handle, user_handle)
            print(f" Subscribed to variable: {var}")
        except Exception as e:
            print(f" Subscription failed {var}: {e}")

async def websocket_server(websocket):
    """ Handle WebSocket client connections """
    connected_clients.add(websocket)
    print(f" Client connected: {websocket.remote_address}")

    try:
        async for message in websocket:
            print(f" Received message from client: {message}")
    except websockets.exceptions.ConnectionClosed:
        print(f" Client disconnected: {websocket.remote_address}")
    finally:
        connected_clients.discard(websocket)  

async def broadcast_ws_message(message):
    """ Broadcast message to WebSocket clients """
    if connected_clients:
        await asyncio.gather(*[ws.send(message) for ws in connected_clients])

async def run_websocket_server():
    """ Start WebSocket server """
    async with websockets.serve(websocket_server, WS_HOST, WS_PORT):
        print(f" WebSocket server running: ws://{WS_HOST}:{WS_PORT}")
        await asyncio.Future()  # Keeps the server running

async def shutdown():
    """ Cleanup resources on server shutdown """
    print(" Shutting down WebSocket server...")
    for ws in connected_clients:
        await ws.close()
    cleanup()

def cleanup():
    """ Unsubscribe from PLC variables and close PLC connection """
    for var, (notification_handle, user_handle) in notification_handles.items():
        plc.del_device_notification(notification_handle, user_handle)
        print(f" Unsubscribed: {var}")
    
    plc.close()
    print(" PLC connection closed.")

async def main():
    """ Main function: Start PLC monitoring and WebSocket server """
    global main_loop
    main_loop = asyncio.get_running_loop()  # Store the main event loop

    connect_plc()  # Connect to PLC
    subscribe_plc_variables()  # Subscribe to PLC variable changes

    try:
        await run_websocket_server()  # Start WebSocket server
    except asyncio.CancelledError:
        print(" WebSocket server task canceled.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n Exiting program...")
        asyncio.run(shutdown())
