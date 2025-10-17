"""Helpers to orchestrate a SOLLOL gateway in the local cluster example."""

import os
from typing import Optional

from sollol import SOLLOL

from .process_utils import ManagedProcess, start_mock_server, wait_for_port


DEFAULT_GATEWAY_PORT = 18000
DEFAULT_MOCK_OLLAMA_PORT = 11434
DEFAULT_RAY_WORKERS = 2
DEFAULT_DASK_WORKERS = 1


def _bool_from_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "t", "yes", "y", "on"}


def run_gateway(
    *,
    gateway_port: Optional[int] = None,
    mock_port: Optional[int] = None,
    enable_batch_processing: Optional[bool] = None,
    ray_workers: Optional[int] = None,
    dask_workers: Optional[int] = None,
) -> None:
    """Start a SOLLOL gateway that targets the local mock Ollama service."""

    resolved_gateway_port = gateway_port if gateway_port is not None else int(
        os.getenv("SOLLOL_GATEWAY_PORT", DEFAULT_GATEWAY_PORT)
    )
    resolved_mock_port = mock_port if mock_port is not None else int(
        os.getenv("MOCK_OLLAMA_PORT", DEFAULT_MOCK_OLLAMA_PORT)
    )
    resolved_enable_batch = (
        enable_batch_processing
        if enable_batch_processing is not None
        else _bool_from_env("SOLLOL_ENABLE_BATCH_PROCESSING", True)
    )
    resolved_ray_workers = ray_workers if ray_workers is not None else int(
        os.getenv("SOLLOL_RAY_WORKERS", DEFAULT_RAY_WORKERS)
    )
    resolved_dask_workers = dask_workers if dask_workers is not None else int(
        os.getenv("SOLLOL_DASK_WORKERS", DEFAULT_DASK_WORKERS)
    )

    gateway = SOLLOL(
        port=resolved_gateway_port,
        ray_workers=resolved_ray_workers,
        dask_workers=resolved_dask_workers,
        enable_batch_processing=resolved_enable_batch,
        ollama_nodes=[{"host": "127.0.0.1", "port": resolved_mock_port}],
    )

    gateway.start(blocking=True)


def launch_gateway(
    *,
    gateway_port: Optional[int] = None,
    mock_port: Optional[int] = None,
    enable_batch_processing: Optional[bool] = None,
    ray_workers: Optional[int] = None,
    dask_workers: Optional[int] = None,
    readiness_timeout: float = 30.0,
) -> ManagedProcess:
    """Spawn the SOLLOL gateway in a background process for tests and demos."""

    resolved_gateway_port = gateway_port if gateway_port is not None else int(
        os.getenv("SOLLOL_GATEWAY_PORT", DEFAULT_GATEWAY_PORT)
    )

    def _readiness_check(*, timeout: float, **_kwargs) -> None:
        wait_for_port("127.0.0.1", resolved_gateway_port, timeout=timeout)

    return start_mock_server(
        run_gateway,
        kwargs={
            "gateway_port": gateway_port,
            "mock_port": mock_port,
            "enable_batch_processing": enable_batch_processing,
            "ray_workers": ray_workers,
            "dask_workers": dask_workers,
        },
        name="sollol_gateway",
        readiness_check=_readiness_check,
        readiness_timeout=readiness_timeout,
    )
