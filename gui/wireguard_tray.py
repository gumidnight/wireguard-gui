#!/usr/bin/env python3
"""WireGuard GUI Tray application (GTK3)."""

import sys
import os
import signal
import gi
import logging

gi.require_version('Gtk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')

from gi.repository import Gtk, GLib, AyatanaAppIndicator3 as AppIndicator

# Add parent directory to path so we can import wireguard_gui modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wireguard_gui.services.dbus_client import DaemonClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
log = logging.getLogger("wireguard-gui-tray")

APP_ID = "org.wireguardgui.Tray"

class TrayApp:
    def __init__(self):
        self._client = DaemonClient()
        self._tunnels = []
        
        # Use the wireguard-tray icon installed in hicolor theme
        _icon_name = "wireguard-tray"

        self._indicator = AppIndicator.Indicator.new(
            "wireguard-gui-tray",
            _icon_name,
            AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        self._indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._tray_icon_name = _icon_name
        
        # Connect signals
        if not self._client.is_connected:
            self._client.connect()
            
        self._client.subscribe_signals(
            state_cb=self._on_state_changed,
            stats_cb=self._on_stats_updated
        )
        
        # Create base static items for the menu
        self._menu = Gtk.Menu()
        self._indicator.set_menu(self._menu)
        
        self._refresh_status()
        
        # Poll occasionally
        GLib.timeout_add_seconds(5, self._poll_status)

    def _build_menu(self, tunnels, active_count, has_error):
        # Clear existing menu items
        for child in self._menu.get_children():
            self._menu.remove(child)
            
        # Status Item
        status_text = "Disconnected"
        if has_error:
            status_text = "Error"
        elif active_count > 0:
            status_text = f"Connected ({active_count})"
            
        status_item = Gtk.MenuItem(label=f"Status: {status_text}")
        status_item.set_sensitive(False)
        self._menu.append(status_item)
        
        self._menu.append(Gtk.SeparatorMenuItem())
        
        # Tunnels section
        if len(tunnels) > 0:
            for t in tunnels:
                is_active = t.state == "active"
                
                # Use CheckMenuItem to show a tick
                item = Gtk.CheckMenuItem(label=t.name)
                item.set_active(is_active)
                
                item.connect("toggled", self._on_tunnel_toggled, t.name, is_active)
                self._menu.append(item)
        else:
            no_tunnels = Gtk.MenuItem(label="No tunnels configured")
            no_tunnels.set_sensitive(False)
            self._menu.append(no_tunnels)
            
        self._menu.append(Gtk.SeparatorMenuItem())
        
        # Show Manager
        show_item = Gtk.MenuItem(label="Show Manager")
        show_item.connect("activate", self._launch_manager)
        self._menu.append(show_item)
        
        self._menu.append(Gtk.SeparatorMenuItem())
        
        quit_item = Gtk.MenuItem(label="Quit Tray")
        quit_item.connect("activate", self._quit)
        self._menu.append(quit_item)
        
        self._menu.show_all()

    def _on_tunnel_toggled(self, checkitem, name, was_active):
        # We need to block recursive signaling if we programmatically altered checkitem,
        # but since we rebuild the menu on refresh, just firing Activate/Deactivate is fine.
        is_active = checkitem.get_active()
        
        # Only do something if the state actually changed
        if is_active != was_active:
            if is_active:
                log.info(f"Tray requesting activation of {name}")
                self._client.activate(name)
            else:
                log.info(f"Tray requesting deactivation of {name}")
                self._client.deactivate(name)
                
            # Rebuild menu to freeze the UI immediately, or just rely on backend signal
            # Backend should send TunnelStateChanged quickly anyway.
            # self._refresh_status()

    def _refresh_status(self):
        try:
            tunnels = self._client.list_tunnels()
            # Check if state actually changed to avoid rebuilding menu constantly
            self._tunnels = tunnels
            active_count = 0
            has_error = False
            
            for t in tunnels:
                if t.state == "active":
                    active_count += 1
                elif t.state == "error":
                    has_error = True
            
            if has_error:
                self._update_icon("error")
            elif active_count > 0:
                self._update_icon("active")
            else:
                self._update_icon("inactive")
                
            self._build_menu(tunnels, active_count, has_error)
            
        except Exception as e:
            log.error(f"Failed to refresh status: {e}")
            self._update_icon("inactive")

    def _poll_status(self):
        self._refresh_status()
        return True

    def _on_state_changed(self, name, state, error):
        log.info(f"Tunnel {name} changed to {state}")
        self._refresh_status()

    def _on_stats_updated(self, stats_json):
        pass # Could update tooltip here

    def _update_icon(self, state):
        if state == "error":
            self._indicator.set_icon("network-error-symbolic")
        else:
            self._indicator.set_icon(self._tray_icon_name)

    def _launch_manager(self, _):
        os.system("wireguard-gui &")

    def _quit(self, _):
        Gtk.main_quit()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = TrayApp()
    Gtk.main()
