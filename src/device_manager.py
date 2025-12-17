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

@Gtk.Template(filename='ui/device_manager.ui')
class DeviceManagerDialog (Gtk.Window):
    __gtype_name__ = "DeviceManagerDialog"

    lsv_devices = Gtk.Template.Child("devices")
    btn_add = Gtk.Template.Child("add")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)       
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_listitem)
        factory.connect("bind", self.bind_listitem)
        self.lsv_devices.set_factory(factory)        
        self.result = None
        
    def setup_listitem(self, factory, listitem):
        label = Gtk.Label()
        listitem.set_child(label)

    def bind_listitem(self, factory, listitem):
        label = listitem.get_child()
        device = listitem.get_item()
        label.set_text(device.controller.name)

    @Gtk.Template.Callback()
    def btn_add_clicked(self, sender):
        from device_discovery import DeviceDiscoveryDialog
        dlg = DeviceDiscoveryDialog()
        dlg.set_modal(True)
        dlg.connect('close-request', self.device_discovery_closed)
        dlg.present()

    def device_discovery_closed(self, dlg):
        if dlg.result:
            self.add_device(dlg.result)
   
    def add_device(self, controller):
        device_selection = self.lsv_devices.get_model()
        device = GObject.Object()
        device.controller = controller
        device_selection.get_model().append(device)
