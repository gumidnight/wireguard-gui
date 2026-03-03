#!/bin/bash
# Launcher script for WireGuard GUI Tray (GTK3)
# Use env -i to completely strip Snap contamination
exec /usr/bin/env -i \
    HOME="$HOME" \
    USER="$USER" \
    PATH="/usr/local/bin:/usr/bin:/bin" \
    DISPLAY="${DISPLAY:-:0}" \
    XAUTHORITY="${XAUTHORITY:-$HOME/.Xauthority}" \
    WAYLAND_DISPLAY="${WAYLAND_DISPLAY}" \
    XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR}" \
    XDG_DATA_DIRS="/usr/local/share:/usr/share" \
    DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS}" \
    PYTHONPATH="/usr/local/share/wireguard-gui" \
    python3 /usr/local/share/wireguard-gui/wireguard_tray.py "$@"
