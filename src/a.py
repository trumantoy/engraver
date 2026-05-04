import os
import sys
import argparse

if __name__ == '__main__':
    # 读取命令行参数
    from device_discovery import USBController
    import time
    import serial.tools.list_ports
    ports = serial.tools.list_ports.comports()
    for port in [port.device for port in ports]:
        print(port)
        controller = USBController()
        controller.connect(port)
        controller.set_pulse()
        controller.set_axes_invert()
        controller.set_process_params()

        gcode = ''
        with open(args.output, 'r') as f:
            i = 0
            while True:
                s = f.readline()
                i+=1
                print(i,s,end='')

                if s.startswith('G0 Z'):
                    controller.excute(gcode)

                    while controller.steps or controller.hh:
                        time.sleep(2)

                    # time.sleep(2)
                    controller.excute(s)
                    # time.sleep(2)
                    gcode = ''
                else:
                    gcode += s
    
                if s.startswith('M2'): break
        input()
        break
