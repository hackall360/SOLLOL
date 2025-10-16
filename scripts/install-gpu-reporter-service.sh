#!/bin/bash
# Install SOLLOL GPU Reporter as systemd user service

set -e

echo "================================================"
echo "SOLLOL GPU Reporter Service Installer"
echo "================================================"
echo ""

# Check if gpustat is installed
if ! python3 -c "import gpustat" 2>/dev/null; then
    echo "⚠️  gpustat not installed. Installing..."
    pip install --user gpustat
fi

# Check if redis is available
if ! python3 -c "import redis" 2>/dev/null; then
    echo "⚠️  redis-py not installed. Installing..."
    pip install --user redis
fi

# Auto-detect local IP address for node ID
LOCAL_IP=$(hostname -I | awk '{print $1}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="127.0.0.1"
fi

# Prompt for configuration
echo ""
echo "Configuration:"
echo "--------------"
echo ""
read -p "Redis host [localhost]: " REDIS_HOST
REDIS_HOST=${REDIS_HOST:-localhost}

read -p "Redis port [6379]: " REDIS_PORT
REDIS_PORT=${REDIS_PORT:-6379}

read -p "Node ID [$LOCAL_IP:11434]: " NODE_ID
NODE_ID=${NODE_ID:-$LOCAL_IP:11434}

read -p "Report interval in seconds [5]: " REPORT_INTERVAL
REPORT_INTERVAL=${REPORT_INTERVAL:-5}

echo ""
echo "Installing with:"
echo "  Redis Host: $REDIS_HOST"
echo "  Redis Port: $REDIS_PORT"
echo "  Node ID: $NODE_ID"
echo "  Interval: ${REPORT_INTERVAL}s"
echo ""

# Create user systemd directory if needed
mkdir -p ~/.config/systemd/user/

# Copy service file
cp "$(dirname "$0")/../systemd/sollol-gpu-reporter.service" ~/.config/systemd/user/

# Replace placeholders
sed -i "s|%h|$HOME|g" ~/.config/systemd/user/sollol-gpu-reporter.service
sed -i "s|%u|$USER|g" ~/.config/systemd/user/sollol-gpu-reporter.service
sed -i "s|%REDIS_HOST%|$REDIS_HOST|g" ~/.config/systemd/user/sollol-gpu-reporter.service
sed -i "s|%REDIS_PORT%|$REDIS_PORT|g" ~/.config/systemd/user/sollol-gpu-reporter.service
sed -i "s|%NODE_ID%|$NODE_ID|g" ~/.config/systemd/user/sollol-gpu-reporter.service
sed -i "s|%REPORT_INTERVAL%|$REPORT_INTERVAL|g" ~/.config/systemd/user/sollol-gpu-reporter.service

# Reload systemd
systemctl --user daemon-reload

# Enable and start service
systemctl --user enable sollol-gpu-reporter.service
systemctl --user start sollol-gpu-reporter.service

# Enable lingering so service runs even when not logged in
loginctl enable-linger $USER 2>/dev/null || echo "⚠️  Could not enable lingering (may require sudo)"

echo ""
echo "================================================"
echo "✅ SOLLOL GPU Reporter installed successfully!"
echo "================================================"
echo ""
echo "Service Status:"
systemctl --user status sollol-gpu-reporter.service --no-pager || true
echo ""
echo "Useful Commands:"
echo "  systemctl --user status sollol-gpu-reporter    # Check status"
echo "  systemctl --user restart sollol-gpu-reporter   # Restart service"
echo "  systemctl --user stop sollol-gpu-reporter      # Stop service"
echo "  journalctl --user -u sollol-gpu-reporter -f    # View logs"
echo ""
echo "Configuration File:"
echo "  ~/.config/systemd/user/sollol-gpu-reporter.service"
echo ""
