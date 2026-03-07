import pyads

PLC_AMS_ID = '192.168.82.13.1.1'
PLC_PORT = 851

plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
plc.open()

var_list = ['MAIN.i', 'MAIN.IGNORE_DEFINITION', 'MAIN.IGNORE_STOP', 'MAIN.INSTANCE_NAME', 'MAIN.m_allRampsFull']

structure_defs = {
    'MAIN.m_allRampsFull': (
        ('m_left', 'Resi4MPM.IExpression', 1),  #HOW mappe PLCdata type
        ('m_sign', 'Resi4MPM.EBoolOperation', 1), 
        ('m_right', 'Resi4MPM.IExpression', 1)
    )
}

try:

    value = plc.read_list_by_name(var_list, structure_defs)
    print(f"Value: {value}")
finally:
    plc.close()