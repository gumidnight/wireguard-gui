// Package dbus provides the D-Bus service for the WireGuard GUI daemon.
package dbus

import (
	"encoding/json"
	"fmt"
	"log"

	godbus "github.com/godbus/dbus/v5"
	"github.com/godbus/dbus/v5/introspect"

	"github.com/gumidnight/wireguard-gui/daemon/internal/tunnel"
)

const (
	busName   = "org.wireguardgui.Manager"
	objPath   = "/org/wireguardgui/Manager"
	ifaceName = "org.wireguardgui.Manager"
)

// Service is the D-Bus service that exposes tunnel management methods.
type Service struct {
	conn *godbus.Conn
	mgr  *tunnel.Manager
}

// tunnelInfoJSON is the JSON-serializable tunnel info sent over D-Bus.
type tunnelInfoJSON struct {
	Name       string `json:"name"`
	State      string `json:"state"`
	Error      string `json:"error,omitempty"`
	Address    string `json:"address,omitempty"`
	DNS        string `json:"dns,omitempty"`
	Endpoint   string `json:"endpoint,omitempty"`
	AllowedIPs string `json:"allowed_ips,omitempty"`
	PeerCount  int    `json:"peer_count"`
	HasScripts bool   `json:"has_scripts"`
}

// tunnelStatsJSON is the JSON-serializable stats sent over D-Bus.
type tunnelStatsJSON struct {
	Name        string         `json:"name"`
	PublicKey   string         `json:"public_key"`
	ListenPort  int            `json:"listen_port"`
	Peers       []peerStatJSON `json:"peers"`
	LastUpdated string         `json:"last_updated"`
}

type peerStatJSON struct {
	PublicKey       string `json:"public_key"`
	Endpoint        string `json:"endpoint"`
	AllowedIPs      string `json:"allowed_ips"`
	LatestHandshake string `json:"latest_handshake"`
	TransferRx      int64  `json:"transfer_rx"`
	TransferTx      int64  `json:"transfer_tx"`
}

// NewService creates and registers the D-Bus service on the system bus.
func NewService(mgr *tunnel.Manager) (*Service, error) {
	conn, err := godbus.ConnectSystemBus()
	if err != nil {
		return nil, fmt.Errorf("failed to connect to system bus: %w", err)
	}

	svc := &Service{
		conn: conn,
		mgr:  mgr,
	}

	// Export the service object
	if err := conn.Export(svc, objPath, ifaceName); err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to export D-Bus object: %w", err)
	}

	// Export introspection
	node := &introspect.Node{
		Name: objPath,
		Interfaces: []introspect.Interface{
			introspect.IntrospectData,
			{
				Name: ifaceName,
				Methods: []introspect.Method{
					{Name: "ListTunnels", Args: []introspect.Arg{{Name: "tunnels", Type: "s", Direction: "out"}}},
					{Name: "Activate", Args: []introspect.Arg{{Name: "name", Type: "s", Direction: "in"}, {Name: "result", Type: "s", Direction: "out"}}},
					{Name: "Deactivate", Args: []introspect.Arg{{Name: "name", Type: "s", Direction: "in"}, {Name: "result", Type: "s", Direction: "out"}}},
					{Name: "GetStatus", Args: []introspect.Arg{{Name: "name", Type: "s", Direction: "in"}, {Name: "status", Type: "s", Direction: "out"}}},
					{Name: "GetConfig", Args: []introspect.Arg{{Name: "name", Type: "s", Direction: "in"}, {Name: "config", Type: "s", Direction: "out"}}},
					{Name: "GetRawConfig", Args: []introspect.Arg{{Name: "name", Type: "s", Direction: "in"}, {Name: "config", Type: "s", Direction: "out"}}},
					{Name: "ImportConfig", Args: []introspect.Arg{{Name: "name", Type: "s", Direction: "in"}, {Name: "content", Type: "s", Direction: "in"}, {Name: "result", Type: "s", Direction: "out"}}},
					{Name: "DeleteTunnel", Args: []introspect.Arg{{Name: "name", Type: "s", Direction: "in"}, {Name: "result", Type: "s", Direction: "out"}}},
					{Name: "RefreshConfigs", Args: []introspect.Arg{{Name: "result", Type: "s", Direction: "out"}}},
				},
				Signals: []introspect.Signal{
					{Name: "TunnelStateChanged", Args: []introspect.Arg{{Name: "name", Type: "s"}, {Name: "state", Type: "s"}, {Name: "error", Type: "s"}}},
					{Name: "StatsUpdated", Args: []introspect.Arg{{Name: "stats_json", Type: "s"}}},
				},
			},
		},
	}

	if err := conn.Export(introspect.NewIntrospectable(node), objPath, "org.freedesktop.DBus.Introspectable"); err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to export introspection: %w", err)
	}

	// Request the bus name
	reply, err := conn.RequestName(busName, godbus.NameFlagDoNotQueue)
	if err != nil {
		conn.Close()
		return nil, fmt.Errorf("failed to request bus name: %w", err)
	}
	if reply != godbus.RequestNameReplyPrimaryOwner {
		conn.Close()
		return nil, fmt.Errorf("bus name %s already taken", busName)
	}

	log.Printf("D-Bus service registered: %s at %s", busName, objPath)
	return svc, nil
}

// Close releases the D-Bus connection.
func (s *Service) Close() {
	if s.conn != nil {
		s.conn.Close()
	}
}

// ── D-Bus Method Implementations ───────────────────────────────────

// ListTunnels returns a JSON array of all tunnel info.
func (s *Service) ListTunnels() (string, *godbus.Error) {
	tunnels := s.mgr.ListTunnels()
	result := make([]tunnelInfoJSON, len(tunnels))

	for i, t := range tunnels {
		info := tunnelInfoJSON{
			Name:       t.Name,
			State:      string(t.State),
			Error:      t.Error,
			HasScripts: t.HasScripts,
		}
		if t.Config != nil {
			info.Address = t.Config.Interface.Address
			info.DNS = t.Config.Interface.DNS
			info.PeerCount = len(t.Config.Peers)
			if len(t.Config.Peers) > 0 {
				info.Endpoint = t.Config.Peers[0].Endpoint
				info.AllowedIPs = t.Config.Peers[0].AllowedIPs
			}
		}
		result[i] = info
	}

	data, err := json.Marshal(result)
	if err != nil {
		return "", makeDBusError("Marshal", err)
	}
	return string(data), nil
}

// Activate activates a tunnel by name.
func (s *Service) Activate(name string) (string, *godbus.Error) {
	if err := s.mgr.Activate(name); err != nil {
		return fmt.Sprintf(`{"error": %q}`, err.Error()), nil
	}
	return `{"ok": true}`, nil
}

// Deactivate deactivates a tunnel by name.
func (s *Service) Deactivate(name string) (string, *godbus.Error) {
	if err := s.mgr.Deactivate(name); err != nil {
		return fmt.Sprintf(`{"error": %q}`, err.Error()), nil
	}
	return `{"ok": true}`, nil
}

// GetStatus returns detailed status/stats for a tunnel as JSON.
func (s *Service) GetStatus(name string) (string, *godbus.Error) {
	info, err := s.mgr.GetTunnel(name)
	if err != nil {
		return "", makeDBusError("GetStatus", err)
	}

	if info.State != tunnel.StateActive {
		result := map[string]interface{}{
			"name":  info.Name,
			"state": string(info.State),
			"error": info.Error,
		}
		data, _ := json.Marshal(result)
		return string(data), nil
	}

	stats, err := s.mgr.GetStats(name)
	if err != nil {
		return "", makeDBusError("GetStats", err)
	}

	sj := tunnelStatsJSON{
		Name:        stats.Name,
		PublicKey:   stats.PublicKey,
		ListenPort:  stats.ListenPort,
		LastUpdated: stats.LastUpdated.Format("2006-01-02T15:04:05Z"),
	}
	for _, p := range stats.Peers {
		handshakeStr := ""
		if !p.LatestHandshake.IsZero() {
			handshakeStr = p.LatestHandshake.Format("2006-01-02T15:04:05Z")
		}
		sj.Peers = append(sj.Peers, peerStatJSON{
			PublicKey:       p.PublicKey,
			Endpoint:        p.Endpoint,
			AllowedIPs:      p.AllowedIPs,
			LatestHandshake: handshakeStr,
			TransferRx:      p.TransferRx,
			TransferTx:      p.TransferTx,
		})
	}

	data, err := json.Marshal(sj)
	if err != nil {
		return "", makeDBusError("Marshal", err)
	}
	return string(data), nil
}

// GetConfig returns the (sanitized) raw config for a tunnel.
func (s *Service) GetConfig(name string) (string, *godbus.Error) {
	content, err := s.mgr.GetConfig(name)
	if err != nil {
		return "", makeDBusError("GetConfig", err)
	}
	return content, nil
}

// GetRawConfig returns the raw (unsanitized) config with private keys.
func (s *Service) GetRawConfig(name string) (string, *godbus.Error) {
	content, err := s.mgr.GetRawConfig(name)
	if err != nil {
		return "", makeDBusError("GetRawConfig", err)
	}
	return content, nil
}

// ImportConfig imports a new tunnel config.
func (s *Service) ImportConfig(name string, content string) (string, *godbus.Error) {
	if err := s.mgr.ImportConfig(name, content); err != nil {
		return fmt.Sprintf(`{"error": %q}`, err.Error()), nil
	}
	return `{"ok": true}`, nil
}

// DeleteTunnel deletes a tunnel.
func (s *Service) DeleteTunnel(name string) (string, *godbus.Error) {
	if err := s.mgr.DeleteTunnel(name); err != nil {
		return fmt.Sprintf(`{"error": %q}`, err.Error()), nil
	}
	return `{"ok": true}`, nil
}

// RefreshConfigs re-reads config files from disk.
func (s *Service) RefreshConfigs() (string, *godbus.Error) {
	if err := s.mgr.RefreshConfigs(); err != nil {
		return fmt.Sprintf(`{"error": %q}`, err.Error()), nil
	}
	return `{"ok": true}`, nil
}

// ── D-Bus Signal Emitters (implements tunnel.StatsCallback) ────────

// OnStatsUpdated emits a StatsUpdated signal on D-Bus.
func (s *Service) OnStatsUpdated(name string, stats *tunnel.TunnelStats) {
	sj := tunnelStatsJSON{
		Name:        stats.Name,
		PublicKey:   stats.PublicKey,
		ListenPort:  stats.ListenPort,
		LastUpdated: stats.LastUpdated.Format("2006-01-02T15:04:05Z"),
	}
	for _, p := range stats.Peers {
		handshakeStr := ""
		if !p.LatestHandshake.IsZero() {
			handshakeStr = p.LatestHandshake.Format("2006-01-02T15:04:05Z")
		}
		sj.Peers = append(sj.Peers, peerStatJSON{
			PublicKey:       p.PublicKey,
			Endpoint:        p.Endpoint,
			AllowedIPs:      p.AllowedIPs,
			LatestHandshake: handshakeStr,
			TransferRx:      p.TransferRx,
			TransferTx:      p.TransferTx,
		})
	}

	data, _ := json.Marshal(sj)
	if err := s.conn.Emit(objPath, ifaceName+".StatsUpdated", string(data)); err != nil {
		log.Printf("failed to emit StatsUpdated signal: %v", err)
	}
}

// OnTunnelStateChanged emits a TunnelStateChanged signal on D-Bus.
func (s *Service) OnTunnelStateChanged(name string, state tunnel.TunnelState, errMsg string) {
	if err := s.conn.Emit(objPath, ifaceName+".TunnelStateChanged", name, string(state), errMsg); err != nil {
		log.Printf("failed to emit TunnelStateChanged signal: %v", err)
	}
}

// ── Helpers ─────────────────────────────────────────────────────────

func makeDBusError(method string, err error) *godbus.Error {
	return godbus.MakeFailedError(fmt.Errorf("%s: %w", method, err))
}
