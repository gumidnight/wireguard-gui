"""WireGuard GUI application entry point."""

import sys
import logging

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gio

from wireguard_gui.services.dbus_client import DaemonClient
from wireguard_gui.window import MainWindow

log = logging.getLogger(__name__)


class WireGuardApp(Adw.Application):
    """Main GTK application."""

    def __init__(self):
        super().__init__(
            application_id="org.wireguardgui.Client",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._client = DaemonClient()

    def do_activate(self):
        """Called when the application is activated."""
        win = self.get_active_window()
        if not win:
            win = MainWindow(self, self._client)
        win.present()


def main():
    """Entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    log.info("Starting WireGuard GUI")

    GLib.set_prgname("wireguard-gui")
    GLib.set_application_name("WireGuard GUI")

    app = WireGuardApp()
    return app.run(sys.argv)
