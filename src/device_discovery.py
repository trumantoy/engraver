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
import serial

from simtoy import *

class USBController:
    def __init__(self):
        """初始化Grbl控制器连接"""
        self.serial = None
        
    def connect(self,port):
        """连接到Grbl控制器"""
        try:
            # 初始化串口（根据实际设备修改参数）
            self.serial = serial.Serial(port=port,baudrate=9600,timeout=1)

            # 检查串口是否打开
            if not self.serial.is_open:
                self.serial = None
                print("串口打开失败") 
                return False
            
        except Exception as e:
            self.serial = None
            print(f"连接失败: {str(e)}")
            return False

        print(f"串口 {self.serial.name} 已打开")
        return True
    
    def disconnect(self):
        """断开与Grbl控制器的连接"""
        if self.serial:
            self.serial.close()
            print("已断开与Grbl控制器的连接")


    def set_axes_invert(self):
        """设置轴 invert"""
        req = f'$240P2P6P5\n'.encode()
        print(req)
        self.serial.write(req)
        res = self.serial.readline()
        print(res)

    def set_process_params(self):
        """
        T：参数识别 F:速度 S:功率 C:频率 D:占空比 E:开光延时
        H:关光延时 U:跳转延时
        单位F:mm/s S[0-100]% Cus Dus EHUms
        1kHz占空比50%  C：1000 D：500
        """

        req = f'T0 C22\n'.encode()
        print(req)
        self.serial.write(req)
        res = self.serial.readline()
        print(res)
    
    def excute(self, lines):
        queue_size = self.get_queue_size()
        print('queue_size',queue_size)   

        for line in lines:
            req = f'{line}\n'.encode()
            self.serial.write(req)
        
        for _ in range(len(lines)):
            self.serial.readline()
    
    def get_queue_size(self):
        """获取Grbl接收缓存队列余量"""
        req = '%\n'.encode()
        print(req)
        self.serial.write(req)
        res = self.serial.readline()
        print(res)
        return int(res.decode().split(':')[1])
    
    def get_status(self):
        """获取Grbl状态信息"""
        if not self.connected:
            print("未连接到控制器，请先连接")
            return None
            
        try:
            # 发送状态请求
            self.serial.write(b'?')
            response = self.serial.readline().decode('utf-8').strip()
            return response
        except Exception as e:
            print(f"获取状态出错: {str(e)}")
            return None

@Gtk.Template(filename='ui/device_discovery.ui')
class DeviceDiscoveryDialog (Gtk.Window):
    __gtype_name__ = "DeviceDiscoveryDialog"

    lsv_usb_list = Gtk.Template.Child("usb_list")
    btn_usb_refresh = Gtk.Template.Child("usb_refresh")
    btn_usb_add = Gtk.Template.Child("usb_add")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
        model = Gtk.StringList.new(['a','b','c'])
        selection_model = Gtk.SingleSelection.new(model)
        selection_model.set_autoselect(True)
        selection_model.set_can_unselect(False)
        
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_listitem)
        factory.connect("bind", self.bind_listitem)

        self.lsv_usb_list.set_model(selection_model)
        self.lsv_usb_list.set_factory(factory)
        self.btn_usb_refresh.emit('clicked')

        self.result = None
        
    def setup_listitem(self, factory, listitem):
        label = Gtk.Label()
        listitem.set_child(label)

    def bind_listitem(self, factory, listitem):
        label = listitem.get_child()
        label.set_text(listitem.get_item().get_string())

    @Gtk.Template.Callback()
    def btn_usb_add_clicked(self, sender):
        model = self.lsv_usb_list.get_model()
        item = model.get_selected_item()
        if item: 
            self.result = item.get_string()
            self.usb_controller.set_axes_invert()
            self.usb_controller.set_process_params()
        
        self.close()

    @Gtk.Template.Callback()
    def btn_usb_refresh_clicked(self, sender):
        import serial.tools.list_ports
        ports = serial.tools.list_ports.comports()
        devices = [port.device for port in ports]
        model = Gtk.StringList.new(devices)
        selection_model = self.lsv_usb_list.get_model()
        selection_model.set_model(model)