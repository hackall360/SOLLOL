#!/bin/bash
# Complete SOLLOL RPC Backend Setup
# Installs RPC server + GPU monitoring as systemd services

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOLLOL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=================================="
echo "SOLLOL RPC Backend Complete Setup"
echo "=================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Please install Python 3.8+"
    exit 1
fi
echo "✅ Python3 found"

# Check cmake
if ! command -v cmake &> /dev/null; then
    echo "❌ cmake not found. Installing..."
    sudo apt-get update && sudo apt-get install -y cmake build-essential
fi
echo "✅ cmake found"

# Check Redis
if ! command -v redis-cli &> /dev/null; then
    echo "⚠️  Redis not found. GPU monitoring requires Redis."
    echo "   Install Redis with: sudo apt-get install redis-server"
    echo "   Or skip GPU monitoring with --no-gpu-monitoring"
    read -p "Continue without GPU monitoring? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    SKIP_GPU=true
else
    echo "✅ Redis found"
    SKIP_GPU=false
fi

# Build llama.cpp
echo ""
echo "Step 1/3: Building llama.cpp with RPC support..."
echo "-----------------------------------------------"

LLAMA_DIR="$HOME/llama.cpp"

if [ ! -d "$LLAMA_DIR" ]; then
    echo "Cloning llama.cpp..."
    git clone https://github.com/ggerganov/llama.cpp "$LLAMA_DIR"
fi

cd "$LLAMA_DIR"

# Check if we need to update
CURRENT_COMMIT=$(git rev-parse --short HEAD)
echo "Current llama.cpp commit: $CURRENT_COMMIT"

# Pull latest (includes build 6743+ with stability fixes)
echo "Updating to latest stable version (recommended: build 6743+)..."
git pull origin master

echo "Building with RPC support..."
cmake -B build -DGGML_RPC=ON -DLLAMA_CURL=OFF
cmake --build build --config Release --target rpc-server -j$(nproc)

# Copy to ~/.local/bin
mkdir -p "$HOME/.local/bin"
cp "$LLAMA_DIR/build/bin/rpc-server" "$HOME/.local/bin/"
chmod +x "$HOME/.local/bin/rpc-server"
echo "✅ RPC server built and installed to ~/.local/bin/rpc-server"

# Install RPC server service
echo ""
echo "Step 2/3: Installing RPC server systemd service..."
echo "--------------------------------------------------"
"$SCRIPT_DIR/install-rpc-service.sh"

# Install GPU monitoring (optional)
if [ "$SKIP_GPU" = false ]; then
    echo ""
    echo "Step 3/3: Installing GPU monitoring service..."
    echo "----------------------------------------------"

    # Install Python dependencies
    pip install gpustat redis

    # Copy gpu_reporter.py to user home
    cp "$SOLLOL_DIR/gpu_reporter.py" "$HOME/SOLLOL/" 2>/dev/null || \
        cp "$SOLLOL_DIR/gpu_reporter.py" "$HOME/"

    # Install service
    "$SCRIPT_DIR/install-gpu-reporter-service.sh"
else
    echo ""
    echo "Step 3/3: Skipping GPU monitoring (Redis not available)"
    echo "-------------------------------------------------------"
fi

# Summary
echo ""
echo "=================================="
echo "✅ Installation Complete!"
echo "=================================="
echo ""
echo "Services installed:"
echo "  ✅ sollol-rpc-server    - llama.cpp RPC backend (port 50052)"
if [ "$SKIP_GPU" = false ]; then
    echo "  ✅ sollol-gpu-reporter  - GPU monitoring with Redis pub/sub"
fi
echo ""
echo "Service management:"
echo "  systemctl --user status sollol-rpc-server"
echo "  systemctl --user restart sollol-rpc-server"
echo "  journalctl --user -u sollol-rpc-server -f"
echo ""
if [ "$SKIP_GPU" = false ]; then
    echo "  systemctl --user status sollol-gpu-reporter"
    echo "  systemctl --user restart sollol-gpu-reporter"
    echo "  journalctl --user -u sollol-gpu-reporter -f"
    echo ""
fi
echo "Next steps:"
echo "  1. Start SOLLOL with HybridRouter to use RPC backends"
echo "  2. Run 'sollol discover' to verify RPC backends are detected"
echo "  3. Test with large models (70B+) for distributed inference"
echo ""
echo "Documentation:"
echo "  - DISTRIBUTED_INFERENCE_STATUS.md - Testing results and troubleshooting"
echo "  - GPU_MONITORING_SETUP.md - GPU monitoring architecture"
echo ""
