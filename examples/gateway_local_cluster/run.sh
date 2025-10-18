#!/usr/bin/env bash
set -euo pipefail

# Convenience wrapper for launching the local cluster demo with real Ollama
# runtimes. The script forwards common environment variables into the Typer
# CLI so you can configure behaviour without typing long option lists:
#
#   * ``OLLAMA_MODELS``/``MODEL_NAMES`` – comma-separated (or space-separated
#     for ``MODEL_NAMES``) list of models to preload with ``ollama pull``.
#   * ``NODES`` – number of ``ollama serve`` processes to launch.
#   * ``OLLAMA_PORT`` – base port for the first ``ollama serve`` instance.
#   * ``GATEWAY_PORT`` – listening port for the SOLLOL gateway process.
#
# The wrapper also ensures the source tree is importable without an editable
# installation.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${PYTHONPATH}:${PROJECT_ROOT}/src"
else
  export PYTHONPATH="${PROJECT_ROOT}/src"
fi

CLI_MODULE="examples.gateway_local_cluster.cli"
CLI_COMMAND="run"

CLI_ARGS=()

if [[ -n "${OLLAMA_MODELS:-}" ]]; then
  IFS=',' read -ra __models <<< "${OLLAMA_MODELS}"
  for __model in "${__models[@]}"; do
    __trimmed="$(echo "${__model}" | xargs)"
    if [[ -n "${__trimmed}" ]]; then
      CLI_ARGS+=("--model" "${__trimmed}")
    fi
  done
  unset __models
  unset __model
  unset __trimmed
fi

if [[ -n "${MODEL_NAMES:-}" ]]; then
  for __model in ${MODEL_NAMES}; do
    CLI_ARGS+=("--model" "${__model}")
  done
  unset __model
fi

if [[ -n "${GATEWAY_PORT:-}" ]]; then
  CLI_ARGS+=("--gateway-port" "${GATEWAY_PORT}")
fi

if [[ -n "${OLLAMA_PORT:-}" ]]; then
  CLI_ARGS+=("--first-runtime-port" "${OLLAMA_PORT}")
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
