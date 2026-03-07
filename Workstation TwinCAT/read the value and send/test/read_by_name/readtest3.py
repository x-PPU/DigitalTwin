import pyads

# PRIMITIVE DATA READ

PLC_AMS_ID = '192.168.82.13.1.1'
PLC_PORT = 851

plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
plc.open()
var_list = ['MAIN.i', 'MAIN.IGNORE_DEFINITION', 'MAIN.m_container.m_iCraneWP.raln_prodTypeAdr.Port', 'MAIN.SFCCurrentStep']


try:

    value = plc.read_list_by_name(var_list)
    print(f"Value: {value}")
finally:
    plc.close()