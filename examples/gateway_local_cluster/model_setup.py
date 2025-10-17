"""Helpers for ensuring required Ollama models are available locally."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Iterable, Sequence


class ModelSetupError(RuntimeError):
    """Raised when the Ollama CLI is unavailable or model management fails."""


def _resolve_ollama_binary() -> str:
    binary = shutil.which("ollama")
    if not binary:
        raise ModelSetupError(
            "The 'ollama' command could not be found. Install Ollama and ensure the "
            "CLI is on your PATH before running this example."
        )
    return binary


def _list_models(binary: str, timeout: float) -> set[str]:
    try:
        result = subprocess.run(
            [binary, "list", "--json"],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ModelSetupError(
            "Failed to execute the 'ollama' CLI. Install Ollama and verify the "
            "binary is accessible."
        ) from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise ModelSetupError(
            "Unable to query installed Ollama models. "
            "Ensure Ollama is installed and responding correctly.\n" + message
        ) from exc

    available: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:  # pragma: no cover - defensive
            raise ModelSetupError(
                "Received unexpected output from 'ollama list --json'. "
                "Upgrade Ollama or rerun the command manually to verify."
            ) from exc
        name = payload.get("name") or payload.get("model")
        if name:
            available.add(name)
    return available


def _pull_model(binary: str, model_name: str, timeout: float) -> None:
    try:
        subprocess.run(
            [binary, "pull", model_name],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise ModelSetupError(
            "Failed to execute the 'ollama' CLI while pulling models. "
            "Install Ollama and verify the binary is on your PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise ModelSetupError(
            "The 'ollama pull' command failed. Confirm you have network access, "
            "are signed into Ollama if required, and that the model name is valid.\n"
            + message
        ) from exc


def ensure_model(model_name: str, *, timeout: float = 300.0) -> None:
    """Ensure an Ollama model is present locally, pulling it if necessary."""

    binary = _resolve_ollama_binary()
    available = _list_models(binary, timeout)
    if model_name in available:
        return
    _pull_model(binary, model_name, timeout)


def ensure_models(models: Iterable[str], *, timeout: float = 300.0) -> None:
    """Ensure multiple Ollama models are present before starting the gateway."""

    unique_models = list(dict.fromkeys(model for model in models if model))
    if not unique_models:
        return

    binary = _resolve_ollama_binary()
    available = _list_models(binary, timeout)

    for name in unique_models:
        if name in available:
            continue
        _pull_model(binary, name, timeout)


def collect_requested_models(cli_models: Sequence[str] | None = None) -> list[str]:
    """Combine models requested via CLI with those configured via environment."""

    models: list[str] = []
    env_value = os.getenv("OLLAMA_MODELS")
    if env_value:
        models.extend(part.strip() for part in env_value.split(",") if part.strip())

    if cli_models:
        models.extend(cli_models)

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(models))
