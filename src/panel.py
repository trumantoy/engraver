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
    swt_excutable = Gtk.Template.Child('excutable')
    btn_engraving_mode_stroke = Gtk.Template.Child('a')
    btn_engraving_mode_full = Gtk.Template.Child('b')
    btn_engraving_mode_threed = Gtk.Template.Child('c')
    dp_light_source = Gtk.Template.Child('light_source')
    spin_power = Gtk.Template.Child('power')
    spin_speed = Gtk.Template.Child('speed')
    layers = Gtk.Template.Child('layers')
    passes = Gtk.Template.Child('passes')
    pass_depth = Gtk.Template.Child('pass_depth')
    density_x = Gtk.Template.Child('density_x')
    density_y = Gtk.Template.Child('density_y')

    box_present = Gtk.Template.Child('box_present')
    btn_present = Gtk.Template.Child('present')
    box_process = Gtk.Template.Child('box_process')
    box_start = Gtk.Template.Child('box_start')
    btn_start = Gtk.Template.Child('start')
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
        GLib.timeout_add(1000,self.update_status)

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
        item = self.device_selection.get_selected_item()
        if item and item.controller.connected:
            self.img_status.remove_css_class('red-dot')
            self.img_status.add_css_class('green-dot')
            self.lbl_status.set_label('已连接')
        else:
            self.img_status.remove_css_class('green-dot')
            self.img_status.add_css_class('red-dot')
            self.lbl_status.set_label('未连接')
        return True
    
    @Gtk.Template.Callback()
    def focus_clicked(self, btn):
        from focus import FocusDialog
        dlg = FocusDialog()

        item = self.device_selection.get_selected_item()
        if item and item.controller.connected:
            dlg.set_controller(item.controller)
        else:
            dlg.set_controller(self.owner)
        dlg.present()

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
            self.btn_engraving_mode_stroke.set_sensitive(True)
            self.btn_engraving_mode_threed.set_sensitive(False)            
            if obj.params['engraving_mode'] == 'stroke':
                self.btn_engraving_mode_stroke.set_active(True)
            elif obj.params['engraving_mode'] == 'fill':
                self.btn_engraving_mode_full.set_active(True)

        elif obj.__class__.__name__ == 'Vectors':
            self.label_kind.set_label('矢量图')
            self.image_icon.set_from_icon_name('folder-publicshare-symbolic')
            self.btn_engraving_mode_stroke.set_sensitive(True)
            self.btn_engraving_mode_threed.set_sensitive(False)
            if obj.params['engraving_mode'] == 'stroke':
                self.btn_engraving_mode_stroke.set_active(True)
            elif obj.params['engraving_mode'] == 'fill':
                self.btn_engraving_mode_full.set_active(True)

        else:
            self.label_kind.set_label('图片')
            self.image_icon.set_from_icon_name('image-x-generic-symbolic')
            self.btn_engraving_mode_stroke.set_sensitive(False)
            self.btn_engraving_mode_threed.set_sensitive(True)
            if obj.params['engraving_mode'] == 'fill':
                self.btn_engraving_mode_full.set_active(True)
            elif obj.params['engraving_mode'] == 'threed':
                self.btn_engraving_mode_threed.set_active(True)
        
        self.dp_light_source.set_selected(0 if obj.params['light_source'] == 'blue' else 1)
        self.spin_power.set_value(obj.params['power'])
        self.spin_speed.set_value(obj.params['speed'])
        self.swt_excutable.set_active(obj.params['excutable'])

    @Gtk.Template.Callback()
    def swt_excutable_state_set(self,swt,state):
        self.obj.set_excutable(state)

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

    @Gtk.Template.Callback()
    def btn_engraving_mode_threed_clicked(self,btn):
        self.obj.set_engraving_mode('threed')
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
        light_source = '紫外光' if item.obj.params["light_source"] == 'blue' else '红光'
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
    def layers_value_changed(self,spin):
        self.obj.set_layers(spin.get_value())

    @Gtk.Template.Callback()
    def passes_value_changed(self,spin):
        print(spin.get_value())
        self.obj.set_passes(spin.get_value())

    @Gtk.Template.Callback()
    def pass_depth_value_changed(self,spin):
        self.obj.set_pass_depth(spin.get_value())


    @Gtk.Template.Callback()
    def power_value_changed(self,spin):
        self.obj.set_power(spin.get_value())

    @Gtk.Template.Callback()
    def speed_value_changed(self,spin):
        self.obj.set_speed(spin.get_value())

    @Gtk.Template.Callback()
    def density_x_value_changed(self,spin):
        self.obj.set_density_x(spin.get_value())

    @Gtk.Template.Callback()
    def density_y_value_changed(self,spin):
        self.obj.set_density_y(spin.get_value())

    @Gtk.Template.Callback()
    def btn_present_toggled(self,sender):
        controller = None
        item = self.device_selection.get_selected_item()
        if item and item.controller.connected:
            controller = item.controller
        else:
            controller = self.owner

        if sender.get_active():
            sender.set_label('停止')
            gcode = ''
            if self.obj: items = [self.obj]
            else: items = self.items
            for item in items:
                lb,rb,rt,lt = item.get_oriented_bounding_box()
                gcode += f'G0 X{lb[0]*1000:.3f} Y{lb[1]*1000:.3f}\n'
                gcode += f'G0 X{rb[0]*1000:.3f} Y{rb[1]*1000:.3f}\n'
                gcode += f'G0 X{rt[0]*1000:.3f} Y{rt[1]*1000:.3f}\n'
                gcode += f'G0 X{lt[0]*1000:.3f} Y{lt[1]*1000:.3f}\n'
                gcode += f'G0 X{lb[0]*1000:.3f} Y{lb[1]*1000:.3f}\n'
            
            controller.excute('M5\nG0 F200\n')

            def present():
                if len(controller.steps) < 5: 
                    controller.excute(gcode)

                if self.get_mapped() and sender.get_active():
                    return True
                return False
            GLib.idle_add(present)
        else:
            sender.set_label('走边框')
            controller.steps.clear()
            controller.excute('G0\n')

    @GObject.Signal(return_type=bool, arg_types=(object,))
    def preview(self,*args): pass

    @Gtk.Template.Callback()
    def btn_process_clicked(self,sender):
        if 0 == self.owner.count_elements(): return

        self.stack.set_visible_child_name('preview')
        self.box_start.set_visible(True)
        self.box_present.set_visible(False)
        self.box_process.set_visible(False)
       
        self.emit('preview', True)
        self.gcode = []
        buffer = self.textview_gcode.get_buffer()
        buffer.set_text('')

        svg = self.owner.export_svg()
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(delete=False); temp_file.close()
        svg_filepath = temp_file.name + '.svg'
        gc_filepath = temp_file.name + '.gc'

        with open(svg_filepath,'w',encoding='utf-8') as f2:
            f2.write(svg)
        
        import subprocess as sp
        cmd = ['python','tests/gcoder.py',svg_filepath,gc_filepath]
        self.p = sp.Popen(cmd,stdout=sp.PIPE,text=True,encoding='utf-8')
        print(' '.join(cmd))
        
        controller = None
        item = self.device_selection.get_selected_item()
        if item and item.controller.connected:
            controller = item.controller
        else:
            controller = self.owner
        limit = line_count = 0

        def f():
            def f2(line):
                buffer = self.textview_gcode.get_buffer()
                buffer.insert(buffer.get_end_iter(), line)

            def f3(n):
                buffer = self.textview_gcode.get_buffer()
                iter = buffer.get_start_iter()
                iter.forward_lines(n)
                mark = buffer.create_mark("offset", iter, False)
                self.textview_gcode.grab_focus()
                self.textview_gcode.scroll_mark_onscreen(mark)
                buffer.place_cursor(iter)
                buffer.delete_mark(mark)

            nonlocal line_count,limit
            if not self.get_root().get_mapped() or (line_count == len(self.gcode) and self.p.poll() is not None):
                return False

            lines = self.p.stdout.readlines(20 * 500)

            if len(lines):                
                self.gcode.extend(lines)
                f2(''.join(lines))

            if not self.btn_start.get_active(): return True

            try:
                limit = self.gcode.index('M5\n',limit) + 1
                if self.gcode[limit] == 'M2\n': limit += 1
            except:
                pass

            if line_count == limit: return True
            
            f3(limit)

            lines = ''.join(self.gcode[line_count:limit])
            controller.excute(lines)

            line_count = limit
            return True
        
        GLib.idle_add(f)

    @Gtk.Template.Callback()
    def btn_back_clicked(self,sender):
        self.btn_start.set_active(False)
        self.stack.set_visible_child_name('overview')
        self.box_start.set_visible(False)
        self.box_present.set_visible(True)
        self.box_process.set_visible(True)
        self.emit('preview', None)
        
        controller = None
        item = self.device_selection.get_selected_item()
        if item and item.controller.connected:
            controller = item.controller
        else:
            controller = self.owner
        
        controller.steps.clear()
        controller.excute('M5\nG0\n')


    @Gtk.Template.Callback()
    def btn_start_toggled(self,sender):
        if sender.get_active():
            sender.set_label('停止')
        else:
            sender.set_label('开始')
