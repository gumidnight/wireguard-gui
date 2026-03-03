"""Allow running as `python -m wireguard_gui`."""

from wireguard_gui.app import main

if __name__ == "__main__":
    raise SystemExit(main())
