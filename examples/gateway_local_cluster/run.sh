#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper that bridges environment variables into the Typer CLI and
# guarantees the source tree is importable without an editable installation.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${PYTHONPATH}:${PROJECT_ROOT}/src"
else
  export PYTHONPATH="${PROJECT_ROOT}/src"
fi

CLI_MODULE="examples.gateway_local_cluster"
CLI_COMMAND="run"

CLI_ARGS=()

if [[ -n "${GATEWAY_PORT:-}" ]]; then
  CLI_ARGS+=("--gateway-port" "${GATEWAY_PORT}")
fi

if [[ -n "${MOCK_PORT:-}" ]]; then
  CLI_ARGS+=("--mock-port" "${MOCK_PORT}")
fi

if [[ -n "${OLLAMA_PORT:-}" ]]; then
  CLI_ARGS+=("--ollama-port" "${OLLAMA_PORT}")
fi

if [[ -n "${HOST:-}" ]]; then
  CLI_ARGS+=("--host" "${HOST}")
fi

if [[ -n "${READINESS_TIMEOUT:-}" ]]; then
  CLI_ARGS+=("--readiness-timeout" "${READINESS_TIMEOUT}")
fi

if [[ "${VERBOSE:-}" =~ ^(1|true|TRUE|yes|YES|on|ON)$ ]]; then
  CLI_ARGS+=("--verbose")
fi

if [[ -n "${NODES:-}" ]]; then
  CLI_ARGS+=("--nodes" "${NODES}")
fi

if [[ "${ENABLE_RAY:-}" =~ ^(1|true|TRUE|yes|YES|on|ON)$ ]]; then
  CLI_ARGS+=("--enable-ray")
elif [[ "${ENABLE_RAY:-}" =~ ^(0|false|FALSE|no|NO|off|OFF)$ ]]; then
  CLI_ARGS+=("--disable-ray")
fi

if [[ "${ENABLE_DASK:-}" =~ ^(1|true|TRUE|yes|YES|on|ON)$ ]]; then
  CLI_ARGS+=("--enable-dask")
elif [[ "${ENABLE_DASK:-}" =~ ^(0|false|FALSE|no|NO|off|OFF)$ ]]; then
  CLI_ARGS+=("--disable-dask")
fi

cd "${PROJECT_ROOT}"
exec "${PYTHON_BIN}" -m "${CLI_MODULE}" "${CLI_COMMAND}" "${CLI_ARGS[@]}"
