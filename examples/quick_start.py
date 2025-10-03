"""
SOLLOL Quick Start Example

Demonstrates the simplest way to use SOLLOL for intelligent routing.
"""

from sollol import connect

def main():
    """Quick start demo."""

    print("🚀 SOLLOL Quick Start Demo\n")

    # Step 1: Connect to SOLLOL (one line!)
    print("1️⃣  Connecting to SOLLOL...")
    sollol = connect()  # That's it!

    # Step 2: Check health
    print("2️⃣  Checking health...")
    health = sollol.health()
    print(f"   ✓ Status: {health['status']}")
    print(f"   ✓ Available hosts: {len(health['hosts'])}\n")

    # Step 3: Send intelligent chat request
    print("3️⃣  Sending chat request with intelligent routing...")
    response = sollol.chat(
        message="Explain the concept of distributed computing in simple terms",
        priority=7  # High priority for user-facing request
    )

    # Step 4: View response
    print("\n📝 Response:")
    print(f"   {response['message']['content'][:200]}...\n")

    # Step 5: Check routing intelligence
    routing = response.get('_sollol_routing', {})
    print("🎯 Routing Intelligence:")
    print(f"   ✓ Routed to: {routing.get('host', 'N/A')}")
    print(f"   ✓ Task type: {routing.get('task_type', 'N/A')}")
    print(f"   ✓ Complexity: {routing.get('complexity', 'N/A')}")
    print(f"   ✓ Duration: {routing.get('actual_duration_ms', 0):.0f}ms")
    print(f"   ✓ Decision score: {routing.get('decision_score', 0):.1f}\n")

    # Step 6: Demonstrate different priority levels
    print("4️⃣  Testing priority-based routing...\n")

    priorities = [
        (10, "CRITICAL: System alert"),
        (8, "HIGH: User query"),
        (5, "NORMAL: Background task"),
        (3, "LOW: Analytics"),
    ]

    for priority, description in priorities:
        print(f"   Priority {priority} ({description})...")
        resp = sollol.chat(
            message="Quick test",
            priority=priority
        )
        routing = resp.get('_sollol_routing', {})
        print(f"      → Routed to {routing.get('host', 'N/A')} "
              f"in {routing.get('actual_duration_ms', 0):.0f}ms\n")

    # Step 7: Get statistics
    print("5️⃣  Fetching routing statistics...")
    stats = sollol.stats()

    print("\n📊 System Statistics:")
    print(f"   Hosts: {len(stats.get('hosts', []))}")

    routing_intel = stats.get('routing_intelligence', {})
    print(f"   Task patterns detected: {len(routing_intel.get('task_patterns_detected', []))}")
    print(f"   Performance history: {routing_intel.get('performance_history_tasks', 0)} task-model combinations\n")

    # Step 8: Demonstrate embeddings
    print("6️⃣  Testing embedding generation...")
    vector = sollol.embed("This is a test document for embedding")
    print(f"   ✓ Generated embedding: {len(vector)} dimensions\n")

    print("✅ Demo complete!\n")
    print("💡 Next steps:")
    print("   - Check dashboard.html for real-time monitoring")
    print("   - See BENCHMARKS.md for performance data")
    print("   - Read ARCHITECTURE.md for system design")

    # Cleanup
    sollol.close()


if __name__ == "__main__":
    main()
