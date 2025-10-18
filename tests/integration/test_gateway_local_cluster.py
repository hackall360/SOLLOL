"""Integration tests for the gateway local cluster example."""
from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from typing import Callable

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"
for _path in (_REPO_ROOT, _SRC_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from examples.gateway_local_cluster import client, process_utils
from examples.gateway_local_cluster.gateway_process import run_gateway
from sollol.pool import OllamaPool
from tests.integration.mock_ollama_server import run_server as run_mock_ollama

pytestmark = [
    pytest.mark.requires_ollama,
    pytest.mark.skipif(
        os.getenv("SOLLOL_RUN_OLLAMA_TESTS", "").lower() not in {"1", "true", "yes"},
        reason="Ollama integration tests disabled. Set SOLLOL_RUN_OLLAMA_TESTS=1 to enable.",
    ),
]


@pytest.fixture(scope="module")
def disable_dask() -> None:
    original = OllamaPool._init_dask_client
    OllamaPool._init_dask_client = lambda self, dask_address=None: None
    try:
        yield
    finally:
        OllamaPool._init_dask_client = original


@pytest.fixture
def register_process(
    request: pytest.FixtureRequest,
) -> Callable[[process_utils.ManagedProcess], process_utils.ManagedProcess]:
    handles: list[process_utils.ManagedProcess] = []

    def finalize() -> None:
        for handle in reversed(handles):
            try:
                handle.terminate(timeout=30.0)
            finally:
                handle.wait(timeout=5.0)
        handles.clear()

    request.addfinalizer(finalize)

    def _register(handle: process_utils.ManagedProcess) -> process_utils.ManagedProcess:
        handles.append(handle)
        return handle

    return _register


def _allocate_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def test_gateway_local_cluster_end_to_end(
    disable_dask: None,
    register_process: Callable[[process_utils.ManagedProcess], process_utils.ManagedProcess],
) -> None:
    host = "127.0.0.1"
    gateway_port = _allocate_port(host)
    mock_port = _allocate_port(host)
    gateway_base = f"http://{host}:{gateway_port}"
    mock_base = f"http://{host}:{mock_port}"

    def mock_ready(*, timeout: float, **_: object) -> None:
        process_utils.wait_for_port(host, mock_port, timeout=timeout)
        process_utils.poll_endpoint(f"{mock_base}/", timeout=timeout)

    def gateway_ready(*, timeout: float, **_: object) -> None:
        process_utils.wait_for_port(host, gateway_port, timeout=timeout)
        process_utils.poll_endpoint(f"{gateway_base}/api/health", timeout=timeout)

    register_process(
        process_utils.start_mock_server(
            run_mock_ollama,
            kwargs={"port": mock_port},
            name="mock_ollama",
            readiness_check=mock_ready,
            readiness_timeout=180.0,
            daemon=False,
        )
    )

    register_process(
        process_utils.start_mock_server(
            run_gateway,
            kwargs={
                "gateway_port": gateway_port,
                "mock_port": mock_port,
                "enable_batch_processing": False,
                "ray_workers": 0,
                "dask_workers": 0,
            },
            name="sollol_gateway",
            readiness_check=gateway_ready,
            readiness_timeout=240.0,
            daemon=False,
        )
    )

    health = client.fetch_health(gateway_base)
    chat = client.run_chat(gateway_base)
    generate = client.run_generate(gateway_base)
    embed = client.run_embed(gateway_base)

    assert health.get("service") == "SOLLOL"
    assert "status" in health

    assert chat.get("model") == "llama3.2"
    assert chat.get("done") is True
    message = chat.get("message")
    assert isinstance(message, dict)
    assert message.get("role") == "assistant"
    assert isinstance(message.get("content"), str) and message["content"].strip()

    assert generate.get("model") == "llama3.2"
    assert generate.get("done") is True
    response_text = generate.get("response")
    assert isinstance(response_text, str) and response_text.strip()

    embed_model = embed.get("model")
    assert embed_model in {"nomic-embed-text", "mxbai-embed-large"}
    vector = embed.get("embedding")
    if not vector and isinstance(embed.get("embeddings"), list) and embed["embeddings"]:
        vector = embed["embeddings"][0]
    assert isinstance(vector, list) and len(vector) > 0
    assert all(isinstance(value, (int, float)) for value in vector[: min(5, len(vector))])

    usage = chat.get("usage")
    if isinstance(usage, dict):
        total_tokens = usage.get("total_tokens")
        if total_tokens is not None:
            assert isinstance(total_tokens, int) and total_tokens >= 0

    usage = generate.get("usage")
    if isinstance(usage, dict):
        total_tokens = usage.get("total_tokens")
        if total_tokens is not None:
            assert isinstance(total_tokens, int) and total_tokens >= 0
