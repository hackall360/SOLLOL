# Gateway Local Cluster Demo

Spin up a miniature SOLLOL deployment on a single workstation that talks only to
**real** Ollama runtimes. The helper script in this directory installs models on
demand, starts optional Ray and Dask services, and prints the formatted
responses that the validation client receives from the gateway—no FastAPI mock
services or placeholder ports involved.

## Prerequisites

| Requirement | Why it matters | Verification command |
| --- | --- | --- |
| [Ollama CLI](https://ollama.com/download) 0.1.30 or newer | Required to pull models and launch real runtimes with `ollama serve`. | `ollama --version` |
| Python 3.9+ with SOLLOL installed in editable mode | Provides the `examples.gateway_local_cluster` Typer CLI. | `pip install -e .[dev]` |
| Redis (optional) | Needed only when you want to showcase GPU monitoring flows. | `redis-cli ping` |
| Docker Desktop / Docker Engine (optional) | Simplifies running Ray and Dask in containers instead of locally. | `docker version` |
| Ray + Dask (optional) | Demonstrate distributed batching from the gateway. Both stacks are installed via `pip install -e .[dev]`. | `ray --version`, `dask-scheduler --version` |

> **Tip:** The CLI automatically honours `OLLAMA_MODELS` and other environment
> variables, so you can preconfigure model downloads across terminal sessions.

## Automatic setup with `run.sh`

From the repository root execute:

```bash
./examples/gateway_local_cluster/run.sh
```

The wrapper exports `src/` onto `PYTHONPATH`, calls `python -m
examples.gateway_local_cluster.cli run`, and automatically:

1. Ensures every model requested via `--model`, `OLLAMA_MODELS`, or the
   `MODEL_NAMES` environment variable is installed using the local `ollama`
   binary.
2. Starts the SOLLOL gateway on `GATEWAY_PORT` (defaults to `18000`) and the
   first real Ollama runtime on `OLLAMA_PORT` (`11434`).
3. Launches additional `ollama serve` processes when `NODES` is greater than one,
   offsetting their ports from `OLLAMA_PORT` so you can scale to multiple
   runtimes that mirror actual cluster topologies.
4. Brings up Ray actors and Dask workers when `ENABLE_RAY` / `ENABLE_DASK`
   resolve to truthy values, mirroring the CLI toggles.
5. Runs the validation client and prints a health, chat, and generate summary
   before tearing everything down.

### Key environment variables

| Variable | Effect | Default |
| --- | --- | --- |
| `GATEWAY_PORT` | Forwarded to `--gateway-port`. | `18000` |
| `OLLAMA_PORT` | Port for the first real Ollama runtime (`--first-runtime-port`). | `11434` |
| `HOST` | Bind address used when starting services. | `127.0.0.1` |
| `READINESS_TIMEOUT` | Seconds to wait for readiness checks. | `30` |
| `VERBOSE` | Truthy values add `--verbose`. | unset |
| `OLLAMA_MODELS` | Comma-separated list bridged to repeated `--model` flags. | unset |
| `MODEL_NAMES` | Whitespace-delimited model list forwarded to `--model`. | unset |
| `NODES` | Number of real Ollama runtimes to launch (`--nodes`). | `1` |
| `ENABLE_RAY` | Truthy values add `--enable-ray`, falsy adds `--disable-ray`. | unset |
| `ENABLE_DASK` | Truthy values add `--enable-dask`, falsy adds `--disable-dask`. | unset |

All other CLI switches remain available; you can extend the invocation by
modifying `CLI_ARGS` inside the script or by calling the module directly:

```bash
PYTHONPATH=src python -m examples.gateway_local_cluster.cli run --help
```

## Expected output from real Ollama runtimes

When `ollama serve` is available and `NODES` is non-zero, the demo streams
responses from real models. The following excerpts were captured from a run with
`OLLAMA_MODELS=llama3,phi3`, `NODES=2`, and `--enable-ray --enable-dask`:

```
HEALTH
{
  "service": "SOLLOL",
  "status": "healthy",
  "task_distribution": {
    "ollama_nodes": 2,
    "description": "Load balance across Ollama nodes",
    "enabled": true
  },
  "ray_parallel_execution": {
    "actors": 2,
    "enabled": true
  },
  "dask_batching": {
    "workers": 2,
    "enabled": true
  }
}

CHAT
{
  "done": true,
  "model": "llama3",
  "message": {
    "role": "assistant",
    "content": "Sea otters wrap themselves in kelp so ocean currents do not sweep them away while they rest."
  }
}

GENERATE
{
  "done": true,
  "model": "phi3",
  "response": "- Silence notifications to protect focus.\n- Block time on your calendar for deep work.\n- Review priorities before you wrap up."
}
```

Model wording varies per run, but both chat and generate responses should
complete quickly after the initial model load, and additional requests reuse the
cached weights held by the live runtimes.

## Troubleshooting real deployments

- **`ollama` command not found.** Ensure the Ollama CLI is installed and on your
  `PATH`. On macOS this typically means launching the Ollama app once; on Linux
  install the `.deb`/`.rpm` or extract the tarball, then verify with
  `which ollama`. Update `PATH` or symlink the binary if you are running from a
  container.
- **Runtimes fail to bind to the requested ports.** Verify that `OLLAMA_PORT`
  and the subsequent offsets (`OLLAMA_PORT + node index`) are free. Use
  `lsof -i :<port>` or adjust the base port with `export OLLAMA_PORT=12000`.
- **Slow model pulls or repeated downloads.** Large models can take several
  minutes on first run. Pre-pull them with `ollama pull <model>` or run
  `python -m examples.gateway_local_cluster.cli prepare-models -m <model>`.
  The CLI caches models in `~/.ollama/models`, so subsequent runs reuse them.
- **Gateway waits indefinitely for readiness.** Increase
  `READINESS_TIMEOUT`, confirm that each `ollama serve` process reports "Listening"
  in its stdout, and ensure the gateway host can reach the runtime ports (e.g.,
  firewalls or container bridges allow localhost connections).
- **Ray or Dask fail to start.** Set `ENABLE_RAY=0` or `ENABLE_DASK=0` to skip
  those subsystems when running in constrained containers. For Docker-based
  demos, confirm the Docker daemon is running and that ports `8265` (Ray) and
  `8787` (Dask) are free.

## Manual workflow

Prefer to launch each component yourself? The Typer CLI contains additional
commands:

- `python -m examples.gateway_local_cluster.cli prepare-models -m llama3`
- `python -m examples.gateway_local_cluster.cli start-ollama --nodes 2`
- `python -m examples.gateway_local_cluster.cli status --include-stats`

Combine these commands with direct `curl` requests to
`http://localhost:18000/api/chat` to explore gateway behaviour before rolling
changes into shared infrastructure.
