import gi


gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, GObject, Gio, Gdk
from PIL import Image
import pygfx as gfx
from simtoy import *
from simtoy.tools.engravtor import *
import threading

@Gtk.Template(filename='ui/panel.ui')
class Panel (Gtk.Box):
    __gtype_name__ = "Panel"
    provider = Gtk.CssProvider.new()
    btn_device_manager = Gtk.Template.Child('device_manager')
    btn_device_discovery = Gtk.Template.Child('device_discovery')
    img_status = Gtk.Template.Child('img_status')
    lbl_status = Gtk.Template.Child('lbl_status')
    
    stack = Gtk.Template.Child('stack')
    lsv_params = Gtk.Template.Child('params')
    label_kind = Gtk.Template.Child('kind')
    image_icon = Gtk.Template.Child('icon')
    btn_engraving_mode_stroke = Gtk.Template.Child('a')
    btn_engraving_mode_full = Gtk.Template.Child('b')
    dp_light_source = Gtk.Template.Child('light_source')
    spin_power = Gtk.Template.Child('power')
    spin_speed = Gtk.Template.Child('speed')
    swt_excutable = Gtk.Template.Child('excutable')
    
    box_present = Gtk.Template.Child('box_present')
    box_process = Gtk.Template.Child('box_process')
    box_start = Gtk.Template.Child('box_start')
    textview_gcode = Gtk.Template.Child('textview_gcode')
    
    # listview = Gtk.Template.Child('geoms')
    # expander_device = Gtk.Template.Child('expander_device')
    # expander_gcode = Gtk.Template.Child('expander_gcode')


    # expander_text = Gtk.Template.Child('expander_text')
    # expander_bitmap = Gtk.Template.Child('expander_bitmap')
    # btn_connect = Gtk.Template.Child('btn_connect')
    # dp_com_port = Gtk.Template.Child('dp_com_port')

    # menu_add = Gtk.Template.Child('popover_menu_add')
    # menu = Gtk.Template.Child('popover_menu')

    def __init__(self):
        self.provider.load_from_path('ui/panel.css')
        Gtk.StyleContext.add_provider_for_display(self.get_display(),self.provider,Gtk.STYLE_PROVIDER_PRIORITY_USER)

        model = Gio.ListStore(item_type=GObject.Object)
        self.device_selection = Gtk.SingleSelection.new(model)
        self.device_selection.set_autoselect(True)
        self.device_selection.set_can_unselect(True)
        # self.device_selection.connect('selection-changed', self.update_status)
        # GLib.timeout_add(1000, self.update_status)
        threading.Thread(target=self.update_status,daemon=True).start()


        model = Gio.ListStore(item_type=GObject.Object)
        self.param_selection = Gtk.NoSelection.new(model)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_listitem)
        factory.connect("bind", self.bind_listitem)
        self.lsv_params.set_factory(factory)

        self.items = None
        self.obj = None
    
    def bind_owner(self,tool : Engravtor):
        self.owner = tool

    def update_status(self):
        from time import sleep
        condition = threading.Event()
        while True:
            sleep(1)
            item = self.device_selection.get_selected_item()
            if item and item.controller.is_connected():
                def f():
                    self.img_status.remove_css_class('red-dot')
                    self.img_status.add_css_class('green-dot')
                    self.lbl_status.set_label('已连接')
                    condition.set()
                GLib.idle_add(f)
            else:
                def f():
                    self.img_status.remove_css_class('green-dot')
                    self.img_status.add_css_class('red-dot')
                    self.lbl_status.set_label('未连接')
                    condition.set()
                GLib.idle_add(f)

            condition.wait()
            condition.clear()
            

    @Gtk.Template.Callback()
    def device_manager_clicked(self, btn):
        from device_manager import DeviceManagerDialog
        dlg = DeviceManagerDialog()
        dlg.lsv_devices.set_model(self.device_selection)
        dlg.set_modal(True)
        dlg.present()
    
    @Gtk.Template.Callback()
    def device_discovery_clicked(self, btn):
        from device_discovery import DeviceDiscoveryDialog
        dlg = DeviceDiscoveryDialog()
        dlg.set_modal(True)
        dlg.connect('close-request', self.device_discovery_closed)
        dlg.present()

    def device_discovery_closed(self, dlg):
        if dlg.result:
            self.add_device(dlg.result)

    def add_device(self,controller):
        device = GObject.Object()
        device.controller = controller
        self.device_selection.get_model().append(device)

    def set_obj(self,obj):
        self.stack.set_visible_child_name('param' if obj else 'overview')
        self.obj = obj

        if not obj: return
        self.btn_engraving_mode_stroke.set_sensitive(True)

        if obj.__class__.__name__ == 'Label':
            self.label_kind.set_label('文本')
            self.image_icon.set_from_icon_name('format-text-bold')
            
            if obj.params['engraving_mode'] == 'stroke':
                self.btn_engraving_mode_stroke.set_active(True)
            elif obj.params['engraving_mode'] == 'fill':
                self.btn_engraving_mode_full.set_active(True)

        elif obj.__class__.__name__ == 'Vectors':
            self.label_kind.set_label('矢量图')
            self.image_icon.set_from_icon_name('folder-publicshare-symbolic')

            if obj.params['engraving_mode'] == 'stroke':
                self.btn_engraving_mode_stroke.set_active(True)
            elif obj.params['engraving_mode'] == 'fill':
                self.btn_engraving_mode_full.set_active(True)

        else:
            self.label_kind.set_label('图片')
            self.image_icon.set_from_icon_name('image-x-generic-symbolic')
            self.btn_engraving_mode_stroke.set_sensitive(False)
            self.btn_engraving_mode_full.set_active(True)
        
        self.dp_light_source.set_selected(0 if obj.params['light_source'] == 'blue' else 1)
        self.spin_power.set_value(obj.params['power'])
        self.spin_speed.set_value(obj.params['speed'])
        self.swt_excutable.set_active(obj.params['excutable'])

    @Gtk.Template.Callback()
    def btn_engraving_mode_stroke_clicked(self,btn):
        self.obj.set_engraving_mode('stroke')
        model = self.param_selection.get_model()
        self.param_selection.set_model(None)
        self.param_selection.set_model(model)

    @Gtk.Template.Callback()
    def btn_engraving_mode_full_clicked(self,btn):
        self.obj.set_engraving_mode('fill')
        model = self.param_selection.get_model()
        self.param_selection.set_model(None)
        self.param_selection.set_model(model)

    def setup_listitem(self, factory, lsi):
        box = Gtk.Box()
        box.set_size_request(-1,80)
        box.set_spacing(5)

        img = Gtk.Image()
        img.set_pixel_size(80)
        img_bg = Image.new("RGBA", (img.get_pixel_size(), img.get_pixel_size()), (50,50,50,255))
        texture = Gdk.MemoryTexture.new(img.get_pixel_size(),img.get_pixel_size(),Gdk.MemoryFormat.B8G8R8A8,GLib.Bytes.new(img_bg.tobytes()),img.get_pixel_size()*4)
        img.set_from_paintable(texture)
        
        box.append(img)
    
        box_1 = Gtk.Box()
        box_1.set_orientation(Gtk.Orientation.VERTICAL)
        box_1.set_spacing(1)
        box_1.set_hexpand(True)
        box_1.set_valign(Gtk.Align.CENTER)

        mode = Gtk.Label()
        mode.set_label(f'<span size="large">模式</span>')
        mode.set_use_markup(True)
        mode.set_halign(Gtk.Align.START)
        box_1.append(mode)

        light_source = Gtk.Label()
        light_source.set_label(f'<span size="medium">光源</span>')
        light_source.set_use_markup(True)
        light_source.set_halign(Gtk.Align.START)
        box_1.append(light_source)

        box_11 = Gtk.Box()
        box_11.set_spacing(20)
        box_11.set_hexpand(True)
        box_11.set_valign(Gtk.Align.CENTER)

        power = Gtk.Label()
        power.set_label(f'<span color="gray" size="medium">0%</span>')
        power.set_use_markup(True)
        power.set_halign(Gtk.Align.START)
        box_11.append(power)

        speed = Gtk.Label()
        speed.set_label(f'<span color="gray" size="medium">0mm/s</span>')
        speed.set_use_markup(True)
        speed.set_halign(Gtk.Align.START)
        box_11.append(speed)
        box_1.append(box_11)

        box.append(box_1)
        lsi.set_child(box)

    def bind_listitem(self, factory, lsi):
        item = lsi.get_item()
        box = lsi.get_child()
        img = box.get_first_child()
        box_1 = img.get_next_sibling()

        lbl_mode = box_1.get_first_child()
        lbl_light_source = lbl_mode.get_next_sibling()
        box_11 = lbl_light_source.get_next_sibling()
        lbl_power = box_11.get_first_child()
        lbl_speed = lbl_power.get_next_sibling()

        surface = item.obj.draw_to_image()
        argb = np.frombuffer(surface.get_data(), dtype=np.uint8).reshape((surface.get_height(),surface.get_width(), 4))
        img_size = img.get_pixel_size()
        img_content = Image.fromarray(argb[...,[2,1,0,3]],mode="RGBA")
        img_content.thumbnail((img_size, img_size))
        img_bg = Image.new("RGBA", (img_size, img_size), (50,50,50,255))
        img_bg.paste(img_content, (int((img_size - img_content.size[0])/2), int((img_size - img_content.size[1])/2)), mask=img_content.split()[3])
        texture = Gdk.MemoryTexture.new(img_size,img_size,Gdk.MemoryFormat.B8G8R8A8,GLib.Bytes.new(np.asarray(img_bg)[...,[2,1,0,3]].tobytes()),img_size*4)
        img.set_from_paintable(texture)

        mode = '线条' if item.obj.params["engraving_mode"] == 'stroke' else '填充'
        lbl_mode.set_label(f'<span size="large">{mode}</span>')
        light_source = '蓝光' if item.obj.params["light_source"] == 'blue' else '红光'
        lbl_light_source.set_label(f'<span size="medium">{light_source}</span>')
        lbl_power.set_label(f'<span color="lightgray" size="medium">{item.obj.params["power"]}%</span>')
        lbl_speed.set_label(f'<span color="lightgray" size="medium">{item.obj.params["speed"]}mm/s</span>')

    @Gtk.Template.Callback()
    def on_params_activate(self, sender, idx):
        print(idx)

    def set_params(self,items):
        self.items = items
        model = self.param_selection.get_model()
        model.remove_all()
        for item in items:
            param = GObject.Object()
            param.obj = item
            model.append(param)
        self.lsv_params.set_model(self.param_selection)

    @Gtk.Template.Callback()
    def btn_present_toggled(self,sender):

        if sender.get_active():
            sender.set_label('停止')
            gcode = ''
            if self.obj: items = [self.obj]
            else: items = self.items
            for item in items:
                lb,rb,rt,lt = item.get_oriented_bounding_box()
                gcode += f'G0 X{lb[0]*1000:.3f} Y{lb[1]*1000:.3f} F100\n'
                gcode += f'M3\n'
                gcode += f'G1 X{rb[0]*1000:.3f} Y{rb[1]*1000:.3f} S10\n'
                gcode += f'G1 X{rt[0]*1000:.3f} Y{rt[1]*1000:.3f}\n'
                gcode += f'G1 X{lt[0]*1000:.3f} Y{lt[1]*1000:.3f}\n'
                gcode += f'G1 X{lb[0]*1000:.3f} Y{lb[1]*1000:.3f}\n'
                gcode += f'M5\n'

            def present():
                if len(self.owner.steps) == 0: 
                    self.owner.excute(gcode)
                    item = self.device_selection.get_selected_item()
                    if item: item.controller.excute(gcode)
    
                return self.get_mapped() and sender.get_active()
            GLib.idle_add(present)
        else:
            sender.set_label('走边框')
            self.owner.steps.clear()        
            self.owner.excute('G0\n')

    @GObject.Signal(return_type=bool, arg_types=(object,))
    def preview(self,*args): pass

    @Gtk.Template.Callback()
    def btn_process_clicked(self,sender):
        if 0 == self.owner.count_elements():
            return

        self.stack.set_visible_child_name('preview')
        self.box_start.set_visible(True)
        self.box_present.set_visible(False)
        self.box_process.set_visible(False)
        
        gcode = ''
        for svg,width,height,params in self.owner.export_svg():            
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(delete=False); temp_file.close()
            svg_filepath = temp_file.name + '.svg'
            gc_filepath = temp_file.name + '.gc'
            print(svg_filepath)

            with open(svg_filepath,'w') as f:
                f.write(self.parse_svg(svg.getvalue().decode()))
            
            if self.export_gcode_from_svg(svg_filepath,gc_filepath,width,height,params['power'],params['speed'],params['pixelsize'],params['lightspotsize']):
                continue
            
            with open(gc_filepath,'r') as f:
                gcode += f.read()
        
        buffer = self.textview_gcode.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        buffer.insert(end_iter, gcode)
        self.emit('preview', gcode)
        
        self.owner.excute(gcode)
        
    @Gtk.Template.Callback()
    def btn_back_clicked(self,sender):
        buffer = self.textview_gcode.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        buffer.delete(start_iter,end_iter)

        self.stack.set_visible_child_name('overview')
        self.box_start.set_visible(False)
        self.box_present.set_visible(True)
        self.box_process.set_visible(True)
        self.emit('preview', None)
        self.owner.steps.clear()
        self.owner.excute('G0\n')


    @Gtk.Template.Callback()
    def btn_start_clicked(self,sender):
        buffer = self.textview_gcode.get_buffer()
        start_iter = buffer.get_start_iter()
        end_iter = buffer.get_end_iter()
        gcode = buffer.get_text(start_iter, end_iter, True)
        
        self.owner.steps.clear()
        self.owner.excute('G0\n')
        item = self.device_selection.get_selected_item()
        if item: item.controller.excute(gcode)
        
    def parse_svg(self,svg_content):
        from lxml import etree
        import re

        # 2. 解析SVG（保留XML声明和格式）
        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.fromstring(svg_content.encode("utf-8"), parser=parser)
        ns = {"svg": "http://www.w3.org/2000/svg", "xlink": "http://www.w3.org/1999/xlink"}

        # 需求1：移除defs标签，保留内部image标签
        if (defs := root.find("svg:defs", ns)) is not None:
            for img in defs.findall("svg:image", ns):
                root.append(img)  # 将image移到svg根节点
            root.remove(defs)

        # 需求2：移除image标签href属性的xlink前缀
        for img in root.findall("svg:image", ns):
            xlink_href = img.get(f'{{{ns["xlink"]}}}href')
            if xlink_href:
                img.set("href", xlink_href)  # 新增普通href属性
                del img.attrib[f'{{{ns["xlink"]}}}href']  # 删除xlink:href

        # 需求3：移除use标签，将transform转移到对应id的元素
        for use in root.findall("svg:use", ns):
            target_id = use.get(f'{{{ns["xlink"]}}}href').lstrip("#")  # 提取目标id
            if (target := root.xpath(f'//svg:*[@id="{target_id}"]', namespaces=ns)):
                target[0].set("transform", use.get("transform"))  # 转移transform
            root.remove(use)

        # 需求4：替换所有rgb颜色为red/blue（红色分量最高则为red，否则blue）
        rgb_pattern = re.compile(r"rgb\([^)]+\)", re.I)
        for elem in root.iter():
            for attr, val in list(elem.attrib.items()):
                if rgb_pattern.match(val):
                    # 解析RGB分量（支持百分比/数值格式）
                    r, g, b = [float(v.strip("%")) * (2.55 if "%" in v else 1) 
                            for v in re.findall(r"\d+%?", val)]
                    elem.set(attr, "red" if r > g and r > b else "blue")

        # 3. 输出处理后的SVG
        result = etree.tostring(
            root, encoding="utf-8", xml_declaration=True, pretty_print=True
        ).decode("utf-8")
        return result

    def export_gcode_from_svg(self,svg_filepath,gc_filepath,width,height,power,speed,pixelsize,lightspotsize):
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
        args = parser.parse_args([svg_filepath, gc_filepath,'--origin',str(-width / 2),str(-height / 2),'--imagepower',str(power),'--imagespeed',str(speed), '--pixelsize',str(pixelsize),'--lightspotsize',str(lightspotsize)])
        
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
