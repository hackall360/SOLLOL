"""Utilities for launching local Ollama instances for the gateway cluster demos."""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterator, Mapping, MutableMapping, Optional


@dataclass
class OllamaProcessHandle:
    """Simple wrapper exposing lifecycle helpers for a spawned Ollama process."""

    process: subprocess.Popen[bytes]
    host: str
    port: int

    def terminate(self) -> None:
        """Terminate the underlying Ollama process if it is still running."""

        if self.process.poll() is None:
            self.process.terminate()

    def wait(self, timeout: Optional[float] = None) -> int:
        """Block until the process exits and return its exit code."""

        return self.process.wait(timeout=timeout)


def _prepare_environment(
    host: str,
    port: int,
    env: Optional[Mapping[str, str]] = None,
) -> MutableMapping[str, str]:
    merged_env: MutableMapping[str, str] = os.environ.copy()
    if env:
        merged_env.update(env)
    merged_env.setdefault("OLLAMA_HOST", f"{host}:{port}")
    return merged_env


def _wait_for_readiness(
    host: str,
    port: int,
    timeout: float,
    poll_interval: float,
    process: subprocess.Popen[bytes],
) -> None:
    """Block until the Ollama HTTP health endpoint responds or timeout expires."""

    deadline = time.time() + timeout
    url = f"http://{host}:{port}/api/health"

    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                "Ollama process exited before it became ready; "
                f"return code {process.returncode}"
            )
        try:
            with urllib.request.urlopen(url, timeout=poll_interval) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(poll_interval)
            continue

    raise TimeoutError(
        "Timed out waiting for Ollama readiness check to succeed at "
        f"{url}"
    )


@contextlib.contextmanager
def run_ollama(
    host: str = "127.0.0.1",
    port: int = 11434,
    env: Optional[Mapping[str, str]] = None,
    readiness_timeout: float = 60.0,
    poll_interval: float = 0.5,
    extra_args: Optional[list[str]] = None,
) -> Iterator[OllamaProcessHandle]:
    """Launch ``ollama serve`` and yield a handle once the instance is reachable."""

    binary = shutil.which("ollama")
    if not binary:
        raise FileNotFoundError(
            "Unable to locate the 'ollama' binary. Please install Ollama or "
            "ensure it is on PATH."
        )

    command = [binary, "serve"]
    if extra_args:
        command.extend(extra_args)

    full_env = _prepare_environment(host, port, env)

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=full_env,
    )
    handle = OllamaProcessHandle(process=process, host=host, port=port)

    try:
        _wait_for_readiness(host, port, readiness_timeout, poll_interval, process)
        yield handle
    finally:
        handle.terminate()
        try:
            handle.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            handle.wait()
