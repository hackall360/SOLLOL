#!/usr/bin/env python3
"""Test script to generate sample routing events."""

import time
from sollol.routing_logger import get_routing_logger

# Enable console output for debugging
logger = get_routing_logger(console_output=True)

print("🧪 Testing SOLLOL Routing Logger\n")
print("Generating sample routing events...\n")

# Test 1: Route decision to Ollama
logger.log_route_decision(
    model="llama3.2:3b",
    backend="ollama",
    reason="sufficient_resources (estimated 2.5GB)",
    parameter_count=3
)

time.sleep(0.5)

# Test 2: Route decision to RPC
logger.log_route_decision(
    model="llama3.1:70b",
    backend="rpc",
    reason="insufficient_ollama_resources (requires 40.0GB)",
    parameter_count=70
)

time.sleep(0.5)

# Test 3: Fallback from Ollama to RPC
logger.log_fallback(
    model="codellama:13b",
    from_backend="ollama",
    to_backend="rpc",
    reason="ollama_error: Out of memory"
)

time.sleep(0.5)

# Test 4: Coordinator start
logger.log_coordinator_start(
    model="llama3.1:70b",
    rpc_backends=3,
    coordinator_host="127.0.0.1",
    coordinator_port=18080
)

time.sleep(0.5)

# Test 5: Ollama node selection
logger.log_ollama_node_selected(
    node_url="10.9.66.48:11434",
    model="llama3.2:3b",
    reason="lowest_latency (15ms) + high_vram (8192MB free)",
    confidence=0.92,
    priority=5
)

time.sleep(0.5)

# Test 6: Cached routing decision
logger.log_route_decision(
    model="llama3.2:3b",
    backend="ollama",
    reason="cached_routing_decision",
    cached=True
)

print("\n✅ Test events published to Redis!")
print("📺 Watch them live with: python -m sollol.routing_viewer")
print("📜 View history with: python -m sollol.routing_viewer --history 10")
