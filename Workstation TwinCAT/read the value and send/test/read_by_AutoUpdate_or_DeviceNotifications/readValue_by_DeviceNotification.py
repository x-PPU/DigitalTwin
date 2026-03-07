import pyads
import csv
from datetime import datetime
from ctypes import sizeof

# TwinCAT PLC AMS ID and port
PLC_AMS_ID = '192.168.82.13.1.1'
PLC_PORT = 851

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

# Connect to PLC
plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
plc.open()

# Store device notification handles
notification_handles = {}

# Store the last recorded values of variables
last_values = {var: None for var in var_list}

# CSV file path
csv_file_path = "C:/Users/STUD_LiJiayang/Desktop/Jiayang/src/read_by_AutoUpdate_or_DeviceNotifications//Variable_DN.csv"

# Initialize CSV file (create if it does not exist)
with open(csv_file_path, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(["Timestamp"] + var_list)  # Write header row

# Device notification callback function
def mycallback(notification, data):
    """Handles variable value changes."""
    notification_id = notification.contents.hNotification
    var_name = next((k for k, v in notification_handles.items() if v[0] == notification_id), None)

    if var_name is None:
        print(f" Unknown variable for notification ID: {notification_id}")
        return

    # Parse variable value
    value = plc.parse_notification(notification, tags[var_name])[2]

    # Only log when the variable value changes
    if last_values[var_name] != value:
        last_values[var_name] = value  # Update stored value
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]  # Millisecond precision

        print(f"[{timestamp}] {var_name} changed: {value}")

        # Write to CSV
        with open(csv_file_path, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([timestamp] + [last_values[v] for v in var_list])

# Define optimized notification attributes (trigger only on value change)
attr = pyads.NotificationAttrib(
    length=sizeof(pyads.PLCTYPE_BOOL),
    trans_mode=pyads.ADSTRANS_SERVERONCHA,  # Trigger only on change
    max_delay=0.01,  # Max delay of 10ms
    cycle_time=0.01  # 10ms cycle time
)
attr._attrib.dwChangeFilter = 1  # Ensure notification triggers ONLY on change

# Subscribe to variables
for var in var_list:
    try:
        notification_handle, user_handle = plc.add_device_notification(var, attr, mycallback)
        notification_handles[var] = (notification_handle, user_handle)
        print(f" Subscribed to: {var}")
    except Exception as e:
        print(f" Failed to subscribe to {var}: {e}")

print(" Monitoring variables... Press Ctrl+C to stop.")

try:
    while True:
        pass  # Keep running to receive notifications
except KeyboardInterrupt:
    print("\n Stopping...")

# Unsubscribe before closing
for var, (notification_handle, user_handle) in notification_handles.items():
    plc.del_device_notification(notification_handle, user_handle)
    print(f" Unsubscribed from: {var}")

# Close PLC connection
plc.close()
print(" PLC connection closed.")
