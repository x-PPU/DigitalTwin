import pyads
import time
import csv

# # PRIMITIVE DATA READ 10S to csv
PLC_AMS_ID = '192.168.82.13.1.1'
PLC_PORT = 851

plc = pyads.Connection(PLC_AMS_ID, PLC_PORT)
plc.open()

var_list = ['MAIN.m_container.m_crane.Motor.Stopped', #add
            'MAIN.m_container.m_crane.Motor.TurningClockwise', #add
            'MAIN.m_container.m_crane.Motor.TurningCounterclockwise', #add
            'MAIN.m_container.m_crane.Motor.DO_TurnClockwise', 
            'MAIN.m_container.m_crane.Motor.DO_TurnCounterclockwise',
            'MAIN.m_container.m_crane.Motor.AI_Position', 
            'MAIN.m_container.m_crane.Motor.AI_Speed', 
            'MAIN.m_container.m_crane.o_VacuumGripper.DI_TakenIn', 
            'MAIN.m_container.m_crane.o_VacuumGripper.DO_VacuumOn', 
            'MAIN.m_container.m_crane.o_VacuumGripper.VacuumHit', 
            'MAIN.m_container.m_crane.o_MonostableCylinder.AI_FlowPressure', 
            'MAIN.m_container.m_crane.o_MonostableCylinder.AI_PositionTransmitter', 
            'MAIN.m_container.m_crane.o_MonostableCylinder.AI_PressureSensor', 
            'MAIN.m_container.m_crane.o_MonostableCylinder.DI_BoundaryFlowPressure', 
            'MAIN.m_container.m_crane.o_MonostableCylinder.DI_BoundaryPressure', 
            'MAIN.m_container.m_crane.o_MonostableCylinder.DI_Extended', 
            'MAIN.m_container.m_crane.o_MonostableCylinder.DI_Retracted', 
            'MAIN.m_container.m_crane.o_MonostableCylinder.DO_Extend', 
            'MAIN.m_container.m_crane.o_Angle',#add            
            'MAIN.m_container.m_crane.m_PresenceSensorAtStack.DI_WPDetected',
            'MAIN.m_container.m_crane.m_PresenceSensorAtConveyor.DI_WPDetected',  
            'MAIN.m_container.m_crane.m_PresenceSensorAtStamp.DI_WPDetected', 
            'MAIN.m_container.m_stack.o_slidingCylinder.AI_FlowPressure', 
            'MAIN.m_container.m_stack.o_slidingCylinder.AI_PositionTransmitter', 
            'MAIN.m_container.m_stack.o_slidingCylinder.AI_PressureSensor', 
            'MAIN.m_container.m_stack.o_slidingCylinder.DI_BoundaryFlowPressure', 
            'MAIN.m_container.m_stack.o_slidingCylinder.DI_BoundaryPressure', 
            'MAIN.m_container.m_stack.o_slidingCylinder.DI_Extended', 
            'MAIN.m_container.m_stack.o_slidingCylinder.DI_Retracted', 
            'MAIN.m_container.m_stack.o_slidingCylinder.DO_Extend', 
            'MAIN.m_container.m_stack.m_Presencesensor.DI_WPDetected',
            'MAIN.m_container.m_stack.m_Opticalsensor.DI_WPLight', 
            'MAIN.m_container.m_stack.m_Inductivesensor.DI_WPMetallic',  
            'MAIN.m_container.m_stack.m_Weightsensor.AI_WPWeight', 
            'MAIN.m_container.m_stamp.m_stampingCylinder.AI_FlowPressure', 
            'MAIN.m_container.m_stamp.m_stampingCylinder.AI_PositionTransmitter', 
            'MAIN.m_container.m_stamp.m_stampingCylinder.AI_PressureSensor',
            'MAIN.m_container.m_stamp.m_stampingCylinder.DO_Extend', 
            'MAIN.m_container.m_stamp.m_stampingCylinder.DI_BoundaryFlowPressure', 
            'MAIN.m_container.m_stamp.m_stampingCylinder.DI_BoundaryPressure', 
            'MAIN.m_container.m_stamp.m_stampingCylinder.DI_Extended', 
            'MAIN.m_container.m_stamp.m_stampingCylinder.DI_Retracted',
            'MAIN.m_container.m_stamp.m_slidingCylinder.AI_FlowPressure', 
            'MAIN.m_container.m_stamp.m_slidingCylinder.AI_PositionTransmitter', 
            'MAIN.m_container.m_stamp.m_slidingCylinder.AI_PressureSensor', 
            'MAIN.m_container.m_stamp.m_slidingCylinder.DI_BoundaryFlowPressure', 
            'MAIN.m_container.m_stamp.m_slidingCylinder.DI_BoundaryPressure', 
            'MAIN.m_container.m_stamp.m_slidingCylinder.DI_Extended', 
            'MAIN.m_container.m_stamp.m_slidingCylinder.DI_Retracted', 
            'MAIN.m_container.m_stamp.m_slidingCylinder.DO_Extend', 
            'MAIN.m_container.m_stamp.m_slidingCylinder.DO_Retract',              
            'MAIN.m_container.m_stamp.m_presenceSensor.DI_WPDetected', 
            'MAIN.m_container.m_stamp.m_pressureSensor.AI_CurrentPressure', 
            'MAIN.m_container.m_stamp.m_pressureValve.AO_SetPressure', 
            'MAIN.m_container.m_LSC.Motor.AI_Position', 
            'MAIN.m_container.m_LSC.Motor.AI_Speed', 
            'MAIN.m_container.m_LSC.Motor.DO_TurnClockwise', 
            'MAIN.m_container.m_LSC.Motor.DO_TurnCounterclockwise',
            'MAIN.m_container.m_LSC.Motor.Stopped',#add
            'MAIN.m_container.m_LSC.Motor.TurningClockwise', #add
            'MAIN.m_container.m_LSC.Motor.TurningCounterclockwise', #add
            'MAIN.m_container.m_LSC.m_rampPusherStart.AI_FlowPressure', 
            'MAIN.m_container.m_LSC.m_rampPusherStart.AI_PositionTransmitter', 
            'MAIN.m_container.m_LSC.m_rampPusherStart.AI_PressureSensor', 
            'MAIN.m_container.m_LSC.m_rampPusherStart.DI_BoundaryFlowPressure', 
            'MAIN.m_container.m_LSC.m_rampPusherStart.DI_BoundaryPressure', 
            'MAIN.m_container.m_LSC.m_rampPusherStart.DI_Extended', 
            'MAIN.m_container.m_LSC.m_rampPusherStart.DI_Retracted', 
            'MAIN.m_container.m_LSC.m_rampPusherStart.DO_Extend', 
            'MAIN.m_container.m_LSC.m_rampPusherMid.AI_FlowPressure', 
            'MAIN.m_container.m_LSC.m_rampPusherMid.AI_PositionTransmitter', 
            'MAIN.m_container.m_LSC.m_rampPusherMid.AI_PressureSensor', 
            'MAIN.m_container.m_LSC.m_rampPusherMid.DI_BoundaryFlowPressure', 
            'MAIN.m_container.m_LSC.m_rampPusherMid.DI_BoundaryPressure', 
            'MAIN.m_container.m_LSC.m_rampPusherMid.DI_Extended', 
            'MAIN.m_container.m_LSC.m_rampPusherMid.DI_Retracted', 
            'MAIN.m_container.m_LSC.m_rampPusherMid.DO_Extend', 
            'MAIN.m_container.m_LSC.m_Switch.DI_BoundaryPressure', 
            'MAIN.m_container.m_LSC.m_Switch.DI_Extended', 
            'MAIN.m_container.m_LSC.m_Switch.DI_Retracted', 
            'MAIN.m_container.m_LSC.m_Switch.DO_Extend',
            'MAIN.m_container.m_LSC.m_presenceSensorStart.DI_WPDetected',
            'MAIN.m_container.m_LSC.m_opticalSensorStart.DI_WPLight',
            'MAIN.m_container.m_LSC.m_opticalSensorMid.DI_WPLight', 
            'MAIN.m_container.m_LSC.m_opticalSensorEnd.DI_WPLight',             
            'MAIN.m_container.m_LSC.m_inductiveSensorMid.DI_WPMetallic', 
            'MAIN.m_container.m_LSC.m_inductiveSensorStart.DI_WPMetallic', 
            'MAIN.m_container.m_LSC.m_rampStart.m_presenceSensorRampFull.DI_WPDetected', 
            'MAIN.m_container.m_LSC.m_rampMiddle.m_presenceSensorRampFull.DI_WPDetected',  
            'MAIN.m_container.m_LSC.m_rampEnd.m_presenceSensorRampFull.DI_WPDetected',
            'MAIN.m_container.m_PAC.Motor.AI_Position', 
            'MAIN.m_container.m_PAC.Motor.AI_Speed', 
            'MAIN.m_container.m_PAC.Motor.DO_TurnClockwise', 
            'MAIN.m_container.m_PAC.Motor.DO_TurnCounterclockwise', 
            'MAIN.m_container.m_PAC.Motor.TurningClockwise', #add
            'MAIN.m_container.m_PAC.Motor.TurningCounterclockwise', #add
            'MAIN.m_container.m_PAC.Motor.Stopped',#add 
            'MAIN.m_container.m_PAC.m_PresencesensorEnd.DI_WPDetected', 
            'MAIN.m_container.m_PAC.m_PresencesensorStart.DI_WPDetected',             
            'MAIN.m_container.m_PAC.m_Switch.DI_BoundaryPressure', 
            'MAIN.m_container.m_PAC.m_Switch.DI_Extended', 
            'MAIN.m_container.m_PAC.m_Switch.DI_Retracted', 
            'MAIN.m_container.m_PAC.m_Switch.DO_Extend', 
            'MAIN.m_container.m_PAC.m_WPNumberAtPAC',#add
            'MAIN.m_container.m_PicAlpha.Motor.AI_Position', 
            'MAIN.m_container.m_PicAlpha.Motor.AI_Speed', 
            'MAIN.m_container.m_PicAlpha.Motor.DO_TurnClockwise', 
            'MAIN.m_container.m_PicAlpha.Motor.DO_TurnCounterclockwise', 
            'MAIN.m_container.m_PicAlpha.Motor.TurningClockwise', #add
            'MAIN.m_container.m_PicAlpha.Motor.TurningCounterclockwise', #add 
            'MAIN.m_container.m_PicAlpha.Motor.Stopped',#add            
            'MAIN.m_container.m_PicAlpha.o_VacuumGripper.DI_TakenIn', 
            'MAIN.m_container.m_PicAlpha.o_VacuumGripper.DO_VacuumOn', 
            'MAIN.m_container.m_PicAlpha.o_VacuumGripper.VacuumHit', 
            'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.AI_FlowPressure', 
            'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.AI_PositionTransmitter', 
            'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.AI_PressureSensor', 
            'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.DI_BoundaryFlowPressure', 
            'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.DI_BoundaryPressure', 
            'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.DI_Extended', 
            'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.DI_Retracted', 
            'MAIN.m_container.m_PicAlpha.o_MonostableCylinder.DO_Extend', 
            'MAIN.m_container.m_PicAlpha.o_Distance', #add 
            'MAIN.m_container.m_PicAlpha.m_PresenceSensorPosition1.DI_WPDetected', 
            'MAIN.m_container.m_PicAlpha.m_PresenceSensorPosition2.DI_WPDetected', 
            'MAIN.m_container.m_PicAlpha.m_PresenceSensorPosition3.DI_WPDetected', 
            'MAIN.m_container.m_PicAlpha.m_PresenceSensorPosition4.DI_WPDetected',
            'MAIN.m_container.m_SSC.Motor.AI_Position', 
            'MAIN.m_container.m_SSC.Motor.AI_Speed', 
            'MAIN.m_container.m_SSC.Motor.DO_TurnClockwise', 
            'MAIN.m_container.m_SSC.Motor.DO_TurnCounterclockwise', 
            'MAIN.m_container.m_SSC.Motor.TurningClockwise', #add
            'MAIN.m_container.m_SSC.Motor.TurningCounterclockwise', #add 
            'MAIN.m_container.m_SSC.Motor.Stopped',#add 
            'MAIN.m_container.m_SSC.m_PresencesensorEnd.DI_WPDetected', 
            'MAIN.m_container.m_SSC.m_PresencesensorStart.DI_WPDetected',            
            'MAIN.m_container.m_SSC.m_Inductivesensor.DI_WPMetallic', 
            'MAIN.m_container.m_SSC.m_Opticalsensor.DI_WPLight', 
            'MAIN.m_container.m_SSC.m_Ramp.m_presenceSensorRampFull.DI_WPDetected', 
            'MAIN.m_container.m_SSC.m_Switch.DI_BoundaryPressure', 
            'MAIN.m_container.m_SSC.m_Switch.DI_Extended', 
            'MAIN.m_container.m_SSC.m_Switch.DI_Retracted', 
            'MAIN.m_container.m_SSC.m_Switch.DO_Extend',
            'MAIN.m_container.m_RFC.Motor.AI_Position', 
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

csv_file = 'D:/Neuer Ordner/readtest/readvalue.csv'

with open(csv_file, mode='w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['TimeStamp'] + var_list)

try:
    start_time = time.time()
    while time.time() - start_time < 60:  # 10s
        value = plc.read_list_by_name(var_list)
        iso_time = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime())

        with open(csv_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([iso_time] + [value[var] for var in var_list])
        time.sleep(1)  # 1 time /s
finally:
    plc.close()
