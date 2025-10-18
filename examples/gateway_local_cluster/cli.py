"""Command-line interface for the gateway local cluster example."""
from __future__ import annotations

import json
import time
from contextlib import ExitStack
from typing import Any, Iterable, Mapping, Sequence

import typer

from . import client
from .gateway_process import (
    DEFAULT_DASK_WORKERS,
    DEFAULT_GATEWAY_PORT,
    DEFAULT_OLLAMA_PORT,
    DEFAULT_RAY_WORKERS,
    run_gateway,
)
from .model_setup import ModelSetupError, collect_requested_models, ensure_models
from .ollama_runtime import ollama_runtime
from .run_demo import run_demo

app = typer.Typer(help="Utilities for running the gateway local cluster demo")


def _preload_models(
    models: Sequence[str],
    *,
    timeout: float,
    verbose: bool,
) -> None:
    if not models:
        return

    if verbose:
        typer.echo("Ensuring required Ollama models are available: " + ", ".join(models))

    try:
        ensure_models(models, timeout=timeout)
    except ModelSetupError as exc:
        typer.secho(str(exc), fg="red")
        raise typer.Exit(code=1) from exc


def _extract_node_entries(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    nodes_field: Any = payload.get("ollama_nodes")
    candidates: Iterable[Any] = ()

    if isinstance(nodes_field, Mapping):
        nested = nodes_field.get("nodes") or nodes_field.get("items")
        if isinstance(nested, Mapping):
            candidates = nested.values()
        elif isinstance(nested, Iterable) and not isinstance(nested, (str, bytes)):
            candidates = nested
        else:
            candidates = nodes_field.values()
    elif isinstance(nodes_field, Iterable) and not isinstance(nodes_field, (str, bytes)):
        candidates = nodes_field
    else:
        fallback = payload.get("nodes")
        if isinstance(fallback, Mapping):
            candidates = fallback.values()
        elif isinstance(fallback, Iterable) and not isinstance(fallback, (str, bytes)):
            candidates = fallback

    entries: list[Mapping[str, Any]] = []
    for item in candidates:
        if isinstance(item, Mapping):
            entries.append(item)
    return entries


def _summarise_node(node: Mapping[str, Any]) -> str:
    host = str(node.get("host") or node.get("address") or "unknown")
    port = node.get("port")
    if isinstance(port, str) and port.isdigit():
        port = int(port)
    label = host if port in (None, "") else f"{host}:{port}"

    status = node.get("status") or node.get("state") or node.get("health")
    if status:
        label += f" ({status})"

    model = node.get("model") or node.get("default_model")
    if model:
        label += f" model={model}"

    return label


@app.command()
def run(
    gateway_port: int = typer.Option(
        DEFAULT_GATEWAY_PORT,
        "--gateway-port",
        show_default=True,
        help="Port the SOLLOL gateway should listen on.",
    ),
    ollama_port: int = typer.Option(
        DEFAULT_OLLAMA_PORT,
        "--ollama-port",
        "--mock-port",
        show_default=True,
        help="Base port used for the first Ollama runtime.",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        show_default=True,
        help="Host used when connecting to the services.",
    ),
    readiness_timeout: float = typer.Option(
        30.0,
        "--readiness-timeout",
        min=0.0,
        show_default=True,
        help="Maximum seconds to wait for background services to become ready.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output while running the demo.",
    ),
    models: tuple[str, ...] = typer.Option(
        (),
        "--model",
        "-m",
        help="Name of an Ollama model to preload before starting services. Can be provided multiple times.",
    ),
    model_timeout: float = typer.Option(
        300.0,
        "--model-timeout",
        min=1.0,
        show_default=True,
        help="Maximum seconds to wait for Ollama commands when preloading models.",
    ),
    node_count: int = typer.Option(
        0,
        "--nodes",
        min=0,
        show_default=True,
        help="Number of real Ollama runtimes to launch for the demo.",
    ),
    enable_ray: bool = typer.Option(
        True,
        "--enable-ray/--disable-ray",
        show_default=True,
        help="Toggle Ray integration when launching the gateway.",
    ),
    enable_dask: bool = typer.Option(
        True,
        "--enable-dask/--disable-dask",
        show_default=True,
        help="Toggle Dask integration when launching the gateway.",
    ),
    ray_workers: int = typer.Option(
        DEFAULT_RAY_WORKERS,
        "--ray-workers",
        min=0,
        show_default=True,
        help="Number of Ray workers to start when Ray is enabled.",
    ),
    dask_workers: int = typer.Option(
        DEFAULT_DASK_WORKERS,
        "--dask-workers",
        min=0,
        show_default=True,
        help="Number of Dask workers to start when Dask is enabled.",
    ),
    enable_batch_processing: bool = typer.Option(
        True,
        "--enable-batch/--disable-batch",
        show_default=True,
        help="Toggle batch processing support in the gateway.",
    ),
) -> None:
    """Run the full demo with configurable Ollama backends and SOLLOL gateway."""

    requested_models = collect_requested_models(models)
    _preload_models(requested_models, timeout=model_timeout, verbose=verbose)

    runtime_configs: list[dict[str, object]] = []
    if node_count > 0:
        base_port = ollama_port
        for index in range(node_count):
            port_value = base_port + index
            config: dict[str, object] = {"host": host, "port": port_value}
            if requested_models:
                config["ensure_models"] = requested_models
                config["model_timeout"] = model_timeout
            runtime_configs.append(config)

    if verbose:
        typer.echo(
            "Starting demo with gateway on %s and base Ollama port %s"
            % (gateway_port, ollama_port)
        )
        if runtime_configs:
            typer.echo(
                "Launching %d Ollama runtime(s) beginning at port %s"
                % (len(runtime_configs), runtime_configs[0]["port"])
            )
        typer.echo(
            "Ray: %s (workers=%d), Dask: %s (workers=%d)"
            % (
                "enabled" if enable_ray else "disabled",
                ray_workers,
                "enabled" if enable_dask else "disabled",
                dask_workers,
            )
        )

    result = run_demo(
        gateway_port=gateway_port,
        ollama_port=ollama_port,
        host=host,
        readiness_timeout=readiness_timeout,
        ollama_runtimes=runtime_configs or None,
        enable_ray=enable_ray,
        enable_dask=enable_dask,
        ray_workers=ray_workers,
        dask_workers=dask_workers,
        enable_batch_processing=enable_batch_processing,
    )

    if verbose:
        typer.echo(f"Gateway base URL: {result.gateway_base_url}")
        if result.ollama_base_urls:
            typer.echo("Ollama backend URLs:")
            for backend_url in result.ollama_base_urls:
                typer.echo(f"  - {backend_url}")

    typer.echo(result.formatted())


@app.command("prepare-models")
def prepare_models(
    models: tuple[str, ...] = typer.Option(
        (),
        "--model",
        "-m",
        help="Name of an Ollama model to ensure is available locally. Can be provided multiple times.",
    ),
    model_timeout: float = typer.Option(
        300.0,
        "--timeout",
        min=1.0,
        show_default=True,
        help="Maximum seconds to wait for each Ollama model command.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output while preparing models.",
    ),
) -> None:
    """Ensure one or more Ollama models are installed before launching runtimes."""

    requested_models = collect_requested_models(models)
    if not requested_models:
        typer.echo(
            "No model names were provided via --model or OLLAMA_MODELS. Nothing to prepare."
        )
        return

    _preload_models(requested_models, timeout=model_timeout, verbose=verbose)

    if verbose:
        typer.echo("All requested models are available locally.")
    else:
        typer.echo("Prepared models: " + ", ".join(requested_models))


@app.command("start-ollama")
def start_ollama(
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        show_default=True,
        help="Host interface to bind the Ollama runtime(s) to.",
    ),
    port: int = typer.Option(
        DEFAULT_OLLAMA_PORT,
        "--port",
        show_default=True,
        help="Starting port for launched Ollama runtimes.",
    ),
    nodes: int = typer.Option(
        1,
        "--nodes",
        min=1,
        show_default=True,
        help="Number of Ollama runtimes to launch.",
    ),
    readiness_timeout: float = typer.Option(
        60.0,
        "--readiness-timeout",
        min=1.0,
        show_default=True,
        help="Seconds to wait for each runtime's /api/health endpoint to respond.",
    ),
    poll_interval: float = typer.Option(
        0.5,
        "--poll-interval",
        min=0.1,
        show_default=True,
        help="Seconds between readiness probes while waiting for runtimes.",
    ),
    extra_args: tuple[str, ...] = typer.Option(
        (),
        "--extra-arg",
        help="Additional arguments forwarded to 'ollama serve'. Can be provided multiple times.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output while launching runtimes.",
    ),
) -> None:
    """Launch one or more Ollama runtimes using the local 'ollama serve' binary."""

    args_list = list(extra_args)

    try:
        with ExitStack() as stack:
            processes: list[tuple[int, Any]] = []
            for index in range(nodes):
                node_port = port + index
                if verbose:
                    typer.echo(f"Starting Ollama runtime {index + 1}/{nodes} on {host}:{node_port}")

                process = stack.enter_context(
                    ollama_runtime(
                        host=host,
                        port=node_port,
                        readiness_timeout=readiness_timeout,
                        poll_interval=poll_interval,
                        extra_args=args_list or None,
                    )
                )
                processes.append((node_port, process))

            if processes:
                typer.echo(
                    "Started %d Ollama runtime(s). Press Ctrl+C to stop them."
                    % len(processes)
                )

            while processes:
                running = [proc for proc in processes if proc[1].poll() is None]
                if not running:
                    for node_port, process in processes:
                        return_code = process.poll()
                        if return_code not in (None, 0):
                            typer.secho(
                                f"Runtime on {host}:{node_port} exited with code {return_code}",
                                fg="yellow",
                            )
                    break
                time.sleep(1.0)

    except KeyboardInterrupt:
        typer.echo("Stopping Ollama runtimes...")
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg="red")
        raise typer.Exit(code=1) from exc
    else:
        typer.echo("All Ollama runtimes exited.")


@app.command()
def status(
    gateway_port: int = typer.Option(
        DEFAULT_GATEWAY_PORT,
        "--gateway-port",
        show_default=True,
        help="Port the SOLLOL gateway should listen on.",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        show_default=True,
        help="Hostname or IP where the gateway is reachable.",
    ),
    include_stats: bool = typer.Option(
        False,
        "--include-stats/--skip-stats",
        show_default=True,
        help="Fetch /api/stats in addition to /api/health for troubleshooting.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Print raw JSON payloads returned by the gateway.",
    ),
) -> None:
    """Check gateway health and report Ollama node connectivity details."""

    base_url = f"http://{host}:{gateway_port}"

    try:
        health = client.fetch_health(base_url)
    except Exception as exc:  # pragma: no cover - diagnostic helper
        typer.secho(f"Gateway health check failed for {base_url}: {exc}", fg="red")
        raise typer.Exit(code=1) from exc

    status_value = health.get("status") or health.get("state") or "unknown"
    typer.echo(f"Gateway at {base_url} reports status: {status_value}")

    nodes = _extract_node_entries(health)
    if nodes:
        active = sum(
            1
            for node in nodes
            if str(node.get("status") or node.get("state") or "").lower()
            in {"ok", "ready", "running", "healthy"}
        )
        typer.echo(
            "Ollama nodes: %d reported (%d healthy)" % (len(nodes), active)
        )
        for node in nodes:
            typer.echo(f"  - {_summarise_node(node)}")
    else:
        typer.echo("No Ollama node metadata reported by the gateway.")

    stats_payload: Mapping[str, Any] | None = None
    if include_stats:
        try:
            stats_payload = client.fetch_stats(base_url)
        except Exception as exc:  # pragma: no cover - diagnostic helper
            typer.secho(f"Failed to fetch stats from {base_url}: {exc}", fg="yellow")
        else:
            request_count = stats_payload.get("requests")
            if isinstance(request_count, Mapping):
                total_requests = request_count.get("total")
            else:
                total_requests = None
            if total_requests is not None:
                typer.echo(f"Total requests handled: {total_requests}")
            else:
                typer.echo("Retrieved /api/stats payload from gateway.")

    if verbose:
        typer.echo("\nHealth payload:")
        typer.echo(json.dumps(health, indent=2, sort_keys=True))
        if stats_payload is not None:
            typer.echo("\nStats payload:")
            typer.echo(json.dumps(stats_payload, indent=2, sort_keys=True))


@app.command("start-gateway")
def start_gateway(
    gateway_port: int = typer.Option(
        DEFAULT_GATEWAY_PORT,
        "--gateway-port",
        show_default=True,
        help="Port for the SOLLOL gateway.",
    ),
    ollama_port: int = typer.Option(
        DEFAULT_OLLAMA_PORT,
        "--ollama-port",
        "--mock-port",
        show_default=True,
        help="Port used to reach the primary Ollama runtime.",
    ),
    enable_batch_processing: bool = typer.Option(
        True,
        "--enable-batch/--disable-batch",
        show_default=True,
        help="Toggle batch processing support in the gateway.",
    ),
    ray_workers: int = typer.Option(
        DEFAULT_RAY_WORKERS,
        "--ray-workers",
        show_default=True,
        help="Number of Ray workers to start.",
    ),
    dask_workers: int = typer.Option(
        DEFAULT_DASK_WORKERS,
        "--dask-workers",
        show_default=True,
        help="Number of Dask workers to start.",
    ),
    enable_ray: bool = typer.Option(
        True,
        "--enable-ray/--disable-ray",
        show_default=True,
        help="Toggle Ray integration when launching the gateway.",
    ),
    enable_dask: bool = typer.Option(
        True,
        "--enable-dask/--disable-dask",
        show_default=True,
        help="Toggle Dask integration when launching the gateway.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output before launching the gateway.",
    ),
    models: tuple[str, ...] = typer.Option(
        (),
        "--model",
        "-m",
        help="Name of an Ollama model to preload before launching the gateway. Can be provided multiple times.",
    ),
    model_timeout: float = typer.Option(
        300.0,
        "--model-timeout",
        min=1.0,
        show_default=True,
        help="Maximum seconds to wait for Ollama commands when preloading models.",
    ),
) -> None:
    """Run only the SOLLOL gateway configured for the local cluster demo."""

    requested_models = collect_requested_models(models)
    _preload_models(requested_models, timeout=model_timeout, verbose=verbose)

    if verbose:
        typer.echo(
            "Starting SOLLOL gateway on %s targeting Ollama on %s"
            % (gateway_port, ollama_port)
        )

    run_gateway(
        gateway_port=gateway_port,
        ollama_port=ollama_port,
        enable_batch_processing=enable_batch_processing,
        ray_workers=ray_workers,
        dask_workers=dask_workers,
        enable_ray=enable_ray,
        enable_dask=enable_dask,
    )


if __name__ == "__main__":
    app()
