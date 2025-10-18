"""Typer CLI orchestrating the complete SOLLOL demo workflow."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence

import typer


def _ensure_sollol_importable() -> None:
    try:  # pragma: no cover - environment bootstrap
        import sollol  # noqa: F401
    except ModuleNotFoundError:  # pragma: no cover - environment bootstrap
        repo_src = Path(__file__).resolve().parents[2] / "src"
        if repo_src.exists():
            sys.path.insert(0, str(repo_src))
        import sollol  # noqa: F401


_ensure_sollol_importable()

from examples.gateway_local_cluster.gateway_process import (  # noqa: E402
    DEFAULT_GATEWAY_PORT,
    DEFAULT_OLLAMA_PORT,
    launch_gateway,
)
from examples.gateway_local_cluster.model_setup import (  # noqa: E402
    ModelSetupError,
    collect_requested_models,
    ensure_models,
)
from examples.gateway_local_cluster.process_utils import (  # noqa: E402
    ManagedProcess,
    start_unified_dashboard,
)

app = typer.Typer(help="Run end-to-end SOLLOL demonstrations on local hardware.")

integration_app = typer.Typer(help="Run integration example suites.")
app.add_typer(integration_app, name="integration")


@dataclass
class StepResult:
    name: str
    status: str
    details: Optional[str] = None


def _configure_logging(verbose: bool) -> logging.Logger:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger("full_project_demo")
    logger.debug("Logging configured (verbose=%s)", verbose)
    return logger


def _parse_ollama_nodes(nodes: Iterable[str]) -> Optional[list[dict[str, int]]]:
    formatted: list[dict[str, int]] = []
    for node in nodes:
        host, _, port_text = node.partition(":")
        if not host or not port_text:
            raise typer.BadParameter(
                "Ollama nodes must be specified as host:port, e.g. 127.0.0.1:11434"
            )
        try:
            port = int(port_text)
        except ValueError as exc:  # pragma: no cover - user input
            raise typer.BadParameter(f"Invalid port in {node!r}") from exc
        formatted.append({"host": host, "port": port})
    return formatted or None


@contextlib.contextmanager
def _managed_process(handle: ManagedProcess, *, description: str) -> Iterable[ManagedProcess]:
    typer.secho(f"Starting {description} (pid={handle.pid})", fg="cyan")
    try:
        yield handle
    finally:
        typer.secho(f"Stopping {description}...", fg="cyan")
        handle.terminate()
        handle.wait(timeout=5)
        typer.secho(f"{description} stopped", fg="cyan")


def _run_coroutine(coro):
    return asyncio.run(coro)


def _print_summary(results: Sequence[StepResult]) -> None:
    if not results:
        return
    typer.echo("\nSummary:")
    max_name = max(len(result.name) for result in results)
    for result in results:
        status = result.status.upper()
        colour = "green" if status == "SUCCESS" else "red" if status == "FAILED" else "yellow"
        detail = f" - {result.details}" if result.details else ""
        typer.secho(f"  {result.name.ljust(max_name)} : {status}{detail}", fg=colour)


@app.command("prepare-models")
def prepare_models(
    models: List[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Ensure the listed Ollama models are available locally.",
    ),
    timeout: float = typer.Option(
        300.0,
        help="Timeout (seconds) for each ollama pull operation.",
        show_default=True,
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging."),
) -> None:
    """Pull Ollama models used across the full project demo."""

    _configure_logging(verbose)
    requested = collect_requested_models(models)
    if not requested:
        requested = ["llama3.2:3b"]
        typer.echo("No models specified; defaulting to llama3.2:3b")

    typer.echo(f"Ensuring models are present: {', '.join(requested)}")
    try:
        ensure_models(requested, timeout=timeout)
    except ModelSetupError as exc:
        typer.secho(f"Model preparation failed: {exc}", fg="red")
        raise typer.Exit(code=1) from exc

    typer.secho("Models ready", fg="green")


@app.command("start-gateway")
def start_gateway(
    gateway_port: int = typer.Option(
        DEFAULT_GATEWAY_PORT,
        help="Port for the SOLLOL gateway.",
        show_default=True,
    ),
    ollama_port: int = typer.Option(
        DEFAULT_OLLAMA_PORT,
        help="Default Ollama port for auto-generated nodes.",
        show_default=True,
    ),
    enable_batch: bool = typer.Option(
        True,
        "--enable-batch/--disable-batch",
        help="Toggle batch processing when launching the gateway.",
    ),
    ray_workers: int = typer.Option(2, help="Number of Ray workers to spawn.", show_default=True),
    dask_workers: int = typer.Option(1, help="Number of Dask workers to spawn.", show_default=True),
    enable_ray: bool = typer.Option(True, "--enable-ray/--disable-ray", help="Toggle Ray integration."),
    enable_dask: bool = typer.Option(True, "--enable-dask/--disable-dask", help="Toggle Dask integration."),
    ollama_node: List[str] = typer.Option(
        None,
        "--ollama-node",
        help="Explicit Ollama node definitions (host:port). Can be passed multiple times.",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging."),
) -> None:
    """Start the SOLLOL gateway using the reusable launcher."""

    _configure_logging(verbose)
    nodes = _parse_ollama_nodes(ollama_node)

    typer.echo("Launching SOLLOL gateway with configuration:")
    typer.echo(f"  Port           : {gateway_port}")
    typer.echo(f"  Ray workers    : {ray_workers if enable_ray else 0}")
    typer.echo(f"  Dask workers   : {dask_workers if enable_dask else 0}")
    typer.echo(f"  Batch enabled  : {enable_batch and enable_dask}")
    if nodes:
        typer.echo(f"  Ollama nodes   : {nodes}")
    else:
        typer.echo(f"  Default Ollama : 127.0.0.1:{ollama_port}")

    try:
        with _managed_process(
            launch_gateway(
                gateway_port=gateway_port,
                ollama_port=ollama_port,
                enable_batch_processing=enable_batch,
                ray_workers=ray_workers,
                dask_workers=dask_workers,
                enable_ray=enable_ray,
                enable_dask=enable_dask,
                ollama_nodes=nodes,
            ),
            description="SOLLOL gateway",
        ):
            typer.secho("Gateway running. Press Ctrl+C to stop.", fg="green")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        typer.echo("\nReceived interrupt; shutting down gateway.")


@app.command("run-dashboard")
def run_dashboard(
    dashboard_port: int = typer.Option(8080, help="Unified dashboard port.", show_default=True),
    host: str = typer.Option("0.0.0.0", help="Host interface for the dashboard.", show_default=True),
    enable_dask: bool = typer.Option(True, "--enable-dask/--disable-dask", help="Embed Dask dashboard."),
    ray_dashboard_port: int = typer.Option(8265, help="Ray dashboard port.", show_default=True),
    dask_dashboard_port: int = typer.Option(8787, help="Dask dashboard port.", show_default=True),
    verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging."),
) -> None:
    """Launch the SOLLOL unified dashboard as a managed background service."""

    _configure_logging(verbose)

    typer.echo("Starting unified dashboard:")
    typer.echo(f"  Dashboard      : http://{host}:{dashboard_port}")
    typer.echo(f"  Ray dashboard  : http://{host}:{ray_dashboard_port}")
    if enable_dask:
        typer.echo(f"  Dask dashboard : http://{host}:{dask_dashboard_port}")
    else:
        typer.echo("  Dask dashboard : disabled")

    try:
        with _managed_process(
            start_unified_dashboard(
                dashboard_port=dashboard_port,
                host=host,
                enable_dask=enable_dask,
                ray_dashboard_port=ray_dashboard_port,
                dask_dashboard_port=dask_dashboard_port,
            ),
            description="Unified dashboard",
        ):
            typer.secho("Dashboard running. Press Ctrl+C to stop.", fg="green")
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        typer.echo("\nReceived interrupt; shutting down dashboard.")


@app.command("run-auto-setup")
def run_auto_setup(verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging.")) -> None:
    """Execute the auto-setup example within the full project workflow."""

    _configure_logging(verbose)

    from examples import auto_setup_example

    typer.secho("Running auto-setup example...", fg="cyan")
    _run_coroutine(auto_setup_example.main())
    typer.secho("Auto-setup example completed", fg="green")


def _run_live_dashboard_demo(run_duration: Optional[float]) -> dict[str, float | int]:
    from examples import live_dashboard_demo

    typer.secho("Starting live dashboard demo...", fg="cyan")
    summary = _run_coroutine(live_dashboard_demo.run_demo(run_duration=run_duration))
    typer.secho("Live dashboard demo completed", fg="green")
    return summary


@app.command("run-live-dashboard")
def run_live_dashboard(
    run_duration: Optional[float] = typer.Option(
        None,
        help="Optional duration (seconds) to run before shutting down automatically.",
    ),
    start_gateway_first: bool = typer.Option(
        True,
        "--start-gateway/--skip-gateway",
        help="Automatically launch the SOLLOL gateway before running the demo.",
    ),
    gateway_port: int = typer.Option(
        DEFAULT_GATEWAY_PORT,
        help="Gateway port when auto-starting the service.",
        show_default=True,
    ),
    enable_ray: bool = typer.Option(True, "--enable-ray/--disable-ray", help="Toggle Ray integration."),
    enable_dask: bool = typer.Option(True, "--enable-dask/--disable-dask", help="Toggle Dask integration."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging."),
) -> None:
    """Run the live dashboard demo with optional managed gateway orchestration."""

    _configure_logging(verbose)
    results: list[StepResult] = []

    if start_gateway_first:
        gateway_handle = launch_gateway(
            gateway_port=gateway_port,
            enable_ray=enable_ray,
            enable_dask=enable_dask,
        )
        context_manager = _managed_process(gateway_handle, description="SOLLOL gateway")
    else:
        context_manager = contextlib.nullcontext()

    with context_manager:
        summary = _run_live_dashboard_demo(run_duration)
        results.append(
            StepResult(
                name="live-dashboard-demo",
                status="success",
                details=(
                    f"requests={summary.get('requests_succeeded', 0)}/"
                    f"{summary.get('requests_attempted', 0)}, uptime={summary.get('uptime_seconds', 0):.1f}s"
                ),
            )
        )

    _print_summary(results)


def _run_integration_suite(
    name: str, functions: Sequence[tuple[str, Callable[[], None]]]
) -> list[StepResult]:
    results: list[StepResult] = []
    for display_name, func in functions:
        typer.secho(f"→ {display_name}", fg="cyan")
        try:
            func()
        except Exception as exc:  # pragma: no cover - demo feedback
            typer.secho(f"   ✗ {exc}", fg="red")
            results.append(StepResult(name=f"{name}:{display_name}", status="failed", details=str(exc)))
        else:
            typer.secho("   ✓ Completed", fg="green")
            results.append(StepResult(name=f"{name}:{display_name}", status="success"))
    return results


@integration_app.command("sync-agents")
def integration_sync_agents() -> list[StepResult]:
    """Run the synchronous agent orchestration integration examples."""

    from examples.integration import sync_agents

    results = _run_integration_suite(
        "sync-agents",
        [
            ("Simple synchronous agent example", sync_agents.simple_agent_example),
            ("Multi-agent orchestration", sync_agents.multi_agent_orchestration),
            ("Hybrid router usage", sync_agents.hybrid_router_example),
            ("Error handling", sync_agents.error_handling_example),
            ("Priority comparison", sync_agents.priority_comparison),
        ],
    )
    _print_summary(results)
    return results


@integration_app.command("load-balancer")
def integration_load_balancer() -> list[StepResult]:
    """Run the load balancer wrapper integration examples."""

    from examples.integration import load_balancer_wrapper

    results = _run_integration_suite(
        "load-balancer",
        [
            ("Gradual migration", load_balancer_wrapper.gradual_migration_example),
            ("Detection example", load_balancer_wrapper.detection_example),
            ("Multi-tier routing", load_balancer_wrapper.multi_tier_routing_example),
        ],
    )
    _print_summary(results)
    return results


@integration_app.command("priority-mapping")
def integration_priority_mapping() -> list[StepResult]:
    """Run the priority mapping integration examples."""

    from examples.integration import priority_mapping

    results = _run_integration_suite(
        "priority-mapping",
        [
            ("Semantic priorities", priority_mapping.semantic_priorities_example),
            ("Role-based priorities", priority_mapping.role_based_priorities_example),
            ("Task-based priorities", priority_mapping.task_based_priorities_example),
            ("Custom priority registration", priority_mapping.custom_priority_registration),
            ("Priority mapper", priority_mapping.priority_mapper_example),
            ("Dynamic priority adjustment", priority_mapping.dynamic_priority_adjustment),
        ],
    )
    _print_summary(results)
    return results


@app.command("run-all")
def run_all(
    models: List[str] = typer.Option(
        None,
        "--model",
        "-m",
        help="Optional list of Ollama models to ensure before running.",
    ),
    gateway_port: int = typer.Option(
        DEFAULT_GATEWAY_PORT,
        help="Port for the SOLLOL gateway.",
        show_default=True,
    ),
    dashboard_port: int = typer.Option(8080, help="Unified dashboard port.", show_default=True),
    run_duration: float = typer.Option(
        20.0,
        help="Seconds to keep the live dashboard demo running during the full workflow.",
        show_default=True,
    ),
    enable_ray: bool = typer.Option(True, "--enable-ray/--disable-ray", help="Toggle Ray integration."),
    enable_dask: bool = typer.Option(True, "--enable-dask/--disable-dask", help="Toggle Dask integration."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging."),
) -> None:
    """Execute the complete SOLLOL feature tour on local hardware."""

    _configure_logging(verbose)
    results: list[StepResult] = []

    typer.secho("Preparing environment...", fg="cyan")
    requested_models = collect_requested_models(models) or ["llama3.2:3b"]
    try:
        ensure_models(requested_models)
    except ModelSetupError as exc:
        results.append(StepResult(name="model-preparation", status="failed", details=str(exc)))
        _print_summary(results)
        raise typer.Exit(code=1) from exc
    else:
        results.append(
            StepResult(
                name="model-preparation",
                status="success",
                details=f"models={','.join(requested_models)}",
            )
        )

    typer.secho("Launching core services...", fg="cyan")
    gateway_handle = launch_gateway(
        gateway_port=gateway_port,
        enable_ray=enable_ray,
        enable_dask=enable_dask,
    )

    with _managed_process(gateway_handle, description="SOLLOL gateway"):
        dashboard_handle = start_unified_dashboard(
            dashboard_port=dashboard_port,
            host="0.0.0.0",
            enable_dask=enable_dask,
            ray_dashboard_port=8265,
            dask_dashboard_port=8787,
        )
        with _managed_process(dashboard_handle, description="Unified dashboard"):
            results.append(
                StepResult(
                    name="services",
                    status="success",
                    details=f"gateway=http://127.0.0.1:{gateway_port}, dashboard=http://127.0.0.1:{dashboard_port}",
                )
            )

            typer.secho("Running auto-setup example...", fg="cyan")
            _run_coroutine(__import__("examples.auto_setup_example", fromlist=["main"]).main())
            results.append(StepResult(name="auto-setup-example", status="success"))

            summary = _run_live_dashboard_demo(run_duration)
            results.append(
                StepResult(
                    name="live-dashboard-demo",
                    status="success",
                    details=(
                        f"requests={summary.get('requests_succeeded', 0)}/"
                        f"{summary.get('requests_attempted', 0)}, uptime={summary.get('uptime_seconds', 0):.1f}s"
                    ),
                )
            )

            typer.secho("Running integration suites...", fg="cyan")
            integration_results: list[StepResult] = []
            for command in (
                integration_sync_agents,
                integration_load_balancer,
                integration_priority_mapping,
            ):
                integration_results.extend(command())

            failed = [item for item in integration_results if item.status != "success"]
            if failed:
                details = f"{len(failed)} failures across integration demos"
                results.append(StepResult(name="integration-suites", status="failed", details=details))
            else:
                details = f"{len(integration_results)} demos"
                results.append(StepResult(name="integration-suites", status="success", details=details))

    _print_summary(results)
    typer.secho("Full project demo complete!", fg="green")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
