#!/usr/bin/env python3
"""
SOLLOL Unified Dashboard - Programmatic Usage Example

This example shows how any application can use SOLLOL's unified dashboard
for universal network observability - it works WITHOUT requiring a router!

The dashboard automatically:
1. Auto-discovers Ollama nodes on the network
2. Detects RPC backends
3. Streams real-time events via WebSocket
4. Provides HTTP endpoints for current state
"""

from sollol.unified_dashboard import UnifiedDashboard

def example_1_standalone():
    """
    Example 1: Standalone dashboard (no router needed)

    Perfect for monitoring your Ollama cluster without SOLLOL gateway.
    """
    print("=" * 70)
    print("Example 1: Standalone Dashboard (Router-Agnostic)")
    print("=" * 70)

    # Create dashboard without any router - it auto-discovers nodes
    dashboard = UnifiedDashboard(
        dashboard_port=8080,
        ray_dashboard_port=8265,
        dask_dashboard_port=8787
    )

    print("\n✅ Dashboard initialized (router-agnostic)")
    print("   📊 HTTP Endpoints:")
    print("      - http://localhost:8080/api/network/nodes")
    print("      - http://localhost:8080/api/network/backends")
    print("      - http://localhost:8080/api/network/health")
    print("\n   🔌 WebSocket Endpoints:")
    print("      - ws://localhost:8080/ws/network/nodes (event-driven)")
    print("      - ws://localhost:8080/ws/network/backends (event-driven)")
    print("      - ws://localhost:8080/ws/ollama_activity (model lifecycle)")
    print("      - ws://localhost:8080/ws/logs (centralized logs)")
    print("\n   🎨 Web UI:")
    print("      - http://localhost:8080")
    print("\n🚀 Starting dashboard...")

    # Run dashboard - blocks until stopped
    dashboard.run(host="0.0.0.0", debug=False)


def example_2_with_router():
    """
    Example 2: Dashboard with SOLLOL router

    When using SOLLOL gateway, pass the router to get enhanced metrics.
    """
    print("=" * 70)
    print("Example 2: Dashboard with SOLLOL Router")
    print("=" * 70)

    # This is how you'd use it with a SOLLOL router
    from sollol.ray_hybrid_router import RayHybridRouter

    # Create router
    router = RayHybridRouter(
        num_ray_workers=4,
        enable_distributed=False
    )

    # Create dashboard WITH router (gets enhanced metrics)
    dashboard = UnifiedDashboard(
        router=router,
        dashboard_port=8080
    )

    print("\n✅ Dashboard initialized with router")
    print("   📊 Enhanced features:")
    print("      - Router metrics (pool stats, routing decisions)")
    print("      - Ray cluster info")
    print("      - Performance analytics (P50/P95/P99)")
    print("\n🚀 Starting dashboard...")

    dashboard.run(host="0.0.0.0")


def example_3_synapticllamas():
    """
    Example 3: How to use from SynapticLlamas

    Shows integration pattern for SynapticLlamas or any other application.
    """
    print("=" * 70)
    print("Example 3: Integration from SynapticLlamas")
    print("=" * 70)

    # In your SynapticLlamas main.py or __init__.py:
    print("\n```python")
    print("from sollol.unified_dashboard import UnifiedDashboard")
    print("import threading")
    print()
    print("def start_sollol_dashboard():")
    print('    """Start SOLLOL dashboard in background thread."""')
    print("    dashboard = UnifiedDashboard(dashboard_port=8080)")
    print("    dashboard.run(host='0.0.0.0')")
    print()
    print("# Start dashboard in background")
    print("dashboard_thread = threading.Thread(")
    print("    target=start_sollol_dashboard,")
    print("    daemon=True,")
    print("    name='SOLLOLDashboard'")
    print(")")
    print("dashboard_thread.start()")
    print()
    print("# Your application continues running...")
    print("# Dashboard is now monitoring your network at http://localhost:8080")
    print("```")
    print("\n✅ Dashboard runs in background, your app continues normally")


def example_4_websocket_client():
    """
    Example 4: WebSocket client example

    Shows how to consume real-time events from the dashboard.
    """
    print("=" * 70)
    print("Example 4: WebSocket Client (Consuming Events)")
    print("=" * 70)

    print("\n```python")
    print("import websocket")
    print("import json")
    print()
    print("# Connect to node events stream")
    print("ws = websocket.create_connection('ws://localhost:8080/ws/network/nodes')")
    print()
    print("while True:")
    print("    event = json.loads(ws.recv())")
    print("    ")
    print("    if event['type'] == 'node_discovered':")
    print("        print(f\"✅ {event['message']}\")")
    print("    elif event['type'] == 'status_change':")
    print("        print(f\"🔄 {event['message']}\")")
    print("    elif event['type'] == 'node_removed':")
    print("        print(f\"❌ {event['message']}\")")
    print("```")
    print("\nEvent Types:")
    print("  /ws/network/nodes:")
    print("    - node_discovered")
    print("    - status_change (healthy ↔ unhealthy)")
    print("    - node_removed")
    print("    - heartbeat (every 10s)")
    print("\n  /ws/network/backends:")
    print("    - backend_connected")
    print("    - backend_disconnected")
    print("    - heartbeat")
    print("\n  /ws/ollama_activity:")
    print("    - model_loaded")
    print("    - model_unloaded")
    print("    - model_processing")
    print("    - node_error")


if __name__ == "__main__":
    import sys

    examples = {
        "1": ("Standalone (no router)", example_1_standalone),
        "2": ("With SOLLOL router", example_2_with_router),
        "3": ("SynapticLlamas integration", example_3_synapticllamas),
        "4": ("WebSocket client", example_4_websocket_client),
    }

    print("\n🎯 SOLLOL Unified Dashboard - Programmatic Usage Examples\n")
    print("Choose an example:")
    for key, (desc, _) in examples.items():
        print(f"  {key}. {desc}")
    print()

    choice = input("Enter example number (1-4): ").strip()

    if choice in examples:
        _, func = examples[choice]
        print()
        func()
    else:
        print("Invalid choice. Running Example 1 (standalone)...")
        example_1_standalone()
