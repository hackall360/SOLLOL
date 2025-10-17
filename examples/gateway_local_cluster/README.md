# Gateway Local Cluster Demo

The gateway local cluster example illustrates how to spin up a miniature SOLLOL deployment on a single workstation.  It shows how the SOLLOL gateway coordinates mock Ollama nodes, Ray actors, and optional Dask batch workers so that you can rehearse load-balancing behavior before touching production infrastructure.

## Prerequisites
- Python 3.9+ with the SOLLOL package installed in editable mode (`pip install -e .`).
- Access to the repository root so you can run `python -m sollol.cli` commands.
- (Optional) Local Ollama runtimes or lightweight HTTP mocks that respond like Ollama nodes for realism.
- Redis server available when testing GPU monitoring flows (defaults to `localhost:6379`).

## Quickstart Script

An executable helper, [`run.sh`](./run.sh), orchestrates the full loop: it spawns the mock Ollama server, launches the SOLLOL gateway, runs the validation client, and then shuts everything down cleanly. From the repository root run:

```bash
./examples/gateway_local_cluster/run.sh
```

Environment variables map to the CLI flags exposed by `python -m examples.gateway_local_cluster run`:

| Environment variable | Description | Default |
| --- | --- | --- |
| `GATEWAY_PORT` | Gateway listener forwarded to `--gateway-port`. | 18000 |
| `MOCK_PORT` | Mock Ollama listener forwarded to `--mock-port`. | 11434 |
| `HOST` | Hostname passed via `--host`. | `127.0.0.1` |
| `READINESS_TIMEOUT` | Seconds supplied to `--readiness-timeout`. | 30 |
| `VERBOSE` | When set to `1`, `true`, `yes`, or `on`, adds `--verbose`. | unset |

If you are running inside a restricted container, consider exporting `SOLLOL_DASK_WORKERS=0` before invoking the script to disable optional Dask batch workers that may not be able to fork child processes.

The script prints the formatted payload summaries emitted by `client.format_results`. Abridged output looks like:

```
HEALTH
{
  "service": "SOLLOL",
  "status": "healthy",
  "ray_parallel_execution": {
    "actors": 2,
    "enabled": true,
    "description": "Ray actors for concurrent request handling"
  },
  "task_distribution": {
    "enabled": true,
    "ollama_nodes": 1,
    "description": "Load balance across Ollama nodes"
  },
  ...
}

CHAT
{
  "message": {
    "content": "ready",
    "role": "assistant"
  },
  "model": "llama3.2"
}

GENERATE
{
  "response": "Status: ready.",
  "model": "llama3.2"
}
```

## Manual Run Outline
1. **Prepare environment**
   - Activate your virtual environment and install dependencies with `pip install -e .[dev]` if you plan to hack on the code.
   - Export any environment variables your mock Ollama services require.
2. **Launch mock backends**
   - Start local Ollama instances or lightweight HTTP mocks that mimic `/api/generate` and `/api/chat` endpoints.
   - (Optional) Start llama.cpp RPC servers to demonstrate sharding.
3. **Start the gateway**
   - From the repository root run:
     ```bash
     python -m sollol.cli up \
       --port 18000 \
       --ray-workers 2 \
       --dask-workers 1 \
       --ollama-nodes "127.0.0.1:11434,127.0.0.1:21434"
     ```
   - Adjust flags (see above) to emphasize the behavior you want to demo.
4. **Interact with the local cluster**
   - Send sample requests to `http://localhost:18000/api/chat` or `.../api/generate` and observe routing decisions in the logs.
   - Inspect Ray and Dask dashboards if they are running to highlight task distribution.
5. **Extend the scenario**
   - Toggle `--no-batch-processing` or change `--rpc-backends` to showcase different modes.

## Cleanup Outline
1. Stop the SOLLOL gateway process (Ctrl+C in the terminal running `sollol up`).
2. Terminate Ray and Dask workers if they continue running:
   ```bash
   pkill -f "ray::"
   pkill -f "dask"
   ```
3. Shut down mock Ollama services and llama.cpp RPC servers.
4. (Optional) Stop Redis if you launched a dedicated instance for monitoring.
