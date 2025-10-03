"""
Pytest configuration and shared fixtures for SOLLOL tests.
"""
import pytest
import asyncio
from typing import Dict, List


@pytest.fixture
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_chat_payload() -> Dict:
    """Sample chat completion payload."""
    return {
        "model": "llama3.2",
        "messages": [
            {"role": "user", "content": "Hello! How are you?"}
        ]
    }


@pytest.fixture
def sample_embedding_payload() -> Dict:
    """Sample embedding payload."""
    return {
        "model": "nomic-embed-text",
        "prompt": "This is a test document for embedding"
    }


@pytest.fixture
def sample_hosts_metadata() -> List[Dict]:
    """Sample host metadata for testing routing."""
    return [
        {
            "host": "10.0.0.2:11434",
            "available": True,
            "latency_ms": 120.0,
            "success_rate": 0.98,
            "cpu_load": 0.3,
            "gpu_free_mem": 16384,
            "priority": 0,
            "preferred_task_types": ["generation"],
            "last_updated": "2025-10-03T12:00:00"
        },
        {
            "host": "10.0.0.3:11434",
            "available": True,
            "latency_ms": 200.0,
            "success_rate": 0.95,
            "cpu_load": 0.6,
            "gpu_free_mem": 8192,
            "priority": 1,
            "preferred_task_types": [],
            "last_updated": "2025-10-03T12:00:00"
        },
        {
            "host": "10.0.0.4:11434",
            "available": True,
            "latency_ms": 80.0,
            "success_rate": 0.99,
            "cpu_load": 0.1,
            "gpu_free_mem": 0,
            "priority": 2,
            "preferred_task_types": ["embedding", "classification"],
            "last_updated": "2025-10-03T12:00:00"
        }
    ]


@pytest.fixture
def degraded_host_metadata() -> Dict:
    """Metadata for a degraded/failing host."""
    return {
        "host": "10.0.0.5:11434",
        "available": True,
        "latency_ms": 1500.0,  # High latency
        "success_rate": 0.65,  # Low success rate
        "cpu_load": 0.95,      # High load
        "gpu_free_mem": 512,   # Low GPU memory
        "priority": 10,
        "preferred_task_types": [],
        "last_updated": "2025-10-03T12:00:00"
    }


@pytest.fixture
def unavailable_host_metadata() -> Dict:
    """Metadata for an unavailable host."""
    return {
        "host": "10.0.0.6:11434",
        "available": False,
        "latency_ms": 0.0,
        "success_rate": 0.0,
        "cpu_load": 0.0,
        "gpu_free_mem": 0,
        "priority": 0,
        "preferred_task_types": [],
        "last_updated": "2025-10-03T12:00:00"
    }
