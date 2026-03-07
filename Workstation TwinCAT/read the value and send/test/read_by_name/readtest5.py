import pyads

PLC_AMS_ID = '192.168.82.13.1.1'
PLC_PORT = 851

plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
plc.open()

var_list = ['MAIN.i', 'MAIN.IGNORE_DEFINITION', 'MAIN.IGNORE_STOP', 'MAIN.INSTANCE_NAME', 'MAIN.m_allRampsFull', 'MAIN.m_appObservation']

structure_defs = {

    #Array
    'MAIN.m_appObservation': (
        ('MAIN.m_appObservation[1]', 'Resi4MPM.SValue', 3)
    ),
    'MAIN.m_appObservation[1]': (
        ('DataType', 'Resi4MPM.EDataType', 1),  
        ('Value', 'Resi4MPM.UValues', 1), 
        ('Defined', pyads.PLCTYPE_BOOL, 1)
    ),    
}

try:

    value = plc.read_list_by_name(var_list, structure_defs)
    print(f"Value: {value}")
finally:
    plc.close()