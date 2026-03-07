import pyads
from ctypes import sizeof

# TwinCAT PLC AMS ID and port
PLC_AMS_ID = '192.168.82.13.1.1'  
PLC_PORT = 851 

# Connect to the PLC
plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
plc.open()

tags = {"MAIN.m_container.m_stack.o_slidingCylinder.DI_Extended": pyads.PLCTYPE_BOOL}

def mycallback(notification, data):
    """ Device notification callback function """
    data_type = tags[data]
    handle, timestamp, value = plc.parse_notification(notification, data_type)
    print(f"[{timestamp}] Variable changed: {value}")

# Define notification attributes
attr = pyads.NotificationAttrib(sizeof(pyads.PLCTYPE_BOOL))

# Subscribe to PLC variable
notification_handle, user_handle = plc.add_device_notification(
    'MAIN.m_container.m_stack.o_slidingCylinder.DI_Extended', attr, mycallback
)

print("Monitoring variable... Press Ctrl+C to stop.")
try:
    while True:
        pass  # Keep the program running to receive notifications
except KeyboardInterrupt:
    print("\nStopping...")

# Correctly unsubscribe before closing
plc.del_device_notification(notification_handle, user_handle)

plc.close()
