import pyads

PLC_AMS_ID = '192.168.82.13.1.1'
PLC_PORT = 851

plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
plc.open()

try:

    value = plc.read_by_name(
        'MAIN.m_container.m_stack.o_slidingCylinder.DI_Extended',
        pyads.PLCTYPE_BOOL
    )
    print(f"Value: {value}")
finally:
    plc.close()