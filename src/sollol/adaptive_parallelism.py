"""
Adaptive Parallelism Strategy for SOLLOL

Automatically chooses between sequential and parallel processing based on
cluster performance characteristics, preventing wasteful parallelization
when one GPU is dominant.

Key Decision Factors:
1. GPU Performance Gap - If one node is 10x faster, sequential is better
2. Node Count - More similar nodes = better parallelism
3. Network Latency - High latency favors fewer nodes
4. Batch Size - Small batches favor sequential (less overhead)
"""

import logging
import time
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class AdaptiveParallelismStrategy:
    """
    Intelligently decides whether to use parallel or sequential processing
    based on real-time performance metrics.

    Integrates with SOLLOL's NodeRegistry and routing intelligence to avoid
    wasteful parallelization when cluster characteristics don't favor it.
    """

    def __init__(self, node_registry=None):
        """
        Initialize adaptive parallelism strategy.

        Args:
            node_registry: NodeRegistry instance (optional, can be set later)
        """
        self.registry = node_registry
        self.performance_history = []  # Track decisions and results

    def set_registry(self, registry):
        """Set the NodeRegistry after initialization."""
        self.registry = registry

    def should_parallelize(self, batch_size: int, model_name: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Decide whether to parallelize based on cluster state.

        Args:
            batch_size: Number of items to process
            model_name: Model being used (for GPU-specific logic)

        Returns:
            (should_parallelize: bool, reasoning: Dict)
        """
        if not self.registry:
            logger.warning("No NodeRegistry set, defaulting to sequential")
            return False, {"reason": "no_registry", "detail": "No node registry configured"}

        nodes = list(self.registry.nodes.values())

        # Get available nodes (exclude unhealthy)
        available_nodes = [n for n in nodes if n.is_healthy]

        if len(available_nodes) <= 1:
            return False, {
                "reason": "single_node",
                "detail": "Only one healthy node available, sequential is optimal",
                "available_nodes": len(available_nodes),
            }

        # Calculate performance metrics
        node_speeds = []

        for node in available_nodes:
            # Get node's health and performance metrics
            has_gpu = node.capabilities.has_gpu
            avg_latency = node.metrics.get_avg_latency()

            # Estimate speed score (higher = faster)
            if has_gpu:
                # GPU nodes are generally much faster
                speed_score = 100 / max(avg_latency, 0.01)
            else:
                # CPU nodes are slower
                speed_score = 10 / max(avg_latency, 0.01)

            node_speeds.append({"node": node.url, "speed_score": speed_score, "has_gpu": has_gpu})

        # Sort by speed
        node_speeds.sort(key=lambda x: x["speed_score"], reverse=True)

        fastest_node = node_speeds[0]
        slowest_node = node_speeds[-1]

        # Calculate speed ratio
        speed_ratio = fastest_node["speed_score"] / max(slowest_node["speed_score"], 1)

        # Decision logic
        reasoning = {
            "available_nodes": len(available_nodes),
            "batch_size": batch_size,
            "fastest_node": fastest_node["node"],
            "fastest_speed": fastest_node["speed_score"],
            "speed_ratio": speed_ratio,
        }

        # CASE 1: One GPU node is 5x+ faster than others
        if speed_ratio >= 5.0:
            # Sequential on fastest node is better
            return False, {
                **reasoning,
                "reason": "dominant_node",
                "detail": f"Fastest node is {speed_ratio:.1f}x faster - sequential wins",
                "recommended_node": fastest_node["node"],
            }

        # CASE 2: Small batch (<20 items)
        if batch_size < 20:
            # Overhead of parallelism not worth it
            return False, {
                **reasoning,
                "reason": "small_batch",
                "detail": f"Batch size {batch_size} too small for parallel overhead",
                "recommended_node": fastest_node["node"],
            }

        # CASE 3: Multiple similar-speed nodes
        if speed_ratio < 3.0:
            # Nodes are similar speed, parallelize!
            return True, {
                **reasoning,
                "reason": "balanced_cluster",
                "detail": f"Speed ratio {speed_ratio:.1f}x - parallel is efficient",
                "parallel_workers": len(available_nodes) * 2,
            }

        # CASE 4: Medium speed difference (3-5x)
        # Use fastest 2-3 nodes in parallel
        if speed_ratio < 5.0 and len(available_nodes) >= 3:
            return True, {
                **reasoning,
                "reason": "hybrid_parallel",
                "detail": f"Using top {min(3, len(available_nodes))} nodes in parallel",
                "parallel_workers": min(3, len(available_nodes)) * 2,
            }

        # Default: Sequential on fastest
        return False, {
            **reasoning,
            "reason": "default_sequential",
            "detail": "Defaulting to sequential on fastest node",
            "recommended_node": fastest_node["node"],
        }

    def get_optimal_workers(self, batch_size: int) -> int:
        """
        Calculate optimal number of parallel workers.

        Args:
            batch_size: Number of items to process

        Returns:
            Number of workers (minimum 1)
        """
        if not self.registry:
            return 1

        available_nodes = [n for n in self.registry.nodes.values() if n.is_healthy]

        # Base workers on number of nodes
        base_workers = len(available_nodes) * 2

        # Adjust for batch size
        # Don't create more workers than items
        workers = min(base_workers, batch_size)

        # Minimum 1 worker
        return max(1, workers)

    def get_recommended_node(self, model_name: Optional[str] = None) -> Optional[str]:
        """
        Get the recommended node for sequential execution.

        Args:
            model_name: Model name (for GPU-specific routing)

        Returns:
            Node URL or None
        """
        if not self.registry:
            return None

        available_nodes = [n for n in self.registry.nodes.values() if n.is_healthy]

        if not available_nodes:
            return None

        # Prefer GPU nodes for most models
        gpu_nodes = [n for n in available_nodes if n.capabilities.has_gpu]

        if gpu_nodes:
            # Return fastest GPU node (lowest avg latency)
            fastest_gpu = min(gpu_nodes, key=lambda n: n.metrics.get_avg_latency())
            return fastest_gpu.url

        # Fallback to fastest CPU node
        fastest_cpu = min(available_nodes, key=lambda n: n.metrics.get_avg_latency())
        return fastest_cpu.url

    def print_parallelism_report(self, batch_size: int):
        """
        Print parallelism analysis report.

        Args:
            batch_size: Batch size to analyze
        """
        should_parallel, reasoning = self.should_parallelize(batch_size)

        print("\n" + "=" * 70)
        print("🔀 SOLLOL ADAPTIVE PARALLELISM REPORT")
        print("=" * 70)

        print(f"\nBatch Size: {batch_size}")
        print(f"Available Nodes: {reasoning.get('available_nodes', 0)}")

        if reasoning.get("fastest_node"):
            print(f"Fastest Node: {reasoning['fastest_node']}")
            print(f"Speed Ratio: {reasoning.get('speed_ratio', 0):.1f}x")

        print(f"\n{'✅ PARALLEL' if should_parallel else '⏭️  SEQUENTIAL'} Processing Recommended")
        print(f"Reason: {reasoning['reason']}")
        print(f"Detail: {reasoning['detail']}")

        if should_parallel:
            workers = reasoning.get("parallel_workers", 1)
            print(f"Recommended Workers: {workers}")
        else:
            recommended = reasoning.get("recommended_node", "unknown")
            print(f"Recommended Node: {recommended}")

        print("=" * 70 + "\n")

    def record_decision(self, decision: Dict, actual_time: float):
        """
        Record a parallelism decision and its outcome for learning.

        Args:
            decision: Decision dict from should_parallelize()
            actual_time: Actual execution time in seconds
        """
        self.performance_history.append(
            {"decision": decision, "actual_time": actual_time, "timestamp": time.time()}
        )

        # Keep only last 100 decisions
        if len(self.performance_history) > 100:
            self.performance_history = self.performance_history[-100:]


# Example integration with SOLLOL's OllamaPool
def integrate_with_pool(pool, strategy: AdaptiveParallelismStrategy):
    """
    Integrate adaptive parallelism with OllamaPool.

    Args:
        pool: OllamaPool instance
        strategy: AdaptiveParallelismStrategy instance

    Example:
        strategy = AdaptiveParallelismStrategy(node_registry)
        integrate_with_pool(pool, strategy)
    """
    # Set registry from pool
    if hasattr(pool, "registry"):
        strategy.set_registry(pool.registry)

    logger.info("✅ Adaptive parallelism integrated with OllamaPool")
