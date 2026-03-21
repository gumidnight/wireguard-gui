# WireGuard GUI for Linux

A native GTK4/Libadwaita desktop client for managing WireGuard VPN tunnels on Ubuntu, modeled after the simplicity of the official Windows WireGuard client.

> Tested on **Ubuntu 22.04** and **Ubuntu 24.04** with GNOME.

---
<p align="center">
  <a href="https://www.buymeacoffee.com/gumidnight">
    <img src="https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&button_colour=5F7FFF&font_colour=ffffff&coffee_colour=FFDD00" />
  </a>
</p>

## Features

- **Sidebar + detail layout** — list all tunnels, click to see config, stats, and controls
- **Activate / Deactivate tunnels** with a single click
- **Import** tunnel configs from `.conf` files or create new ones in a built-in editor
- **Live stats** — transfer bytes and latest handshake per peer, updated every few seconds
- **System tray** — optional tray icon with quick connect/disconnect
- **Secure architecture** — GUI runs unprivileged; a small root daemon handles `wg-quick` calls
- **Polkit authentication** — per-session admin auth before any tunnel change

---

## Architecture

```
┌───────────────────┐       D-Bus (system bus)       ┌──────────────────────┐
│   GUI Process     │  ◄──────────────────────────►  │  Privileged Daemon   │
│   (user session)  │   org.wireguardgui.Manager     │  (root, systemd)     │
│   Python/GTK4     │                                │  Go binary           │
│   No root access  │                                │  Calls wg-quick/wg   │
└───────────────────┘                                └──────────────────────┘
```

| Component | Language | Role |
|---|---|---|
| **Daemon** | Go | Runs as root via systemd. Exposes a D-Bus API, manages tunnel lifecycle and config files. |
| **GUI** | Python / GTK4 / Libadwaita | Runs unprivileged in the user session. Communicates with the daemon over D-Bus. |
| **Polkit** | — | Authorises GUI requests to the daemon. User authenticates once per session. |

---

## Prerequisites

**Ubuntu 22.04 / 24.04**

```bash
sudo apt install \
    wireguard-tools \
    golang-go \
    python3-gi python3-gi-cairo \
    gir1.2-gtk-4.0 gir1.2-adw-1 \
    python3-dasbus \
    libadwaita-1-dev \
    gir1.2-ayatanaappindicator3-0.1
```

---

## Install

```bash
git clone https://github.com/gumidnight/wireguard-gui.git
cd wireguard-gui

make daemon
sudo make install
sudo systemctl enable --now wireguard-gui-daemon
```

That's it. "WireGuard GUI" will appear in your application menu.

---

## Usage

1. Place your WireGuard `.conf` files in `/etc/wireguard/`, **or** use the in-app importer.
2. Open **WireGuard GUI** from the application menu (or run `wireguard-gui`).
3. Select a tunnel from the sidebar.
4. Click **Activate** — authenticate with Polkit once per session.
5. View live transfer stats and handshake times in the detail panel.

The **system tray** icon (auto-started with the GUI) lets you toggle tunnels quickly from anywhere on the desktop.

---

## Development

```bash
# Build the Go daemon
make daemon

# Run the daemon in the foreground (needs root)
make run-daemon

# Run the GUI (separate terminal, no root needed)
make run-gui
```

Run daemon unit tests:

```bash
cd daemon && go test ./...
```

---

## Uninstall

```bash
sudo systemctl disable --now wireguard-gui-daemon
sudo make uninstall
```

---

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

- [Report a bug](https://github.com/gumidnight/wireguard-gui/issues/new?template=bug_report.md)
- [Request a feature](https://github.com/gumidnight/wireguard-gui/issues/new?template=feature_request.md)

---

## License

[MIT](LICENSE) © gumidnight
