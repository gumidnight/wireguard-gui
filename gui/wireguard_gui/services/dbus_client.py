"""D-Bus client for communicating with the WireGuard GUI daemon."""

import json
import logging
from typing import Optional, Callable

from dasbus.connection import SystemMessageBus
from dasbus.error import DBusError
from gi.repository import GLib

log = logging.getLogger(__name__)

BUS_NAME = "org.wireguardgui.Manager"
OBJ_PATH = "/org/wireguardgui/Manager"
IFACE_NAME = "org.wireguardgui.Manager"


class TunnelInfo:
    """Represents tunnel information from the daemon."""

    def __init__(self, data: dict):
        self.name: str = data.get("name", "")
        self.state: str = data.get("state", "inactive")
        self.error: str = data.get("error", "")
        self.address: str = data.get("address", "")
        self.dns: str = data.get("dns", "")
        self.endpoint: str = data.get("endpoint", "")
        self.allowed_ips: str = data.get("allowed_ips", "")
        self.peer_count: int = data.get("peer_count", 0)
        self.has_scripts: bool = data.get("has_scripts", False)

    @property
    def is_active(self) -> bool:
        return self.state == "active"

    @property
    def is_error(self) -> bool:
        return self.state == "error"


class PeerStats:
    """Represents per-peer statistics."""

    def __init__(self, data: dict):
        self.public_key: str = data.get("public_key", "")
        self.endpoint: str = data.get("endpoint", "")
        self.allowed_ips: str = data.get("allowed_ips", "")
        self.latest_handshake: str = data.get("latest_handshake", "")
        self.transfer_rx: int = data.get("transfer_rx", 0)
        self.transfer_tx: int = data.get("transfer_tx", 0)


class TunnelStats:
    """Represents tunnel statistics from the daemon."""

    def __init__(self, data: dict):
        self.name: str = data.get("name", "")
        self.public_key: str = data.get("public_key", "")
        self.listen_port: int = data.get("listen_port", 0)
        self.last_updated: str = data.get("last_updated", "")
        self.peers: list[PeerStats] = [
            PeerStats(p) for p in data.get("peers", []) or []
        ]


class DaemonClient:
    """Client for the WireGuard GUI daemon D-Bus service."""

    def __init__(self):
        self._bus = SystemMessageBus()
        self._proxy = None
        self._connected = False
        self._state_callback: Optional[Callable] = None
        self._stats_callback: Optional[Callable] = None

    def connect(self) -> bool:
        """Connect to the daemon over D-Bus."""
        try:
            self._proxy = self._bus.get_proxy(BUS_NAME, OBJ_PATH)
            self._connected = True
            log.info("Connected to daemon via D-Bus")
            return True
        except DBusError as e:
            log.error(f"Failed to connect to daemon: {e}")
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def list_tunnels(self) -> list[TunnelInfo]:
        """Get list of all tunnels."""
        try:
            result = self._proxy.ListTunnels()
            data = json.loads(result)
            return [TunnelInfo(t) for t in data]
        except (DBusError, json.JSONDecodeError) as e:
            log.error(f"ListTunnels failed: {e}")
            return []

    def activate(self, name: str) -> tuple[bool, str]:
        """Activate a tunnel. Returns (success, error_message)."""
        try:
            result = json.loads(self._proxy.Activate(name))
            if "error" in result:
                return False, result["error"]
            return True, ""
        except DBusError as e:
            return False, str(e)

    def deactivate(self, name: str) -> tuple[bool, str]:
        """Deactivate a tunnel. Returns (success, error_message)."""
        try:
            result = json.loads(self._proxy.Deactivate(name))
            if "error" in result:
                return False, result["error"]
            return True, ""
        except DBusError as e:
            return False, str(e)

    def get_status(self, name: str) -> Optional[TunnelStats]:
        """Get detailed status/stats for a tunnel."""
        try:
            result = self._proxy.GetStatus(name)
            data = json.loads(result)
            return TunnelStats(data)
        except (DBusError, json.JSONDecodeError) as e:
            log.error(f"GetStatus failed: {e}")
            return None

    def get_config(self, name: str) -> Optional[str]:
        """Get the sanitized config for a tunnel."""
        try:
            return self._proxy.GetConfig(name)
        except DBusError as e:
            log.error(f"GetConfig failed: {e}")
            return None

    def get_raw_config(self, name: str) -> Optional[str]:
        """Get the raw (unsanitized) config for a tunnel."""
        try:
            return self._proxy.GetRawConfig(name)
        except DBusError as e:
            log.error(f"GetRawConfig failed: {e}")
            return None

    def import_config(self, name: str, content: str) -> tuple[bool, str]:
        """Import a new tunnel config."""
        try:
            result = json.loads(self._proxy.ImportConfig(name, content))
            if "error" in result:
                return False, result["error"]
            return True, ""
        except DBusError as e:
            return False, str(e)

    def delete_tunnel(self, name: str) -> tuple[bool, str]:
        """Delete a tunnel."""
        try:
            result = json.loads(self._proxy.DeleteTunnel(name))
            if "error" in result:
                return False, result["error"]
            return True, ""
        except DBusError as e:
            return False, str(e)

    def refresh_configs(self) -> tuple[bool, str]:
        """Re-read configs from disk."""
        try:
            result = json.loads(self._proxy.RefreshConfigs())
            if "error" in result:
                return False, result["error"]
            return True, ""
        except DBusError as e:
            return False, str(e)

    def subscribe_signals(self, state_cb: Optional[Callable] = None,
                          stats_cb: Optional[Callable] = None):
        """Subscribe to D-Bus signals from the daemon.

        state_cb(name: str, state: str, error: str)
        stats_cb(stats: TunnelStats)
        """
        self._state_callback = state_cb
        self._stats_callback = stats_cb

        try:
            bus_conn = self._bus.connection
            bus_conn.signal_subscribe(
                BUS_NAME,
                IFACE_NAME,
                "TunnelStateChanged",
                OBJ_PATH,
                None,
                0,
                self._on_state_changed,
            )
            bus_conn.signal_subscribe(
                BUS_NAME,
                IFACE_NAME,
                "StatsUpdated",
                OBJ_PATH,
                None,
                0,
                self._on_stats_updated,
            )
            log.info("Subscribed to D-Bus signals")
        except Exception as e:
            log.error(f"Failed to subscribe to signals: {e}")

    def _on_state_changed(self, connection, sender, path, iface, signal, params):
        """Handle TunnelStateChanged signal."""
        if self._state_callback and params:
            name = params[0]
            state = params[1]
            error = params[2] if len(params) > 2 else ""
            GLib.idle_add(self._state_callback, name, state, error)

    def _on_stats_updated(self, connection, sender, path, iface, signal, params):
        """Handle StatsUpdated signal."""
        if self._stats_callback and params:
            try:
                data = json.loads(params[0])
                stats = TunnelStats(data)
                GLib.idle_add(self._stats_callback, stats)
            except (json.JSONDecodeError, IndexError) as e:
                log.error(f"Failed to parse stats signal: {e}")
