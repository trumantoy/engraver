import xml.etree.ElementTree as ET
import cairo

def export_gcode_from_svg(svg_filepath,gc_filepath,width,height,power,speed,pixelsize):
    from svg2gcode.__main__ import svg2gcode
    from svg2gcode.svg_to_gcode import css_color
    import argparse
    import re

    # defaults
    cfg = {
        "lightspotsize_default": 0.1,
        "pixelsize_default": 0.1,
        "imagespeed_default": 100,
        "cuttingspeed_default": 100,
        "imagepower_default": 100,
        "poweroffset_default": 0,
        "cuttingpower_default": 100,
        "xmaxtravel_default": 100, 
        "ymaxtravel_default": 100,
        "rapidmove_default": 10,
        "noise_default": 0,
        "overscan_default": 0,
        "pass_depth_default": 0,
        "passes_default": 1,
        "rotate_default": 0,
        "colorcoded_default": "",
        "constantburn_default": True,
    }

    # Define command line argument interface
    parser = argparse.ArgumentParser(description='Convert svg to gcode for GRBL v1.1 compatible diode laser engravers.')
    parser.add_argument('svg', type=str, help='svg file to be converted to gcode')
    parser.add_argument('gcode', type=str, help='gcode output file')
    parser.add_argument('--showimage', action='store_true', default=False, help='show b&w converted image' )
    parser.add_argument('--selfcenter', action='store_true', default=False, help='self center the gcode (--origin cannot be used at the same time)' )
    parser.add_argument('--lightspotsize', default=cfg["lightspotsize_default"], metavar="<default:" + str(cfg["lightspotsize_default"])+">",type=float, help="")
    parser.add_argument('--pixelsize', default=cfg["pixelsize_default"], metavar="<default:" + str(cfg["pixelsize_default"])+">",type=float, help="pixel size in mm (XY-axis): each image pixel is drawn this size")
    parser.add_argument('--imagespeed', default=cfg["imagespeed_default"], metavar="<default:" + str(cfg["imagespeed_default"])+">",type=int, help='image draw speed in mm/min')
    parser.add_argument('--cuttingspeed', default=cfg["cuttingspeed_default"], metavar="<default:" + str(cfg["cuttingspeed_default"])+">",type=int, help='cutting speed in mm/min')
    parser.add_argument('--imagepower', default=cfg["imagepower_default"], metavar="<default:" +str(cfg["imagepower_default"])+ ">",type=int, help="maximum laser power while drawing an image (as a rule of thumb set to 1/3 of the machine maximum for a 5W laser)")
    parser.add_argument('--poweroffset', default=cfg["poweroffset_default"], metavar="<default:" +str(cfg["poweroffset_default"])+ ">",type=int, help="pixel intensity to laser power: shift power range [0-imagepower]")
    parser.add_argument('--cuttingpower', default=cfg["cuttingpower_default"], metavar="<default:" +str(cfg["cuttingpower_default"])+ ">",type=int, help="sets laser power of line (path) cutting")
    parser.add_argument('--passes', default=cfg["passes_default"], metavar="<default:" +str(cfg["passes_default"])+ ">",type=int, help="Number of passes (iterations) for line drawings, only active when pass_depth is set")
    parser.add_argument('--pass_depth', default=cfg["pass_depth_default"], metavar="<default:" + str(cfg["pass_depth_default"])+">",type=float, help="cutting depth in mm for one pass, only active for passes > 1")
    parser.add_argument('--rapidmove', default=cfg["rapidmove_default"], metavar="<default:" + str(cfg["rapidmove_default"])+ ">",type=int, help='generate G0 moves between shapes, for images: G0 moves when skipping more than 10mm (default), 0 is no G0 moves' )
    parser.add_argument('--noise', default=cfg["noise_default"], metavar="<default:" +str(cfg["noise_default"])+ ">",type=int, help='reduces image noise by not emitting pixels with power lower or equal than this setting')
    parser.add_argument('--overscan', default=cfg["overscan_default"], metavar="<default:" +str(cfg["overscan_default"])+ ">",type=int, help="overscan image lines to avoid incorrect power levels for pixels at left and right borders, number in pixels, default off")
    parser.add_argument('--showoverscan', action='store_true', default=False, help='show overscan pixels (note that this is visible and part of the gcode emitted!)' )
    parser.add_argument('--constantburn', action=argparse.BooleanOptionalAction, default=cfg["constantburn_default"], help='default constant burn mode (M3)')
    parser.add_argument('--origin', default=None, nargs=2, metavar=('delta-x', 'delta-y'),type=float, help="translate origin by vector (delta-x,delta-y) in mm (default not set, option --selfcenter cannot be used at the same time)")
    parser.add_argument('--scale', default=None, nargs=2, metavar=('factor-x', 'factor-y'),type=float, help="scale svg with (factor-x,factor-y) (default not set)")
    parser.add_argument('--rotate', default=cfg["rotate_default"], metavar="<default:" +str(cfg["rotate_default"])+ ">",type=int, help="number of degrees to rotate")
    parser.add_argument('--splitfile', action='store_true', default=False, help='split gcode output of SVG path and image objects' )
    parser.add_argument('--pathcut', action='store_true', default=False, help='alway cut SVG path objects! (use laser power set with option --cuttingpower)' )
    parser.add_argument('--nofill', action='store_true', default=False, help='ignore SVG fill attribute' )
    parser.add_argument('--xmaxtravel', default=cfg["xmaxtravel_default"], metavar="<default:" +str(cfg["xmaxtravel_default"])+ ">",type=int, help="machine x-axis lengh in mm")
    parser.add_argument('--ymaxtravel', default=cfg["ymaxtravel_default"], metavar="<default:" +str(cfg["ymaxtravel_default"])+ ">",type=int, help="machine y-axis lengh in mm")
    parser.add_argument( '--color_coded', action = 'store', default=cfg["colorcoded_default"], metavar="<default:\"" + str(cfg["colorcoded_default"])+ "\">",type = str, help = 'set action for path with specific stroke color "[color = [cut|engrave|ignore] *]*"'', example: --color_coded "black = ignore purple = cut blue = engrave"' )
    parser.add_argument('--fan', action='store_true', default=False, help='set machine fan on' )
    parser.add_argument('-V', '--version', action='version', version='%(prog)s ' + '3.3.6', help="show version number and exit")

    # 使用临时文件作为输出路径
    args = parser.parse_args([svg_filepath, gc_filepath,'--origin',str(-width / 2),str(-height / 2),'--cuttingpower',str(round(power)),'--imagepower',str(round(power)),'--cuttingspeed',str(round(speed)), '--imagespeed',str(round(speed)), '--pixelsize',str(round(pixelsize,2))])
    
    if args.color_coded != "":
        if args.pathcut:
            print("options --color_coded and --pathcut cannot be used at the same time, program abort")
            return 1
        # check argument validity (1)

        # category names
        category = ["cut", "engrave", "ignore"]
        # get css color names
        colors = str([*css_color.css_color_keywords])
        colors = re.sub(r"(,|\[|\]|\'| )", '', colors.replace(",", "|"))

        # make a color list
        colors = colors.split("|")

        # get all names from color_code
        names_regex = "[a-zA-Z]+"
        match = re.findall(names_regex, args.color_coded)
        names = [i for i in match]

        for name in names:
            if not (name in colors or name in category):
                print(f"argument error: '--color_coded {args.color_coded}' has a name '{name}' that does not correspond to a css color or category (cut|engrave|ignore).")
                return 1

    if args.origin is not None and args.selfcenter:
        print("options --selfcenter and --origin cannot be used at the same time, program abort")
        return 1

    return svg2gcode(args)

if __name__ == '__main__':
    tree = ET.parse('a.svg')
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    
    root = tree.getroot()  # 获取根节点 <svg>
    width = int(root.attrib.get('width'))
    height = int(root.attrib.get('height'))

    with cairo.SVGSurface('~a.svg', width, height) as surface:
        cr = cairo.Context(surface)
        cr.translate(width / 2,height / 2)

        for text_elem in root.findall('.//svg:text', ns):
            # 获取属性
            x = text_elem.attrib.get('x')
            y = text_elem.attrib.get('y')
            font_size = text_elem.attrib.get('font-size')
            family = text_elem.attrib.get('font-family')
            stroke = text_elem.attrib.get('stroke')
            fill = text_elem.attrib.get('fill')
            stroke_width = text_elem.attrib.get('stroke-width')
            transform = text_elem.attrib.get('transform').replace('matrix(', '').replace(')', '').split(',')
            text = text_elem.text

            # 打印结果
            print(f"文本内容: {text}")
            print(f"位置 (x, y): ({x}, {y})")
            print(f"字体大小: {font_size}")
            print(f"描边颜色: {stroke}")
            print(f"填充颜色: {fill}")
            print(f"描边宽度: {stroke_width}")
            print(f'矩阵：{transform}')

            tm = cairo.Matrix(float(transform[0]),float(transform[1]),float(transform[2]),float(transform[3]),float(transform[4]),float(transform[5]))
            cr.set_matrix(tm)

            if stroke == 'red': cr.set_source_rgb(1, 0, 0)
            else: cr.set_source_rgb(0, 0, 1)

            cr.set_line_width(float(stroke_width))

            if fill != 'none': 
                temp_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)  # 临时1x1像素表面
                temp_ctx = cairo.Context(temp_surface)
                
                # 配置与最终绘制一致的字体
                temp_ctx.select_font_face(family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                temp_ctx.set_font_size(float(font_size))
                
                # 获取文字的详细边界信息（核心参数）
                text_info = temp_ctx.text_extents(text)
                text_width = text_info.width          # 文字左边缘到右边缘的实际宽度（无多余）
                text_height = text_info.height        # 文字上边缘到下边缘的实际高度（含上下伸部分）

                # 2. 图片尺寸=文字实际尺寸（零留白关键）
                img_width = int(text_width)
                img_height = int(text_height)

                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, img_width, img_height)
                cr2 = cairo.Context(surface)
                cr2.select_font_face(family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                cr2.set_font_size(float(font_size))
                cr2.move_to(-text_info.x_bearing, -text_info.y_bearing)
                cr2.text_path(text)
                cr2.fill()

                cr.set_source_surface(surface, -img_width / 2, -img_height / 2)
                cr.paint()
            else: 
                cr.select_font_face(family, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
                cr.set_font_size(float(font_size))
                text_extents = cr.text_extents(text)
                cr.move_to(float(x),float(y))
                cr.text_path(text)
                cr.stroke()
