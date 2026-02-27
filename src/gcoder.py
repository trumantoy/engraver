import os
import sys
import argparse

from svg2gcode.svg_to_gcode.svg_parser import parse_file
from svg2gcode.svg_to_gcode.compiler import Compiler, interfaces

from svg2gcode import __version__

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
