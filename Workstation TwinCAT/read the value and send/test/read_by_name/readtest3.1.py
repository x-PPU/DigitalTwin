import pyads
import time

# PRIMITIVE DATA READ 10S

PLC_AMS_ID = '192.168.82.13.1.1'
PLC_PORT = 851

plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
plc.open()

var_list = ['MAIN.m_container.m_RFC.Motor.AI_Position', 
            'MAIN.m_container.m_RFC.Motor.AI_Speed', 
            'MAIN.m_container.m_RFC.Motor.DO_TurnClockwise', 
            'MAIN.m_container.m_RFC.Motor.DO_TurnCounterclockwise',
            'MAIN.m_container.m_RFC.Motor.TurningClockwise', #add
            'MAIN.m_container.m_RFC.Motor.TurningCounterclockwise', #add 
            'MAIN.m_container.m_RFC.Motor.Stopped',#add                      
            'MAIN.m_container.m_RFC.m_PresencesensorEnd.DI_WPDetected', 
            'MAIN.m_container.m_RFC.m_PresencesensorStart.DI_WPDetected', 
            'MAIN.m_container.m_RFC.m_Switch.DI_BoundaryPressure', 
            'MAIN.m_container.m_RFC.m_Switch.DI_Extended', 
            'MAIN.m_container.m_RFC.m_Switch.DI_Retracted', 
            'MAIN.m_container.m_RFC.m_Switch.DO_Extend']

try:
    start_time = time.time()
    while time.time() - start_time < 2:  #  10 S
        value = plc.read_list_by_name(var_list)
        iso_time = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())
        print(f"Value at {iso_time}: {value}")
        time.sleep(1)  # 1 TIME PER 1S
finally:
    plc.close()

