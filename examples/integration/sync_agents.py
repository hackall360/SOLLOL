"""
Example: Using SOLLOL with synchronous agent frameworks.

This example shows how to use SOLLOL's synchronous API wrapper to integrate
with agent frameworks that don't use async/await.

Demonstrates:
- Synchronous HybridRouter usage
- Synchronous OllamaPool usage
- Priority-based multi-agent orchestration
- No async/await needed
"""

from sollol.sync_wrapper import HybridRouter, OllamaPool
from sollol.priority_helpers import Priority, get_priority_for_role


def simple_agent_example():
    """Simple example with synchronous OllamaPool."""
    print("=== Simple Synchronous Agent Example ===\n")

    # Auto-configure pool (discovers nodes automatically)
    pool = OllamaPool.auto_configure()

    # Define agents with different priorities
    agents = [
        {"name": "Researcher", "role": "researcher", "model": "llama3.2"},
        {"name": "Editor", "role": "editor", "model": "llama3.2"},
        {"name": "Summarizer", "role": "summarizer", "model": "llama3.2"},
    ]

    # Process tasks with different priorities
    for agent in agents:
        priority = get_priority_for_role(agent["role"])
        print(f"\n{agent['name']} (priority={priority}):")

        # Synchronous call - no async/await needed!
        response = pool.chat(
            model=agent["model"],
            messages=[{"role": "user", "content": f"Hello from {agent['name']}!"}],
            priority=priority,
            timeout=60,  # Request timeout in seconds
        )

        print(f"  Response: {response['message']['content'][:100]}...")

    # Get pool statistics
    stats = pool.get_stats()
    print(f"\nPool stats: {stats}")


def multi_agent_orchestration():
    """Example with multiple agents using priority-based orchestration."""
    print("\n=== Multi-Agent Orchestration Example ===\n")

    # Configure pool
    pool = OllamaPool.auto_configure()

    # Define a multi-agent workflow
    workflow = [
        {
            "agent": "Researcher",
            "priority": Priority.HIGH,
            "task": "Research the history of artificial intelligence",
        },
        {
            "agent": "Critic",
            "priority": Priority.HIGH,
            "task": "Analyze the research for accuracy",
        },
        {
            "agent": "Editor",
            "priority": Priority.ABOVE_NORMAL,
            "task": "Edit and refine the content",
        },
        {
            "agent": "Summarizer",
            "priority": Priority.NORMAL,
            "task": "Create a brief summary",
        },
    ]

    results = {}

    for step in workflow:
        print(f"\n{step['agent']} (priority={step['priority']}):")
        print(f"  Task: {step['task']}")

        # Synchronous execution
        response = pool.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": step["task"]}],
            priority=step["priority"],
            timeout=120,
        )

        results[step["agent"]] = response["message"]["content"]
        print(f"  ✓ Completed")

    print("\n=== Workflow Complete ===")
    for agent, result in results.items():
        print(f"\n{agent}:")
        print(f"  {result[:150]}...")


def hybrid_router_example():
    """Example with HybridRouter for automatic model sharding."""
    print("\n=== Hybrid Router Example ===\n")

    # Configure pool
    pool = OllamaPool.auto_configure()

    # Create hybrid router with model sharding enabled
    # (assuming RPC backends are configured via environment)
    router = HybridRouter(
        ollama_pool=pool,
        enable_distributed=True,  # Enable model sharding for large models
    )

    # Small model - routes to Ollama pool (task distribution)
    print("Small model (llama3.2) - routes to Ollama pool:")
    response = router.route_request(
        model="llama3.2",
        messages=[{"role": "user", "content": "What is SOLLOL?"}],
        timeout=60,
    )
    print(f"  Backend: {response.get('_routing', {}).get('backend', 'unknown')}")
    print(f"  Response: {response['message']['content'][:100]}...")

    # Large model - routes to distributed inference (if available)
    print("\nLarge model (llama3.1:70b) - routes to model sharding:")
    try:
        response = router.route_request(
            model="llama3.1:70b",
            messages=[{"role": "user", "content": "Explain distributed inference"}],
            timeout=120,
        )
        print(f"  Backend: {response.get('_routing', {}).get('backend', 'unknown')}")
        print(f"  Response: {response['message']['content'][:100]}...")
    except Exception as e:
        print(f"  (Model sharding not available: {e})")

    # Get router stats
    stats = router.get_stats()
    print(f"\nRouter stats: {stats}")


def error_handling_example():
    """Example with proper error handling."""
    print("\n=== Error Handling Example ===\n")

    pool = OllamaPool.auto_configure()

    try:
        # Request with timeout
        response = pool.chat(
            model="llama3.2",
            messages=[{"role": "user", "content": "Hello!"}],
            priority=Priority.NORMAL,
            timeout=30,  # 30 second timeout
        )
        print(f"✓ Success: {response['message']['content'][:50]}...")

    except TimeoutError:
        print("✗ Request timed out")

    except Exception as e:
        print(f"✗ Error: {e}")


def priority_comparison():
    """Demonstrate priority behavior with concurrent requests."""
    print("\n=== Priority Comparison Example ===\n")

    pool = OllamaPool.auto_configure()

    # Submit multiple requests with different priorities
    import threading
    import time

    results = {}
    timestamps = {}

    def submit_request(name, priority):
        start_time = time.time()
        try:
            response = pool.chat(
                model="llama3.2",
                messages=[{"role": "user", "content": f"Task from {name}"}],
                priority=priority,
                timeout=60,
            )
            end_time = time.time()
            results[name] = "✓ Completed"
            timestamps[name] = end_time - start_time
        except Exception as e:
            results[name] = f"✗ Failed: {e}"
            timestamps[name] = None

    # Create threads for concurrent requests
    threads = []
    requests = [
        ("Low Priority Task", Priority.LOW),
        ("High Priority Task", Priority.HIGH),
        ("Normal Priority Task", Priority.NORMAL),
        ("Urgent Task", Priority.URGENT),
    ]

    # Submit all at once
    start = time.time()
    for name, priority in requests:
        t = threading.Thread(target=submit_request, args=(name, priority))
        threads.append(t)
        t.start()

    # Wait for all to complete
    for t in threads:
        t.join()

    total_time = time.time() - start

    # Show results
    print("\nResults (priority affects execution order):")
    for name, priority in requests:
        status = results.get(name, "pending")
        duration = timestamps.get(name)
        duration_str = f"{duration:.2f}s" if duration else "N/A"
        print(f"  {name} (priority={priority}): {status} in {duration_str}")

    print(f"\nTotal time: {total_time:.2f}s")


if __name__ == "__main__":
    # Run examples
    try:
        simple_agent_example()
    except Exception as e:
        print(f"Simple example failed: {e}")

    try:
        multi_agent_orchestration()
    except Exception as e:
        print(f"Multi-agent example failed: {e}")

    try:
        hybrid_router_example()
    except Exception as e:
        print(f"Hybrid router example failed: {e}")

    try:
        error_handling_example()
    except Exception as e:
        print(f"Error handling example failed: {e}")

    try:
        priority_comparison()
    except Exception as e:
        print(f"Priority comparison example failed: {e}")
