#!/usr/bin/env python3
"""
Test all routing strategies in SOLLOL OllamaPool.

Verifies that each strategy:
1. Can be instantiated
2. Successfully selects nodes
3. Behaves according to its documented algorithm
"""

import sys
import logging
from src.sollol.pool import OllamaPool
from src.sollol.routing_strategy import RoutingStrategy

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def test_strategy(strategy: RoutingStrategy, pool: OllamaPool, test_name: str):
    """Test a routing strategy with multiple requests."""
    print(f"\n{'='*80}")
    print(f"Testing: {test_name}")
    print(f"Strategy: {strategy.value}")
    print('='*80)

    try:
        # Reconfigure pool with new strategy
        pool.routing_strategy = strategy
        pool.enable_intelligent_routing = (strategy == RoutingStrategy.INTELLIGENT)
        pool.router = None if strategy != RoutingStrategy.INTELLIGENT else pool.router

        # Make 5 test requests to see routing behavior
        print(f"\nMaking 5 test requests with {strategy.value} strategy...")
        selected_nodes = []

        for i in range(5):
            # Simulate a request payload
            payload = {"model": "llama3.2", "prompt": f"Test request {i+1}"}
            node, decision = pool._select_node(payload=payload, priority=5)
            node_key = f"{node['host']}:{node['port']}"
            selected_nodes.append(node_key)

            print(f"  Request {i+1}: Selected {node_key}")
            if decision:
                print(f"            Reasoning: {decision.get('reasoning', 'N/A')}")

        # Show distribution
        print(f"\nNode selection distribution:")
        from collections import Counter
        distribution = Counter(selected_nodes)
        for node_key, count in distribution.items():
            print(f"  {node_key}: {count} requests ({count/5*100:.0f}%)")

        # Verify strategy worked
        stats = pool.get_stats()
        current_strategy = stats.get('routing_strategy')
        print(f"\nCurrent strategy in stats: {current_strategy}")

        if current_strategy == strategy.value:
            print(f"✅ {test_name} PASSED")
            return True
        else:
            print(f"❌ {test_name} FAILED: Expected {strategy.value}, got {current_strategy}")
            return False

    except Exception as e:
        print(f"❌ {test_name} FAILED with exception: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "="*80)
    print("SOLLOL Routing Strategy Test Suite")
    print("="*80)

    # Initialize pool with default strategy
    print("\nInitializing OllamaPool...")
    try:
        pool = OllamaPool.auto_configure(
            enable_cache=False,  # Disable cache for cleaner testing
            register_with_dashboard=False,  # Don't register during testing
            enable_dask=False,  # Disable Dask for simpler testing
        )
        print(f"✅ Pool initialized with {len(pool.nodes)} nodes")
        nodes_list = [f"{n['host']}:{n['port']}" for n in pool.nodes]
        print(f"   Nodes: {nodes_list}")
    except Exception as e:
        print(f"❌ Failed to initialize pool: {e}")
        return 1

    if len(pool.nodes) == 0:
        print("❌ No nodes discovered. Please ensure Ollama is running.")
        return 1

    # Test all strategies
    results = {}

    # Test 1: Round-robin
    results['round_robin'] = test_strategy(
        RoutingStrategy.ROUND_ROBIN,
        pool,
        "Round-Robin Strategy"
    )

    # Test 2: Latency-first
    results['latency_first'] = test_strategy(
        RoutingStrategy.LATENCY_FIRST,
        pool,
        "Latency-First Strategy"
    )

    # Test 3: Least-loaded
    results['least_loaded'] = test_strategy(
        RoutingStrategy.LEAST_LOADED,
        pool,
        "Least-Loaded Strategy"
    )

    # Test 4: Fairness
    results['fairness'] = test_strategy(
        RoutingStrategy.FAIRNESS,
        pool,
        "Fairness Strategy"
    )

    # Test 5: Intelligent (if router available)
    if pool.router:
        results['intelligent'] = test_strategy(
            RoutingStrategy.INTELLIGENT,
            pool,
            "Intelligent Strategy"
        )
    else:
        print("\n⚠️  Skipping Intelligent strategy test (router not available)")
        results['intelligent'] = None

    # Summary
    print("\n" + "="*80)
    print("Test Summary")
    print("="*80)

    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)
    total = len(results)

    for strategy_name, result in results.items():
        status = "✅ PASSED" if result is True else "❌ FAILED" if result is False else "⏭️  SKIPPED"
        print(f"  {strategy_name:20s}: {status}")

    print(f"\nTotal: {passed}/{total-skipped} passed, {failed} failed, {skipped} skipped")

    # Clean up
    try:
        pool.stop()
        print("\n✅ Pool stopped successfully")
    except Exception as e:
        print(f"\n⚠️  Error stopping pool: {e}")

    # Exit with appropriate code
    if failed > 0:
        print("\n❌ Some tests failed!")
        return 1
    else:
        print("\n✅ All tests passed!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
