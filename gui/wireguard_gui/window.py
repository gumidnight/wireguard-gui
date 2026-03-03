"""Main application window."""

import logging
import os

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Gdk, Adw, GLib, Gio

from wireguard_gui.services.dbus_client import DaemonClient, TunnelInfo
from wireguard_gui.widgets.tunnel_list import TunnelList
from wireguard_gui.widgets.tunnel_detail import TunnelDetail
from wireguard_gui.widgets.config_editor import ConfigEditor

log = logging.getLogger(__name__)


class MainWindow(Adw.ApplicationWindow):
    """Main application window with sidebar + detail layout."""

    def __init__(self, app: Adw.Application, client: DaemonClient):
        super().__init__(application=app)
        self._client = client
        self._tunnels: dict[str, TunnelInfo] = {}
        self._selected_tunnel: str = ""
        self._poll_source = None

        self.set_title("WireGuard")
        
        # Load custom icon
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        res_dir = os.path.join(os.path.dirname(__file__), "resources", "icons")
        if os.path.isdir(res_dir):
            icon_theme.add_search_path(res_dir)
        self.set_icon_name("wireguard-gui")

        self.set_default_size(800, 520)
        self.set_size_request(600, 400)

        # ── Build UI ──
        self._build_ui()

        # ── Connect to daemon ──
        if not self._client.is_connected:
            if not self._client.connect():
                self._show_daemon_error()
                return

        # Subscribe to D-Bus signals
        self._client.subscribe_signals(
            state_cb=self._on_state_changed,
            stats_cb=self._on_stats_updated,
        )

        # Initial load
        self._refresh_tunnels()

        # Start poll timer as fallback (in case signals don't work)
        self._poll_source = GLib.timeout_add_seconds(3, self._poll_tick)

    def _build_ui(self):
        """Construct the window layout."""
        # Outer box
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Header bar
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)

        # Refresh button
        refresh_btn = Gtk.Button()
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Refresh tunnel list")
        refresh_btn.connect("clicked", lambda _: self._refresh_tunnels())
        header.pack_end(refresh_btn)

        outer.append(header)

        # Main content: sidebar + detail pane
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)
        paned.set_position(240)
        paned.set_vexpand(True)

        # Sidebar
        self._tunnel_list = TunnelList()
        self._tunnel_list.connect("tunnel-selected", self._on_tunnel_selected)
        self._tunnel_list.connect("import-requested", self._on_import_requested)
        self._tunnel_list.connect("create-requested", self._on_create_requested)
        paned.set_start_child(self._tunnel_list)

        # Detail panel
        self._detail = TunnelDetail()
        self._detail.connect("activate-requested", self._on_activate_requested)
        self._detail.connect("deactivate-requested", self._on_deactivate_requested)
        self._detail.connect("delete-requested", self._on_delete_requested)
        self._detail.connect("edit-requested", self._on_edit_requested)
        paned.set_end_child(self._detail)

        outer.append(paned)

        # Status bar
        self._statusbar = Gtk.Label(label="Connected to daemon")
        self._statusbar.add_css_class("dim-label")
        self._statusbar.add_css_class("caption")
        self._statusbar.set_halign(Gtk.Align.START)
        
        # Open Source link
        about_link = Gtk.LinkButton(uri="https://github.com/gumidnight/wireguard-gui")
        about_link.set_label("Open Source Project")
        about_link.add_css_class("caption")
        about_link.add_css_class("flat")
        about_link.add_css_class("destructive-action")
        about_link.set_halign(Gtk.Align.END)
        
        status_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        status_box.set_margin_start(12)
        status_box.set_margin_end(12)
        status_box.set_margin_top(4)
        status_box.set_margin_bottom(4)
        
        status_box.append(self._statusbar)
        status_box.append(Gtk.Label(label="   ")) # Spacer
        status_box.append(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)) # Filler
        status_box.get_last_child().set_hexpand(True)
        status_box.append(about_link)
        
        outer.append(status_box)

        self.set_content(outer)

    # ── Data Operations ──────────────────────────────────────────

    def _refresh_tunnels(self):
        """Fetch tunnel list from daemon and update UI."""
        tunnels = self._client.list_tunnels()
        self._tunnels = {t.name: t for t in tunnels}
        self._tunnel_list.set_tunnels(tunnels)
        self._statusbar.set_label(f"{len(tunnels)} tunnel(s)")
        log.info(f"Refreshed: {len(tunnels)} tunnels")

        # If we had a selected tunnel, re-show it
        if self._selected_tunnel and self._selected_tunnel in self._tunnels:
            self._show_tunnel_detail(self._selected_tunnel)

    def _show_tunnel_detail(self, name: str):
        """Show detail panel for a specific tunnel."""
        self._selected_tunnel = name
        t = self._tunnels.get(name)
        if not t:
            self._detail.show_empty()
            return

        config_text = self._client.get_config(name) or ""
        self._detail.show_tunnel(t, config_text)

        # If active, fetch fresh stats
        if t.is_active:
            stats = self._client.get_status(name)
            if stats:
                self._detail.update_stats(stats)

    def _poll_tick(self) -> bool:
        """Periodic polling fallback for stats updates."""
        if self._selected_tunnel and self._selected_tunnel in self._tunnels:
            t = self._tunnels[self._selected_tunnel]
            if t.is_active:
                stats = self._client.get_status(self._selected_tunnel)
                if stats:
                    self._detail.update_stats(stats)
        return True  # Keep timer running

    # ── Signal Handlers ──────────────────────────────────────────

    def _on_tunnel_selected(self, widget, name: str):
        self._show_tunnel_detail(name)

    def _on_activate_requested(self, widget, name: str):
        self._statusbar.set_label(f"Activating {name}...")
        self._set_ui_busy(True)

        def do_activate():
            success, error = self._client.activate(name)
            GLib.idle_add(self._on_activate_done, name, success, error)

        # Run in thread to not block UI
        import threading
        threading.Thread(target=do_activate, daemon=True).start()

    def _on_activate_done(self, name: str, success: bool, error: str):
        self._set_ui_busy(False)
        if success:
            self._statusbar.set_label(f"Activated {name}")
        else:
            self._statusbar.set_label(f"Failed to activate {name}")
            self._show_error_dialog(f"Failed to activate {name}", error)
        self._refresh_tunnels()

    def _on_deactivate_requested(self, widget, name: str):
        self._statusbar.set_label(f"Deactivating {name}...")
        self._set_ui_busy(True)

        def do_deactivate():
            success, error = self._client.deactivate(name)
            GLib.idle_add(self._on_deactivate_done, name, success, error)

        import threading
        threading.Thread(target=do_deactivate, daemon=True).start()

    def _on_deactivate_done(self, name: str, success: bool, error: str):
        self._set_ui_busy(False)
        if success:
            self._statusbar.set_label(f"Deactivated {name}")
        else:
            self._statusbar.set_label(f"Failed to deactivate {name}")
            self._show_error_dialog(f"Failed to deactivate {name}", error)
        self._refresh_tunnels()

    def _on_delete_requested(self, widget, name: str):
        """Show confirmation dialog before deleting."""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.NONE,
            text=f"Delete tunnel '{name}'?",
            secondary_text="This will remove the configuration file. This action cannot be undone.",
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        delete_btn = dialog.add_button("Delete", Gtk.ResponseType.OK)
        delete_btn.add_css_class("destructive-action")
        dialog.connect("response", self._on_delete_confirmed, name)
        dialog.present()

    def _on_delete_confirmed(self, dialog, response, name: str):
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        success, error = self._client.delete_tunnel(name)
        if success:
            self._statusbar.set_label(f"Deleted {name}")
            self._selected_tunnel = ""
            self._detail.show_empty()
        else:
            self._show_error_dialog(f"Failed to delete {name}", error)
        self._refresh_tunnels()

    def _on_create_requested(self, widget):
        template = "[Interface]\nPrivateKey = \nAddress = \n\n[Peer]\nPublicKey = \nEndpoint = \nAllowedIPs = 0.0.0.0/0\n"
        editor = ConfigEditor(self, "new_tunnel", template, self._on_create_saved, is_new=True)
        editor.present()

    def _on_create_saved(self, orig_name: str, new_name: str, content: str):
        success, error = self._client.import_config(new_name, content)
        if success:
            self._statusbar.set_label(f"Created {new_name}")
            self._refresh_tunnels()
            # Select new tunnel
            self._tunnel_list.select_tunnel(new_name)
        else:
            self._show_error_dialog(f"Failed to create {new_name}", error)

    def _on_edit_requested(self, widget, name: str):
        config = self._client.get_raw_config(name)
        if config is None: # explicit None check as empty string is valid-ish
            self._show_error_dialog("Failed to load config", "Config not found")
            return
            
        editor = ConfigEditor(self, name, config, self._on_config_saved)
        editor.present()

    def _on_config_saved(self, original_name: str, new_name: str, content: str):
        # Since ImportConfig fails if exists, we must delete first.
        # Use simple delete-then-import for MVP.
        # Check if running?
        if original_name in self._tunnels and self._tunnels[original_name].is_active:
            self._show_error_dialog("Cannot edit active tunnel", "Please deactivate the tunnel before editing.")
            return

        # Backup the original config before deleting
        backup_config = self._client.get_raw_config(original_name)
        success, error = self._client.delete_tunnel(original_name)
        if not success:
            self._show_error_dialog("Failed to update config", f"Could not delete old config: {error}")
            return

        success, error = self._client.import_config(new_name, content)
        if success:
            self._statusbar.set_label(f"Updated {new_name}")
            self._refresh_tunnels()
            # Reselect to refresh view
            if self._selected_tunnel == original_name:
                self._show_tunnel_detail(new_name)
        else:
            # Restore the original config if import failed
            if backup_config:
                restore_success, restore_error = self._client.import_config(original_name, backup_config)
                if restore_success:
                    self._show_error_dialog(f"Failed to save config {new_name}. Original restored.", error)
                else:
                    self._show_error_dialog(f"Failed to save config {new_name}. Also failed to restore original: {restore_error}", error)
            else:
                self._show_error_dialog(f"Failed to save config {new_name}. No backup available.", error)
            self._refresh_tunnels()

    def _on_import_requested(self, widget):
        """Open file chooser to import a .conf file."""
        try:
            dialog = Gtk.FileChooserDialog(
                title="Import WireGuard Config",
                transient_for=self,
                action=Gtk.FileChooserAction.OPEN,
            )
            dialog.add_buttons(
                "Cancel", Gtk.ResponseType.CANCEL,
                "Import", Gtk.ResponseType.ACCEPT,
            )
            filter_conf = Gtk.FileFilter()
            filter_conf.set_name("WireGuard configs (*.conf)")
            filter_conf.add_pattern("*.conf")
            filter_all = Gtk.FileFilter()
            filter_all.set_name("All files")
            filter_all.add_pattern("*")
            dialog.add_filter(filter_conf)
            dialog.add_filter(filter_all)
            dialog.connect("response", self._on_import_file_chosen)
            dialog.present()
        except Exception as e:
            log.error(f"Failed to open import dialog: {e}")
            self._show_error_dialog("Import Error", str(e))

    def _on_import_file_chosen(self, dialog, response):
        # Get the path BEFORE destroying/closing the dialog
        path = None
        if response == Gtk.ResponseType.ACCEPT:
            try:
                file = dialog.get_file()
                if file:
                    path = file.get_path()
            except Exception as e:
                log.error(f"Failed to get file from dialog: {e}")

        dialog.destroy()

        if not path:
            return

        try:
            name = os.path.splitext(os.path.basename(path))[0]
            log.info(f"Importing config from {path} as {name!r}")
            with open(path, "r") as f:
                content = f.read()

            success, error = self._client.import_config(name, content)
            if success:
                self._statusbar.set_label(f"Imported {name}")
                self._refresh_tunnels()
                self._tunnel_list.select_tunnel(name)
            else:
                log.error(f"Import rejected by daemon: {error}")
                # Open the editor so user can fix the config
                editor = ConfigEditor(self, name, content, self._on_create_saved, is_new=True)
                editor.present()
                # Also show the specific error
                self._show_error_dialog(f"Failed to import '{name}'", error)
        except Exception as e:
            log.error(f"Import failed: {e}")
            self._show_error_dialog("Import failed", str(e))

    # ── D-Bus Signal Callbacks ───────────────────────────────────

    def _on_state_changed(self, name: str, state: str, error: str):
        """Handle TunnelStateChanged signal from daemon."""
        log.info(f"State changed: {name} -> {state}")
        if name in self._tunnels:
            self._tunnels[name].state = state
            self._tunnels[name].error = error
            self._tunnel_list.update_tunnel_state(name, state)
            if name == self._selected_tunnel:
                self._show_tunnel_detail(name)

    def _on_stats_updated(self, stats):
        """Handle StatsUpdated signal from daemon."""
        if stats.name == self._selected_tunnel:
            self._detail.update_stats(stats)

    # ── UI Helpers ─────────────────────────────────────────────

    def _set_ui_busy(self, busy: bool):
        """Disable/enable interactive elements during operations."""
        # Just set cursor for now; could add a spinner
        pass

    def _show_error_dialog(self, title: str, message: str):
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title,
            secondary_text=message,
        )
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.present()

    def _show_daemon_error(self):
        """Show error when daemon is not reachable."""
        # Show in the status bar and disable interactive elements
        self._statusbar.set_label("⚠ Cannot connect to daemon. Is wireguard-gui-daemon running?")
        # Show a dialog too
        self._show_error_dialog(
            "Daemon not running",
            "Could not connect to the WireGuard GUI daemon.\n\n"
            "Start it with:\n"
            "  sudo systemctl start wireguard-gui-daemon\n\n"
            "Or for development:\n"
            "  sudo ./daemon/wireguard-gui-daemon"
        )
