import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

class ConfigEditor(Gtk.Window):
    __gtype_name__ = "ConfigEditor"

    def __init__(self, parent, name: str, initial_content: str, on_save, is_new: bool = False):
        super().__init__(transient_for=parent)
        self.set_title("New Tunnel" if is_new else f"Editing {name}")
        self.set_modal(True)
        self.set_default_size(600, 500)
        
        self.name = name
        self.on_save_cb = on_save
        self.is_new = is_new
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_child(vbox)
        
        # Toolbar
        header = Gtk.HeaderBar()
        self.set_titlebar(header)
        
        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda _: self.close())
        header.pack_start(cancel_btn)
        
        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        save_btn.connect("clicked", self._on_save)
        header.pack_end(save_btn)
        
        # Name Entry (Always present)
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        name_box.set_margin_top(10)
        name_box.set_margin_start(10)
        name_box.set_margin_end(10)
        name_box.set_margin_bottom(10)
        lbl = Gtk.Label(label="Tunnel Name:")
        self.name_entry = Gtk.Entry()
        self.name_entry.set_text(self.name)
        self.name_entry.set_hexpand(True)
        name_box.append(lbl)
        name_box.append(self.name_entry)
        vbox.append(name_box)
        
        # Editor
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.textview = Gtk.TextView()
        self.textview.set_monospace(True)
        self.textview.set_wrap_mode(Gtk.WrapMode.NONE)
        self.textview.set_left_margin(10)
        self.textview.set_right_margin(10)
        self.textview.set_top_margin(10)
        self.textview.set_bottom_margin(10)
        
        buffer = self.textview.get_buffer()
        buffer.set_text(initial_content)
        
        scrolled.set_child(self.textview)
        vbox.append(scrolled)

    def _on_save(self, btn):
        buffer = self.textview.get_buffer()
        start = buffer.get_start_iter()
        end = buffer.get_end_iter()
        content = buffer.get_text(start, end, True)
        
        final_name = self.name_entry.get_text().strip()
        if not final_name:
            return  # Don't save empty name
                
        self.on_save_cb(self.name, final_name, content)
        self.close()
