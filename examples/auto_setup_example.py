#!/usr/bin/env python3
"""
SOLLOL Auto-Setup Example
==========================

Demonstrates zero-config setup of distributed inference with automatic
RPC backend configuration.

This example shows how SOLLOL can automatically:
1. Discover or setup RPC backends
2. Configure hybrid routing
3. Handle both small and large models seamlessly
"""

import asyncio
import logging
from sollol import HybridRouter, OllamaPool, auto_setup_rpc_backends

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_1_hybrid_router_auto_setup():
    """Example 1: HybridRouter with auto-setup"""
    print("\n" + "=" * 70)
    print("Example 1: HybridRouter with Auto-Setup")
    print("=" * 70)

    # Create hybrid router with auto-setup
    # This will automatically:
    # - Discover Ollama nodes
    # - Try to discover RPC backends
    # - If no RPC backends found, clone/build/start llama.cpp
    router = HybridRouter(
        ollama_pool=OllamaPool.auto_configure(),
        enable_distributed=True,
        auto_discover_rpc=True,
        auto_setup_rpc=True,      # Enable auto-setup!
        num_rpc_backends=2         # Start 2 RPC servers if needed
    )

    print(f"\n✅ Router configured!")
    print(f"   Distributed enabled: {router.enable_distributed}")
    if router.rpc_backends:
        print(f"   RPC backends: {len(router.rpc_backends)}")
        for backend in router.rpc_backends:
            print(f"      → {backend['host']}:{backend['port']}")

    # Test with a small model (goes to Ollama)
    print("\n📝 Testing with small model (llama3.2:3b)...")
    uses_distributed = router.should_use_distributed("llama3.2:3b")
    print(f"   Uses distributed: {uses_distributed}")
    print(f"   → Will route to: {'llama.cpp' if uses_distributed else 'Ollama'}")

    # Test with a large model (goes to llama.cpp)
    print("\n📝 Testing with large model (llama3.1:405b)...")
    uses_distributed = router.should_use_distributed("llama3.1:405b")
    print(f"   Uses distributed: {uses_distributed}")
    print(f"   → Will route to: {'llama.cpp' if uses_distributed else 'Ollama'}")


def example_2_standalone_auto_setup():
    """Example 2: Standalone auto-setup"""
    print("\n" + "=" * 70)
    print("Example 2: Standalone Auto-Setup")
    print("=" * 70)

    # Use standalone auto-setup function
    print("\n🚀 Setting up RPC backends...")
    backends = auto_setup_rpc_backends(
        num_backends=2,      # Start 2 RPC servers
        auto_build=True,     # Build llama.cpp if needed
        discover_network=True  # Also discover network backends
    )

    if backends:
        print(f"\n✅ RPC backends ready: {len(backends)}")
        for backend in backends:
            print(f"   → {backend['host']}:{backend['port']}")
    else:
        print("\n⚠️  No RPC backends available")


def example_3_conditional_setup():
    """Example 3: Conditional setup based on model requirements"""
    print("\n" + "=" * 70)
    print("Example 3: Conditional Setup")
    print("=" * 70)

    # Only setup distributed if you need it
    model_to_run = "llama3.1:405b"  # Large model requiring distributed

    print(f"\n📋 Planning to run: {model_to_run}")

    # Check if we need distributed inference
    from sollol.hybrid_router import MODEL_PROFILES

    profile = MODEL_PROFILES.get(model_to_run)
    if profile and profile.requires_distributed:
        print(f"   Model requires distributed inference")
        print(f"   Parameters: {profile.parameter_count}B")
        print(f"   Estimated memory: {profile.estimated_memory_gb}GB")

        # Setup RPC backends only when needed
        print("\n🚀 Setting up distributed inference...")
        backends = auto_setup_rpc_backends(num_backends=2)

        if backends:
            print(f"✅ Ready for distributed inference with {len(backends)} backends")
        else:
            print("⚠️  Could not setup distributed inference")
    else:
        print(f"   Model can run on single node (Ollama)")


async def main():
    """Run all examples"""
    print("\n" + "=" * 70)
    print("SOLLOL Auto-Setup Examples")
    print("=" * 70)
    print("\nThese examples demonstrate SOLLOL's zero-config distributed inference.")
    print("SOLLOL will automatically setup llama.cpp RPC backends if needed!")

    try:
        # Example 1: Auto-setup with HybridRouter
        await example_1_hybrid_router_auto_setup()

        # Example 2: Standalone auto-setup
        example_2_standalone_auto_setup()

        # Example 3: Conditional setup
        example_3_conditional_setup()

        print("\n" + "=" * 70)
        print("✅ All examples completed!")
        print("=" * 70)
        print("\nNote: RPC servers are running in the background.")
        print("They will continue running after this script exits.")
        print("To stop them, run: pkill rpc-server")

    except Exception as e:
        logger.error(f"Error running examples: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
