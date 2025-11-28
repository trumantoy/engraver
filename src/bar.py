import numpy as np
import pygfx as gfx

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Gio

from PIL import Image
from simtoy import *
from panel import *

@Gtk.Template(filename='ui/actionbar.ui')
class Actionbar (Gtk.ScrolledWindow):
    __gtype_name__ = "Actionbar"
    
    def __init__(self):
        provider = Gtk.CssProvider.new()
        provider.load_from_path('ui/actionbar.css')
        Gtk.StyleContext.add_provider_for_display(self.get_display(),provider,Gtk.STYLE_PROVIDER_PRIORITY_USER)

@Gtk.Template(filename='ui/viewbar.ui')
class Viewbar (Gtk.ScrolledWindow):
    __gtype_name__ = "Viewbar"

    view_mode : Gtk.Button = Gtk.Template.Child('view_mode')

    def __init__(self):
        provider = Gtk.CssProvider.new()
        provider.load_from_path('ui/viewbar.css')
        Gtk.StyleContext.add_provider_for_display(self.get_display(),provider,Gtk.STYLE_PROVIDER_PRIORITY_USER)

    def set_editor(self,view_controller : gfx.OrbitController):
        self.view_controller = view_controller

    @Gtk.Template.Callback()
    def on_top_clicked(self,button):
        perspective,orthographic = self.view_controller.cameras
        perspective : gfx.PerspectiveCamera
        orthographic : gfx.OrthographicCamera        
        extent = perspective.height
        factor = 0.5 / m.tan(0.5 * m.radians(perspective.fov))
        distance = extent * factor
        origin = perspective.local.position
        direction = perspective.local.forward
        target = origin + direction * distance
        perspective.local.position = target + np.array([0,0,1]) * distance
        orthographic.local.position = target + np.array([0,0,1]) * distance
        perspective.local.euler = np.array([0,0,perspective.local.euler_z])
        orthographic.local.euler = np.array([0,0,orthographic.local.euler_z])

    @Gtk.Template.Callback()
    def on_bottom_clicked(self,button):
        perspective,orthographic = self.view_controller.cameras
        perspective : gfx.PerspectiveCamera
        orthographic : gfx.OrthographicCamera        
        extent = perspective.height
        factor = 0.5 / m.tan(0.5 * m.radians(perspective.fov))
        distance = extent * factor
        origin = perspective.local.position
        direction = perspective.local.forward
        target = origin + direction * distance
        perspective.local.position = target + np.array([0,0,-1]) * distance
        orthographic.local.position = target + np.array([0,0,-1]) * distance
        perspective.local.euler = np.array([m.pi,0,perspective.local.euler_z])
        orthographic.local.euler = np.array([m.pi,0,orthographic.local.euler_z])

    @Gtk.Template.Callback()
    def on_left_clicked(self,button):
        perspective,orthographic = self.view_controller.cameras
        perspective : gfx.PerspectiveCamera
        orthographic : gfx.OrthographicCamera        
        extent = perspective.height
        factor = 0.5 / m.tan(0.5 * m.radians(perspective.fov))
        distance = extent * factor
        origin = perspective.local.position
        direction = perspective.local.forward
        target = origin + direction * distance
        perspective.local.position = target + np.array([-1,0,0]) * distance
        orthographic.local.position = target + np.array([-1,0,0]) * distance
        perspective.look_at(target)
        orthographic.look_at(target)

    @Gtk.Template.Callback()
    def on_right_clicked(self,button):
        perspective,orthographic = self.view_controller.cameras
        perspective : gfx.PerspectiveCamera
        orthographic : gfx.OrthographicCamera        
        extent = perspective.height
        factor = 0.5 / m.tan(0.5 * m.radians(perspective.fov))
        distance = extent * factor
        origin = perspective.local.position
        direction = perspective.local.forward
        target = origin + direction * distance
        perspective.local.position = target + np.array([1,0,0]) * distance
        orthographic.local.position = target + np.array([1,0,0]) * distance
        perspective.look_at(target)
        orthographic.look_at(target)

    @Gtk.Template.Callback()
    def on_front_clicked(self,button):
        perspective,orthographic = self.view_controller.cameras
        perspective : gfx.PerspectiveCamera
        orthographic : gfx.OrthographicCamera        
        extent = perspective.height
        factor = 0.5 / m.tan(0.5 * m.radians(perspective.fov))
        distance = extent * factor
        origin = perspective.local.position
        direction = perspective.local.forward
        target = origin + direction * distance
        perspective.local.position = target + np.array([0,-1,0]) * distance
        orthographic.local.position = target + np.array([0,-1,0]) * distance
        perspective.look_at(target)
        orthographic.look_at(target)
        
    @Gtk.Template.Callback()
    def on_back_clicked(self,button):
        perspective,orthographic = self.view_controller.cameras
        perspective : gfx.PerspectiveCamera
        orthographic : gfx.OrthographicCamera
        extent = perspective.height
        factor = 0.5 / m.tan(0.5 * m.radians(perspective.fov))
        distance = extent * factor
        origin = perspective.local.position
        direction = perspective.local.forward
        target = origin + direction * distance
        perspective.local.position = target + np.array([0,1,0]) * distance
        orthographic.local.position = target + np.array([0,1,0]) * distance 
        perspective.look_at(target)
        orthographic.look_at(target)

    @Gtk.Template.Callback()
    def on_persp_clicked(self,button):
        if '透视' == button.get_label():
            button.set_label('正交')
        else:
            button.set_label('透视')

@Gtk.Template(filename='ui/hotbar.ui')
class Hotbar (Gtk.ScrolledWindow):
    __gtype_name__ = "Hotbar"
    tools = Gtk.Template.Child('tools')

    def __init__(self):
        provider = Gtk.CssProvider.new()
        provider.load_from_path('ui/hotbar.css')
        Gtk.StyleContext.add_provider_for_display(self.get_display(),provider,Gtk.STYLE_PROVIDER_PRIORITY_USER)

    @GObject.Signal(return_type=bool, arg_types=(object,))
    def item_added(self,*args): 
        pass
        
    def set_items(self,items):
        widget = self.tools.get_first_child()
        while widget:
            next_widget = widget.get_next_sibling()
            self.tools.remove(widget)
            widget = next_widget

        for text,action,icon in items:
            def callback(sender,text,obj_make):
                if text == '图片':
                    self.image_add(obj_make)
                else:
                    obj_make()

            button = Gtk.Button()
            button.connect('clicked',callback, text, action)
            button.set_label(text)
            button.set_size_request(50,50)
            if icon: button.set_icon_name(icon)
            self.tools.append(button)
    
    def image_add(self,obj_make):
        dialog = Gtk.FileDialog()
        dialog.set_modal(True)

        filter_text = Gtk.FileFilter()
        filter_text.set_name("图片文件")
        filter_text.add_pattern("*.png")
        filter_text.add_pattern("*.jpg")
        filter_text.add_pattern("*.jpeg")
        
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(filter_text)
        dialog.set_filters(filters)
        dialog.set_default_filter(filter_text)

        def open_file(dialog, result): 
            file_path = None
            try:
                file = dialog.open_finish(result)
                file_path = file.get_path()
            except:
                return
            else:
                im = Image.open(file_path)
                image_array = np.array(im)
                obj_make(image_array)

        dialog.open(None, None, open_file) 


@Gtk.Template(filename='ui/propbar.ui')
class Propbar (Gtk.ScrolledWindow):
    __gtype_name__ = "Propbar"
    tools = Gtk.Template.Child('tools')
    spin_x = Gtk.Template.Child('x')
    spin_y = Gtk.Template.Child('y')
    spin_w = Gtk.Template.Child('w')
    spin_h = Gtk.Template.Child('h')
    spin_rotate = Gtk.Template.Child('rotate')
    entry_text = Gtk.Template.Child('text')
    btn_remove = Gtk.Template.Child('remove')
    stack = Gtk.Template.Child('stack')

    def __init__(self):
        provider = Gtk.CssProvider.new()
        provider.load_from_path('ui/propbar.css')
        Gtk.StyleContext.add_provider_for_display(self.get_display(),provider,Gtk.STYLE_PROVIDER_PRIORITY_USER)

    @GObject.Signal(return_type=bool, arg_types=(object,))
    def item_removed(self,*args): 
        pass

    @Gtk.Template.Callback()
    def btn_remove_clicked(self,button):
        self.emit('item-removed',self.obj)

    def set_obj(self,obj):
        if not obj: return
        self.obj = obj
        self.spin_x.set_value(obj.local.position[0] * 1000)
        self.spin_y.set_value(obj.local.position[1] * 1000)
        aabb = self.obj.get_geometry_bounding_box()
        width = aabb[1][0] - aabb[0][0]
        height = aabb[1][1] - aabb[0][1]
        self.spin_w.set_value(width * obj.local.scale[0] * 1000)
        self.spin_h.set_value(height * obj.local.scale[1] * 1000)
        self.spin_rotate.set_value(-m.degrees(obj.local.euler_z))

        if obj.__class__.__name__ == 'Label':
            self.entry_text.set_text(obj.text)
            obj.font_size
            obj.family

        self.stack.set_visible_child_name(obj.__class__.__name__)

