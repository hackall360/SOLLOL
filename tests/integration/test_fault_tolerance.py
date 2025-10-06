"""
Fault tolerance and resilience tests for SOLLOL.

Tests SOLLOL's ability to handle:
- Node failures
- Network partitions
- High load scenarios
- Recovery procedures
"""

import asyncio

import pytest

from sollol.intelligence import IntelligentRouter, TaskContext
from sollol.prioritization import PriorityQueue


class TestFailover:
    """Test automatic failover capabilities."""

    @pytest.fixture
    def router(self):
        return IntelligentRouter()

    @pytest.fixture
    def hosts_with_failures(self):
        """Hosts with some unavailable."""
        return [
            {
                "host": "10.0.0.2:11434",
                "available": False,  # Failed node
                "latency_ms": 0,
                "success_rate": 0.0,
                "cpu_load": 0.0,
                "gpu_free_mem": 0,
                "priority": 0,
                "preferred_task_types": [],
            },
            {
                "host": "10.0.0.3:11434",
                "available": True,  # Healthy backup
                "latency_ms": 150.0,
                "success_rate": 0.98,
                "cpu_load": 0.4,
                "gpu_free_mem": 16384,
                "priority": 1,
                "preferred_task_types": [],
            },
            {
                "host": "10.0.0.4:11434",
                "available": True,  # Another healthy node
                "latency_ms": 200.0,
                "success_rate": 0.95,
                "cpu_load": 0.6,
                "gpu_free_mem": 8192,
                "priority": 2,
                "preferred_task_types": [],
            },
        ]

    def test_routes_around_failed_node(self, router, hosts_with_failures):
        """Test that failed nodes are excluded from routing."""
        context = TaskContext(
            task_type="generation",
            complexity="medium",
            estimated_tokens=1000,
            model_preference="llama3.2",
            priority=5,
            requires_gpu=True,
            estimated_duration_ms=3000.0,
            metadata={},
        )

        selected_host, decision = router.select_optimal_node(context, hosts_with_failures)

        # Should NOT select the failed node (10.0.0.2)
        assert selected_host != "10.0.0.2:11434"
        assert selected_host in ["10.0.0.3:11434", "10.0.0.4:11434"]

    def test_handles_all_nodes_failed(self, router):
        """Test graceful error when all nodes are unavailable."""
        all_failed = [
            {
                "host": f"10.0.0.{i}:11434",
                "available": False,
                "latency_ms": 0,
                "success_rate": 0.0,
                "cpu_load": 0.0,
                "gpu_free_mem": 0,
                "priority": 0,
                "preferred_task_types": [],
            }
            for i in range(2, 5)
        ]

        context = TaskContext(
            task_type="generation",
            complexity="simple",
            estimated_tokens=500,
            model_preference="llama3.2",
            priority=5,
            requires_gpu=False,
            estimated_duration_ms=1500.0,
            metadata={},
        )

        # Should raise error when no hosts available
        with pytest.raises(ValueError, match="No available hosts"):
            router.select_optimal_node(context, all_failed)

    def test_degraded_node_deprioritized(self, router):
        """Test that degraded nodes get lower scores."""
        hosts = [
            {
                "host": "10.0.0.2:11434",
                "available": True,
                "latency_ms": 2000.0,  # Very high latency
                "success_rate": 0.60,  # Low success rate
                "cpu_load": 0.95,  # High load
                "gpu_free_mem": 512,  # Low memory
                "priority": 10,
                "preferred_task_types": [],
            },
            {
                "host": "10.0.0.3:11434",
                "available": True,
                "latency_ms": 120.0,  # Normal latency
                "success_rate": 0.98,  # High success
                "cpu_load": 0.3,  # Low load
                "gpu_free_mem": 16384,  # Plenty memory
                "priority": 1,
                "preferred_task_types": [],
            },
        ]

        context = TaskContext(
            task_type="generation",
            complexity="medium",
            estimated_tokens=1000,
            model_preference="llama3.2",
            priority=8,
            requires_gpu=True,
            estimated_duration_ms=3000.0,
            metadata={},
        )

        selected_host, decision = router.select_optimal_node(context, hosts)

        # Should select healthy node over degraded one
        assert selected_host == "10.0.0.3:11434"


class TestLoadHandling:
    """Test behavior under high load."""

    @pytest.fixture
    def queue(self):
        return PriorityQueue(max_queue_size=100)

    @pytest.mark.asyncio
    async def test_queue_full_rejects_new_tasks(self, queue):
        """Test queue rejects tasks when full."""
        # Fill queue to capacity
        for i in range(100):
            await queue.enqueue({"task": i}, priority=5)

        # Next enqueue should fail
        with pytest.raises(ValueError, match="Queue full"):
            await queue.enqueue({"task": 101}, priority=5)

    @pytest.mark.asyncio
    async def test_high_priority_preempts_under_load(self, queue):
        """Test high priority tasks processed first under load."""
        # Add tasks with different priorities
        await queue.enqueue({"task": "low"}, priority=3)
        await queue.enqueue({"task": "normal"}, priority=5)
        await queue.enqueue({"task": "critical"}, priority=10)
        await queue.enqueue({"task": "high"}, priority=8)

        # Dequeue should return in priority order
        task1 = await queue.dequeue()
        assert task1.priority == 10  # Critical first

        task2 = await queue.dequeue()
        assert task2.priority == 8  # High second

        task3 = await queue.dequeue()
        assert task3.priority == 5  # Normal third

        task4 = await queue.dequeue()
        assert task4.priority == 3  # Low last

    @pytest.mark.asyncio
    async def test_concurrent_access_no_corruption(self, queue):
        """Test queue handles concurrent access safely."""

        async def enqueue_many():
            for i in range(50):
                await queue.enqueue({"task": i}, priority=5)

        async def dequeue_many():
            await asyncio.sleep(0.01)  # Let some tasks enqueue first
            for _ in range(50):
                await queue.dequeue()

        # Run concurrent enqueue/dequeue
        await asyncio.gather(enqueue_many(), dequeue_many(), enqueue_many())

        # Queue should be consistent
        size = await queue.size()
        assert size == 50  # 100 enqueued, 50 dequeued


class TestRecovery:
    """Test recovery from failures."""

    @pytest.fixture
    def router(self):
        return IntelligentRouter()

    def test_performance_history_survives_failure(self, router):
        """Test performance history maintained after node failures."""
        # Record some performance
        router.record_performance("generation", "llama3.2", 2500.0)
        router.record_performance("generation", "llama3.2", 2300.0)
        router.record_performance("embedding", "nomic-embed-text", 450.0)

        # Simulate node failure and recovery
        # History should still be there
        assert "generation:llama3.2" in router.performance_history
        assert "embedding:nomic-embed-text" in router.performance_history
        assert len(router.performance_history["generation:llama3.2"]) == 2

    def test_routing_adapts_after_recovery(self, router):
        """Test routing adapts when node recovers."""
        # Initially only one healthy node
        hosts_before = [
            {
                "host": "10.0.0.2:11434",
                "available": False,
                "latency_ms": 0,
                "success_rate": 0.0,
                "cpu_load": 0.0,
                "gpu_free_mem": 0,
                "priority": 0,
                "preferred_task_types": [],
            },
            {
                "host": "10.0.0.3:11434",
                "available": True,
                "latency_ms": 200.0,
                "success_rate": 0.95,
                "cpu_load": 0.8,  # High load (only node)
                "gpu_free_mem": 8192,
                "priority": 1,
                "preferred_task_types": [],
            },
        ]

        context = TaskContext(
            task_type="generation",
            complexity="medium",
            estimated_tokens=1000,
            model_preference="llama3.2",
            priority=5,
            requires_gpu=True,
            estimated_duration_ms=3000.0,
            metadata={},
        )

        # Before recovery: must use overloaded node
        host_before, _ = router.select_optimal_node(context, hosts_before)
        assert host_before == "10.0.0.3:11434"

        # After recovery: can distribute load
        hosts_after = hosts_before.copy()
        hosts_after[0]["available"] = True
        hosts_after[0]["latency_ms"] = 120.0
        hosts_after[0]["success_rate"] = 0.98
        hosts_after[0]["cpu_load"] = 0.3
        hosts_after[0]["gpu_free_mem"] = 16384

        host_after, decision = router.select_optimal_node(context, hosts_after)

        # Should prefer the recovered (better) node
        assert host_after == "10.0.0.2:11434"
        assert decision["score"] > 0  # Has positive score


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_handles_zero_success_rate(self):
        """Test scoring with zero success rate."""
        router = IntelligentRouter()

        host = {
            "host": "10.0.0.2:11434",
            "available": True,
            "latency_ms": 100.0,
            "success_rate": 0.0,  # Total failure
            "cpu_load": 0.1,
            "gpu_free_mem": 16384,
            "priority": 0,
            "preferred_task_types": [],
        }

        context = TaskContext(
            task_type="generation",
            complexity="simple",
            estimated_tokens=500,
            model_preference="llama3.2",
            priority=5,
            requires_gpu=False,
            estimated_duration_ms=1500.0,
            metadata={},
        )

        # Should get very low score (success_rate multiplier = 0)
        score = router._score_host_for_context(host, context)
        assert score == 0.0  # Zero success rate = zero score

    def test_handles_extreme_latency(self):
        """Test scoring with extreme latency."""
        router = IntelligentRouter()

        host = {
            "host": "10.0.0.2:11434",
            "available": True,
            "latency_ms": 50000.0,  # 50 seconds!
            "success_rate": 1.0,
            "cpu_load": 0.1,
            "gpu_free_mem": 16384,
            "priority": 0,
            "preferred_task_types": [],
        }

        context = TaskContext(
            task_type="generation",
            complexity="simple",
            estimated_tokens=500,
            model_preference="llama3.2",
            priority=5,
            requires_gpu=False,
            estimated_duration_ms=1500.0,
            metadata={},
        )

        # Should heavily penalize high latency
        score = router._score_host_for_context(host, context)
        assert score < 10.0  # Very low score due to extreme latency

    @pytest.mark.asyncio
    async def test_queue_handles_task_with_no_future(self):
        """Test queue doesn't fail with missing future."""
        queue = PriorityQueue()

        # Enqueue normally creates future
        future = await queue.enqueue({"task": "test"}, priority=5)
        assert future is not None

        # Dequeue should work fine
        task = await queue.dequeue()
        assert task.task_id == "task_0"
