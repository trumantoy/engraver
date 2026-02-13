import os
import sys
import argparse

from svg2gcode.svg_to_gcode.svg_parser import parse_file
from svg2gcode.svg_to_gcode.compiler import Compiler, interfaces

from svg2gcode import __version__
from svg2gcode.svg_to_gcode import css_color
import trimesh
import serial
import threading

class USBController:
    def __init__(self):
        self.serial = None
        self.name = ''
        self.steps = []        
        self.connected = False
        self.mutex = threading.Lock()
        self.event = threading.Event()
        threading.Thread(target=self.worker,daemon=True).start()

    
    def connect(self,port):
        try:
            # 初始化串口（根据实际设备修改参数）
            self.serial = serial.Serial(port=port,baudrate=9600,timeout=1)

            # 检查串口是否打开
            if not self.serial.is_open:
                self.serial = None
                return False            
        except Exception as e:
            self.serial = None
            return False
    
        self.connected = self.is_connected()
        return self.connected
    
    def disconnect(self):
        if self.serial:
            self.serial.close()

    def is_connected(self):
        with self.mutex:
            if not self.serial: return False
            
            try:
                self.serial.write(b'$I\n')
                res = self.serial.readall().decode()
                
                if '[MODEL:' not in res:
                    return False

                model_start = res.find('[MODEL:') + len('[MODEL:')
                model_end = res.find(']', model_start)
                if model_start > 0 and model_end > model_start:
                    self.name = res[model_start:model_end]
            except:
                import traceback as tb
                tb.print_exc()
                return False
        return True

    def set_pulse(self):
        with self.mutex:
            req = f'$222P1P400\n'.encode()
            self.serial.write(req)
            res = self.serial.readline()

    def set_axes_invert(self):
        with self.mutex:
            req = f'$240P3P6P5P1\n'.encode()
            self.serial.write(req)
            res = self.serial.readline()
            
    def set_process_params(self):
        with self.mutex:
            req = f'T0 C25\n'.encode()
            self.serial.write(req)
            res = self.serial.readline()
            
    def excute(self, gcode:str):
        with self.mutex:
            for line in gcode.splitlines(True):
                if not line.strip(): continue
                if line.strip().startswith(';'): continue
                req = line.encode()
                self.steps.append(req)
        self.event.set()

    def worker(self):
        while True:
            sent = 0
            received = 0
            limit = 200
            n = 1
            with self.mutex:
                while self.steps:
                    req = self.steps[:received + 200 - sent]
                    print(sent,received,len(self.steps),flush=True)
                    if not req: continue
                    self.serial.write(b''.join(req))
                    self.steps = self.steps[len(req):]
                    sent += len(req)
                    print(sent,received,len(self.steps),flush=True)
                    res = self.serial.read_all()
                    if not res: continue
                    print(res,flush=True)
                    received += len(res.splitlines(True))
                    print(sent,received,len(self.steps),flush=True)

                for _ in range(sent - received):
                    self.serial.readline()
                    n = 1
                    limit += n
                    received += n
            
            import time
            time.sleep(1)

            if not self.steps:
                self.connected = self.is_connected()

          
if __name__ == '__main__':
    # 读取命令行参数
    parser = argparse.ArgumentParser(description='SVG to G-code Compiler')
    parser.add_argument('input', type=str, help='Input SVG file path')
    parser.add_argument('output', type=str, help='Output G-code file path')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    args = parser.parse_args()

    compiler = Compiler(interfaces.Gcode, params={'laser_power': 100,'movement_speed':100, 'pixel_size':1.0,
                'maximum_image_laser_power':100, 'image_movement_speed':100, 'fan':False,'rapid_move':10,
                'showimage':False, 'x_axis_maximum_travel':100,'y_axis_maximum_travel':100, 'image_noise': 0,
                'pass_depth': 0, 'laser_mode': "constant" if True else "dynamic", 'splitfile':False, 'pathcut':False,
                'nofill': False, 'image_poweroffset': 0, 'image_overscan': 0, 'image_showoverscan':False,
                'color_coded': '',})
    
    compiler.compile_to_file(args.output, args.input, parse_file(args.input, delta_origin=(-49.5, -50.5), scale_factor=(1,1), rotate_deg=0), passes=1)
