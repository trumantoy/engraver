import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Gio, GObject

import subprocess as sp
import numpy as np
import os
import threading
import shutil
import zipfile
import trimesh
import io
import serial

from simtoy import *

class USBController:
    def __init__(self):
        self.serial = None
        self.name = ''
        self.steps = []
        threading.Thread(target=self.worker,daemon=True).start()
        self.mutex = threading.Lock()
        self.event = threading.Event()
    
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
        
        return self.is_connected()
    
    def disconnect(self):
        if self.serial:
            self.serial.close()

    def is_connected(self):
        if not self.serial: return False
        
        try:
            self.serial.write(b'$I\n')
            res = self.serial.readall().decode()
            print(res)
            
            if '[MODEL:' not in res:
                return False

            model_start = res.find('[MODEL:') + len('[MODEL:')
            model_end = res.find(']', model_start)
            if model_start > 0 and model_end > model_start:
                self.name = res[model_start:model_end]
        except:
            return False
        
        return True
    
    def set_axes_invert(self):
        req = f'$240P2P6P5\n'.encode()
        self.serial.write(req)
        res = self.serial.readline()

    def set_process_params(self):
        req = f'T0 C22\n'.encode()
        self.serial.write(req)
        res = self.serial.readline()
    
    def excute(self, gcode:str):
        for line in gcode.splitlines(True):
            if not line or line.startswith(';'): continue
            req = line.encode()
            self.steps.append(req)
            print(req)
        
        self.event.set()
            
    def worker(self):
        limit = 100
        sent = 0
        while True:
            self.event.wait()

            for i in range(len(self.steps)):
                req = self.steps.pop(0)
                self.serial.write(req)
                sent += 1
                if sent > limit: sent -= len(self.serial.readlines())
            

    def get_queue_size(self):
        req = '%\n'.encode()
        self.serial.write(req)
        res = self.serial.readline()
        return int(res.decode().split(':')[1])

@Gtk.Template(filename='ui/device_discovery.ui')
class DeviceDiscoveryDialog (Gtk.Window):
    __gtype_name__ = "DeviceDiscoveryDialog"

    lsv_usb_list = Gtk.Template.Child("usb_list")
    btn_usb_refresh = Gtk.Template.Child("usb_refresh")
    btn_usb_add = Gtk.Template.Child("usb_add")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
        model = Gio.ListStore(item_type=GObject.Object)
        self.selection = Gtk.SingleSelection.new(model)
        self.selection.set_autoselect(True)
        self.selection.set_can_unselect(True)
        
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_listitem)
        factory.connect("bind", self.bind_listitem)

        self.lsv_usb_list.set_model(self.selection)
        self.lsv_usb_list.set_factory(factory)
        self.btn_usb_refresh.emit('clicked')

        self.result = None
        
    def setup_listitem(self, factory, listitem):
        label = Gtk.Label()
        listitem.set_child(label)

    def bind_listitem(self, factory, listitem):
        label = listitem.get_child()
        device = listitem.get_item()
        label.set_text(device.controller.name)

    @Gtk.Template.Callback()
    def btn_usb_add_clicked(self, sender):
        model = self.lsv_usb_list.get_model()
        item = model.get_selected_item()
        if item: self.result = item.controller
        self.close()

    @Gtk.Template.Callback()
    def btn_usb_refresh_clicked(self, sender):
        def f():
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            for port in [port.device for port in ports]:
                controller = USBController()
                if not controller.connect(port): continue
                controller.set_axes_invert()
                controller.set_process_params()
                device = GObject.Object()
                device.controller = controller
                GLib.idle_add(lambda: self.selection.get_model().append(device))

        threading.Thread(target=f,daemon=True).start()

