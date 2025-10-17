import os
import socket
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_DIR = _REPO_ROOT / "src"

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

existing_pythonpath = os.environ.get("PYTHONPATH", "")
if str(_SRC_DIR) not in existing_pythonpath.split(os.pathsep):
    updated = f"{_SRC_DIR}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(_SRC_DIR)
    os.environ["PYTHONPATH"] = updated

from examples.gateway_local_cluster import client
from examples.gateway_local_cluster.gateway_process import run_gateway
from examples.gateway_local_cluster.mock_ollama import run as run_mock_ollama
from examples.gateway_local_cluster import process_utils
from sollol.pool import OllamaPool


@pytest.fixture(scope="module")
def disable_dask():
    original = OllamaPool._init_dask_client
    OllamaPool._init_dask_client = lambda self, dask_address=None: None
    try:
        yield
    finally:
        OllamaPool._init_dask_client = original


def _allocate_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def test_gateway_local_cluster_end_to_end(disable_dask):
    host = "127.0.0.1"
    gateway_port = _allocate_port(host)
    mock_port = _allocate_port(host)
    gateway_base = f"http://{host}:{gateway_port}"
    mock_base = f"http://{host}:{mock_port}"

    handles: list[process_utils.ManagedProcess] = []

    def mock_ready(**kwargs):
        timeout = kwargs.get("timeout", 60.0)
        process_utils.wait_for_port(host, mock_port, timeout=timeout)
        process_utils.poll_endpoint(f"{mock_base}/api/health", timeout=timeout)

    def gateway_ready(**kwargs):
        timeout = kwargs.get("timeout", 90.0)
        process_utils.wait_for_port(host, gateway_port, timeout=timeout)
        process_utils.poll_endpoint(f"{gateway_base}/api/health", timeout=timeout)

    try:
        mock_handle = process_utils.start_mock_server(
            run_mock_ollama,
            kwargs={"argv": ["--host", host, "--port", str(mock_port)]},
            name="mock_ollama",
            readiness_check=mock_ready,
            readiness_timeout=60.0,
            daemon=False,
        )
        handles.append(mock_handle)

        gateway_handle = process_utils.start_mock_server(
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
            readiness_timeout=90.0,
            daemon=False,
        )
        handles.append(gateway_handle)

        health = client.fetch_health(gateway_base)
        chat = client.run_chat(gateway_base)
        generate = client.run_generate(gateway_base)
        embed = client.run_embed(gateway_base)
    finally:
        for handle in reversed(handles):
            with handle:
                pass

    assert health.get("service") == "SOLLOL"

    assert chat.get("model") == "llama3.2"
    assert isinstance(chat.get("created_at"), str)
    assert chat.get("done") is True
    message = chat.get("message")
    assert isinstance(message, dict)
    assert message.get("role") == "assistant"
    assert isinstance(message.get("content"), str) and message["content"].strip()
    usage = chat.get("usage")
    if isinstance(usage, dict):
        total_tokens = usage.get("total_tokens")
        if total_tokens is not None:
            assert isinstance(total_tokens, int) and total_tokens >= 0

    assert generate.get("model") == "llama3.2"
    assert isinstance(generate.get("created_at"), str)
    assert generate.get("done") is True
    response_text = generate.get("response")
    assert isinstance(response_text, str) and response_text.strip()
    usage = generate.get("usage")
    if isinstance(usage, dict):
        total_tokens = usage.get("total_tokens")
        if total_tokens is not None:
            assert isinstance(total_tokens, int) and total_tokens >= 0

    assert embed.get("model") == "nomic-embed-text"
    created_at = embed.get("created_at")
    if created_at is not None:
        assert isinstance(created_at, str)
    vector = embed.get("embedding")
    if vector is None and isinstance(embed.get("embeddings"), list):
        embeddings_list = embed["embeddings"]
        if embeddings_list:
            vector = embeddings_list[0]
    assert isinstance(vector, list) and len(vector) > 0
    assert all(isinstance(value, (int, float)) for value in vector[: min(5, len(vector))])
