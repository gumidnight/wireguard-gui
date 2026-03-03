package security

import (
	"testing"
)

func TestValidateTunnelName(t *testing.T) {
	tests := []struct {
		name    string
		input   string
		wantErr bool
	}{
		{"valid simple", "wg0", false},
		{"valid with dash", "wg-office", false},
		{"valid with underscore", "my_tunnel", false},
		{"valid max length", "abcdefghijklmno", false}, // 15 chars
		{"empty", "", true},
		{"too long", "abcdefghijklmnop", true}, // 16 chars
		{"starts with dash", "-wg0", true},
		{"starts with underscore", "_wg0", true},
		{"has space", "wg 0", true},
		{"has dot", "wg.0", true},
		{"path traversal", "../etc", true},
		{"has slash", "wg/0", true},
		{"has backslash", "wg\\0", true},
		{"shell metachar", "wg;ls", true},
		{"backtick", "wg`ls`", true},
		{"dollar sign", "wg$HOME", true},
		{"pipe", "wg|ls", true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			err := ValidateTunnelName(tt.input)
			if (err != nil) != tt.wantErr {
				t.Errorf("ValidateTunnelName(%q) error = %v, wantErr %v", tt.input, err, tt.wantErr)
			}
		})
	}
}

func TestSanitizeConfigForDisplay(t *testing.T) {
	input := `[Interface]
PrivateKey = abc123secret
Address = 10.0.0.1/24

[Peer]
PublicKey = xyz789public
Endpoint = 1.2.3.4:51820`

	result := SanitizeConfigForDisplay(input)

	if !contains(result, "(hidden)") {
		t.Error("expected PrivateKey to be hidden")
	}
	if contains(result, "abc123secret") {
		t.Error("PrivateKey value should not appear in sanitized output")
	}
	if !contains(result, "xyz789public") {
		t.Error("PublicKey should still be visible")
	}
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && searchString(s, substr)
}

func searchString(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}
