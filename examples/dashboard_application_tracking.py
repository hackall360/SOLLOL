#!/usr/bin/env python3
"""
Example: Application Tracking with SOLLOL Unified Dashboard

This demonstrates how any application using SOLLOL can register itself
with the centralized dashboard for network-wide observability.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
from sollol import DashboardClient, RayHybridRouter, OllamaPool

print("=" * 70)
print("SOLLOL Application Tracking Demo")
print("=" * 70)
print()

# Example 1: Register application with dashboard
print("1️⃣  Registering application with dashboard...")
print()

client = DashboardClient(
    app_name="MyApp - Example",
    router_type="RayHybridRouter",
    version="1.0.0",
    dashboard_url="http://localhost:8080",
    metadata={
        "environment": "development",
        "node_count": 2,
    }
)

print(f"✅ Registered as: {client.app_name}")
print(f"   App ID: {client.app_id}")
print(f"   Router: {client.router_type}")
print()

# Example 2: Create SOLLOL router (normal usage)
print("2️⃣  Creating SOLLOL router...")
print()

router = RayHybridRouter(
    ollama_pool=OllamaPool.auto_configure(discover_all_nodes=True),
    num_ray_workers=4,
    enable_distributed=False,
)

print("✅ Router initialized")
print()

# Example 3: Update metadata during runtime
print("3️⃣  Updating metadata during runtime...")
print()

client.update_metadata({
    "requests_processed": 100,
    "uptime_hours": 2.5,
})

print("✅ Metadata updated")
print()

# Dashboard shows:
# - Application name, router type, version
# - Status (active/stale based on heartbeats)
# - Uptime
# - Custom metadata

print("=" * 70)
print("Dashboard Access")
print("=" * 70)
print()
print("📊 View all applications at:")
print("   http://localhost:8080")
print()
print("   The 'Applications' panel shows:")
print("   • Name, Router Type, Status, Uptime")
print("   • Real-time updates (heartbeat every 10s)")
print("   • Auto-cleanup when app stops")
print()

print("🔌 Or access via API:")
print("   GET  http://localhost:8080/api/applications")
print("   POST http://localhost:8080/api/applications/register")
print("   POST http://localhost:8080/api/applications/heartbeat")
print()

print("📡 Or stream via WebSocket:")
print("   ws://localhost:8080/ws/applications")
print("   (Real-time events: app_registered, app_unregistered, app_stale)")
print()

# Keep running for demo
print("=" * 70)
print("Demo Running - Press Ctrl+C to exit")
print("=" * 70)
print()
print("💡 Check http://localhost:8080 to see this application listed!")
print("   It will automatically send heartbeats every 10 seconds.")
print()

try:
    # Simulate application doing work
    for i in range(60):
        time.sleep(1)
        if i % 10 == 0:
            print(f"⏱️  Running for {i} seconds... (still sending heartbeats)")

except KeyboardInterrupt:
    print("\n\n🛑 Shutting down...")
    client.unregister()
    print("✅ Unregistered from dashboard")
