"""Entry point for the gateway local cluster demonstration."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from . import client
from .gateway_process import (
    DEFAULT_GATEWAY_PORT,
    DEFAULT_MOCK_OLLAMA_PORT,
    launch_gateway,
)
from .mock_ollama import run as run_mock_ollama
from .process_utils import poll_endpoint, start_mock_server, wait_for_port


_DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class DemoResult:
    """Container holding payloads used for the demo and the gateway responses."""

    gateway_base_url: str
    mock_base_url: str
    payloads: Mapping[str, Mapping[str, Any]]
    responses: Mapping[str, Mapping[str, Any]]

    def formatted(self) -> str:
        """Return a human readable representation of the captured responses."""

        return client.format_results(self.responses)


def _load_payloads() -> dict[str, Mapping[str, Any]]:
    payloads: dict[str, Mapping[str, Any]] = {}
    for name in ("chat", "generate", "embed"):
        file_path = _DATA_DIR / f"{name}_request.json"
        with file_path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        payloads[name] = data
    return payloads


def run_demo(
    *,
    gateway_port: int = DEFAULT_GATEWAY_PORT,
    mock_port: int = DEFAULT_MOCK_OLLAMA_PORT,
    host: str = "127.0.0.1",
    readiness_timeout: float = 30.0,
) -> DemoResult:
    """Run the mock Ollama + SOLLOL gateway demo and return captured responses."""

    payloads = _load_payloads()
    mock_base_url = f"http://{host}:{mock_port}"
    gateway_base_url = f"http://{host}:{gateway_port}"

    def _mock_readiness_check(*, timeout: float, **_kwargs: Any) -> None:
        wait_for_port(host, mock_port, timeout=timeout)
        poll_endpoint(f"{mock_base_url}/api/health", timeout=timeout)

    with start_mock_server(
        run_mock_ollama,
        kwargs={"argv": ["--host", host, "--port", str(mock_port)]},
        name="mock_ollama",
        readiness_check=_mock_readiness_check,
        readiness_timeout=readiness_timeout,
    ):
        with launch_gateway(
            gateway_port=gateway_port,
            mock_port=mock_port,
            readiness_timeout=readiness_timeout,
        ):
            poll_endpoint(f"{gateway_base_url}/api/health")
            responses = client.run_full_sequence(gateway_base_url)

    return DemoResult(
        gateway_base_url=gateway_base_url,
        mock_base_url=mock_base_url,
        payloads=payloads,
        responses=responses,
    )


if __name__ == "__main__":
    result = run_demo()
    print(result.formatted())
