# Contributing to WireGuard GUI

Thank you for your interest in contributing! Contributions of all kinds are welcome — bug reports, feature requests, documentation improvements, and code.

## Getting Started

1. **Fork** the repository and clone your fork.
2. Create a branch for your change:
   ```bash
   git checkout -b feat/my-feature
   ```
3. Set up the development environment (see [README.md](README.md#development)).
4. Make your changes and test them.
5. Open a **Pull Request** against `main`.

## Development Environment

```bash
# Install system dependencies (Ubuntu 22.04/24.04)
sudo apt install wireguard-tools golang-go python3-gi python3-gi-cairo \
    gir1.2-gtk-4.0 gir1.2-adw-1 python3-dasbus libadwaita-1-dev \
    gir1.2-ayatanaappindicator3-0.1

# Build the daemon
make daemon

# Run daemon (needs root)
make run-daemon

# Run GUI (separate terminal, no root needed)
make run-gui
```

## Project Structure

```
daemon/         Go daemon — runs as root via systemd, owns wg-quick/wg calls
gui/            Python/GTK4 GUI — runs unprivileged in the user session
data/           System configs (D-Bus policy, polkit, systemd unit, desktop entry)
```

## Code Style

- **Go**: run `gofmt` and `go vet` before committing.
- **Python**: follow PEP 8; use `ruff` or `flake8` to lint.
- Keep commits focused and write clear commit messages.

## Reporting Bugs

Please use the [GitHub issue tracker](https://github.com/gumidnight/wireguard-gui/issues) and include:
- Ubuntu version and GNOME version
- Steps to reproduce
- Expected vs actual behaviour
- Relevant log output (`journalctl -u wireguard-gui-daemon` for daemon issues)

## Feature Requests

Open an issue with the **enhancement** label describing the use case and proposed solution.

## License

By contributing you agree that your contributions will be licensed under the [MIT License](LICENSE).
