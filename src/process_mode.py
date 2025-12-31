import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, GObject, Gio, Gdk

import subprocess as sp
import numpy as np
import os
import threading
import shutil
import zipfile
import trimesh
import io
from simtoy import *

@Gtk.Template(filename='ui/process_mode.ui')
class ProcessModeDialog (Gtk.Window):
    __gtype_name__ = "ProcessModeDialog"
        
    giv_process_modes = Gtk.Template.Child("process_modes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model = Gio.ListStore(item_type=GObject.Object)
        item = GObject.Object()
        item.label = '平面加工'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 椴木板
        item = GObject.Object()
        item.label = '浮雕加工'
        item.image = 'res/栅格图.png'
        model.append(item)

        
        self.selection = Gtk.SingleSelection.new(model)
        self.selection.set_autoselect(True)
        self.selection.set_can_unselect(False)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_listitem)
        factory.connect("bind", self.bind_listitem)
        self.giv_process_modes.set_factory(factory)
        self.giv_process_modes.set_model(self.selection)
        self.giv_process_modes.set_max_columns(10)
        
        self.result = None

    def setup_listitem(self, factory, listitem):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        image = Gtk.Image()
        image.set_pixel_size(100)
        box.append(image)
        label = Gtk.Label()
        box.append(label)
        listitem.set_child(box)

    def bind_listitem(self, factory, listitem):
        item = listitem.get_item()
        box = listitem.get_child()
        img = box.get_first_child()
        img.set_from_file(item.image)
        lbl = img.get_next_sibling()
        lbl.set_text(item.label)


    @Gtk.Template.Callback()
    def btn_ok_clicked(self, sender):
        model = self.giv_process_modes.get_model()
        item = model.get_selected_item()
        if item: self.result = item
        self.close()
    
