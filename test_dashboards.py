#!/usr/bin/env python3
"""
Quick test to verify Ray and Dask dashboards are properly initialized.
"""

import sys
import os

# Add local src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import time
import ray
import requests
from sollol import RayAdvancedRouter, OllamaPool, UnifiedDashboard

print("=" * 80)
print("Testing Dashboard Initialization")
print("=" * 80 + "\n")

# Test 1: Initialize RayAdvancedRouter (should start Ray with dashboard)
print("1️⃣ Initializing RayAdvancedRouter...")
try:
    router = RayAdvancedRouter(
        ollama_pool=OllamaPool.auto_configure(discover_all_nodes=True),
        enable_batching=False,
        enable_speculation=False,
        auto_discover_rpc=False,  # Don't need RPC for this test
    )
    print("✅ Router initialized\n")
except Exception as e:
    print(f"❌ Router initialization failed: {e}\n")
    exit(1)

# Test 2: Check if Ray is initialized
print("2️⃣ Checking Ray status...")
if ray.is_initialized():
    print("✅ Ray is initialized")
    print(f"   Nodes: {len(ray.nodes())}")
    print(f"   Resources: {ray.cluster_resources()}\n")
else:
    print("❌ Ray is not initialized\n")

# Test 3: Check if Ray dashboard is accessible
print("3️⃣ Checking Ray dashboard accessibility...")
time.sleep(2)  # Give dashboard a moment to start
try:
    response = requests.get("http://localhost:8265", timeout=5)
    if response.status_code == 200:
        print("✅ Ray dashboard is accessible at http://localhost:8265\n")
    else:
        print(f"⚠️  Ray dashboard returned status {response.status_code}\n")
except requests.exceptions.ConnectionError:
    print("❌ Ray dashboard is NOT accessible at http://localhost:8265")
    print("   This means Ray dashboard is not enabled or not running\n")
except Exception as e:
    print(f"❌ Error checking Ray dashboard: {e}\n")

# Test 4: Initialize UnifiedDashboard with Dask
print("4️⃣ Initializing UnifiedDashboard with Dask...")
try:
    dashboard = UnifiedDashboard(
        router=router,
        ray_dashboard_port=8265,
        dask_dashboard_port=8787,
        dashboard_port=8080,
        enable_dask=True,  # Enable Dask
    )
    print("✅ UnifiedDashboard initialized\n")
except Exception as e:
    print(f"⚠️  UnifiedDashboard initialization: {e}\n")

# Test 5: Check if Dask dashboard is accessible
if dashboard.dask_client:
    print("5️⃣ Checking Dask dashboard accessibility...")
    time.sleep(2)
    try:
        response = requests.get("http://localhost:8787", timeout=5)
        if response.status_code == 200:
            print("✅ Dask dashboard is accessible at http://localhost:8787\n")
        else:
            print(f"⚠️  Dask dashboard returned status {response.status_code}\n")
    except requests.exceptions.ConnectionError:
        print("❌ Dask dashboard is NOT accessible at http://localhost:8787\n")
    except Exception as e:
        print(f"❌ Error checking Dask dashboard: {e}\n")
else:
    print("5️⃣ Dask client not initialized (skipped)\n")

print("=" * 80)
print("Dashboard Test Complete")
print("=" * 80)
print("\n📊 Expected URLs:")
print("   - Ray Dashboard:     http://localhost:8265")
print("   - Dask Dashboard:    http://localhost:8787")
print("   - Unified Dashboard: http://localhost:8080")
print("\n💡 To start the unified dashboard, run:")
print("   python3 examples/unified_dashboard_demo.py")
