#!/usr/bin/env python3
"""
Test script to verify SOLLOL dashboard works end-to-end.
"""
import time
import logging

logging.basicConfig(level=logging.INFO)

print("=" * 70)
print("Testing SOLLOL Dashboard Integration")
print("=" * 70)

# 1. Create router with auto-dashboard
print("\n1. Creating RayHybridRouter with auto-dashboard...")
from sollol import RayHybridRouter

# Simple initialization - dashboard should auto-start
router = RayHybridRouter(
    nodes=["http://localhost:11434"],
    rpc_backends=[
        {"host": "10.9.66.154", "port": 50052},
        {"host": "10.9.66.45", "port": 50052},
        {"host": "10.9.66.142", "port": 50052},
    ]
)

print("   ✅ Router created")
print(f"   Dashboard enabled: {router.dashboard_enabled}")
print(f"   Dashboard port: {router.dashboard_port}")

# 2. Publish test log to Redis
print("\n2. Publishing test log to Redis...")
import redis
import json
from datetime import datetime

r = redis.from_url("redis://localhost:6379", decode_responses=True)
log_entry = {
    "timestamp": datetime.utcnow().isoformat(),
    "level": "INFO",
    "name": "test.dashboard",
    "message": "🎯 TEST: Dashboard integration working!",
    "process": 99999,
    "thread": 88888,
    "hostname": "test-host"
}
r.publish("sollol:dashboard:logs", json.dumps(log_entry))
print("   ✅ Test log published to Redis")

# 3. Test API endpoints
print("\n3. Testing dashboard API endpoints...")
import requests

time.sleep(2)  # Give dashboard time to start

try:
    # Test metrics endpoint
    resp = requests.get("http://localhost:8080/api/metrics", timeout=5)
    print(f"   /api/metrics: {resp.status_code}")
    print(f"   Response: {resp.json()}")

    # Test nodes endpoint
    resp = requests.get("http://localhost:8080/api/ollama_nodes", timeout=5)
    print(f"   /api/ollama_nodes: {resp.status_code}, {len(resp.json())} nodes")

    # Test RPC backends
    resp = requests.get("http://localhost:8080/api/rpc_backends", timeout=5)
    print(f"   /api/rpc_backends: {resp.status_code}, {len(resp.json())} backends")

    print("\n✅ All API endpoints responding!")

except Exception as e:
    print(f"\n❌ API test failed: {e}")

# 4. Test a simple query
print("\n4. Testing simple query through router...")
try:
    result = router.generate("Hello, test!", model="llama3.2", stream=False)
    print(f"   ✅ Query successful: {result[:50] if result else 'No response'}...")
except Exception as e:
    print(f"   ❌ Query failed: {e}")

print("\n" + "=" * 70)
print("Dashboard running at: http://localhost:8080")
print("Press Ctrl+C to stop...")
print("=" * 70)

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n\nStopping...")
