package config

import (
	"testing"
)

const sampleConfig = `[Interface]
PrivateKey = yAnz5TF+lXXJte14tji3zlMNq+hd2rYUIgJBgB3fBmk=
Address = 10.200.100.8/24
DNS = 10.200.100.1

[Peer]
PublicKey = xTIBA5rboUvnH4htodjb6e697QjLERt1NAB4mZqp8Dg=
AllowedIPs = 0.0.0.0/0
Endpoint = demo.wireguard.com:51820
PersistentKeepalive = 25
`

func TestParseValidConfig(t *testing.T) {
	cfg, err := Parse(sampleConfig)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if cfg.Interface.PrivateKey == "" {
		t.Error("expected PrivateKey to be parsed")
	}
	if cfg.Interface.Address != "10.200.100.8/24" {
		t.Errorf("Address = %q, want %q", cfg.Interface.Address, "10.200.100.8/24")
	}
	if cfg.Interface.DNS != "10.200.100.1" {
		t.Errorf("DNS = %q, want %q", cfg.Interface.DNS, "10.200.100.1")
	}
	if len(cfg.Peers) != 1 {
		t.Fatalf("expected 1 peer, got %d", len(cfg.Peers))
	}
	if cfg.Peers[0].Endpoint != "demo.wireguard.com:51820" {
		t.Errorf("Endpoint = %q, want %q", cfg.Peers[0].Endpoint, "demo.wireguard.com:51820")
	}
	if cfg.Peers[0].PersistentKeepalive != "25" {
		t.Errorf("PersistentKeepalive = %q, want %q", cfg.Peers[0].PersistentKeepalive, "25")
	}
}

func TestParseMissingPrivateKey(t *testing.T) {
	content := `[Interface]
Address = 10.0.0.1/24

[Peer]
PublicKey = abc123
`
	_, err := Parse(content)
	if err == nil {
		t.Error("expected error for missing PrivateKey")
	}
}

func TestParseNoPeers(t *testing.T) {
	content := `[Interface]
PrivateKey = abc123
Address = 10.0.0.1/24
`
	_, err := Parse(content)
	if err == nil {
		t.Error("expected error for no peers")
	}
}

func TestParseMultiplePeers(t *testing.T) {
	content := `[Interface]
PrivateKey = abc123
Address = 10.0.0.1/24

[Peer]
PublicKey = peer1key
Endpoint = 1.1.1.1:51820
AllowedIPs = 10.0.1.0/24

[Peer]
PublicKey = peer2key
Endpoint = 2.2.2.2:51820
AllowedIPs = 10.0.2.0/24
`
	cfg, err := Parse(content)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(cfg.Peers) != 2 {
		t.Errorf("expected 2 peers, got %d", len(cfg.Peers))
	}
}

func TestHasPostScripts(t *testing.T) {
	content := `[Interface]
PrivateKey = abc123
PostUp = iptables -A FORWARD -i %i -j ACCEPT
PostDown = iptables -D FORWARD -i %i -j ACCEPT

[Peer]
PublicKey = peer1key
`
	cfg, err := Parse(content)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !cfg.HasPostScripts() {
		t.Error("expected HasPostScripts() to be true")
	}
}

func TestSummary(t *testing.T) {
	cfg, err := Parse(sampleConfig)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	s := cfg.Summary()
	if s["address"] != "10.200.100.8/24" {
		t.Errorf("summary address = %q", s["address"])
	}
	if s["peers"] != "1" {
		t.Errorf("summary peers = %q", s["peers"])
	}
}
