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
    btn_engraving_mode_threed = Gtk.Template.Child('c')
    dp_light_source = Gtk.Template.Child('light_source')
    spin_power = Gtk.Template.Child('power')
    spin_speed = Gtk.Template.Child('speed')
    swt_excutable = Gtk.Template.Child('excutable')
    
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

    @Gtk.Template.Callback()
    def power_value_changed(self,spin):
        self.obj.set_power(spin.get_value())

    @Gtk.Template.Callback()
    def speed_value_changed(self,spin):
        self.obj.set_speed(spin.get_value())

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
                gcode += f'G1 X{rb[0]*1000:.3f} Y{rb[1]*1000:.3f} S5\n'
                gcode += f'G1 X{rt[0]*1000:.3f} Y{rt[1]*1000:.3f}\n'
                gcode += f'G1 X{lt[0]*1000:.3f} Y{lt[1]*1000:.3f}\n'
                gcode += f'G1 X{lb[0]*1000:.3f} Y{lb[1]*1000:.3f}\n'
                gcode += f'M5\n'

            def present():
                if len(self.owner.steps) == 0: 
                    self.owner.excute(gcode)
                
                item = self.device_selection.get_selected_item()
                if item and len(item.controller.steps) == 0: 
                    item.controller.excute(gcode)

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
        if 0 == self.owner.count_elements(): return

        self.stack.set_visible_child_name('preview')
        self.box_start.set_visible(True)
        self.box_present.set_visible(False)
        self.box_process.set_visible(False)
       
        buffer = self.textview_gcode.get_buffer()
        mark = buffer.create_mark("end", buffer.get_end_iter(), False)
        self.emit('preview', True)
        self.gocde = []

        def f(): 
            svg = self.owner.export_svg()
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(delete=False); temp_file.close()
            svg_filepath = temp_file.name + '.svg'
            gc_filepath = temp_file.name + '.gc'

            with open(svg_filepath,'w') as f:
                f.write(svg)
            
            import subprocess as sp
            cmd = ['python','tests/gcoder.py',svg_filepath,gc_filepath]
            p = sp.Popen(cmd,stdout=sp.PIPE,text=True,encoding='utf-8')
            print(' '.join(cmd))
            
            while True:
                line = p.stdout.readline().strip()
                if line: 
                    self.gocde.append(line)
                    GLib.idle_add(lambda line: buffer.insert(buffer.get_end_iter(), line + '\n'),line)
                    continue

                # GLib.idle_add(lambda: self.textview_gcode.scroll_mark_onscreen(mark))
                if p.poll() is not None: break

            # def end():
                # self.textview_gcode.scroll_mark_onscreen(mark)
                # visible_rect = self.textview_gcode.get_visible_rect()
                # iter,i = self.textview_gcode.get_line_at_y(visible_rect.y + visible_rect.height)
                # if iter.get_line() + 1 != buffer.get_line_count(): return True
                # self.btn_start.set_sensitive(True)
            # GLib.idle_add(end)

        self.gcoding = threading.Thread(target=f,daemon=True)
        self.gcoding.start()
        # self.btn_start.set_sensitive(False)

    @Gtk.Template.Callback()
    def btn_back_clicked(self,sender):
        if self.gcoding.is_alive():
            self.gcoding.join()
        self.stack.set_visible_child_name('overview')
        self.box_start.set_visible(False)
        self.box_present.set_visible(True)
        self.box_process.set_visible(True)
        self.emit('preview', None)
        self.owner.steps.clear()
        self.owner.excute('G0\n')
        
        item = self.device_selection.get_selected_item()
        if item and item.controller.connected: 
            item.controller.steps.clear()
            item.controller.excute('M5\nG0\n')
        

    @Gtk.Template.Callback()
    def btn_start_toggled(self,sender):
        if self.gcoding.is_alive():
            self.gcoding.join()
    
        controller = None
        item = self.device_selection.get_selected_item()
        if item and item.controller.connected:
            controller = item.controller
        else:
            controller = self.owner

        if sender.get_active():
            line_count = 0
            def work():
                nonlocal line_count
                if not self.get_mapped() or not (line_count < len(self.gocde)):
                    return False
                
                if len(controller.steps) > 100:
                    return True

                lines = '\n'.join(self.gocde[line_count:line_count+100])                
                print(lines)  
                controller.excute(lines)
                line_count +=100

                buffer = self.textview_gcode.get_buffer()
                iter = buffer.get_start_iter()
                iter.forward_lines(line_count+1)
                mark = buffer.create_mark("offset", iter, False)
                self.textview_gcode.grab_focus()
                self.textview_gcode.scroll_mark_onscreen(mark)
                buffer.place_cursor(iter)
                buffer.delete_mark(mark)
                return True
            GLib.idle_add(work)
            sender.set_label('停止')
        else:
            controller.steps.clear()
            controller.excute('M5\nG0\n')
            sender.set_label('开始')