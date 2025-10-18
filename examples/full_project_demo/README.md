# SOLLOL Full Project Demo

The `examples.full_project_demo` package exposes a Typer-powered CLI that strings
together SOLLOL's advanced examples into a single command. Use it to prepare
models, launch the real gateway and dashboards, and run our orchestration and
integration walkthroughs with consolidated logging.

## Quick start

```bash
python -m examples.full_project_demo run-all
```

The `run-all` command:

1. Ensures required Ollama models are installed locally.
2. Launches the SOLLOL gateway using the reusable real-node launcher.
3. Starts the unified dashboard with Ray and optional Dask integration.
4. Executes the advanced examples:
   - [`examples/auto_setup_example.py`](../auto_setup_example.py)
   - [`examples/live_dashboard_demo.py`](../live_dashboard_demo.py) (with summarised output)
   - Integration suites from [`examples/integration/`](../integration)
5. Shuts everything down gracefully and prints a summary report.

Run `python -m examples.full_project_demo --help` to discover individual
subcommands. Highlights include:

- `prepare-models` – wrap `examples.gateway_local_cluster.model_setup` to pull
  Ollama models in advance.
- `start-gateway` – launch the real SOLLOL gateway with Ray/Dask toggles.
- `run-dashboard` – start the unified dashboard as a managed background service.
- `run-auto-setup`, `run-live-dashboard`, and `integration ...` subcommands –
  invoke the existing advanced example scripts directly.

Each command accepts `--verbose` for additional logging and surfaces a summary at
the end of the run so you can quickly verify outcomes before iterating on your
own infrastructure.
