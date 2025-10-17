"""Entry point for the gateway local cluster demonstration."""
from __future__ import annotations

import json
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from . import client
from .gateway_process import (
    DEFAULT_GATEWAY_PORT,
    DEFAULT_MOCK_OLLAMA_PORT,
    launch_gateway,
)
from .model_setup import ensure_model
from .mock_ollama import run as run_mock_ollama
from .process_utils import (
    format_ollama_nodes,
    poll_endpoint,
    start_mock_server,
    start_ollama_runtime,
    wait_for_port,
)


_DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class DemoResult:
    """Container holding payloads used for the demo and the gateway responses."""

    gateway_base_url: str
    ollama_nodes: tuple[dict[str, Any], ...]
    payloads: Mapping[str, Mapping[str, Any]]
    responses: Mapping[str, Mapping[str, Any]]

    @property
    def ollama_base_urls(self) -> tuple[str, ...]:
        """Return the base URLs for all Ollama backends used in the demo."""

        return tuple(f"http://{node['host']}:{node['port']}" for node in self.ollama_nodes)

    @property
    def mock_base_url(self) -> str:
        """Backward compatible access to the first configured Ollama backend."""

        urls = self.ollama_base_urls
        if not urls:
            raise AttributeError("No Ollama backends configured for this demo run")
        return urls[0]

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
    ollama_runtimes: Sequence[Mapping[str, Any]] | None = None,
    gateway_ollama_nodes: Sequence[Mapping[str, Any]] | None = None,
    use_mock_backend: bool = True,
) -> DemoResult:
    """Run the mock Ollama + SOLLOL gateway demo and return captured responses."""

    payloads = _load_payloads()
    gateway_base_url = f"http://{host}:{gateway_port}"

    if not use_mock_backend and not ollama_runtimes and not gateway_ollama_nodes:
        raise ValueError(
            "No Ollama backends configured; enable the mock backend or provide runtime/node definitions."
        )

    with ExitStack() as stack:
        started_nodes: list[dict[str, Any]] = []

        if use_mock_backend:
            mock_base_url = f"http://{host}:{mock_port}"

            def _mock_readiness_check(*, timeout: float, **_kwargs: Any) -> None:
                wait_for_port(host, mock_port, timeout=timeout)
                poll_endpoint(f"{mock_base_url}/api/health", timeout=timeout)

            mock_handle = start_mock_server(
                run_mock_ollama,
                kwargs={"argv": ["--host", host, "--port", str(mock_port)]},
                name="mock_ollama",
                readiness_check=_mock_readiness_check,
                readiness_timeout=readiness_timeout,
            )
            stack.enter_context(mock_handle)
            started_nodes.append({"host": host, "port": int(mock_port)})

        runtime_entries: Sequence[Mapping[str, Any]] = ollama_runtimes or ()
        for index, runtime_config in enumerate(runtime_entries):
            config = dict(runtime_config)

            ensure_keys = ("model", "models", "ensure_model", "ensure_models")
            ensure_list: list[str] = []
            for key in ensure_keys:
                value = config.pop(key, None)
                if value is None:
                    continue
                if isinstance(value, str):
                    ensure_list.append(value)
                elif isinstance(value, Mapping):
                    ensure_list.extend(str(item) for item in value.values() if item)
                elif isinstance(value, Iterable) and not isinstance(value, (bytes, str)):
                    ensure_list.extend(str(item) for item in value if item)
                else:
                    ensure_list.append(str(value))

            model_timeout = config.pop("model_timeout", None)
            if model_timeout is None:
                model_timeout = config.pop("ensure_timeout", None)
            if model_timeout is None:
                model_timeout = config.pop("ensure_models_timeout", None)
            ensure_timeout = float(model_timeout) if model_timeout is not None else 300.0

            seen_models: set[str] = set()
            for name in ensure_list:
                model_name = str(name).strip()
                if not model_name or model_name in seen_models:
                    continue
                ensure_model(model_name, timeout=ensure_timeout)
                seen_models.add(model_name)

            default_port = mock_port + index if index else mock_port
            host_value = str(config.get("host", host))
            port_value = int(config.get("port", default_port))
            config.setdefault("host", host_value)
            config.setdefault("port", port_value)

            runtime_readiness = config.pop("readiness_timeout", None)
            runtime_handle = start_ollama_runtime(
                config,
                readiness_timeout=float(runtime_readiness)
                if runtime_readiness is not None
                else readiness_timeout,
            )
            stack.enter_context(runtime_handle)
            started_nodes.append({"host": host_value, "port": port_value})

        combined_nodes: list[Mapping[str, Any]] = []
        if gateway_ollama_nodes:
            combined_nodes.extend(gateway_ollama_nodes)
        combined_nodes.extend(started_nodes)

        formatted_nodes = format_ollama_nodes(
            combined_nodes or None,
            default_host=host,
            default_port=mock_port,
        )

        unique_nodes: list[dict[str, Any]] = []
        seen_pairs: set[tuple[str, int]] = set()
        for node in formatted_nodes:
            resolved_host = str(node.get("host", host))
            resolved_port = int(node.get("port", mock_port))
            marker = (resolved_host, resolved_port)
            if marker in seen_pairs:
                continue
            seen_pairs.add(marker)
            unique_nodes.append({"host": resolved_host, "port": resolved_port})

        gateway_handle = launch_gateway(
            gateway_port=gateway_port,
            mock_port=mock_port,
            readiness_timeout=readiness_timeout,
            ollama_nodes=unique_nodes,
        )
        stack.enter_context(gateway_handle)

        poll_endpoint(f"{gateway_base_url}/api/health")
        responses = client.run_full_sequence(gateway_base_url)

    return DemoResult(
        gateway_base_url=gateway_base_url,
        ollama_nodes=tuple(unique_nodes),
        payloads=payloads,
        responses=responses,
    )


if __name__ == "__main__":
    result = run_demo()
    print(result.formatted())
