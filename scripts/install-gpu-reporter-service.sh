#!/bin/bash
# Install SOLLOL GPU Reporter as systemd user service

set -e

echo "Installing SOLLOL GPU Reporter systemd service..."

# Check if gpustat is installed
if ! python3 -c "import gpustat" 2>/dev/null; then
    echo "⚠️  gpustat not installed. Installing..."
    pip install gpustat
fi

# Check if redis is available
if ! python3 -c "import redis" 2>/dev/null; then
    echo "⚠️  redis-py not installed. Installing..."
    pip install redis
fi

# Create user systemd directory if needed
mkdir -p ~/.config/systemd/user/

# Copy service file
cp "$(dirname "$0")/../systemd/sollol-gpu-reporter.service" ~/.config/systemd/user/

# Replace %h and %u placeholders
sed -i "s|%h|$HOME|g" ~/.config/systemd/user/sollol-gpu-reporter.service
sed -i "s|%u|$USER|g" ~/.config/systemd/user/sollol-gpu-reporter.service

# Reload systemd
systemctl --user daemon-reload

# Enable and start service
systemctl --user enable sollol-gpu-reporter.service
systemctl --user start sollol-gpu-reporter.service

# Enable lingering so service runs even when not logged in
loginctl enable-linger $USER

echo ""
echo "✅ SOLLOL GPU Reporter installed as systemd service!"
echo ""
echo "Useful commands:"
echo "  systemctl --user status sollol-gpu-reporter    # Check status"
echo "  systemctl --user restart sollol-gpu-reporter   # Restart service"
echo "  systemctl --user stop sollol-gpu-reporter      # Stop service"
echo "  journalctl --user -u sollol-gpu-reporter -f    # View logs"
echo ""
echo "Configuration:"
echo "  Edit ~/.config/systemd/user/sollol-gpu-reporter.service to customize:"
echo "    - REDIS_HOST (default: localhost)"
echo "    - REDIS_PORT (default: 6379)"
echo "    - OLLAMA_PORT (default: 11434)"
echo "    - REPORT_INTERVAL (default: 5 seconds)"
echo ""
