import pyads
import time
import csv

# # PRIMITIVE DATA READ 10S to csv
PLC_AMS_ID = '192.168.82.13.1.1'
PLC_PORT = 851

plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
plc.open()

var_list = ['MAIN.i', 'MAIN.IGNORE_DEFINITION', 'MAIN.IGNORE_STOP', 'MAIN.INSTANCE_NAME']
csv_file = 'C:/Users/Zhao/Desktop/Jiayang/src/readtest3.2.csv'

with open(csv_file, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['TimeStamp'] + var_list)

try:
    start_time = time.time()
    while time.time() - start_time < 10:  # 10s
        value = plc.read_list_by_name(var_list)
        iso_time = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())

        with open(csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([iso_time] + [value[var] for var in var_list])
        print(f"Value at {iso_time}: {value}")
        time.sleep(1)  # 1 time /s
finally:
    plc.close()
