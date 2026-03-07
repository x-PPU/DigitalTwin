import pyads
import csv

csv_file_path = "C:/Users/Zhao/Desktop/Jiayang/src/plc_symbols.getallsymbols.csv"

PLC_AMS_ID = '192.168.82.13.1.1'
PLC_PORT = 851  

with pyads.Connection(PLC_AMS_ID, PLC_PORT) as plc:
    if plc.is_open:
        print("Connection successful!")

        symbols = plc.get_all_symbols()
        
        filtered_symbols = [symbol for symbol in symbols if symbol.name.startswith("MAIN")]

        with open(csv_file_path, mode='w', newline='') as csv_file:
            csv_writer = csv.writer(csv_file)
            
            csv_writer.writerow(["Name", "Type", "Index Group", "Index Offset", "Comment"])
            
            # Write the filtered symbols
            for symbol in filtered_symbols:
                csv_writer.writerow([
                    symbol.name,
                    symbol.symbol_type,
                    symbol.index_group,
                    symbol.index_offset,
                    symbol.comment
                ])
        
    else:
        print("Failed to connect to the device.")
