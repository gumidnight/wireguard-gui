"""Tunnel detail panel widget — shows config and live stats."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, GObject, Pango
from wireguard_gui.widgets.config_editor import ConfigEditor
from datetime import datetime, timezone


def format_bytes(n: int) -> str:
    """Format byte count to human-readable string."""
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KiB"
    elif n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MiB"
    else:
        return f"{n / (1024 * 1024 * 1024):.2f} GiB"


def format_handshake(iso_str: str) -> str:
    """Format handshake timestamp to relative time string."""
    if not iso_str:
        return "Never"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s ago"
        elif seconds < 86400:
            return f"{seconds // 3600}h {(seconds % 3600) // 60}m ago"
        else:
            return f"{seconds // 86400}d ago"
    except (ValueError, TypeError):
        return iso_str


class TunnelDetail(Gtk.Box):
    """Right panel showing tunnel details and live stats."""

    __gtype_name__ = "TunnelDetail"
    __gsignals__ = {
        "activate-requested": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "deactivate-requested": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "delete-requested": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
        "edit-requested": (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._current_tunnel = None

        # ── Header bar with tunnel name and toggle ──
        self._header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._header.set_margin_top(12)
        self._header.set_margin_bottom(12)
        self._header.set_margin_start(16)
        self._header.set_margin_end(16)

        self._name_label = Gtk.Label(label="No tunnel selected")
        self._name_label.add_css_class("title-2")
        self._name_label.set_halign(Gtk.Align.START)
        self._name_label.set_hexpand(True)
        self._name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._header.append(self._name_label)
        
        # Edit button
        self._edit_btn = Gtk.Button()
        self._edit_btn.set_icon_name("document-edit-symbolic")
        self._edit_btn.set_tooltip_text("Edit config")
        self._edit_btn.add_css_class("flat")
        self._edit_btn.set_sensitive(False)
        self._edit_btn.connect("clicked", self._on_edit_clicked)
        self._header.append(self._edit_btn)

        # Delete button
        self._delete_btn = Gtk.Button()
        self._delete_btn.set_icon_name("user-trash-symbolic")
        self._delete_btn.set_tooltip_text("Delete tunnel")
        self._delete_btn.add_css_class("flat")
        self._delete_btn.add_css_class("destructive-action")
        self._delete_btn.set_sensitive(False)
        self._delete_btn.connect("clicked", self._on_delete_clicked)
        self._header.append(self._delete_btn)

        self.append(self._header)
        self.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        # ── Content area (scrollable) ──
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._content.set_margin_top(16)
        self._content.set_margin_bottom(16)
        self._content.set_margin_start(16)
        self._content.set_margin_end(16)

        # Status row
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        status_box.append(Gtk.Label(label="Status:"))
        self._status_label = Gtk.Label(label="—")
        self._status_label.set_halign(Gtk.Align.START)
        status_box.append(self._status_label)
        self._content.append(status_box)

        # Activate/Deactivate button
        self._toggle_btn = Gtk.Button(label="Activate")
        self._toggle_btn.add_css_class("destructive-action")
        self._toggle_btn.add_css_class("pill")
        self._toggle_btn.set_sensitive(False)
        self._toggle_btn.connect("clicked", self._on_toggle_clicked)
        self._content.append(self._toggle_btn)

        # Error display
        self._error_bar = Gtk.InfoBar()
        self._error_bar.set_message_type(Gtk.MessageType.ERROR)
        self._error_bar.set_revealed(False)
        self._error_label = Gtk.Label()
        self._error_label.set_wrap(True)
        self._error_label.set_halign(Gtk.Align.START)
        self._error_bar.add_child(self._error_label)
        self._content.append(self._error_bar)

        # ── Interface info section ──
        self._content.append(self._make_section_label("Interface"))
        self._info_grid = Gtk.Grid()
        self._info_grid.set_column_spacing(12)
        self._info_grid.set_row_spacing(4)
        self._info_grid.set_margin_start(8)

        self._info_fields = {}
        fields = [
            ("Address", "address"),
            ("DNS", "dns"),
        ]
        for i, (label, key) in enumerate(fields):
            lbl = Gtk.Label(label=f"{label}:")
            lbl.add_css_class("dim-label")
            lbl.set_halign(Gtk.Align.START)
            val = Gtk.Label(label="—")
            val.set_halign(Gtk.Align.START)
            val.set_selectable(True)
            val.set_ellipsize(Pango.EllipsizeMode.END)
            self._info_grid.attach(lbl, 0, i, 1, 1)
            self._info_grid.attach(val, 1, i, 1, 1)
            self._info_fields[key] = val

        self._content.append(self._info_grid)

        # ── Peer info section ──
        self._content.append(self._make_section_label("Peer"))
        self._peer_grid = Gtk.Grid()
        self._peer_grid.set_column_spacing(12)
        self._peer_grid.set_row_spacing(4)
        self._peer_grid.set_margin_start(8)

        self._peer_fields = {}
        peer_fields = [
            ("Endpoint", "endpoint"),
            ("Allowed IPs", "allowed_ips"),
            ("Public Key", "public_key"),
            ("Latest Handshake", "handshake"),
            ("Transfer ↓", "transfer_rx"),
            ("Transfer ↑", "transfer_tx"),
        ]
        for i, (label, key) in enumerate(peer_fields):
            lbl = Gtk.Label(label=f"{label}:")
            lbl.add_css_class("dim-label")
            lbl.set_halign(Gtk.Align.START)
            val = Gtk.Label(label="—")
            val.set_halign(Gtk.Align.START)
            val.set_selectable(True)
            val.set_ellipsize(Pango.EllipsizeMode.END)
            self._peer_grid.attach(lbl, 0, i, 1, 1)
            self._peer_grid.attach(val, 1, i, 1, 1)
            self._peer_fields[key] = val

        self._content.append(self._peer_grid)

        # ── Config view (collapsible) ──
        self._content.append(self._make_section_label("Configuration"))
        self._config_view = Gtk.TextView()
        self._config_view.set_editable(False)
        self._config_view.set_monospace(True)
        self._config_view.add_css_class("card")
        self._config_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self._config_view.set_margin_start(8)
        self._config_view.set_margin_end(8)
        config_frame = Gtk.Frame()
        config_frame.set_child(self._config_view)
        self._content.append(config_frame)

        scrolled.set_child(self._content)
        self.append(scrolled)
        self._scrolled = scrolled

        # ── Empty state (shown initially) ──
        self._empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self._empty.set_valign(Gtk.Align.CENTER)
        self._empty.set_halign(Gtk.Align.CENTER)
        self._empty.set_vexpand(True)
        
        # Try to use WireGuard logo
        import os
        try:
            res_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "icons")
            icon_path = os.path.join(res_dir, "wireguard.png")
            if os.path.exists(icon_path):
                icon = Gtk.Image.new_from_file(icon_path)
            else:
                 icon = Gtk.Image.new_from_icon_name("network-vpn-symbolic")
        except:
             icon = Gtk.Image.new_from_icon_name("network-vpn-symbolic")

        icon.set_pixel_size(64)
        icon.add_css_class("dim-label")
        self._empty.append(icon)
        self._empty.append(Gtk.Label(label="Select a tunnel"))
        
        self.append(self._empty)

        # Show empty state initially
        self._scrolled.set_visible(False)
        self._content.set_visible(False)
        self._delete_btn.set_visible(False)

    def show_tunnel(self, tunnel_info, config_text: str = ""):
        """Display tunnel information."""
        self._current_tunnel = tunnel_info
        self._empty.set_visible(False)
        self._content.set_visible(True)
        self._scrolled.set_visible(True)
        self._edit_btn.set_sensitive(True)
        self._delete_btn.set_visible(True)
        self._delete_btn.set_sensitive(True)
        self._toggle_btn.set_sensitive(True)

        self._name_label.set_label(tunnel_info.name)

        # Status
        state = tunnel_info.state
        self._status_label.set_label(state.capitalize())

        # Reset CSS classes on status label
        for cls in ["success", "error", "dim-label"]:
            self._status_label.remove_css_class(cls)
        if state == "active":
            self._status_label.add_css_class("success")
        elif state == "error":
            self._status_label.add_css_class("error")
        else:
            self._status_label.add_css_class("dim-label")

        # Toggle button
        if state == "active":
            self._toggle_btn.set_label("Deactivate")
            self._toggle_btn.remove_css_class("destructive-action")
        else:
            self._toggle_btn.set_label("Activate")
            self._toggle_btn.add_css_class("destructive-action")

        # Error bar
        if tunnel_info.error:
            self._error_label.set_label(tunnel_info.error)
            self._error_bar.set_revealed(True)
        else:
            self._error_bar.set_revealed(False)

        # Interface info
        self._info_fields["address"].set_label(tunnel_info.address or "—")
        self._info_fields["dns"].set_label(tunnel_info.dns or "—")

        # Peer info (basic, from config)
        self._peer_fields["endpoint"].set_label(tunnel_info.endpoint or "—")
        self._peer_fields["allowed_ips"].set_label(tunnel_info.allowed_ips or "—")
        self._peer_fields["public_key"].set_label("—")
        self._peer_fields["handshake"].set_label("—")
        self._peer_fields["transfer_rx"].set_label("—")
        self._peer_fields["transfer_tx"].set_label("—")

        # Config text
        buf = self._config_view.get_buffer()
        buf.set_text(config_text or "(no config)")

    def update_stats(self, stats):
        """Update live stats display."""
        if stats and stats.peers:
            peer = stats.peers[0]  # Show first peer
            self._peer_fields["public_key"].set_label(
                peer.public_key[:16] + "..." if len(peer.public_key) > 16 else peer.public_key
            )
            self._peer_fields["endpoint"].set_label(peer.endpoint or "—")
            self._peer_fields["allowed_ips"].set_label(peer.allowed_ips or "—")
            self._peer_fields["handshake"].set_label(format_handshake(peer.latest_handshake))
            self._peer_fields["transfer_rx"].set_label(format_bytes(peer.transfer_rx))
            self._peer_fields["transfer_tx"].set_label(format_bytes(peer.transfer_tx))

    def show_empty(self):
        """Show the empty state."""
        self._current_tunnel = None
        self._empty.set_visible(True)
        self._content.set_visible(False)
        self._scrolled.set_visible(False)
        self._edit_btn.set_sensitive(False)
        self._delete_btn.set_visible(False)
        self._toggle_btn.set_sensitive(False)
        self._name_label.set_label("No tunnel selected")

    def _make_section_label(self, text: str) -> Gtk.Label:
        lbl = Gtk.Label(label=text)
        lbl.add_css_class("title-4")
        lbl.set_halign(Gtk.Align.START)
        lbl.set_margin_top(8)
        return lbl

    def _on_toggle_clicked(self, button):
        if not self._current_tunnel:
            return
        if self._current_tunnel.state == "active":
            self.emit("deactivate-requested", self._current_tunnel.name)
        else:
            self.emit("activate-requested", self._current_tunnel.name)

    def _on_delete_clicked(self, button):
        if self._current_tunnel:
            self.emit("delete-requested", self._current_tunnel.name)

    def _on_edit_clicked(self, button):
        if self._current_tunnel:
            self.emit("edit-requested", self._current_tunnel.name)
