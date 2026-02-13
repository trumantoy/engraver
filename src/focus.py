import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Gio, GObject

import subprocess as sp
import numpy as np
                    
@Gtk.Template(filename='ui/focus.ui')
class FocusDialog (Gtk.Window):
    __gtype_name__ = "FocusDialog"

    up = Gtk.Template.Child("up")
    down = Gtk.Template.Child("down")
    spin = Gtk.Template.Child("focus_value")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connect("close-request", self.close_request)

    def close_request(self, widget):
        self.controller.excute('M5\n')

    def set_controller(self, controller):
        self.controller = controller
        self.controller.excute('M3\nG1 S0\n')

    @Gtk.Template.Callback()
    def on_power_value_value_changed(self, widget):
        n = widget.get_value()
        self.controller.excute(f'G1 S{n}\n')

    @Gtk.Template.Callback()
    def up_clicked(self, widget):
        print("up clicked")
        n = self.spin.get_value()
        self.controller.excute(f'G91\nG1 Z{n}\nG90\n')

    @Gtk.Template.Callback()
    def down_clicked(self, widget):
        print("down clicked")
        n = self.spin.get_value()
        self.controller.excute(f'G91\nG1 Z{-n}\nG90\n')