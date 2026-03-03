// Package config handles WireGuard .conf file parsing and serialization.
package config

import (
	"bufio"
	"fmt"
	"strings"
)

// Config represents a parsed WireGuard configuration file.
type Config struct {
	Interface InterfaceSection
	Peers     []PeerSection
	Raw       string // Original raw content
}

// InterfaceSection represents the [Interface] section.
type InterfaceSection struct {
	PrivateKey string
	Address    string
	DNS        string
	ListenPort string
	MTU        string
	PostUp     string
	PostDown   string
	Table      string
}

// PeerSection represents a [Peer] section.
type PeerSection struct {
	PublicKey           string
	PresharedKey        string
	AllowedIPs          string
	Endpoint            string
	PersistentKeepalive string
}

// Parse parses a WireGuard .conf file content into a Config struct.
func Parse(content string) (*Config, error) {
	cfg := &Config{Raw: content}
	scanner := bufio.NewScanner(strings.NewReader(content))

	var currentSection string
	var currentPeer *PeerSection

	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())

		// Skip empty lines and comments
		if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, ";") {
			continue
		}

		// Section headers
		lower := strings.ToLower(line)
		if lower == "[interface]" {
			currentSection = "interface"
			continue
		}
		if lower == "[peer]" {
			currentSection = "peer"
			if currentPeer != nil {
				cfg.Peers = append(cfg.Peers, *currentPeer)
			}
			currentPeer = &PeerSection{}
			continue
		}

		// Key = Value pairs
		parts := strings.SplitN(line, "=", 2)
		if len(parts) != 2 {
			continue // Skip malformed lines
		}
		key := strings.TrimSpace(parts[0])
		value := strings.TrimSpace(parts[1])
		keyLower := strings.ToLower(key)

		switch currentSection {
		case "interface":
			switch keyLower {
			case "privatekey":
				cfg.Interface.PrivateKey = value
			case "address":
				cfg.Interface.Address = value
			case "dns":
				cfg.Interface.DNS = value
			case "listenport":
				cfg.Interface.ListenPort = value
			case "mtu":
				cfg.Interface.MTU = value
			case "postup":
				cfg.Interface.PostUp = value
			case "postdown":
				cfg.Interface.PostDown = value
			case "table":
				cfg.Interface.Table = value
			}
		case "peer":
			if currentPeer == nil {
				return nil, fmt.Errorf("peer key-value outside [Peer] section")
			}
			switch keyLower {
			case "publickey":
				currentPeer.PublicKey = value
			case "presharedkey":
				currentPeer.PresharedKey = value
			case "allowedips":
				currentPeer.AllowedIPs = value
			case "endpoint":
				currentPeer.Endpoint = value
			case "persistentkeepalive":
				currentPeer.PersistentKeepalive = value
			}
		}
	}

	// Don't forget the last peer
	if currentPeer != nil {
		cfg.Peers = append(cfg.Peers, *currentPeer)
	}

	// Basic validation
	if cfg.Interface.PrivateKey == "" {
		return nil, fmt.Errorf("missing PrivateKey in [Interface] section")
	}
	if len(cfg.Peers) == 0 {
		return nil, fmt.Errorf("no [Peer] sections found")
	}
	for i, peer := range cfg.Peers {
		if peer.PublicKey == "" {
			return nil, fmt.Errorf("peer %d missing PublicKey", i+1)
		}
	}

	return cfg, nil
}

// HasPostScripts returns true if the config has PostUp or PostDown scripts.
func (c *Config) HasPostScripts() bool {
	return c.Interface.PostUp != "" || c.Interface.PostDown != ""
}

// Summary returns a human-readable summary of the config.
func (c *Config) Summary() map[string]string {
	s := map[string]string{
		"address": c.Interface.Address,
		"dns":     c.Interface.DNS,
	}
	if len(c.Peers) > 0 {
		s["peers"] = fmt.Sprintf("%d", len(c.Peers))
		s["endpoint"] = c.Peers[0].Endpoint
		s["allowed_ips"] = c.Peers[0].AllowedIPs
	}
	return s
}
