#!/usr/bin/env python3
"""
SOLLOL llama.cpp Distributed Inference Example

This example demonstrates how to use SOLLOL's llama.cpp integration for
distributed inference of large language models across multiple machines.

Use Case:
- Large models (e.g., Llama 3.1 70B) that don't fit on a single GPU
- Distributed across multiple machines via RPC (Remote Procedure Call)
- Automatic layer partitioning and load balancing

Prerequisites:
- SOLLOL installed: pip install sollol
- llama.cpp built with CUDA support on each backend machine
- Network connectivity between coordinator and RPC backends
- Model available in Ollama (e.g., llama3.1:70b)

Architecture:
┌──────────────────┐
│   Coordinator    │ ← Main llama-server instance
│  (llama-server)  │
└────────┬─────────┘
         │
    ┌────┴────┬────────────┐
    │         │            │
    ▼         ▼            ▼
┌────────┐┌────────┐┌────────┐
│ RPC #1 ││ RPC #2 ││ RPC #3 │ ← Backend workers
│Layers  ││Layers  ││Layers  │
│ 0-26   ││ 27-53  ││ 54-79  │
└────────┘└────────┘└────────┘
"""

import asyncio
import time
from typing import Optional, List, Dict, Any

# Import SOLLOL components
from sollol.sync_wrapper import HybridRouter, OllamaPool
from sollol.llama_cpp_coordinator import LlamaCppCoordinator
from sollol.rpc_registry import RPCBackendRegistry
from sollol.priority_helpers import Priority


# =============================================================================
# Example 1: Auto-Setup (Recommended for Most Users)
# =============================================================================

def example_auto_setup():
    """
    Simplest approach - SOLLOL handles all setup automatically.

    This will:
    1. Discover available RPC backends on the network
    2. Configure llama-server coordinator
    3. Set up layer distribution automatically
    4. Route requests intelligently
    """
    print("=" * 80)
    print("Example 1: Auto-Setup Distributed Inference")
    print("=" * 80)

    # Create hybrid router with auto-setup
    router = HybridRouter(
        ollama_pool=OllamaPool.auto_configure(),
        enable_distributed=True,
        auto_setup_rpc=True,          # Automatically discover RPC backends
        num_rpc_backends=3,            # Expect 3 RPC backend machines
        coordinator_port=18080,        # Port for llama-server coordinator
        min_sharding_layers=40         # Only shard models with 40+ layers
    )

    print(f"\n✓ Router initialized with distributed inference")
    print(f"  - Auto RPC discovery: enabled")
    print(f"  - Expected backends: 3")
    print(f"  - Coordinator port: 18080")

    # Example: Single inference request
    print("\n--- Single Request Example ---")

    try:
        response = router.route_request(
            model="llama3.1:70b",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": "Explain quantum computing in simple terms."}
            ],
            priority=Priority.HIGH,
            timeout=120  # 2 minute timeout for large model
        )

        print(f"\n✓ Response received:")
        print(f"  Model: {response.get('model', 'N/A')}")
        print(f"  Backend: {response.get('_sollol_routing', {}).get('backend', 'N/A')}")
        print(f"  Content: {response.get('message', {}).get('content', 'N/A')[:200]}...")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("  Make sure:")
        print("  - Ollama has llama3.1:70b model available")
        print("  - RPC backends are running on network")
        print("  - llama.cpp is built with CUDA support")


# =============================================================================
# Example 2: Manual Setup (Advanced Users)
# =============================================================================

async def example_manual_setup():
    """
    Manual setup with explicit control over RPC backends and coordinator.

    Use this when you need:
    - Specific backend configurations
    - Custom layer distribution
    - Fine-grained control over coordinator settings
    """
    print("\n" + "=" * 80)
    print("Example 2: Manual Setup with Explicit Configuration")
    print("=" * 80)

    # Step 1: Create RPC backend registry
    registry = RPCBackendRegistry()

    # Manually add RPC backends (replace with your actual IPs/hostnames)
    backends = [
        {"host": "10.9.66.45", "port": 50052},
        {"host": "10.9.66.46", "port": 50052},
        {"host": "10.9.66.47", "port": 50052},
    ]

    print("\n--- Registering RPC Backends ---")
    for idx, backend in enumerate(backends):
        backend_url = f"grpc://{backend['host']}:{backend['port']}"
        registry.add_backend(
            backend_id=f"rpc_backend_{idx}",
            url=backend_url,
            metadata={
                "gpu_count": 1,
                "gpu_memory_gb": 16,
                "layer_capacity": 27  # Approximate layers per backend
            }
        )
        print(f"  ✓ Backend {idx}: {backend_url}")

    # Step 2: Create coordinator with custom settings
    print("\n--- Creating Coordinator ---")
    coordinator = LlamaCppCoordinator(
        coordinator_port=18080,
        ollama_base_url="http://localhost:11434",
        rpc_backends=registry.get_all_backends(),
        context_size=4096,
        gpu_layers=-1,  # Use all GPU layers
        threads=8
    )

    # Step 3: Start coordinator
    print("  Starting llama-server coordinator...")
    try:
        await coordinator.start(model_name="llama3.1:70b")
        print("  ✓ Coordinator started on port 18080")
    except Exception as e:
        print(f"  ✗ Failed to start coordinator: {e}")
        return

    # Step 4: Send inference request
    print("\n--- Sending Inference Request ---")
    try:
        response = await coordinator.generate(
            prompt="Explain the theory of relativity in simple terms.",
            max_tokens=500,
            temperature=0.7
        )

        print(f"\n✓ Response received:")
        print(f"  Tokens: {response.get('tokens_evaluated', 'N/A')}")
        print(f"  Content: {response.get('content', 'N/A')[:200]}...")

    except Exception as e:
        print(f"\n✗ Error during generation: {e}")

    finally:
        # Step 5: Cleanup
        print("\n--- Cleanup ---")
        await coordinator.stop()
        print("  ✓ Coordinator stopped")


# =============================================================================
# Example 3: Multi-Turn Conversation with Performance Monitoring
# =============================================================================

def example_conversation_with_monitoring():
    """
    Demonstrates a multi-turn conversation with performance tracking.

    Shows:
    - Context preservation across turns
    - Performance metrics (latency, tokens/sec)
    - Error recovery
    """
    print("\n" + "=" * 80)
    print("Example 3: Multi-Turn Conversation with Monitoring")
    print("=" * 80)

    router = HybridRouter(
        ollama_pool=OllamaPool.auto_configure(),
        enable_distributed=True,
        auto_setup_rpc=True,
        num_rpc_backends=3
    )

    # Conversation history
    conversation = [
        {"role": "system", "content": "You are a helpful AI assistant specializing in science."}
    ]

    # Questions to ask
    questions = [
        "What is quantum entanglement?",
        "How is it different from classical correlation?",
        "What are its practical applications?",
    ]

    print("\n--- Starting Conversation ---")

    for idx, question in enumerate(questions, 1):
        print(f"\n[Turn {idx}]")
        print(f"User: {question}")

        # Add user message to conversation
        conversation.append({"role": "user", "content": question})

        # Track performance
        start_time = time.time()

        try:
            response = router.route_request(
                model="llama3.1:70b",
                messages=conversation,
                priority=Priority.HIGH,
                timeout=120
            )

            # Calculate metrics
            elapsed = time.time() - start_time
            content = response.get('message', {}).get('content', '')
            tokens = len(content.split())  # Rough estimate
            tokens_per_sec = tokens / elapsed if elapsed > 0 else 0

            # Add assistant response to conversation
            conversation.append({"role": "assistant", "content": content})

            # Display response and metrics
            print(f"Assistant: {content[:200]}...")
            print(f"\n  📊 Metrics:")
            print(f"    - Latency: {elapsed:.2f}s")
            print(f"    - Tokens: ~{tokens}")
            print(f"    - Speed: ~{tokens_per_sec:.1f} tokens/sec")
            print(f"    - Backend: {response.get('_sollol_routing', {}).get('backend', 'N/A')}")

        except Exception as e:
            print(f"\n✗ Error: {e}")
            print("  Attempting recovery...")
            # In production, implement retry logic here
            break

    print(f"\n✓ Conversation completed: {len(conversation)} messages")


# =============================================================================
# Example 4: Batch Processing with Multiple Models
# =============================================================================

def example_batch_processing():
    """
    Process multiple requests in parallel across different model sizes.

    Demonstrates:
    - Intelligent routing based on model size
    - Parallel request handling
    - Small models use Ollama, large models use llama.cpp sharding
    """
    print("\n" + "=" * 80)
    print("Example 4: Batch Processing with Intelligent Routing")
    print("=" * 80)

    router = HybridRouter(
        ollama_pool=OllamaPool.auto_configure(),
        enable_distributed=True,
        auto_setup_rpc=True,
        num_rpc_backends=3,
        min_sharding_layers=40  # Only shard 70B models
    )

    # Mix of small and large model requests
    requests = [
        {
            "model": "llama3.2:3b",
            "messages": [{"role": "user", "content": "What is 2+2?"}],
            "priority": Priority.NORMAL,
            "expected_backend": "Ollama"
        },
        {
            "model": "llama3.1:70b",
            "messages": [{"role": "user", "content": "Explain general relativity."}],
            "priority": Priority.HIGH,
            "expected_backend": "llama.cpp (distributed)"
        },
        {
            "model": "llama3.2:3b",
            "messages": [{"role": "user", "content": "Name three colors."}],
            "priority": Priority.LOW,
            "expected_backend": "Ollama"
        },
        {
            "model": "llama3.1:70b",
            "messages": [{"role": "user", "content": "What is quantum computing?"}],
            "priority": Priority.HIGH,
            "expected_backend": "llama.cpp (distributed)"
        },
    ]

    print(f"\n--- Processing {len(requests)} Requests ---")

    for idx, req in enumerate(requests, 1):
        print(f"\n[Request {idx}]")
        print(f"  Model: {req['model']}")
        print(f"  Priority: {req['priority']}")
        print(f"  Expected Backend: {req['expected_backend']}")

        start = time.time()

        try:
            response = router.route_request(
                model=req['model'],
                messages=req['messages'],
                priority=req['priority'],
                timeout=120 if "70b" in req['model'] else 30
            )

            elapsed = time.time() - start
            backend = response.get('_sollol_routing', {}).get('backend', 'unknown')

            print(f"  ✓ Completed in {elapsed:.2f}s")
            print(f"  ✓ Actual Backend: {backend}")

        except Exception as e:
            print(f"  ✗ Failed: {e}")


# =============================================================================
# Example 5: Error Handling and Recovery
# =============================================================================

async def example_error_handling():
    """
    Demonstrates robust error handling and automatic recovery.

    Covers:
    - Backend failures
    - Timeout handling
    - Automatic failover
    - Graceful degradation
    """
    print("\n" + "=" * 80)
    print("Example 5: Error Handling and Recovery")
    print("=" * 80)

    coordinator = LlamaCppCoordinator(
        coordinator_port=18080,
        ollama_base_url="http://localhost:11434",
        auto_discover_backends=True,
        num_backends=3
    )

    print("\n--- Testing Error Scenarios ---")

    # Scenario 1: Coordinator startup failure
    print("\n[Scenario 1: Coordinator Startup]")
    try:
        await coordinator.start(model_name="llama3.1:70b")
        print("  ✓ Coordinator started successfully")
    except FileNotFoundError as e:
        print(f"  ✗ llama-server not found: {e}")
        print("  → Install llama.cpp: see docs/llama_cpp_guide.md")
        return
    except Exception as e:
        print(f"  ✗ Startup failed: {e}")
        return

    # Scenario 2: Request timeout
    print("\n[Scenario 2: Request Timeout]")
    try:
        response = await asyncio.wait_for(
            coordinator.generate(
                prompt="Very long computation...",
                max_tokens=10000
            ),
            timeout=5.0  # Intentionally short timeout
        )
        print("  ✓ Request completed within timeout")
    except asyncio.TimeoutError:
        print("  ✗ Request timed out (expected)")
        print("  → Increase timeout or reduce max_tokens")

    # Scenario 3: Invalid model
    print("\n[Scenario 3: Invalid Model]")
    try:
        await coordinator.start(model_name="nonexistent:model")
        print("  ✓ Model loaded (unexpected)")
    except Exception as e:
        print(f"  ✗ Model not found: {e}")
        print("  → Pull model with: ollama pull llama3.1:70b")

    # Cleanup
    print("\n--- Cleanup ---")
    await coordinator.stop()
    print("  ✓ Coordinator stopped")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """
    Run all examples in sequence.

    Usage:
        python llama_cpp_distributed.py

    Or run individual examples:
        python llama_cpp_distributed.py --example 1
    """
    import sys

    print("\n")
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║  SOLLOL llama.cpp Distributed Inference Examples              ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print()

    # Check if specific example requested
    example_num = None
    if len(sys.argv) > 1 and sys.argv[1] == "--example":
        if len(sys.argv) > 2:
            example_num = int(sys.argv[2])

    # Run examples
    if example_num is None or example_num == 1:
        example_auto_setup()

    if example_num is None or example_num == 2:
        asyncio.run(example_manual_setup())

    if example_num is None or example_num == 3:
        example_conversation_with_monitoring()

    if example_num is None or example_num == 4:
        example_batch_processing()

    if example_num is None or example_num == 5:
        asyncio.run(example_error_handling())

    print("\n" + "=" * 80)
    print("Examples Completed")
    print("=" * 80)
    print("\nNext Steps:")
    print("  1. Review docs/llama_cpp_guide.md for detailed documentation")
    print("  2. Configure your RPC backends (see guide Section 4)")
    print("  3. Adapt examples to your use case")
    print("  4. Monitor performance with SOLLOL dashboard")
    print("\n")


if __name__ == "__main__":
    main()
