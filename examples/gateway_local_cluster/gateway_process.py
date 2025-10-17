"""Helpers to orchestrate a SOLLOL gateway in the local cluster example."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from sollol import SOLLOL

from .process_utils import (
    ManagedProcess,
    format_ollama_nodes,
    start_mock_server,
    start_sollol_gateway,
    wait_for_port,
)


DEFAULT_GATEWAY_PORT = 18000
DEFAULT_MOCK_OLLAMA_PORT = 11434
DEFAULT_RAY_WORKERS = 2
DEFAULT_DASK_WORKERS = 1


def _bool_from_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "t", "yes", "y", "on"}


@dataclass(frozen=True)
class _GatewayLaunchConfig:
    port: int
    ray_workers: int
    dask_workers: int
    enable_batch_processing: bool
    ollama_nodes: list[dict[str, Any]]


def _resolve_gateway_config(
    *,
    gateway_port: Optional[int],
    mock_port: Optional[int],
    enable_batch_processing: Optional[bool],
    ray_workers: Optional[int],
    dask_workers: Optional[int],
    enable_ray: Optional[bool],
    enable_dask: Optional[bool],
    ollama_nodes: Optional[Sequence[Mapping[str, Any]]],
) -> _GatewayLaunchConfig:
    resolved_gateway_port = gateway_port if gateway_port is not None else int(
        os.getenv("SOLLOL_GATEWAY_PORT", DEFAULT_GATEWAY_PORT)
    )
    resolved_mock_port = mock_port if mock_port is not None else int(
        os.getenv("MOCK_OLLAMA_PORT", DEFAULT_MOCK_OLLAMA_PORT)
    )

    ray_enabled = enable_ray if enable_ray is not None else _bool_from_env("SOLLOL_ENABLE_RAY", True)
    dask_enabled = enable_dask if enable_dask is not None else _bool_from_env("SOLLOL_ENABLE_DASK", True)

    resolved_ray_workers = ray_workers if ray_workers is not None else int(
        os.getenv("SOLLOL_RAY_WORKERS", DEFAULT_RAY_WORKERS)
    )
    if not ray_enabled:
        resolved_ray_workers = 0

    resolved_dask_workers = dask_workers if dask_workers is not None else int(
        os.getenv("SOLLOL_DASK_WORKERS", DEFAULT_DASK_WORKERS)
    )
    if not dask_enabled:
        resolved_dask_workers = 0

    resolved_enable_batch = (
        enable_batch_processing
        if enable_batch_processing is not None
        else _bool_from_env("SOLLOL_ENABLE_BATCH_PROCESSING", True)
    )
    if not dask_enabled or resolved_dask_workers <= 0:
        resolved_enable_batch = bool(resolved_enable_batch and resolved_dask_workers > 0)

    resolved_nodes = format_ollama_nodes(
        ollama_nodes,
        default_host="127.0.0.1",
        default_port=resolved_mock_port,
    )

    return _GatewayLaunchConfig(
        port=resolved_gateway_port,
        ray_workers=resolved_ray_workers,
        dask_workers=resolved_dask_workers,
        enable_batch_processing=resolved_enable_batch,
        ollama_nodes=resolved_nodes,
    )


def run_gateway(
    *,
    gateway_port: Optional[int] = None,
    mock_port: Optional[int] = None,
    enable_batch_processing: Optional[bool] = None,
    ray_workers: Optional[int] = None,
    dask_workers: Optional[int] = None,
    enable_ray: Optional[bool] = None,
    enable_dask: Optional[bool] = None,
    ollama_nodes: Optional[Sequence[Mapping[str, Any]]] = None,
) -> None:
    """Start a SOLLOL gateway that targets the configured Ollama services."""

    config = _resolve_gateway_config(
        gateway_port=gateway_port,
        mock_port=mock_port,
        enable_batch_processing=enable_batch_processing,
        ray_workers=ray_workers,
        dask_workers=dask_workers,
        enable_ray=enable_ray,
        enable_dask=enable_dask,
        ollama_nodes=ollama_nodes,
    )

    gateway = SOLLOL(
        port=config.port,
        ray_workers=config.ray_workers,
        dask_workers=config.dask_workers,
        enable_batch_processing=config.enable_batch_processing,
        ollama_nodes=config.ollama_nodes,
    )

    gateway.start(blocking=True)


def launch_gateway(
    *,
    gateway_port: Optional[int] = None,
    mock_port: Optional[int] = None,
    enable_batch_processing: Optional[bool] = None,
    ray_workers: Optional[int] = None,
    dask_workers: Optional[int] = None,
    enable_ray: Optional[bool] = None,
    enable_dask: Optional[bool] = None,
    ollama_nodes: Optional[Sequence[Mapping[str, Any]]] = None,
    readiness_timeout: float = 30.0,
) -> ManagedProcess:
    """Spawn the SOLLOL gateway in a background process for tests and demos."""

    config = _resolve_gateway_config(
        gateway_port=gateway_port,
        mock_port=mock_port,
        enable_batch_processing=enable_batch_processing,
        ray_workers=ray_workers,
        dask_workers=dask_workers,
        enable_ray=enable_ray,
        enable_dask=enable_dask,
        ollama_nodes=ollama_nodes,
    )

    def _readiness_check(*, timeout: float, **_kwargs) -> None:
        wait_for_port("127.0.0.1", config.port, timeout=timeout)

    return start_mock_server(
        run_gateway,
        kwargs={
            "gateway_port": gateway_port,
            "mock_port": mock_port,
            "enable_batch_processing": enable_batch_processing,
            "ray_workers": ray_workers,
            "dask_workers": dask_workers,
            "enable_ray": enable_ray,
            "enable_dask": enable_dask,
            "ollama_nodes": ollama_nodes,
        },
        name="sollol_gateway",
        readiness_check=_readiness_check,
        readiness_timeout=readiness_timeout,
    )


def launch_gateway_subprocess(
    *,
    gateway_port: Optional[int] = None,
    mock_port: Optional[int] = None,
    enable_batch_processing: Optional[bool] = None,
    ray_workers: Optional[int] = None,
    dask_workers: Optional[int] = None,
    enable_ray: Optional[bool] = None,
    enable_dask: Optional[bool] = None,
    ollama_nodes: Optional[Sequence[Mapping[str, Any]]] = None,
    readiness_timeout: float = 30.0,
    python_executable: Optional[str] = None,
    extra_cli_args: Optional[Sequence[str]] = None,
    env: Optional[Mapping[str, str]] = None,
    cwd: Optional[str] = None,
) -> ManagedProcess:
    """Launch the SOLLOL gateway via subprocess for Ray compatibility."""

    config = _resolve_gateway_config(
        gateway_port=gateway_port,
        mock_port=mock_port,
        enable_batch_processing=enable_batch_processing,
        ray_workers=ray_workers,
        dask_workers=dask_workers,
        enable_ray=enable_ray,
        enable_dask=enable_dask,
        ollama_nodes=ollama_nodes,
    )

    executable = python_executable or sys.executable

    def _command_factory() -> Sequence[str]:
        command: list[str] = [executable, "-m", "sollol.cli", "up", "--port", str(config.port)]
        command.extend(["--ray-workers", str(config.ray_workers)])
        command.extend(["--dask-workers", str(config.dask_workers)])
        if not config.enable_batch_processing:
            command.append("--no-batch-processing")
        if config.ollama_nodes:
            nodes_arg = ",".join(
                f"{node['host']}:{node['port']}" for node in config.ollama_nodes
            )
            command.extend(["--ollama-nodes", nodes_arg])
        if extra_cli_args:
            command.extend(extra_cli_args)
        return command

    popen_kwargs: dict[str, Any] = {}
    if env is not None:
        popen_kwargs["env"] = env
    if cwd is not None:
        popen_kwargs["cwd"] = cwd

    def _readiness_check(*, timeout: float, **_kwargs) -> None:
        wait_for_port("127.0.0.1", config.port, timeout=timeout)

    return start_sollol_gateway(
        _command_factory,
        name="sollol_gateway_subprocess",
        readiness_check=_readiness_check,
        readiness_timeout=readiness_timeout,
        popen_kwargs=popen_kwargs or None,
    )
