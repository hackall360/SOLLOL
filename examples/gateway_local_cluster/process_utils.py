"""Utilities for managing background processes in example clusters.

This module provides lightweight helpers that make it easier to spin up
background processes for integration tests or demo scripts while ensuring that
those processes are cleaned up automatically.  The helpers expose a simple
handle that mirrors the APIs of ``multiprocessing.Process`` and
``subprocess.Popen`` with ``terminate`` and ``wait`` methods that can be used in
``with`` statements.
"""
from __future__ import annotations

import contextlib
import socket
import subprocess
import time
from dataclasses import dataclass
from multiprocessing import Process
from typing import Any, Callable, Iterable, Mapping, Optional, Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen


@dataclass
class ManagedProcess:
    """Wrapper that normalises process management across APIs.

    The handle implements ``terminate``/``wait`` helpers and can be used as a
    context manager.  It knows how to work with both ``subprocess.Popen``
    instances and ``multiprocessing.Process`` objects.
    """

    process: Any
    name: str

    def terminate(self, timeout: float = 5.0) -> None:
        """Terminate the process and ensure it exits within ``timeout`` seconds."""
        if isinstance(self.process, subprocess.Popen):
            with contextlib.suppress(ProcessLookupError):
                self.process.terminate()
            if timeout is not None:
                try:
                    self.process.wait(timeout)
                except subprocess.TimeoutExpired:
                    with contextlib.suppress(ProcessLookupError):
                        self.process.kill()
                    self.process.wait()
        else:
            # multiprocessing.Process implements terminate/kill/join semantics.
            with contextlib.suppress(ProcessLookupError):
                self.process.terminate()
            if timeout is not None:
                self.process.join(timeout)
                if self.process.is_alive():
                    with contextlib.suppress(ProcessLookupError):
                        self.process.kill()
                    self.process.join()

    def wait(self, timeout: Optional[float] = None) -> Optional[int]:
        """Wait for the process to finish and return the exit code."""
        if isinstance(self.process, subprocess.Popen):
            return self.process.wait(timeout)

        self.process.join(timeout)
        return getattr(self.process, "exitcode", None)

    def is_running(self) -> bool:
        if isinstance(self.process, subprocess.Popen):
            return self.process.poll() is None
        return self.process.is_alive()

    @property
    def pid(self) -> Optional[int]:
        if isinstance(self.process, subprocess.Popen):
            return self.process.pid
        return getattr(self.process, "pid", None)

    def __enter__(self) -> "ManagedProcess":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.terminate()


def _invoke_readiness_check(
    readiness_check: Optional[Callable[..., Any]],
    *,
    timeout: float,
    handle: ManagedProcess,
) -> None:
    if not readiness_check:
        return

    try:
        readiness_check(timeout=timeout, handle=handle)
        return
    except TypeError:
        pass

    try:
        readiness_check(timeout=timeout)
        return
    except TypeError:
        pass

    readiness_check()


def start_background_process(
    target: Callable[..., Any],
    *,
    args: Optional[Iterable[Any]] = None,
    kwargs: Optional[Mapping[str, Any]] = None,
    name: str = "background_process",
    readiness_check: Optional[Callable[..., Any]] = None,
    readiness_timeout: float = 30.0,
    daemon: bool = True,
) -> ManagedProcess:
    """Launch a callable in a ``multiprocessing.Process`` and manage its life-cycle."""

    process = Process(target=target, args=tuple(args or ()), kwargs=dict(kwargs or {}), daemon=daemon)
    process.start()
    handle = ManagedProcess(process=process, name=name)
    _invoke_readiness_check(readiness_check, timeout=readiness_timeout, handle=handle)
    return handle


def start_mock_server(
    target: Callable[..., Any],
    *,
    args: Optional[Iterable[Any]] = None,
    kwargs: Optional[Mapping[str, Any]] = None,
    name: str = "mock_server",
    readiness_check: Optional[Callable[..., Any]] = None,
    readiness_timeout: float = 30.0,
    daemon: bool = True,
) -> ManagedProcess:
    """Backward compatible wrapper for :func:`start_background_process`."""

    return start_background_process(
        target,
        args=args,
        kwargs=kwargs,
        name=name,
        readiness_check=readiness_check,
        readiness_timeout=readiness_timeout,
        daemon=daemon,
    )


def start_subprocess(
    popen: subprocess.Popen,
    *,
    name: str,
    readiness_check: Optional[Callable[..., Any]] = None,
    readiness_timeout: float = 30.0,
) -> ManagedProcess:
    """Wrap a :class:`subprocess.Popen` in :class:`ManagedProcess` and run readiness checks."""

    handle = ManagedProcess(process=popen, name=name)
    try:
        _invoke_readiness_check(readiness_check, timeout=readiness_timeout, handle=handle)
    except Exception:
        handle.terminate()
        raise
    return handle


def start_sollol_gateway(
    command_factory: Callable[..., Sequence[str]],
    *,
    factory_kwargs: Optional[Mapping[str, Any]] = None,
    popen_kwargs: Optional[Mapping[str, Any]] = None,
    name: str = "sollol_gateway",
    readiness_check: Optional[Callable[..., Any]] = None,
    readiness_timeout: float = 30.0,
) -> ManagedProcess:
    """Launch the SOLLOL gateway via ``subprocess.Popen`` and wrap it in ``ManagedProcess``."""
    command = command_factory(**(factory_kwargs or {}))
    if isinstance(command, str) or not isinstance(command, Sequence):
        raise TypeError("command_factory must return a sequence of arguments suitable for subprocess.Popen")

    popen = subprocess.Popen(command, **(popen_kwargs or {}))
    return start_subprocess(
        popen,
        name=name,
        readiness_check=readiness_check,
        readiness_timeout=readiness_timeout,
    )


def start_ollama_runtime(
    runtime_config: Mapping[str, Any],
    *,
    readiness_timeout: Optional[float] = None,
) -> ManagedProcess:
    """Launch a real Ollama runtime and wrap it in :class:`ManagedProcess`."""

    from .ollama_runtime import ollama_runtime

    config = dict(runtime_config)
    host = config.pop("host", "127.0.0.1")
    port = int(config.pop("port", 11434))
    env = config.pop("env", None)
    poll_interval = float(config.pop("poll_interval", 0.5))
    extra_args = config.pop("extra_args", None)
    name = config.pop("name", f"ollama:{host}:{port}")
    cm_readiness_timeout = config.pop("readiness_timeout", None)

    if readiness_timeout is None:
        readiness_timeout = float(cm_readiness_timeout) if cm_readiness_timeout is not None else 60.0
    elif cm_readiness_timeout is not None:
        raise ValueError("readiness_timeout provided both in runtime_config and as a keyword argument")

    if config:
        unknown = ", ".join(sorted(config))
        raise TypeError(f"Unsupported runtime configuration keys: {unknown}")

    runtime_cm = ollama_runtime(
        host=host,
        port=port,
        env=env,
        readiness_timeout=readiness_timeout,
        poll_interval=poll_interval,
        extra_args=list(extra_args) if extra_args is not None else None,
    )

    popen = runtime_cm.__enter__()
    context_closed = False

    def _close_context() -> None:
        nonlocal context_closed
        if context_closed:
            return
        context_closed = True
        runtime_cm.__exit__(None, None, None)

    handle = start_subprocess(
        popen,
        name=name,
        readiness_timeout=readiness_timeout,
    )

    original_terminate = handle.terminate

    def terminate(timeout: float = 5.0) -> None:  # type: ignore[override]
        try:
            original_terminate(timeout=timeout)
        finally:
            _close_context()

    handle.terminate = terminate  # type: ignore[assignment]

    original_wait = handle.wait

    def wait(timeout: Optional[float] = None) -> Optional[int]:  # type: ignore[override]
        try:
            return original_wait(timeout=timeout)
        finally:
            if timeout is None or not handle.is_running():
                _close_context()

    handle.wait = wait  # type: ignore[assignment]

    return handle


def format_ollama_nodes(
    definitions: Optional[Sequence[Any]],
    *,
    default_host: str = "127.0.0.1",
    default_port: int = 11434,
) -> list[dict[str, Any]]:
    """Convert runtime definitions into dictionaries suitable for SOLLOL."""

    if definitions is None:
        return [{"host": default_host, "port": int(default_port)}]

    formatted: list[dict[str, Any]] = []
    for definition in definitions:
        host: Any = None
        port: Any = None

        if isinstance(definition, Mapping):
            host = definition.get("host")
            port = definition.get("port")
        elif isinstance(definition, Sequence) and not isinstance(definition, (str, bytes)):
            if len(definition) >= 2:
                host, port = definition[0], definition[1]
        else:
            host = getattr(definition, "host", None)
            port = getattr(definition, "port", None)

        if host is None or port is None:
            raise ValueError(
                "Ollama node definitions must provide host and port information"
            )

        formatted.append({"host": str(host), "port": int(port)})

    return formatted


def wait_for_port(host: str, port: int, *, timeout: float = 30.0, interval: float = 0.1) -> None:
    """Poll ``host:port`` until a TCP connection succeeds or the timeout elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(interval)
            try:
                sock.connect((host, port))
            except OSError:
                time.sleep(interval)
                continue
            return
    raise TimeoutError(f"Timed out waiting for port {host}:{port}")


def poll_endpoint(
    url: str,
    *,
    timeout: float = 30.0,
    interval: float = 0.5,
    expected_status: Iterable[int] = (200,),
    headers: Optional[Mapping[str, str]] = None,
) -> None:
    """Poll an HTTP endpoint until it returns a successful response.

    ``expected_status`` can be any iterable containing acceptable status codes.
    """
    deadline = time.monotonic() + timeout
    expected = tuple(expected_status)
    while time.monotonic() < deadline:
        request = Request(url, headers=dict(headers or {}))
        try:
            with urlopen(request, timeout=interval) as response:
                if response.getcode() in expected:
                    return
        except URLError:
            pass
        time.sleep(interval)
    raise TimeoutError(f"Timed out polling endpoint {url}")
