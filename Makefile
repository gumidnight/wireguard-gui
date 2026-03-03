.PHONY: all daemon gui clean install uninstall run-daemon run-gui

PREFIX ?= /usr/local
DAEMON_BIN = daemon/wireguard-gui-daemon
GUI_APP = gui/wireguard_gui

all: daemon

# ── Daemon ──────────────────────────────────────────────
daemon:
	cd daemon && go build -o wireguard-gui-daemon ./cmd/wireguard-gui-daemon

daemon-test:
	cd daemon && go test ./...

# ── GUI (no build step, Python) ─────────────────────────
gui-deps:
	pip3 install --user pygobject dasbus

# ── Run (development) ──────────────────────────────────
run-daemon: daemon
	sudo ./daemon/wireguard-gui-daemon

run-gui:
	cd gui && python3 -m wireguard_gui

# ── Install ─────────────────────────────────────────────
install: daemon
	# Daemon binary
	install -Dm755 daemon/wireguard-gui-daemon $(DESTDIR)$(PREFIX)/bin/wireguard-gui-daemon
	# GUI (Python package)
	install -d $(DESTDIR)$(PREFIX)/share/wireguard-gui/
	cp -r gui/wireguard_gui $(DESTDIR)$(PREFIX)/share/wireguard-gui/
	# Launcher script
	install -Dm755 gui/wireguard-gui-launcher.sh $(DESTDIR)$(PREFIX)/bin/wireguard-gui
	# Tray App
	install -Dm755 gui/wireguard_tray.py $(DESTDIR)$(PREFIX)/share/wireguard-gui/wireguard_tray.py
	install -Dm755 gui/wireguard-gui-tray-launcher.sh $(DESTDIR)$(PREFIX)/bin/wireguard-gui-tray
	# D-Bus service config
	install -Dm644 data/dbus/org.wireguardgui.Manager.conf \
		$(DESTDIR)/etc/dbus-1/system.d/org.wireguardgui.Manager.conf
	# Polkit policy
	install -Dm644 data/polkit/org.wireguardgui.policy \
		$(DESTDIR)/usr/share/polkit-1/actions/org.wireguardgui.policy
	# Systemd service
	install -Dm644 data/systemd/wireguard-gui-daemon.service \
		$(DESTDIR)/etc/systemd/system/wireguard-gui-daemon.service
	# Desktop entry
	install -Dm644 data/desktop/org.wireguardgui.desktop \
		$(DESTDIR)/usr/share/applications/org.wireguardgui.desktop
	# Tray autostart entry
	install -Dm644 data/desktop/org.wireguardgui.tray.desktop \
		$(DESTDIR)/etc/xdg/autostart/org.wireguardgui.tray.desktop
	# Icons — hicolor theme (256x256 and 512x512)
	install -Dm644 gui/wireguard_gui/resources/icons/wireguard-logo.png \
		$(DESTDIR)/usr/share/icons/hicolor/256x256/apps/wireguard-gui.png
	install -Dm644 gui/wireguard_gui/resources/icons/wireguard-logo.png \
		$(DESTDIR)/usr/share/icons/hicolor/512x512/apps/wireguard-gui.png
	install -Dm644 gui/wireguard_gui/resources/icons/wireguard-tray.png \
		$(DESTDIR)/usr/share/icons/hicolor/256x256/apps/wireguard-tray.png
	install -Dm644 gui/wireguard_gui/resources/icons/wireguard-tray.png \
		$(DESTDIR)/usr/share/icons/hicolor/512x512/apps/wireguard-tray.png
	# Icons — pixmaps fallback
	install -Dm644 gui/wireguard_gui/resources/icons/wireguard-logo.png \
		$(DESTDIR)/usr/share/pixmaps/wireguard-gui.png
	install -Dm644 gui/wireguard_gui/resources/icons/wireguard-tray.png \
		$(DESTDIR)/usr/share/pixmaps/wireguard-tray.png
	# Reload
	systemctl daemon-reload
	gtk-update-icon-cache /usr/share/icons/hicolor/ -f || true
	update-desktop-database /usr/share/applications/ || true
	dbus-send --system --type=method_call --dest=org.freedesktop.DBus \
		/org/freedesktop/DBus org.freedesktop.DBus.ReloadConfig

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/wireguard-gui-daemon
	rm -f $(DESTDIR)$(PREFIX)/bin/wireguard-gui
	rm -rf $(DESTDIR)$(PREFIX)/share/wireguard-gui/
	rm -f $(DESTDIR)/etc/dbus-1/system.d/org.wireguardgui.Manager.conf
	rm -f $(DESTDIR)/usr/share/polkit-1/actions/org.wireguardgui.policy
	rm -f $(DESTDIR)/etc/systemd/system/wireguard-gui-daemon.service
	rm -f $(DESTDIR)/usr/share/applications/org.wireguardgui.desktop
	systemctl daemon-reload

clean:
	rm -f daemon/wireguard-gui-daemon
