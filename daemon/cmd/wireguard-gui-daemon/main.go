package main

import (
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/gumidnight/wireguard-gui/daemon/internal/dbus"
	"github.com/gumidnight/wireguard-gui/daemon/internal/tunnel"
)

func main() {
	log.SetFlags(log.Ldate | log.Ltime | log.Lshortfile)
	log.Println("wireguard-gui-daemon starting...")

	// Verify running as root
	if os.Geteuid() != 0 {
		log.Fatal("daemon must run as root")
	}

	// Initialize tunnel manager
	mgr, err := tunnel.NewManager("/etc/wireguard")
	if err != nil {
		log.Fatalf("failed to initialize tunnel manager: %v", err)
	}

	// Reconcile state on startup: detect already-active interfaces
	if err := mgr.Reconcile(); err != nil {
		log.Printf("warning: state reconciliation error: %v", err)
	}

	// Start D-Bus service
	svc, err := dbus.NewService(mgr)
	if err != nil {
		log.Fatalf("failed to start D-Bus service: %v", err)
	}
	defer svc.Close()

	log.Println("daemon ready on D-Bus: org.wireguardgui.Manager")

	// Start stats polling in background
	mgr.StartStatsPoller(svc)

	// Wait for shutdown signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)
	sig := <-sigCh
	log.Printf("received signal %v, shutting down...", sig)
	mgr.StopStatsPoller()
}
