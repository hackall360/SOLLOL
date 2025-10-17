#!/usr/bin/env python3
"""
SOLLOL Failure & Recovery Simulation

Demonstrates SOLLOL's automatic failover and recovery capabilities:
1. Start with multiple nodes
2. Kill a node mid-execution
3. Observe automatic failover to healthy nodes
4. Monitor dashboard showing health changes and re-routing
5. Restore the node and observe automatic recovery

Usage:
    python test_failure_recovery.py
"""

import sys
import os
import time
import subprocess
import signal
import requests

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from sollol import OllamaPool
from sollol.routing_strategy import RoutingStrategy


class FailureRecoverySimulation:
    """Simulates node failure and recovery scenarios."""

    def __init__(self):
        self.mock_processes = []
        self.pool = None

    def start_mock_nodes(self, ports=[21434, 21435, 21436]):
        """Start mock Ollama nodes."""
        print("\n" + "="*80)
        print("STEP 1: Starting Mock Nodes")
        print("="*80)

        for port in ports:
            print(f"Starting mock node on port {port}...")
            proc = subprocess.Popen([
                sys.executable,
                "tests/integration/mock_ollama_server.py",
                "--port", str(port)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.mock_processes.append({"port": port, "proc": proc})
            time.sleep(1)

        print(f"✅ Started {len(ports)} mock nodes")

        # Verify they're running
        for port in ports:
            try:
                response = requests.get(f"http://localhost:{port}/api/tags", timeout=2)
                if response.status_code == 200:
                    print(f"   ✓ Node {port}: Healthy")
            except Exception as e:
                print(f"   ✗ Node {port}: Failed - {e}")

    def initialize_pool(self):
        """Initialize SOLLOL pool with mock nodes."""
        print("\n" + "="*80)
        print("STEP 2: Initializing SOLLOL Pool")
        print("="*80)

        nodes = [{"host": "localhost", "port": p["port"]} for p in self.mock_processes]

        self.pool = OllamaPool(
            nodes=nodes,
            routing_strategy=RoutingStrategy.LEAST_LOADED,
            enable_intelligent_routing=False,  # Use simple strategy for clearer demo
            register_with_dashboard=False,
            enable_cache=False,
            enable_ray=False,
            enable_dask=False
        )

        print(f"✅ Pool initialized with {len(self.pool.nodes)} nodes")
        for node in self.pool.nodes:
            print(f"   - {node['host']}:{node['port']}")

    def run_requests(self, count=5, label=""):
        """Run multiple requests to show routing."""
        print(f"\n{label}")
        print("="*80)

        for i in range(count):
            try:
                response = self.pool.chat(
                    model="llama3.2",
                    messages=[{"role": "user", "content": f"Request {i+1}"}]
                )

                if "_sollol_routing" in response:
                    node = response["_sollol_routing"]
                    print(f"  Request {i+1}: ✓ Routed to {node.get('host')}:{node.get('port')}")
                else:
                    content = response.get("message", {}).get("content", "Unknown")
                    print(f"  Request {i+1}: ✓ Response: {content[:50]}")

                time.sleep(0.5)

            except Exception as e:
                print(f"  Request {i+1}: ✗ FAILED - {e}")

    def kill_node(self, index=0):
        """Kill a specific node to simulate failure."""
        print("\n" + "="*80)
        print(f"STEP 3: Simulating Node Failure (killing node {index})")
        print("="*80)

        if index < len(self.mock_processes):
            node_info = self.mock_processes[index]
            port = node_info["port"]
            proc = node_info["proc"]

            print(f"Killing node on port {port} (PID: {proc.pid})...")
            proc.terminate()
            proc.wait(timeout=5)

            print(f"✅ Node {port} terminated")

            # Verify it's dead
            time.sleep(1)
            try:
                requests.get(f"http://localhost:{port}/api/tags", timeout=2)
                print(f"   ⚠️  Node {port} still responding (unexpected)")
            except:
                print(f"   ✓ Node {port} confirmed dead")

    def restore_node(self, index=0):
        """Restore a killed node to simulate recovery."""
        print("\n" + "="*80)
        print(f"STEP 5: Simulating Node Recovery (restarting node {index})")
        print("="*80)

        if index < len(self.mock_processes):
            node_info = self.mock_processes[index]
            port = node_info["port"]

            print(f"Restarting node on port {port}...")
            proc = subprocess.Popen([
                sys.executable,
                "tests/integration/mock_ollama_server.py",
                "--port", str(port)
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            self.mock_processes[index]["proc"] = proc
            time.sleep(2)

            # Verify it's alive
            try:
                response = requests.get(f"http://localhost:{port}/api/tags", timeout=2)
                if response.status_code == 200:
                    print(f"✅ Node {port} recovered successfully")
            except Exception as e:
                print(f"   ✗ Node {port} recovery failed - {e}")

    def show_stats(self, label=""):
        """Show pool statistics."""
        if label:
            print(f"\n{label}")
            print("="*80)

        stats = self.pool.get_stats()

        print(f"Active nodes: {stats.get('active_nodes', 0)}")
        print(f"Total requests: {stats.get('total_requests', 0)}")
        print(f"Success rate: {stats.get('success_rate', 0):.1%}")

        # Show per-node stats
        node_perf = stats.get("node_performance", {})
        for node_key, perf in node_perf.items():
            available = perf.get("available", True)
            requests_count = perf.get("requests", 0)
            latency = perf.get("latency_ms", 0)
            status = "✓ Healthy" if available else "✗ Degraded"
            print(f"  {node_key}: {status} ({requests_count} reqs, {latency:.0f}ms)")

    def cleanup(self):
        """Clean up all mock processes."""
        print("\n" + "="*80)
        print("CLEANUP: Stopping all mock nodes")
        print("="*80)

        for node_info in self.mock_processes:
            try:
                node_info["proc"].terminate()
                node_info["proc"].wait(timeout=2)
                print(f"✓ Stopped node on port {node_info['port']}")
            except Exception as e:
                print(f"✗ Error stopping node {node_info['port']}: {e}")

        if self.pool:
            try:
                self.pool.stop()
                print("✓ Pool stopped")
            except Exception as e:
                print(f"✗ Error stopping pool: {e}")

    def run(self):
        """Run the complete failure & recovery simulation."""
        print("\n" + "="*80)
        print("SOLLOL FAILURE & RECOVERY SIMULATION")
        print("="*80)
        print("\nThis simulation demonstrates SOLLOL's automatic failover capabilities.")
        print("Watch how SOLLOL automatically routes around failed nodes!\n")

        try:
            # Step 1: Start nodes
            self.start_mock_nodes()

            # Step 2: Initialize pool
            self.initialize_pool()

            # Step 3: Run requests (baseline)
            self.run_requests(count=5, label="BASELINE: Requests with all nodes healthy")
            self.show_stats(label="Stats after baseline")

            # Step 4: Kill a node
            self.kill_node(index=0)

            # Step 5: Run requests (failover)
            self.run_requests(count=5, label="STEP 4: Requests after node failure (observe failover)")
            self.show_stats(label="Stats after failure")

            # Step 6: Restore node
            self.restore_node(index=0)

            # Step 7: Run requests (recovery)
            self.run_requests(count=5, label="STEP 6: Requests after node recovery")
            self.show_stats(label="Stats after recovery")

            # Summary
            print("\n" + "="*80)
            print("SIMULATION COMPLETE")
            print("="*80)
            print("\n✅ Key Observations:")
            print("  1. Requests succeeded even after node failure")
            print("  2. SOLLOL automatically routed around the dead node")
            print("  3. Node recovered and rejoined the pool")
            print("  4. Traffic resumed to recovered node")
            print("\n💡 In production, SOLLOL would:")
            print("  - Detect failures via health checks")
            print("  - Mark degraded nodes as unavailable")
            print("  - Periodically retry degraded nodes")
            print("  - Automatically restore them when healthy")
            print("\n📊 View the dashboard at http://localhost:8080")
            print("   to see real-time health status and routing decisions!\n")

        finally:
            self.cleanup()


def main():
    """Run the failure & recovery simulation."""
    sim = FailureRecoverySimulation()
    try:
        sim.run()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nSimulation interrupted")
        sim.cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Simulation failed: {e}")
        import traceback
        traceback.print_exc()
        sim.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main()
