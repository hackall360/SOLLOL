"""Command-line interface for the gateway local cluster example."""
from __future__ import annotations

import typer

from .gateway_process import (
    DEFAULT_DASK_WORKERS,
    DEFAULT_GATEWAY_PORT,
    DEFAULT_MOCK_OLLAMA_PORT,
    DEFAULT_RAY_WORKERS,
    run_gateway,
)
from .mock_ollama import run as run_mock_ollama
from .run_demo import run_demo

app = typer.Typer(help="Utilities for running the gateway local cluster demo")


@app.command()
def run(
    gateway_port: int = typer.Option(
        DEFAULT_GATEWAY_PORT,
        "--gateway-port",
        show_default=True,
        help="Port the SOLLOL gateway should listen on.",
    ),
    mock_port: int = typer.Option(
        DEFAULT_MOCK_OLLAMA_PORT,
        "--mock-port",
        show_default=True,
        help="Port the mock Ollama server should listen on.",
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
) -> None:
    """Run the full demo with both the mock Ollama service and SOLLOL gateway."""

    if verbose:
        typer.echo(
            "Starting demo with gateway on %s and mock Ollama on %s"
            % (gateway_port, mock_port)
        )

    result = run_demo(
        gateway_port=gateway_port,
        mock_port=mock_port,
        host=host,
        readiness_timeout=readiness_timeout,
    )

    if verbose:
        typer.echo(f"Gateway base URL: {result.gateway_base_url}")
        typer.echo(f"Mock base URL: {result.mock_base_url}")

    typer.echo(result.formatted())


@app.command("start-mock")
def start_mock(
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        show_default=True,
        help="Host interface for the mock Ollama server.",
    ),
    port: int = typer.Option(
        DEFAULT_MOCK_OLLAMA_PORT,
        "--port",
        show_default=True,
        help="Port for the mock Ollama server.",
    ),
    reload: bool = typer.Option(
        False,
        "--reload/--no-reload",
        show_default=True,
        help="Enable Uvicorn reload mode.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output before launching the server.",
    ),
) -> None:
    """Run only the mock Ollama FastAPI server."""

    if verbose:
        typer.echo(f"Starting mock Ollama on {host}:{port}")

    argv = ["--host", host, "--port", str(port)]
    if reload:
        argv.append("--reload")

    run_mock_ollama(argv=argv)


@app.command("start-gateway")
def start_gateway(
    gateway_port: int = typer.Option(
        DEFAULT_GATEWAY_PORT,
        "--gateway-port",
        show_default=True,
        help="Port for the SOLLOL gateway.",
    ),
    mock_port: int = typer.Option(
        DEFAULT_MOCK_OLLAMA_PORT,
        "--mock-port",
        show_default=True,
        help="Port used to reach the mock Ollama server.",
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
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output before launching the gateway.",
    ),
) -> None:
    """Run only the SOLLOL gateway configured for the local cluster demo."""

    if verbose:
        typer.echo(
            "Starting SOLLOL gateway on %s targeting mock server on %s"
            % (gateway_port, mock_port)
        )

    run_gateway(
        gateway_port=gateway_port,
        mock_port=mock_port,
        enable_batch_processing=enable_batch_processing,
        ray_workers=ray_workers,
        dask_workers=dask_workers,
    )


if __name__ == "__main__":
    app()
