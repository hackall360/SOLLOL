"""
Unit tests for intelligent routing engine.
"""
import pytest
from sollol.intelligence import IntelligentRouter, TaskContext


class TestIntelligentRouter:
    """Test suite for IntelligentRouter class."""

    @pytest.fixture
    def router(self):
        """Create router instance for testing."""
        return IntelligentRouter()

    @pytest.fixture
    def simple_payload(self):
        """Simple chat payload."""
        return {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Hello!"}]
        }

    @pytest.fixture
    def complex_payload(self):
        """Complex multi-turn conversation."""
        # Create a truly complex payload with >2000 characters = >500 tokens
        long_content = "Please analyze this complex dataset in detail. " * 50  # ~2400 chars
        return {
            "model": "llama3.2",
            "messages": [
                {"role": "user", "content": long_content},
                {"role": "assistant", "content": "I'll help analyze that comprehensive dataset..."},
                {"role": "user", "content": "Now summarize the findings in detail..."},
                {"role": "assistant", "content": "Here are the key findings..."},
                {"role": "user", "content": "Provide recommendations based on this analysis."},
                {"role": "assistant", "content": "Based on the analysis, I recommend..."},
            ]
        }

    @pytest.fixture
    def embedding_payload(self):
        """Embedding request payload."""
        return {
            "model": "nomic-embed-text",
            "prompt": "This is a document to embed"
        }

    @pytest.fixture
    def classification_payload(self):
        """Classification task payload."""
        return {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Classify this sentiment: I love this product!"}]
        }

    @pytest.fixture
    def sample_hosts(self):
        """Sample host metadata for testing."""
        return [
            {
                "host": "10.0.0.2:11434",
                "available": True,
                "latency_ms": 120.0,
                "success_rate": 0.98,
                "cpu_load": 0.3,
                "gpu_free_mem": 16384,
                "priority": 0,
                "preferred_task_types": ["generation"]
            },
            {
                "host": "10.0.0.3:11434",
                "available": True,
                "latency_ms": 200.0,
                "success_rate": 0.95,
                "cpu_load": 0.6,
                "gpu_free_mem": 8192,
                "priority": 1,
                "preferred_task_types": []
            },
            {
                "host": "10.0.0.4:11434",
                "available": True,
                "latency_ms": 80.0,
                "success_rate": 0.99,
                "cpu_load": 0.1,
                "gpu_free_mem": 0,
                "priority": 2,
                "preferred_task_types": ["embedding"]
            }
        ]

    # Task Type Detection Tests

    def test_detect_task_type_generation(self, router, simple_payload):
        """Test detection of generation task type."""
        task_type = router.detect_task_type(simple_payload)
        assert task_type == "generation"

    def test_detect_task_type_embedding(self, router, embedding_payload):
        """Test detection of embedding task type."""
        task_type = router.detect_task_type(embedding_payload)
        assert task_type == "embedding"

    def test_detect_task_type_classification(self, router, classification_payload):
        """Test detection of classification task type."""
        task_type = router.detect_task_type(classification_payload)
        assert task_type == "classification"

    # Complexity Estimation Tests

    def test_estimate_complexity_simple(self, router, simple_payload):
        """Test complexity estimation for simple requests."""
        complexity, tokens = router.estimate_complexity(simple_payload)
        assert complexity == "simple"
        assert tokens < 500

    def test_estimate_complexity_complex(self, router, complex_payload):
        """Test complexity estimation for complex requests."""
        complexity, tokens = router.estimate_complexity(complex_payload)
        assert complexity == "complex"
        assert tokens > 500

    def test_estimate_tokens_accuracy(self, router):
        """Test token estimation is roughly accurate."""
        payload = {"messages": [{"role": "user", "content": "a" * 1000}]}
        _, tokens = router.estimate_complexity(payload)
        # ~250 tokens for 1000 chars (4 chars per token)
        assert 200 < tokens < 300

    # Request Analysis Tests

    def test_analyze_request_returns_context(self, router, simple_payload):
        """Test analyze_request returns TaskContext."""
        context = router.analyze_request(simple_payload, priority=5)
        assert isinstance(context, TaskContext)
        assert context.task_type is not None
        assert context.complexity is not None
        assert context.priority == 5

    def test_analyze_request_gpu_requirement_generation(self, router, complex_payload):
        """Test GPU requirement detection for complex generation."""
        context = router.analyze_request(complex_payload, priority=8)
        assert context.requires_gpu is True

    def test_analyze_request_gpu_requirement_simple(self, router, simple_payload):
        """Test GPU not required for simple tasks."""
        context = router.analyze_request(simple_payload, priority=3)
        assert context.requires_gpu is False

    # Host Scoring Tests

    def test_score_host_availability_check(self, router):
        """Test unavailable hosts get zero score."""
        context = TaskContext(
            task_type="generation",
            complexity="medium",
            estimated_tokens=1000,
            model_preference="llama3.2",
            priority=5,
            requires_gpu=True,
            estimated_duration_ms=3000.0,
            metadata={}
        )
        unavailable_host = {
            "host": "10.0.0.5:11434",
            "available": False,
            "latency_ms": 100.0,
            "success_rate": 1.0,
            "cpu_load": 0.1,
            "gpu_free_mem": 16384,
            "priority": 0,
            "preferred_task_types": []
        }
        score = router._score_host_for_context(unavailable_host, context)
        assert score == 0.0

    def test_score_host_gpu_bonus(self, router, sample_hosts):
        """Test GPU bonus is applied correctly."""
        context = TaskContext(
            task_type="generation",
            complexity="medium",
            estimated_tokens=1000,
            model_preference="llama3.2",
            priority=5,
            requires_gpu=True,
            estimated_duration_ms=3000.0,
            metadata={}
        )

        # Host with GPU should score higher than host without
        gpu_host = sample_hosts[0]  # 16384 MB GPU
        no_gpu_host = sample_hosts[2]  # 0 MB GPU

        gpu_score = router._score_host_for_context(gpu_host, context)
        no_gpu_score = router._score_host_for_context(no_gpu_host, context)

        assert gpu_score > no_gpu_score

    def test_score_host_success_rate_impact(self, router):
        """Test success rate impacts scoring."""
        context = TaskContext(
            task_type="generation",
            complexity="simple",
            estimated_tokens=500,
            model_preference="llama3.2",
            priority=5,
            requires_gpu=False,
            estimated_duration_ms=1500.0,
            metadata={}
        )

        high_success_host = {
            "host": "10.0.0.2:11434",
            "available": True,
            "latency_ms": 100.0,
            "success_rate": 0.99,
            "cpu_load": 0.5,
            "gpu_free_mem": 0,
            "priority": 0,
            "preferred_task_types": []
        }

        low_success_host = {
            "host": "10.0.0.3:11434",
            "available": True,
            "latency_ms": 100.0,
            "success_rate": 0.70,
            "cpu_load": 0.5,
            "gpu_free_mem": 0,
            "priority": 0,
            "preferred_task_types": []
        }

        high_score = router._score_host_for_context(high_success_host, context)
        low_score = router._score_host_for_context(low_success_host, context)

        assert high_score > low_score

    # Optimal Node Selection Tests

    def test_select_optimal_node_returns_best(self, router, sample_hosts):
        """Test optimal node selection returns highest scoring host."""
        context = TaskContext(
            task_type="generation",
            complexity="medium",
            estimated_tokens=1000,
            model_preference="llama3.2",
            priority=8,
            requires_gpu=True,
            estimated_duration_ms=3000.0,
            metadata={}
        )

        selected_host, decision = router.select_optimal_node(context, sample_hosts)

        assert selected_host in [h["host"] for h in sample_hosts]
        assert "score" in decision
        assert "reasoning" in decision
        assert decision["task_type"] == "generation"

    def test_select_optimal_node_raises_on_empty(self, router):
        """Test selection raises error with no hosts."""
        context = TaskContext(
            task_type="generation",
            complexity="simple",
            estimated_tokens=500,
            model_preference="llama3.2",
            priority=5,
            requires_gpu=False,
            estimated_duration_ms=1500.0,
            metadata={}
        )

        with pytest.raises(ValueError, match="No available hosts"):
            router.select_optimal_node(context, [])

    # Performance Recording Tests

    def test_record_performance_stores_data(self, router):
        """Test performance recording stores data."""
        router.record_performance("generation", "llama3.2", 2500.0)

        key = "generation:llama3.2"
        assert key in router.performance_history
        assert 2500.0 in router.performance_history[key]

    def test_record_performance_limits_history(self, router):
        """Test performance history is limited to 100 entries."""
        for i in range(150):
            router.record_performance("test", "model", float(i))

        key = "test:model"
        assert len(router.performance_history[key]) == 100
        # Should keep latest 100
        assert 149.0 in router.performance_history[key]
        assert 0.0 not in router.performance_history[key]

    # Edge Cases

    def test_handle_empty_messages(self, router):
        """Test handling of empty message list."""
        payload = {"messages": []}
        task_type = router.detect_task_type(payload)
        assert task_type == "generation"  # Default

    def test_handle_missing_content(self, router):
        """Test handling of messages without content."""
        payload = {"messages": [{"role": "user"}]}
        complexity, tokens = router.estimate_complexity(payload)
        assert tokens == 0

    def test_priority_out_of_range(self, router, simple_payload):
        """Test handling of extreme priority values."""
        # Very high priority
        context = router.analyze_request(simple_payload, priority=100)
        assert context.priority == 100

        # Negative priority
        context = router.analyze_request(simple_payload, priority=-5)
        assert context.priority == -5
