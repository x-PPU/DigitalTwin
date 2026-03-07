import pyads

PLC_AMS_ID = '192.168.82.13.1.1'
PLC_PORT = 851

plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
plc.open()

try:
    symbol = plc.get_symbol(
        name='MAIN.m_buttonManager.DI_AutomaticSwitch_LSCTerminal',
        index_group=16448,
        index_offset=477405
    )
    value = symbol.read()
    print(f"Value: {value}")
finally:
    plc.close()
