# Gateway Mock Cluster Demo

The gateway mock cluster example illustrates how to spin up a miniature SOLLOL deployment on a single workstation.  It shows how the SOLLOL gateway coordinates mock Ollama nodes, Ray actors, and optional Dask batch workers so that you can rehearse load-balancing behavior before touching production infrastructure.

## Prerequisites
- Python 3.9+ with the SOLLOL package installed in editable mode (`pip install -e .`).
- Access to the repository root so you can run `python -m sollol.cli` commands.
- (Optional) Local Ollama runtimes or lightweight HTTP mocks that respond like Ollama nodes for realism.
- Redis server available when testing GPU monitoring flows (defaults to `localhost:6379`).

## Highlighted CLI Parameters
The demo concentrates on the `sollol up` command defined in `src/sollol/cli.py` and calls out a handful of flags that determine cluster behavior:

- `--port`: Gateway listening port (defaults to `11434`, Ollama-compatible). Use this when simulating multiple gateways on one machine.
- `--ray-workers`: Number of Ray actors that fan out real-time requests across the mock cluster.
- `--dask-workers`: Number of Dask workers powering batch workloads. Pair with `--no-batch-processing` to study latency without batch overhead.
- `--rpc-backends`: Comma-separated llama.cpp RPC servers for sharded models. Helpful for illustrating hybrid RPC + Ollama routing.
- `--ollama-nodes`: Comma-separated Ollama (or mock) HTTP endpoints to balance across.
- `--setup-gpu-monitoring/--no-setup-gpu-monitoring`, `--redis-host`, `--redis-port`: Control the optional GPU monitoring bootstrap so you can evaluate telemetry collection.

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
4. **Interact with the mock cluster**
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
