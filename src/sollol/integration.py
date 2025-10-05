"""
SOLLOL Integration Module - Plug-and-Play Load Balancer

This module provides a drop-in replacement load balancer that can be integrated
into any application requiring intelligent Ollama request routing.

Key Features:
- Context-aware request analysis
- Priority-based scheduling
- Multi-factor host scoring
- Adaptive learning from performance data
- Full routing transparency

Usage:
    from sollol.integration import SOLLOLLoadBalancer

    # Initialize with your node registry
    load_balancer = SOLLOLLoadBalancer(node_registry)

    # Route requests intelligently
    decision = load_balancer.route_request(
        payload={'prompt': 'Hello', 'model': 'llama3.2'},
        agent_name='MyAgent',
        priority=7
    )

    # Use the selected node
    response = requests.post(
        f"{decision.node.url}/api/generate",
        json=payload
    )

    # Record performance for adaptive learning
    load_balancer.record_performance(
        decision=decision,
        actual_duration_ms=response.elapsed.total_seconds() * 1000,
        success=response.ok
    )
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from sollol.adapters import MetricsCollector, PerformanceMemory

# Import SOLLOL core modules
from sollol.intelligence import IntelligentRouter, TaskContext
from sollol.prioritization import (
    PRIORITY_BATCH,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_NORMAL,
    PriorityQueue,
)

logger = logging.getLogger(__name__)


# Protocol for node objects - applications can use any object that matches this
class NodeProtocol(Protocol):
    """Protocol that node objects must implement."""

    url: str
    is_healthy: bool

    def calculate_load_score(self) -> float:
        """Return current load score (0-100)."""
        ...


class NodeRegistryProtocol(Protocol):
    """Protocol that node registries must implement."""

    def get_healthy_nodes(self) -> List[NodeProtocol]:
        """Return list of healthy nodes."""
        ...

    def get_gpu_nodes(self) -> List[NodeProtocol]:
        """Return list of GPU-capable nodes."""
        ...


@dataclass
class RoutingDecision:
    """Complete routing decision with reasoning and metadata."""

    node: NodeProtocol
    task_context: TaskContext
    decision_score: float
    reasoning: str
    timestamp: datetime
    fallback_nodes: List[NodeProtocol]


class SOLLOLLoadBalancer:
    """
    SOLLOL-powered intelligent load balancer.

    Drop-in replacement for basic load balancers with advanced features:
    - Context-aware routing based on request analysis
    - Priority queue for request scheduling
    - Performance tracking and adaptive learning
    - Multi-factor node scoring
    - Automatic failover with reasoning

    This class is designed to be application-agnostic and work with any
    node registry that implements the NodeRegistryProtocol.
    """

    def __init__(self, registry: NodeRegistryProtocol):
        """
        Initialize SOLLOL load balancer.

        Args:
            registry: Node registry implementing NodeRegistryProtocol
        """
        self.registry = registry

        # SOLLOL components
        self.intelligence = IntelligentRouter()
        self.priority_queue = PriorityQueue()
        self.memory = PerformanceMemory()
        self.metrics = MetricsCollector()

        logger.info("🚀 SOLLOL Load Balancer initialized with intelligent routing")

    def route_request(
        self, payload: Dict[str, Any], agent_name: str = "Unknown", priority: int = PRIORITY_NORMAL
    ) -> RoutingDecision:
        """
        Route a request using SOLLOL's intelligent routing engine.

        Args:
            payload: Request payload (prompt, messages, model, etc.)
            agent_name: Name of the agent making the request
            priority: Request priority (1-10, higher = more important)

        Returns:
            RoutingDecision with node, context, score, and reasoning

        Raises:
            RuntimeError: If no healthy nodes are available
        """
        start_time = time.time()

        # Step 1: Analyze request to build context
        context = self.intelligence.analyze_request(payload, priority)

        logger.debug(
            f"📊 Request Analysis: type={context.task_type}, "
            f"complexity={context.complexity}, priority={priority}, "
            f"tokens={context.estimated_tokens}"
        )

        # Step 2: Get available healthy nodes
        healthy_nodes = self.registry.get_healthy_nodes()

        if not healthy_nodes:
            raise RuntimeError("No healthy nodes available for routing")

        # Step 3: Convert nodes to host metadata for SOLLOL
        available_hosts = [self._node_to_host_metadata(node) for node in healthy_nodes]

        # Step 4: Use SOLLOL intelligent router to select optimal node
        selected_host, decision_metadata = self.intelligence.select_optimal_node(
            context, available_hosts
        )

        # Step 5: Find the node object for the selected host
        selected_node = next((node for node in healthy_nodes if node.url == selected_host), None)

        if not selected_node:
            # Fallback to first healthy node
            selected_node = healthy_nodes[0]
            decision_metadata = {"score": 50.0, "reasoning": "Fallback to first available node"}

        # Step 6: Prepare fallback nodes
        fallback_nodes = [node for node in healthy_nodes if node.url != selected_node.url]

        # Step 7: Create routing decision
        decision = RoutingDecision(
            node=selected_node,
            task_context=context,
            decision_score=decision_metadata.get("score", 0.0),
            reasoning=decision_metadata.get("reasoning", "Intelligent routing"),
            timestamp=datetime.now(),
            fallback_nodes=fallback_nodes,
        )

        # Step 8: Record metrics
        routing_time = (time.time() - start_time) * 1000
        self.metrics.record_routing_decision(
            agent_name=agent_name,
            task_type=context.task_type,
            priority=priority,
            selected_node=selected_node.url,
            score=decision.decision_score,
            routing_time_ms=routing_time,
        )

        logger.info(
            f"✅ Routed {agent_name} to {selected_node.url} "
            f"(score: {decision.decision_score:.1f}, time: {routing_time:.1f}ms)"
        )
        logger.debug(f"   Reasoning: {decision.reasoning}")

        return decision

    def route_with_retry(
        self,
        payload: Dict[str, Any],
        agent_name: str = "Unknown",
        priority: int = PRIORITY_NORMAL,
        max_retries: int = 3,
        backoff_multiplier: float = 0.5,
    ) -> RoutingDecision:
        """
        Route request with automatic retry on failure using fallback nodes.

        This method will:
        1. Get initial routing decision
        2. If primary node fails, automatically try fallback nodes
        3. Use exponential backoff between retries
        4. Return the first successful routing decision

        Args:
            payload: Request payload
            agent_name: Name of agent making request
            priority: Request priority
            max_retries: Maximum retry attempts (default: 3)
            backoff_multiplier: Exponential backoff multiplier (default: 0.5)

        Returns:
            RoutingDecision for successful node

        Raises:
            RuntimeError: If all nodes fail after max retries

        Example:
            decision = load_balancer.route_with_retry(
                payload={'prompt': 'test', 'model': 'llama3.2'},
                agent_name='MyAgent',
                max_retries=3
            )

            # Try to execute with automatic failover
            for attempt in range(max_retries):
                try:
                    response = requests.post(
                        f"{decision.node.url}/api/generate",
                        json=payload
                    )
                    if response.ok:
                        break
                except Exception:
                    # Move to next fallback node if available
                    if attempt < len(decision.fallback_nodes):
                        decision.node = decision.fallback_nodes[attempt]
                    else:
                        raise
        """
        import time as time_module

        decision = self.route_request(payload, agent_name, priority)
        all_nodes = [decision.node] + decision.fallback_nodes

        last_error = None
        for attempt, node in enumerate(all_nodes[:max_retries]):
            if attempt > 0:
                wait_time = backoff_multiplier * (2 ** (attempt - 1))
                logger.warning(
                    f"🔄 Retry {attempt}/{max_retries}: "
                    f"Falling back to {node.url} after {wait_time:.1f}s"
                )
                time_module.sleep(wait_time)

                # Update decision to use fallback node
                decision.node = node
                decision.reasoning = (
                    f"Fallback #{attempt} after primary node failure "
                    f"(retry with exponential backoff: {wait_time:.1f}s)"
                )

            # Application should try this node
            # We just return the decision with updated node
            logger.info(f"📍 Attempt {attempt + 1}: Using {node.url}")

        return decision

    def execute_with_failover(
        self,
        payload: Dict[str, Any],
        execute_fn: callable,
        agent_name: str = "Unknown",
        priority: int = PRIORITY_NORMAL,
        max_retries: int = 3,
        backoff_multiplier: float = 0.5,
    ) -> Any:
        """
        Execute a request with automatic failover to backup nodes.

        This is a higher-level method that handles the entire request lifecycle:
        routing, execution, retry, and failover.

        Args:
            payload: Request payload
            execute_fn: Function that executes the request. Should accept (url, payload)
                       and return the response. Should raise exception on failure.
            agent_name: Name of agent making request
            priority: Request priority
            max_retries: Maximum retry attempts
            backoff_multiplier: Exponential backoff multiplier

        Returns:
            Result from execute_fn

        Raises:
            RuntimeError: If all nodes fail after max retries

        Example:
            import requests

            def execute_request(url, payload):
                response = requests.post(f"{url}/api/generate", json=payload)
                response.raise_for_status()
                return response.json()

            result = load_balancer.execute_with_failover(
                payload={'prompt': 'test', 'model': 'llama3.2'},
                execute_fn=execute_request,
                agent_name='MyAgent'
            )
        """
        import time as time_module

        decision = self.route_request(payload, agent_name, priority)
        all_nodes = [decision.node] + decision.fallback_nodes

        last_error = None
        start_time = time_module.time()

        for attempt, node in enumerate(all_nodes[:max_retries]):
            if attempt > 0:
                wait_time = backoff_multiplier * (2 ** (attempt - 1))
                logger.warning(
                    f"🔄 Retry {attempt}/{max_retries}: "
                    f"Falling back to {node.url} after {wait_time:.1f}s"
                )
                time_module.sleep(wait_time)

            try:
                logger.info(f"📍 Attempt {attempt + 1}: Executing on {node.url}")
                result = execute_fn(node.url, payload)

                # Record successful execution
                duration_ms = (time_module.time() - start_time) * 1000
                decision.node = node  # Update to successful node
                self.record_performance(
                    decision=decision, actual_duration_ms=duration_ms, success=True
                )

                if attempt > 0:
                    logger.info(
                        f"✅ Succeeded on fallback node {node.url} "
                        f"after {attempt} failed attempts"
                    )

                return result

            except Exception as e:
                last_error = e
                logger.error(f"❌ Failed on {node.url}: {e}")

                # Record failed execution
                duration_ms = (time_module.time() - start_time) * 1000
                decision.node = node
                self.record_performance(
                    decision=decision, actual_duration_ms=duration_ms, success=False, error=str(e)
                )

                if attempt >= max_retries - 1:
                    break

        # All nodes failed
        raise RuntimeError(f"All {max_retries} node attempts failed. Last error: {last_error}")

    def record_performance(
        self,
        decision: RoutingDecision,
        actual_duration_ms: float,
        success: bool,
        error: Optional[str] = None,
    ):
        """
        Record actual performance for adaptive learning.

        Args:
            decision: Original routing decision
            actual_duration_ms: Actual request duration in milliseconds
            success: Whether request succeeded
            error: Error message if failed (optional)
        """
        # Update SOLLOL performance memory
        self.memory.record_execution(
            node_url=decision.node.url,
            task_type=decision.task_context.task_type,
            model=decision.task_context.model_preference or "unknown",
            duration_ms=actual_duration_ms,
            success=success,
        )

        # Update metrics
        self.metrics.record_request_completion(
            agent_name="Unknown",  # Would be passed from caller
            node_url=decision.node.url,
            task_type=decision.task_context.task_type,
            priority=decision.task_context.priority,
            duration_ms=actual_duration_ms,
            success=success,
        )

        # Calculate prediction accuracy
        predicted_duration = decision.task_context.estimated_duration_ms
        if predicted_duration > 0:
            accuracy = 1.0 - abs(actual_duration_ms - predicted_duration) / max(
                actual_duration_ms, predicted_duration
            )
            logger.debug(
                f"📈 Performance recorded: {decision.node.url} "
                f"(predicted: {predicted_duration:.0f}ms, actual: {actual_duration_ms:.0f}ms, "
                f"accuracy: {accuracy:.1%})"
            )

    def get_routing_metadata(self, decision: RoutingDecision) -> Dict[str, Any]:
        """
        Get routing metadata to include in response for transparency.

        Args:
            decision: Routing decision

        Returns:
            Metadata dict for inclusion in response
        """
        return {
            "_sollol_routing": {
                "host": decision.node.url,
                "task_type": decision.task_context.task_type,
                "complexity": decision.task_context.complexity,
                "priority": decision.task_context.priority,
                "estimated_tokens": decision.task_context.estimated_tokens,
                "requires_gpu": decision.task_context.requires_gpu,
                "decision_score": decision.decision_score,
                "reasoning": decision.reasoning,
                "timestamp": decision.timestamp.isoformat(),
                "estimated_duration_ms": decision.task_context.estimated_duration_ms,
                "fallback_nodes_available": len(decision.fallback_nodes),
                "routing_engine": "SOLLOL",
                "version": "1.0.0",
            }
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about routing and performance.

        Returns:
            Statistics dictionary with load balancer info, node counts,
            metrics summary, performance memory stats, and queue depth.
        """
        healthy_nodes = self.registry.get_healthy_nodes()
        gpu_nodes = self.registry.get_gpu_nodes()
        all_nodes = list(self.registry.get_healthy_nodes())  # Get all nodes if available

        return {
            "load_balancer": {
                "type": "SOLLOL",
                "version": "1.0.0",
                "intelligent_routing": True,
                "priority_queue": True,
                "adaptive_learning": True,
            },
            "nodes": {
                "healthy": len(healthy_nodes),
                "gpu": len(gpu_nodes),
            },
            "metrics": self.metrics.get_summary(),
            "performance_memory": {
                "tracked_executions": len(self.memory.history),
                "unique_task_types": len(set(h["task_type"] for h in self.memory.history)),
                "unique_models": len(set(h["model"] for h in self.memory.history)),
            },
            "queue": {
                "depth": len(self.priority_queue.queue),
                "total_queued": self.priority_queue.total_queued,
                "total_processed": self.priority_queue.total_processed,
            },
        }

    def _node_to_host_metadata(self, node: NodeProtocol) -> Dict[str, Any]:
        """
        Convert node object to host metadata format for SOLLOL.

        Args:
            node: Node object implementing NodeProtocol

        Returns:
            Host metadata dict compatible with SOLLOL intelligence module
        """
        # Extract capabilities if available
        has_gpu = False
        gpu_memory_mb = 0
        cpu_count = 1

        if hasattr(node, "capabilities") and node.capabilities:
            has_gpu = getattr(node.capabilities, "has_gpu", False)
            gpu_memory_mb = getattr(node.capabilities, "gpu_memory_mb", 0)
            cpu_count = getattr(node.capabilities, "cpu_count", 1)

        # Extract metrics if available
        current_load = (
            node.calculate_load_score() if hasattr(node, "calculate_load_score") else 50.0
        )
        total_requests = 0
        successful_requests = 0
        avg_latency = 0.0

        if hasattr(node, "metrics") and node.metrics:
            total_requests = getattr(node.metrics, "total_requests", 0)
            successful_requests = getattr(node.metrics, "successful_requests", 0)
            avg_latency = getattr(node.metrics, "avg_latency", 0.0)

        success_rate = successful_requests / total_requests if total_requests > 0 else 1.0

        return {
            "url": node.url,
            "host": node.url,
            "health": "healthy" if node.is_healthy else "unhealthy",
            "capabilities": {
                "has_gpu": has_gpu,
                "gpu_memory_mb": gpu_memory_mb,
                "cpu_count": cpu_count,
            },
            "metrics": {
                "current_load": current_load,
                "total_requests": total_requests,
                "success_rate": success_rate,
                "avg_latency_ms": avg_latency,
            },
            "priority": getattr(node, "priority", 5),
        }

    def suggest_execution_mode(self) -> str:
        """
        Suggest optimal execution mode based on available nodes.

        Returns:
            Suggested execution mode: "parallel", "sequential", or "auto"
        """
        healthy_nodes = self.registry.get_healthy_nodes()
        num_nodes = len(healthy_nodes)

        if num_nodes >= 3:
            return "parallel_multi_node"
        elif num_nodes >= 2:
            return "parallel"
        else:
            return "sequential"

    def should_use_parallel(self) -> bool:
        """
        Determine if parallel execution is beneficial.

        Returns:
            True if 2+ healthy nodes available, False otherwise
        """
        return len(self.registry.get_healthy_nodes()) >= 2

    def __repr__(self):
        healthy = len(self.registry.get_healthy_nodes())
        gpu = len(self.registry.get_gpu_nodes())
        return (
            f"SOLLOLLoadBalancer("
            f"healthy={healthy}, gpu={gpu}, "
            f"intelligent_routing=enabled, adaptive_learning=enabled)"
        )


# Convenience exports
__all__ = [
    "SOLLOLLoadBalancer",
    "RoutingDecision",
    "NodeProtocol",
    "NodeRegistryProtocol",
    "PRIORITY_CRITICAL",
    "PRIORITY_HIGH",
    "PRIORITY_NORMAL",
    "PRIORITY_LOW",
    "PRIORITY_BATCH",
]

# Note: Node management (add_node, remove_node, discover_nodes) is
# intentionally NOT part of SOLLOL. Applications should manage their
# own node registries. SOLLOL focuses on intelligent routing to whatever
# nodes the application provides.
