import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Gio, GObject

import subprocess as sp
import numpy as np
import threading
import serial

from simtoy import *

class USBController:
    def __init__(self):
        self.serial = None
        self.name = ''
        self.steps = []        
        self.connected = False
        self.mutex = threading.Lock()
        self.event = threading.Event()
        threading.Thread(target=self.worker,daemon=True).start()

    
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
    
        self.connected = self.is_connected()
        return self.connected
    
    def disconnect(self):
        if self.serial:
            self.serial.close()

    def is_connected(self):
        import time
        with self.mutex:
            if not self.serial: return False
            
            try:
                self.serial.write(b'$I\n')
                time.sleep(0)
                res = self.serial.readall().decode()
                
                if '[MODEL:' not in res:
                    return False

                model_start = res.find('[MODEL:') + len('[MODEL:')
                model_end = res.find(']', model_start)
                if model_start > 0 and model_end > model_start:
                    self.name = res[model_start:model_end]
            except:
                import traceback as tb
                tb.print_exc()
                return False
        return True

    def set_pulse(self):
        with self.mutex:
            req = f'$222P1P400\n'.encode()
            self.serial.write(req)
            res = self.serial.readline()

    def set_axes_invert(self):
        with self.mutex:
            req = f'$240P3P6P5P1\n'.encode()
            self.serial.write(req)
            res = self.serial.readline()
            
    def set_process_params(self):
        with self.mutex:
            req = f'T0 C25\n'.encode()
            self.serial.write(req)
            res = self.serial.readline()
            
    def excute(self, gcode:str):
        for line in gcode.splitlines(True):
            if not line.strip(): continue
            if line.strip().startswith(';'): continue
            req = line.encode()
            self.steps.append(req)
        self.event.set()

    def worker(self):
        import time
                                                       
        while True:
            count = len(self.steps)
            sent = 0
            received = 0
            limit = 500

            with self.mutex:
                while count or received < sent:
                    req = self.steps[:received + limit - sent]

                    if req:
                        s = b''.join(req)
                        self.serial.write(s)
                        self.steps = self.steps[len(req):]
                        sent += len(req)
                        count -= len(req)

                    res = self.serial.read_all().splitlines(True)

                    if res: 
                        received += len(res)

            time.sleep(0.1)
          
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
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        model = self.selection.get_model()
        model.remove_all()

        for port in [port.device for port in ports]:
            print(port,flush=True)
            controller = USBController()
            if not controller.connect(port): continue
            controller.set_pulse()
            controller.set_axes_invert()
            controller.set_process_params()
            device = GObject.Object()
            device.controller = controller
            self.selection.get_model().append(device)
