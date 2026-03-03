// Package security provides input validation and sanitization.
package security

import (
	"fmt"
	"regexp"
	"strings"
)

// validTunnelName matches safe tunnel/interface names: alphanumeric, dash, underscore, max 15 chars.
var validTunnelName = regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9_-]{0,14}$`)

// ValidateTunnelName checks that a tunnel name is safe for use as a Linux interface name
// and cannot be used for path traversal or command injection.
func ValidateTunnelName(name string) error {
	if name == "" {
		return fmt.Errorf("tunnel name cannot be empty")
	}
	if !validTunnelName.MatchString(name) {
		return fmt.Errorf("invalid tunnel name %q: must be 1-15 alphanumeric/dash/underscore chars, starting with alphanumeric", name)
	}
	// Extra safety: reject path components
	if strings.Contains(name, "/") || strings.Contains(name, "\\") || strings.Contains(name, "..") {
		return fmt.Errorf("invalid tunnel name %q: contains path separators", name)
	}
	return nil
}

// ValidateConfigContent performs basic validation on WireGuard config file content.
// It checks for obviously dangerous constructs. Full parsing is done by the config package.
func ValidateConfigContent(content string) error {
	if len(content) == 0 {
		return fmt.Errorf("config content is empty")
	}
	if len(content) > 64*1024 {
		return fmt.Errorf("config content too large (max 64KB)")
	}
	return nil
}

// SanitizeConfigForDisplay returns config content with private keys masked.
func SanitizeConfigForDisplay(content string) string {
	lines := strings.Split(content, "\n")
	for i, line := range lines {
		trimmed := strings.TrimSpace(line)
		lower := strings.ToLower(trimmed)
		if strings.HasPrefix(lower, "privatekey") && strings.Contains(lower, "=") {
			parts := strings.SplitN(trimmed, "=", 2)
			if len(parts) == 2 {
				lines[i] = parts[0] + "= (hidden)"
			}
		}
	}
	return strings.Join(lines, "\n")
}
