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

@Gtk.Template(filename='ui/consumable.ui')
class ConsumableDialog (Gtk.Window):
    __gtype_name__ = "ConsumableDialog"
        
    giv_consumables = Gtk.Template.Child("consumables")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        model = Gio.ListStore(item_type=GObject.Object)
        item = GObject.Object()
        item.label = '未知材料'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 椴木板
        item = GObject.Object()
        item.label = '椴木板'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 椴木胶合板
        item = GObject.Object()
        item.label = '椴木胶合板'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 黑胡桃胶合板
        item = GObject.Object()
        item.label = '黑胡桃胶合板'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 松木胶合板
        item = GObject.Object()
        item.label = '松木胶合板'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 白蜡胶合板
        item = GObject.Object()
        item.label = '白蜡胶合板'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 卡丝楠胶合板
        item = GObject.Object()
        item.label = '卡丝楠胶合板'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 樱桃胶合板
        item = GObject.Object()
        item.label = '樱桃胶合板'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 黑色金属名片
        item = GObject.Object()
        item.label = '黑色金属名片'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 蓝色金属名片
        item = GObject.Object()
        item.label = '蓝色金属名片'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 紫色金属名片
        item = GObject.Object()
        item.label = '紫色金属名片'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 不锈钢
        item = GObject.Object()
        item.label = '不锈钢'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 黄金
        item = GObject.Object()
        item.label = '黄金'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 白银
        item = GObject.Object()
        item.label = '白银'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 铝合金
        item = GObject.Object()
        item.label = '铝合金'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 原色黄铜
        item = GObject.Object()
        item.label = '原色黄铜'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 黑色亚克力
        item = GObject.Object()
        item.label = '黑色亚克力'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 板岩
        item = GObject.Object()
        item.label = '板岩'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 橡胶垫
        item = GObject.Object()
        item.label = '橡胶垫'
        item.image = 'res/栅格图.png'
        model.append(item)

        # 皮革
        item = GObject.Object()
        item.label = '皮革'
        item.image = 'res/栅格图.png'
        model.append(item)

        
        self.selection = Gtk.SingleSelection.new(model)
        self.selection.set_autoselect(True)
        self.selection.set_can_unselect(False)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.setup_listitem)
        factory.connect("bind", self.bind_listitem)
        self.giv_consumables.set_factory(factory)
        self.giv_consumables.set_model(self.selection)
        self.giv_consumables.set_max_columns(10)
        
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
        model = self.giv_consumables.get_model()
        item = model.get_selected_item()
        if item: self.result = item
        self.close()
    
