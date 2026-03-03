// Package tunnel manages WireGuard tunnel lifecycle using wg-quick and wg CLI tools.
package tunnel

import (
	"bufio"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/gumidnight/wireguard-gui/daemon/internal/config"
	"github.com/gumidnight/wireguard-gui/daemon/internal/security"
)

// TunnelState represents the state of a tunnel.
type TunnelState string

const (
	StateInactive TunnelState = "inactive"
	StateActive   TunnelState = "active"
	StateError    TunnelState = "error"
)

// TunnelInfo contains information about a tunnel.
type TunnelInfo struct {
	Name       string
	State      TunnelState
	Config     *config.Config
	Error      string
	HasScripts bool // true if PostUp/PostDown are present
}

// TunnelStats contains live stats for an active tunnel.
type TunnelStats struct {
	Name             string
	PublicKey        string
	ListenPort       int
	Peers            []PeerStats
	LastUpdated      time.Time
}

// PeerStats contains per-peer statistics.
type PeerStats struct {
	PublicKey          string
	Endpoint           string
	AllowedIPs         string
	LatestHandshake    time.Time
	TransferRx         int64 // bytes received
	TransferTx         int64 // bytes sent
}

// StatsCallback is called when stats are updated.
type StatsCallback interface {
	OnStatsUpdated(name string, stats *TunnelStats)
	OnTunnelStateChanged(name string, state TunnelState, errMsg string)
}

// Manager manages WireGuard tunnels.
type Manager struct {
	configDir string
	mu        sync.RWMutex
	tunnels   map[string]*TunnelInfo
	stopPoll  chan struct{}
	callback  StatsCallback
}

// NewManager creates a new tunnel manager.
func NewManager(configDir string) (*Manager, error) {
	// Verify config directory exists
	info, err := os.Stat(configDir)
	if err != nil {
		if os.IsNotExist(err) {
			log.Printf("config directory %s does not exist, creating...", configDir)
			if err := os.MkdirAll(configDir, 0700); err != nil {
				return nil, fmt.Errorf("failed to create config dir: %w", err)
			}
		} else {
			return nil, fmt.Errorf("failed to stat config dir: %w", err)
		}
	} else if !info.IsDir() {
		return nil, fmt.Errorf("%s is not a directory", configDir)
	}

	// Verify wg and wg-quick are available
	for _, tool := range []string{"wg", "wg-quick"} {
		if _, err := exec.LookPath(tool); err != nil {
			return nil, fmt.Errorf("%s not found in PATH: %w", tool, err)
		}
	}

	m := &Manager{
		configDir: configDir,
		tunnels:   make(map[string]*TunnelInfo),
		stopPoll:  make(chan struct{}),
	}

	// Load initial tunnel list
	if err := m.loadConfigs(); err != nil {
		return nil, fmt.Errorf("failed to load configs: %w", err)
	}

	return m, nil
}

// loadConfigs scans the config directory for .conf files and parses them.
func (m *Manager) loadConfigs() error {
	entries, err := os.ReadDir(m.configDir)
	if err != nil {
		return fmt.Errorf("failed to read config dir: %w", err)
	}

	for _, entry := range entries {
		if entry.IsDir() || !strings.HasSuffix(entry.Name(), ".conf") {
			continue
		}
		name := strings.TrimSuffix(entry.Name(), ".conf")
		if err := security.ValidateTunnelName(name); err != nil {
			log.Printf("skipping invalid config name %q: %v", name, err)
			continue
		}

		content, err := os.ReadFile(filepath.Join(m.configDir, entry.Name()))
		if err != nil {
			log.Printf("failed to read %s: %v", entry.Name(), err)
			continue
		}

		cfg, err := config.Parse(string(content))
		if err != nil {
			log.Printf("failed to parse %s: %v", entry.Name(), err)
			m.tunnels[name] = &TunnelInfo{
				Name:  name,
				State: StateError,
				Error: fmt.Sprintf("config parse error: %v", err),
			}
			continue
		}

		m.tunnels[name] = &TunnelInfo{
			Name:       name,
			State:      StateInactive,
			Config:     cfg,
			HasScripts: cfg.HasPostScripts(),
		}
	}

	return nil
}

// Reconcile checks for already-active WireGuard interfaces and syncs state.
func (m *Manager) Reconcile() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Get list of active WireGuard interfaces
	output, err := exec.Command("wg", "show", "interfaces").Output()
	if err != nil {
		return fmt.Errorf("wg show interfaces failed: %w", err)
	}

	activeIfaces := strings.Fields(strings.TrimSpace(string(output)))
	for _, iface := range activeIfaces {
		if tunnel, ok := m.tunnels[iface]; ok {
			tunnel.State = StateActive
			log.Printf("reconciled: tunnel %s is already active", iface)
		} else {
			log.Printf("reconciled: active interface %s has no config (externally managed?)", iface)
		}
	}

	return nil
}

// ListTunnels returns all known tunnels.
func (m *Manager) ListTunnels() []TunnelInfo {
	m.mu.RLock()
	defer m.mu.RUnlock()

	result := make([]TunnelInfo, 0, len(m.tunnels))
	for _, t := range m.tunnels {
		result = append(result, *t)
	}
	return result
}

// GetTunnel returns info about a specific tunnel.
func (m *Manager) GetTunnel(name string) (*TunnelInfo, error) {
	if err := security.ValidateTunnelName(name); err != nil {
		return nil, err
	}
	m.mu.RLock()
	defer m.mu.RUnlock()

	t, ok := m.tunnels[name]
	if !ok {
		return nil, fmt.Errorf("tunnel %q not found", name)
	}
	return t, nil
}

// Activate brings a tunnel up using wg-quick.
func (m *Manager) Activate(name string) error {
	if err := security.ValidateTunnelName(name); err != nil {
		return err
	}

	m.mu.Lock()
	defer m.mu.Unlock()

	t, ok := m.tunnels[name]
	if !ok {
		return fmt.Errorf("tunnel %q not found", name)
	}
	if t.State == StateActive {
		return fmt.Errorf("tunnel %q is already active", name)
	}

	// SAFE: no shell invocation, name is validated
	cmd := exec.Command("wg-quick", "up", name)
	cmd.Dir = m.configDir
	output, err := cmd.CombinedOutput()
	if err != nil {
		errMsg := fmt.Sprintf("wg-quick up failed: %v\n%s", err, strings.TrimSpace(string(output)))
		t.State = StateError
		t.Error = errMsg
		if m.callback != nil {
			m.callback.OnTunnelStateChanged(name, StateError, errMsg)
		}
		return fmt.Errorf("%s", errMsg)
	}

	t.State = StateActive
	t.Error = ""
	log.Printf("activated tunnel: %s", name)

	if m.callback != nil {
		m.callback.OnTunnelStateChanged(name, StateActive, "")
	}

	return nil
}

// Deactivate brings a tunnel down using wg-quick.
func (m *Manager) Deactivate(name string) error {
	if err := security.ValidateTunnelName(name); err != nil {
		return err
	}

	m.mu.Lock()
	defer m.mu.Unlock()

	t, ok := m.tunnels[name]
	if !ok {
		return fmt.Errorf("tunnel %q not found", name)
	}
	if t.State == StateInactive {
		return fmt.Errorf("tunnel %q is already inactive", name)
	}

	cmd := exec.Command("wg-quick", "down", name)
	cmd.Dir = m.configDir
	output, err := cmd.CombinedOutput()
	if err != nil {
		errMsg := fmt.Sprintf("wg-quick down failed: %v\n%s", err, strings.TrimSpace(string(output)))
		t.State = StateError
		t.Error = errMsg
		if m.callback != nil {
			m.callback.OnTunnelStateChanged(name, StateError, errMsg)
		}
		return fmt.Errorf("%s", errMsg)
	}

	t.State = StateInactive
	t.Error = ""
	log.Printf("deactivated tunnel: %s", name)

	if m.callback != nil {
		m.callback.OnTunnelStateChanged(name, StateInactive, "")
	}

	return nil
}

// GetConfig returns the raw config content for a tunnel (with PrivateKey masked).
func (m *Manager) GetConfig(name string) (string, error) {
	if err := security.ValidateTunnelName(name); err != nil {
		return "", err
	}

	m.mu.RLock()
	defer m.mu.RUnlock()

	t, ok := m.tunnels[name]
	if !ok {
		return "", fmt.Errorf("tunnel %q not found", name)
	}
	if t.Config == nil {
		return "", fmt.Errorf("tunnel %q has no valid config", name)
	}

	return security.SanitizeConfigForDisplay(t.Config.Raw), nil
}

// GetRawConfig returns the raw config content (including private keys).
func (m *Manager) GetRawConfig(name string) (string, error) {
	if err := security.ValidateTunnelName(name); err != nil {
		return "", err
	}

	m.mu.RLock()
	defer m.mu.RUnlock()

	t, ok := m.tunnels[name]
	if !ok {
		return "", fmt.Errorf("tunnel %q not found", name)
	}
	if t.Config == nil {
		return "", fmt.Errorf("tunnel %q has no valid config", name)
	}

	return t.Config.Raw, nil
}

// ImportConfig imports a .conf file into the config directory.
func (m *Manager) ImportConfig(name string, content string) error {
	if err := security.ValidateTunnelName(name); err != nil {
		return err
	}
	if err := security.ValidateConfigContent(content); err != nil {
		return err
	}

	// Parse to validate
	cfg, err := config.Parse(content)
	if err != nil {
		return fmt.Errorf("invalid config: %w", err)
	}

	m.mu.Lock()
	defer m.mu.Unlock()

	// Check for existing
	if _, exists := m.tunnels[name]; exists {
		return fmt.Errorf("tunnel %q already exists", name)
	}

	// Write config file
	confPath := filepath.Join(m.configDir, name+".conf")
	if err := os.WriteFile(confPath, []byte(content), 0600); err != nil {
		return fmt.Errorf("failed to write config: %w", err)
	}

	m.tunnels[name] = &TunnelInfo{
		Name:       name,
		State:      StateInactive,
		Config:     cfg,
		HasScripts: cfg.HasPostScripts(),
	}

	log.Printf("imported tunnel config: %s", name)
	return nil
}

// DeleteTunnel removes a tunnel config. Deactivates it first if active.
func (m *Manager) DeleteTunnel(name string) error {
	if err := security.ValidateTunnelName(name); err != nil {
		return err
	}

	m.mu.Lock()

	t, ok := m.tunnels[name]
	if !ok {
		m.mu.Unlock()
		return fmt.Errorf("tunnel %q not found", name)
	}

	// Deactivate if active (release lock temporarily)
	if t.State == StateActive {
		m.mu.Unlock()
		if err := m.Deactivate(name); err != nil {
			return fmt.Errorf("failed to deactivate before deleting: %w", err)
		}
		m.mu.Lock()
	}

	// Remove config file
	confPath := filepath.Join(m.configDir, name+".conf")
	if err := os.Remove(confPath); err != nil && !os.IsNotExist(err) {
		m.mu.Unlock()
		return fmt.Errorf("failed to remove config file: %w", err)
	}

	delete(m.tunnels, name)
	m.mu.Unlock()

	log.Printf("deleted tunnel: %s", name)
	return nil
}

// RefreshConfigs re-reads config files from disk.
func (m *Manager) RefreshConfigs() error {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Remember active states
	activeStates := make(map[string]TunnelState)
	for name, t := range m.tunnels {
		activeStates[name] = t.State
	}

	// Clear and reload
	m.tunnels = make(map[string]*TunnelInfo)
	if err := m.loadConfigs(); err != nil {
		return err
	}

	// Restore active states
	for name, state := range activeStates {
		if t, ok := m.tunnels[name]; ok {
			t.State = state
		}
	}

	return nil
}

// GetStats retrieves live stats for an active tunnel.
func (m *Manager) GetStats(name string) (*TunnelStats, error) {
	if err := security.ValidateTunnelName(name); err != nil {
		return nil, err
	}

	m.mu.RLock()
	t, ok := m.tunnels[name]
	m.mu.RUnlock()

	if !ok {
		return nil, fmt.Errorf("tunnel %q not found", name)
	}
	if t.State != StateActive {
		return nil, fmt.Errorf("tunnel %q is not active", name)
	}

	return m.fetchStats(name)
}

// fetchStats calls `wg show <name> dump` and parses the output.
func (m *Manager) fetchStats(name string) (*TunnelStats, error) {
	cmd := exec.Command("wg", "show", name, "dump")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("wg show dump failed: %w", err)
	}

	stats := &TunnelStats{
		Name:        name,
		LastUpdated: time.Now(),
	}

	scanner := bufio.NewScanner(strings.NewReader(string(output)))
	lineNum := 0
	for scanner.Scan() {
		fields := strings.Split(scanner.Text(), "\t")
		lineNum++

		if lineNum == 1 {
			// First line: interface info
			// private-key  public-key  listen-port  fwmark
			if len(fields) >= 3 {
				stats.PublicKey = fields[1]
				if port, err := strconv.Atoi(fields[2]); err == nil {
					stats.ListenPort = port
				}
			}
			continue
		}

		// Peer lines:
		// public-key  preshared-key  endpoint  allowed-ips  latest-handshake  transfer-rx  transfer-tx  persistent-keepalive
		if len(fields) >= 8 {
			peer := PeerStats{
				PublicKey:  fields[0],
				Endpoint:   fields[2],
				AllowedIPs: fields[3],
			}

			if ts, err := strconv.ParseInt(fields[4], 10, 64); err == nil && ts > 0 {
				peer.LatestHandshake = time.Unix(ts, 0)
			}
			if rx, err := strconv.ParseInt(fields[5], 10, 64); err == nil {
				peer.TransferRx = rx
			}
			if tx, err := strconv.ParseInt(fields[6], 10, 64); err == nil {
				peer.TransferTx = tx
			}

			stats.Peers = append(stats.Peers, peer)
		}
	}

	return stats, nil
}

// StartStatsPoller begins polling stats for active tunnels every 2 seconds.
func (m *Manager) StartStatsPoller(cb StatsCallback) {
	m.callback = cb
	go func() {
		ticker := time.NewTicker(2 * time.Second)
		defer ticker.Stop()

		for {
			select {
			case <-ticker.C:
				m.pollActiveStats()
			case <-m.stopPoll:
				return
			}
		}
	}()
	log.Println("stats poller started (2s interval)")
}

// StopStatsPoller stops the stats polling loop.
func (m *Manager) StopStatsPoller() {
	close(m.stopPoll)
}

// pollActiveStats fetches stats for all active tunnels.
func (m *Manager) pollActiveStats() {
	m.mu.RLock()
	var activeNames []string
	for name, t := range m.tunnels {
		if t.State == StateActive {
			activeNames = append(activeNames, name)
		}
	}
	m.mu.RUnlock()

	for _, name := range activeNames {
		stats, err := m.fetchStats(name)
		if err != nil {
			log.Printf("stats poll error for %s: %v", name, err)
			continue
		}
		if m.callback != nil {
			m.callback.OnStatsUpdated(name, stats)
		}
	}
}
