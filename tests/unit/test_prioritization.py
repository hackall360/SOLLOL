"""
Unit tests for priority queue system.
"""
import asyncio

import pytest
import pytest_asyncio

from sollol.prioritization import (
    PRIORITY_BATCH,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_NORMAL,
    PrioritizedTask,
    PriorityQueue,
    get_priority_for_task_type,
)


class TestPrioritizedTask:
    """Test suite for PrioritizedTask dataclass."""

    def test_task_ordering_by_priority(self):
        """Test tasks are ordered by priority (higher first)."""
        task_low = PrioritizedTask(
            priority=3,
            timestamp=1.0,
            task_id="low",
            payload={},
            future=asyncio.Future()
        )
        task_high = PrioritizedTask(
            priority=8,
            timestamp=1.0,
            task_id="high",
            payload={},
            future=asyncio.Future()
        )

        assert task_high < task_low  # Higher priority comes first

    def test_task_ordering_by_age(self):
        """Test tasks with same priority ordered by age (older first)."""
        task_old = PrioritizedTask(
            priority=5,
            timestamp=1.0,
            task_id="old",
            payload={},
            future=asyncio.Future()
        )
        task_new = PrioritizedTask(
            priority=5,
            timestamp=2.0,
            task_id="new",
            payload={},
            future=asyncio.Future()
        )

        assert task_old < task_new  # Older timestamp comes first


@pytest.mark.asyncio
class TestPriorityQueue:
    """Test suite for PriorityQueue class."""

    @pytest.fixture
    def queue(self):
        """Create empty priority queue."""
        return PriorityQueue(max_queue_size=10)

    @pytest_asyncio.fixture
    async def populated_queue(self):
        """Create queue with sample tasks."""
        queue = PriorityQueue(max_queue_size=100)

        # Add tasks with different priorities
        await queue.enqueue({"data": "low"}, priority=3, task_id="task_low")
        await queue.enqueue({"data": "normal"}, priority=5, task_id="task_normal")
        await queue.enqueue({"data": "high"}, priority=8, task_id="task_high")

        return queue

    # Enqueue Tests

    async def test_enqueue_success(self, queue):
        """Test successful enqueue operation."""
        future = await queue.enqueue({"test": "data"}, priority=5)

        assert isinstance(future, asyncio.Future)
        assert await queue.size() == 1

    async def test_enqueue_generates_task_id(self, queue):
        """Test automatic task_id generation."""
        await queue.enqueue({"test": "data"}, priority=5)
        task = await queue.dequeue()

        assert task.task_id.startswith("task_")

    async def test_enqueue_custom_task_id(self, queue):
        """Test custom task_id is preserved."""
        await queue.enqueue({"test": "data"}, priority=5, task_id="custom_id")
        task = await queue.dequeue()

        assert task.task_id == "custom_id"

    async def test_enqueue_full_queue_raises_error(self, queue):
        """Test enqueue raises error when queue is full."""
        # Fill queue
        for i in range(10):
            await queue.enqueue({"num": i}, priority=5)

        # Try to add one more
        with pytest.raises(ValueError, match="Queue full"):
            await queue.enqueue({"num": 11}, priority=5)

    async def test_enqueue_increments_counter(self, queue):
        """Test enqueue increments total_queued counter."""
        await queue.enqueue({"data": 1}, priority=5)
        await queue.enqueue({"data": 2}, priority=5)

        assert queue.total_queued == 2

    # Dequeue Tests

    async def test_dequeue_empty_returns_none(self, queue):
        """Test dequeue from empty queue returns None."""
        task = await queue.dequeue()
        assert task is None

    async def test_dequeue_returns_highest_priority(self, populated_queue):
        """Test dequeue returns highest priority task first."""
        task = await populated_queue.dequeue()
        assert task.priority == 8
        assert task.task_id == "task_high"

    async def test_dequeue_fifo_within_priority(self, queue):
        """Test FIFO ordering within same priority level."""
        # Add tasks with same priority but different times
        await queue.enqueue({"order": 1}, priority=5, task_id="first")
        await asyncio.sleep(0.01)  # Ensure different timestamp
        await queue.enqueue({"order": 2}, priority=5, task_id="second")

        task1 = await queue.dequeue()
        task2 = await queue.dequeue()

        assert task1.task_id == "first"
        assert task2.task_id == "second"

    async def test_dequeue_increments_processed(self, populated_queue):
        """Test dequeue increments total_processed counter."""
        initial_processed = populated_queue.total_processed

        await populated_queue.dequeue()
        assert populated_queue.total_processed == initial_processed + 1

    async def test_dequeue_records_wait_time(self, queue):
        """Test dequeue records wait time metrics."""
        await queue.enqueue({"data": "test"}, priority=5)
        await queue.dequeue()

        # Check wait time was recorded
        assert 5 in queue.queue_wait_times
        assert len(queue.queue_wait_times[5]) == 1
        assert queue.queue_wait_times[5][0] >= 0

    async def test_dequeue_limits_wait_time_history(self, queue):
        """Test wait time history is limited to 100 entries."""
        for i in range(150):
            await queue.enqueue({"num": i}, priority=5)
            await queue.dequeue()

        # Should keep only last 100
        assert len(queue.queue_wait_times[5]) == 100

    # Size Tests

    async def test_size_empty_queue(self, queue):
        """Test size of empty queue is 0."""
        size = await queue.size()
        assert size == 0

    async def test_size_after_operations(self, queue):
        """Test size updates correctly after enqueue/dequeue."""
        await queue.enqueue({"data": 1}, priority=5)
        await queue.enqueue({"data": 2}, priority=5)
        assert await queue.size() == 2

        await queue.dequeue()
        assert await queue.size() == 1

        await queue.dequeue()
        assert await queue.size() == 0

    # Statistics Tests

    async def test_get_stats_structure(self, populated_queue):
        """Test get_stats returns expected structure."""
        stats = await populated_queue.get_stats()

        assert "queue_size" in stats
        assert "total_queued" in stats
        assert "total_processed" in stats
        assert "avg_wait_times_ms" in stats
        assert "current_priorities" in stats
        assert "utilization" in stats

    async def test_get_stats_priority_counts(self, populated_queue):
        """Test priority counts are accurate."""
        stats = await populated_queue.get_stats()

        # We added one task of each priority: 3, 5, 8
        counts = stats["current_priorities"]
        assert counts[3] == 1
        assert counts[5] == 1
        assert counts[8] == 1

    async def test_get_stats_avg_wait_times(self, queue):
        """Test average wait times calculation."""
        # Add and process tasks with known wait
        await queue.enqueue({"data": 1}, priority=5)
        await queue.dequeue()

        await queue.enqueue({"data": 2}, priority=8)
        await queue.dequeue()

        stats = await queue.get_stats()
        wait_times = stats["avg_wait_times_ms"]

        # Both priorities should have recorded wait times
        assert 5 in wait_times
        assert 8 in wait_times
        assert wait_times[5] >= 0
        assert wait_times[8] >= 0

    async def test_get_stats_utilization(self, queue):
        """Test utilization calculation."""
        # Half full queue (max=10)
        for i in range(5):
            await queue.enqueue({"num": i}, priority=5)

        stats = await queue.get_stats()
        assert stats["utilization"] == 0.5

    # Priority Level Tests

    async def test_priority_levels_ordering(self, queue):
        """Test all priority levels are correctly ordered."""
        # Add one task of each standard priority
        await queue.enqueue({"p": "batch"}, priority=PRIORITY_BATCH)
        await queue.enqueue({"p": "low"}, priority=PRIORITY_LOW)
        await queue.enqueue({"p": "normal"}, priority=PRIORITY_NORMAL)
        await queue.enqueue({"p": "high"}, priority=PRIORITY_HIGH)
        await queue.enqueue({"p": "critical"}, priority=PRIORITY_CRITICAL)

        # Dequeue in priority order
        task1 = await queue.dequeue()
        task2 = await queue.dequeue()
        task3 = await queue.dequeue()
        task4 = await queue.dequeue()
        task5 = await queue.dequeue()

        assert task1.payload["p"] == "critical"
        assert task2.payload["p"] == "high"
        assert task3.payload["p"] == "normal"
        assert task4.payload["p"] == "low"
        assert task5.payload["p"] == "batch"

    # Concurrent Access Tests

    async def test_concurrent_enqueue(self, queue):
        """Test concurrent enqueue operations."""
        async def add_task(i):
            await queue.enqueue({"num": i}, priority=5)

        # Add 5 tasks concurrently
        await asyncio.gather(*[add_task(i) for i in range(5)])

        assert await queue.size() == 5
        assert queue.total_queued == 5

    async def test_concurrent_dequeue(self, queue):
        """Test concurrent dequeue operations."""
        # Populate queue
        for i in range(5):
            await queue.enqueue({"num": i}, priority=5)

        async def remove_task():
            return await queue.dequeue()

        # Dequeue concurrently
        tasks = await asyncio.gather(*[remove_task() for _ in range(5)])

        assert await queue.size() == 0
        assert len([t for t in tasks if t is not None]) == 5


class TestPriorityHelpers:
    """Test suite for priority helper functions."""

    def test_get_priority_for_task_type_classification(self):
        """Test priority for classification tasks."""
        priority = get_priority_for_task_type("classification")
        assert priority == PRIORITY_HIGH

    def test_get_priority_for_task_type_generation(self):
        """Test priority for generation tasks."""
        priority = get_priority_for_task_type("generation")
        assert priority == PRIORITY_NORMAL

    def test_get_priority_for_task_type_embedding(self):
        """Test priority for embedding tasks."""
        priority = get_priority_for_task_type("embedding")
        assert priority == PRIORITY_LOW

    def test_get_priority_for_task_type_unknown(self):
        """Test default priority for unknown task types."""
        priority = get_priority_for_task_type("unknown_task")
        assert priority == PRIORITY_NORMAL

    def test_priority_constants_ordering(self):
        """Test priority constants are correctly ordered."""
        assert PRIORITY_CRITICAL > PRIORITY_HIGH
        assert PRIORITY_HIGH > PRIORITY_NORMAL
        assert PRIORITY_NORMAL > PRIORITY_LOW
        assert PRIORITY_LOW > PRIORITY_BATCH
