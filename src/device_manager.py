import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Gio

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

    btn_add = Gtk.Template.Child("add")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
        # model = Gtk.StringList.new(['a','b','c'])
        # selection_model = Gtk.SingleSelection.new(model)
        # selection_model.set_autoselect(True)
        # selection_model.set_can_unselect(False)
        
        # factory = Gtk.SignalListItemFactory()
        # factory.connect("setup", self.setup_listitem)
        # factory.connect("bind", self.bind_listitem)

        # self.lsv_usb_list.set_model(selection_model)
        # self.lsv_usb_list.set_factory(factory)
        # self.btn_usb_refresh.emit('clicked')
        
        # self.result = None
        
    def setup_listitem(self, factory, listitem):
        label = Gtk.Label()
        listitem.set_child(label)

    def bind_listitem(self, factory, listitem):
        label = listitem.get_child()
        label.set_text(listitem.get_item().get_string())

    @Gtk.Template.Callback()
    def btn_add_clicked(self, sender):
        from device_discovery import DeviceDiscoveryDialog
        dlg = DeviceDiscoveryDialog()
        dlg.set_modal(True)
        dlg.set_transient_for(self.get_root())
        dlg.connect('close-request', self.device_discovery_closed)
        dlg.present()

    def device_discovery_closed(self, dlg):
        print(dlg.result)
        
