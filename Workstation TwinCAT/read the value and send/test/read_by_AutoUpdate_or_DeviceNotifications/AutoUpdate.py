import pyads
import csv
import time
from datetime import datetime

# TwinCAT PLC AMS ID & Port
PLC_AMS_ID = '192.168.82.13.1.1'
PLC_PORT = 851

# List of PLC variables to monitor
var_list = [
            ##STACK
            'MAIN.m_container.m_stack.o_slidingCylinder.DI_Extended',
            'MAIN.m_container.m_stack.o_slidingCylinder.DI_Retracted', 
            'MAIN.m_container.m_stack.o_slidingCylinder.DO_Extend', 


            ##ROTCRANE
            'MAIN.m_container.m_crane.o_MonostableCylinder.DI_Extended', 
            'MAIN.m_container.m_crane.o_MonostableCylinder.DI_Retracted', 
            'MAIN.m_container.m_crane.o_MonostableCylinder.DO_Extend',
            'MAIN.m_container.m_crane.o_VacuumGripper.DI_TakenIn',
            'MAIN.m_container.m_crane.Motor.DO_TurnClockwise', 
            'MAIN.m_container.m_crane.Motor.DO_TurnCounterclockwise', 
            'MAIN.m_container.m_crane.m_PresenceSensorAtStack.DI_WPDetected',
            'MAIN.m_container.m_crane.m_PresenceSensorAtStamp.DI_WPDetected', 
            'MAIN.m_container.m_crane.m_PresenceSensorAtConveyor.DI_WPDetected', 
            

            ##STAMP
            'MAIN.m_container.m_stamp.m_slidingCylinder.DI_Extended',
            'MAIN.m_container.m_stamp.m_slidingCylinder.DI_Retracted',
            'MAIN.m_container.m_stamp.m_slidingCylinder.DO_Extend', 
            'MAIN.m_container.m_stamp.m_slidingCylinder.DO_Retract',

            
            'MAIN.m_container.m_stamp.m_stampingCylinder.DI_Extended',
            'MAIN.m_container.m_stamp.m_stampingCylinder.DI_Retracted',
            'MAIN.m_container.m_stamp.m_stampingCylinder.DO_Extend', 

            
            ##CONVEYORS
            'MAIN.m_container.m_LSC.Motor.DO_TurnClockwise', 
            'MAIN.m_container.m_LSC.m_rampPusherStart.DI_Retracted',
            'MAIN.m_container.m_LSC.m_rampPusherStart.DO_Extend', 
            'MAIN.m_container.m_LSC.m_rampPusherMid.DI_Retracted',           
            'MAIN.m_container.m_LSC.m_rampPusherMid.DO_Extend',
            'MAIN.m_container.m_LSC.m_Switch.DO_Extend'
            
]

# CSV file path
csv_file = 'C:/Users/STUD_LiJiayang/Desktop/Jiayang/src/read_by_AutoUpdate_or_DeviceNotifications/AutoUpdate.csv'

# Connect to the PLC
plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
plc.open()

# Create Symbol objects with auto-update enabled
symbols = {var: plc.get_symbol(var) for var in var_list}
for sym in symbols.values():
    sym.auto_update = True  # Enable automatic value updates

# Write CSV header
with open(csv_file, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['TimeStamp'] + var_list)

print("Auto-updating PLC variables and writing to CSV... Press Ctrl+C to stop.")

try:
    while True:
        # Get the current timestamp with millisecond precision
        iso_time = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')

        # Read the latest values from auto-updating symbols
        values = [symbols[var].value for var in var_list]

        # Write data to CSV
        with open(csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([iso_time] + values)

except KeyboardInterrupt:
    print("\n Stopping...")

finally:
    plc.close()
