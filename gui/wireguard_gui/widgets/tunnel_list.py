"""Tunnel list sidebar widget."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Gdk, GObject, Pango


class TunnelRow(Gtk.ListBoxRow):
    """A single tunnel entry in the sidebar list."""

    __gtype_name__ = "TunnelRow"

    def __init__(self, name: str, state: str = "inactive"):
        super().__init__()
        self.tunnel_name = name

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(12)
        box.set_margin_end(12)

        # Status indicator dot
        self._status_dot = Gtk.DrawingArea()
        self._status_dot.set_size_request(12, 12)
        self._status_dot.set_valign(Gtk.Align.CENTER)
        self._state = state
        self._status_dot.set_draw_func(self._draw_status)
        box.append(self._status_dot)

        # Tunnel name label
        self._label = Gtk.Label(label=name)
        self._label.set_halign(Gtk.Align.START)
        self._label.set_hexpand(True)
        self._label.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(self._label)

        # State label (small, dimmed)
        self._state_label = Gtk.Label(label=state)
        self._state_label.add_css_class("dim-label")
        self._state_label.add_css_class("caption")
        self._state_label.set_halign(Gtk.Align.END)
        box.append(self._state_label)

        self.set_child(box)

    def update_state(self, state: str):
        """Update the displayed state."""
        self._state = state
        self._state_label.set_label(state)
        self._status_dot.queue_draw()

    def _draw_status(self, area, cr, width, height):
        """Draw the colored status dot."""
        colors = {
            "active": (0.2, 0.8, 0.2),      # green
            "inactive": (0.6, 0.6, 0.6),     # gray
            "error": (0.9, 0.2, 0.2),        # red
        }
        r, g, b = colors.get(self._state, (0.6, 0.6, 0.6))

        cr.set_source_rgb(r, g, b)
        cr.arc(width / 2, height / 2, min(width, height) / 2 - 1, 0, 6.283)
        cr.fill()


class TunnelList(Gtk.Box):
    """Sidebar containing the list of tunnels and action buttons."""

    __gtype_name__ = "TunnelList"
    __gsignals__ = {
        "tunnel-selected": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "import-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "create-requested": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.set_size_request(220, -1)

        self._rows: dict[str, TunnelRow] = {}

        # Header with title
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        header.set_margin_top(8)
        header.set_margin_bottom(8)
        header.set_margin_start(12)
        header.set_margin_end(8)

        title = Gtk.Label(label="Tunnels")
        title.add_css_class("title-4")
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        header.append(title)

        # Create button
        create_btn = Gtk.Button()
        create_btn.set_icon_name("document-new-symbolic")
        create_btn.set_tooltip_text("Create new config")
        create_btn.add_css_class("flat")
        create_btn.connect("clicked", self._on_create_clicked)
        header.append(create_btn)

        # Import button
        import_btn = Gtk.Button()
        import_btn.set_icon_name("document-open-symbolic")
        import_btn.set_tooltip_text("Import tunnel config (.conf)")
        import_btn.add_css_class("flat")
        import_btn.connect("clicked", self._on_import_clicked)
        header.append(import_btn)

        self.append(header)

        # Separator
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # Scrolled list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self._listbox.add_css_class("navigation-sidebar")
        self._listbox.connect("row-selected", self._on_row_selected)

        # Custom icon
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        try:
            import os
            res_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons")
            icon_path = os.path.join(res_dir, "wireguard-logo.png")
            if os.path.exists(icon_path):
                texture = Gdk.Texture.new_from_filename(icon_path)
        except Exception:
            pass

        # Placeholder for empty list
        placeholder = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        placeholder.set_valign(Gtk.Align.CENTER)
        placeholder.set_margin_top(24)
        placeholder.set_margin_bottom(24)
        
        # Try to use the downloaded logo if available, else fallback
        try:
            import os
            res_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons")
            icon_path = os.path.join(res_dir, "wireguard-logo.png")
            if os.path.exists(icon_path):
                icon = Gtk.Image.new_from_file(icon_path)
            else:
                icon = Gtk.Image.new_from_icon_name("network-vpn-symbolic")
        except:
            icon = Gtk.Image.new_from_icon_name("network-vpn-symbolic")

        icon.set_pixel_size(48)
        icon.add_css_class("dim-label")
        placeholder.append(icon)
        lbl = Gtk.Label(label="No tunnels found")
        lbl.add_css_class("dim-label")
        placeholder.append(lbl)
        hint = Gtk.Label(label="Place .conf files in\n/etc/wireguard/\nor click + to import")
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        hint.set_justify(Gtk.Justification.CENTER)
        placeholder.append(hint)
        self._listbox.set_placeholder(placeholder)

        scrolled.set_child(self._listbox)
        self.append(scrolled)

    def set_tunnels(self, tunnels: list):
        """Populate the list with tunnel info objects."""
        # Remember current selection
        selected_name = None
        selected_row = self._listbox.get_selected_row()
        if selected_row and isinstance(selected_row, TunnelRow):
            selected_name = selected_row.tunnel_name

        # Clear existing rows
        while True:
            row = self._listbox.get_row_at_index(0)
            if row is None:
                break
            self._listbox.remove(row)
        self._rows.clear()

        # Add new rows
        reselect_row = None
        for t in sorted(tunnels, key=lambda x: x.name):
            row = TunnelRow(t.name, t.state)
            self._listbox.append(row)
            self._rows[t.name] = row
            if t.name == selected_name:
                reselect_row = row

        # Restore selection
        if reselect_row:
            self._listbox.select_row(reselect_row)
        elif len(self._rows) > 0:
            first = self._listbox.get_row_at_index(0)
            if first:
                self._listbox.select_row(first)

    def update_tunnel_state(self, name: str, state: str):
        """Update the state of a specific tunnel row."""
        if name in self._rows:
            self._rows[name].update_state(state)

    def select_tunnel(self, name: str):
        for i in range(255):  # Arbitrary limit to prevent infinite loops theoretically, get_row_at_index returns None when out of bounds
            row = self._listbox.get_row_at_index(i)
            if not row:
                break
            if isinstance(row, TunnelRow) and row.tunnel_name == name:
                self._listbox.select_row(row)
                break

    def _on_row_selected(self, listbox, row):
        if row and isinstance(row, TunnelRow):
            self.emit("tunnel-selected", row.tunnel_name)

    def _on_import_clicked(self, button):
        self.emit("import-requested")

    def _on_create_clicked(self, button):
        self.emit("create-requested")
