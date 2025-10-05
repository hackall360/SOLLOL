#!/bin/bash
# Install SOLLOL RPC Server as systemd user service

set -e

echo "Installing SOLLOL RPC Server systemd service..."

# Create user systemd directory if needed
mkdir -p ~/.config/systemd/user/

# Copy service file
cp "$(dirname "$0")/../systemd/sollol-rpc-server.service" ~/.config/systemd/user/

# Replace %h and %u placeholders
sed -i "s|%h|$HOME|g" ~/.config/systemd/user/sollol-rpc-server.service
sed -i "s|%u|$USER|g" ~/.config/systemd/user/sollol-rpc-server.service

# Reload systemd
systemctl --user daemon-reload

# Enable and start service
systemctl --user enable sollol-rpc-server.service
systemctl --user start sollol-rpc-server.service

# Enable lingering so service runs even when not logged in
loginctl enable-linger $USER

echo ""
echo "✅ SOLLOL RPC Server installed as systemd service!"
echo ""
echo "Useful commands:"
echo "  systemctl --user status sollol-rpc-server    # Check status"
echo "  systemctl --user restart sollol-rpc-server   # Restart service"
echo "  systemctl --user stop sollol-rpc-server      # Stop service"
echo "  journalctl --user -u sollol-rpc-server -f    # View logs"
echo ""
