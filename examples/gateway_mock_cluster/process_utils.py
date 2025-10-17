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
    """Launch a callable in a ``multiprocessing.Process`` and manage its life-cycle."""
    process = Process(target=target, args=tuple(args or ()), kwargs=dict(kwargs or {}), daemon=daemon)
    process.start()
    handle = ManagedProcess(process=process, name=name)
    _invoke_readiness_check(readiness_check, timeout=readiness_timeout, handle=handle)
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
    handle = ManagedProcess(process=popen, name=name)
    _invoke_readiness_check(readiness_check, timeout=readiness_timeout, handle=handle)
    return handle


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
