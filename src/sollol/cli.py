"""
SOLLOL CLI - Drop-in Ollama replacement with task distribution and model sharding.
"""

import logging
from typing import Optional

import typer

from .gateway import start_api

app = typer.Typer(
    name="sollol",
    help="SOLLOL - Drop-in Ollama replacement with task distribution and model sharding",
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@app.command()
def up(
    port: int = typer.Option(11434, help="Port for SOLLOL gateway (default: 11434, Ollama's port)"),
    rpc_backends: Optional[str] = typer.Option(
        None,
        help="Comma-separated RPC backends for model sharding (e.g., '192.168.1.10:50052,192.168.1.11:50052')",
    ),
    ollama_nodes: Optional[str] = typer.Option(
        None,
        help="Comma-separated Ollama nodes for task distribution (e.g., '192.168.1.20:11434,192.168.1.21:11434'). Auto-discovers if not set.",
    ),
):
    """
    Start SOLLOL gateway - Drop-in Ollama replacement.

    SOLLOL provides TWO INDEPENDENT DISTRIBUTION MODES:
    1. Task Distribution - Load balance agent requests across Ollama nodes (parallel execution)
    2. Model Sharding - Distribute large models via llama.cpp RPC backends (single model, multiple nodes)

    You can use one, both, or neither mode. They work independently!

    Features:
    - Listens on port 11434 (standard Ollama port)
    - Auto-discovers Ollama nodes on network (for task distribution)
    - Auto-discovers RPC backends (for model sharding)
    - Automatic GGUF extraction from Ollama storage
    - Intelligent routing: small models → Ollama, large models → llama.cpp
    - Zero-config setup

    Examples:
        # Zero-config (auto-discovers everything):
        sollol up

        # Custom port:
        sollol up --port 8000

        # Manual RPC backends for model sharding:
        sollol up --rpc-backends "192.168.1.10:50052,192.168.1.11:50052"

        # Manual Ollama nodes for task distribution:
        sollol up --ollama-nodes "192.168.1.20:11434,192.168.1.21:11434"

        # Both modes enabled:
        sollol up --rpc-backends "10.0.0.1:50052" --ollama-nodes "10.0.0.2:11434"
    """
    logger.info("=" * 70)
    logger.info("🚀 Starting SOLLOL Gateway")
    logger.info("=" * 70)
    logger.info("")
    logger.info("Distribution Modes:")
    logger.info("  🔀 Task Distribution - Load balance across Ollama nodes")
    logger.info("  🔗 Model Sharding - Distribute large models via llama.cpp RPC")
    logger.info("")
    logger.info(f"Configuration:")
    logger.info(f"  Port: {port}")

    # Parse RPC backends
    parsed_rpc_backends = None
    if rpc_backends:
        parsed_rpc_backends = []
        for backend_str in rpc_backends.split(","):
            backend_str = backend_str.strip()
            if ":" in backend_str:
                host, port_str = backend_str.rsplit(":", 1)
                parsed_rpc_backends.append({"host": host, "port": int(port_str)})
            else:
                parsed_rpc_backends.append({"host": backend_str, "port": 50052})
        logger.info(f"  RPC Backends: {len(parsed_rpc_backends)} configured")
        logger.info("  → Model Sharding ENABLED")
    else:
        logger.info("  RPC Backends: Auto-discovery mode")

    # Parse Ollama nodes
    parsed_ollama_nodes = None
    if ollama_nodes:
        parsed_ollama_nodes = []
        for node_str in ollama_nodes.split(","):
            node_str = node_str.strip()
            if ":" in node_str:
                host, node_port = node_str.rsplit(":", 1)
                parsed_ollama_nodes.append({"host": host, "port": int(node_port)})
            else:
                parsed_ollama_nodes.append({"host": node_str, "port": 11434})
        logger.info(f"  Ollama Nodes: {len(parsed_ollama_nodes)} configured")
        logger.info("  → Task Distribution ENABLED")
    else:
        logger.info("  Ollama Nodes: Auto-discovery mode")

    logger.info("")
    logger.info("=" * 70)
    logger.info("")

    # Start gateway (blocking call)
    start_api(port=port, rpc_backends=parsed_rpc_backends, ollama_nodes=parsed_ollama_nodes)


@app.command()
def down():
    """
    Stop SOLLOL service.

    Note: For MVP, manually kill Ray/Dask processes:
        pkill -f "ray::"
        pkill -f "dask"
    """
    logger.info("🛑 SOLLOL shutdown")
    logger.info("   To stop Ray: pkill -f 'ray::'")
    logger.info("   To stop Dask: pkill -f 'dask'")


@app.command()
def status():
    """
    Check SOLLOL service status.
    """
    logger.info("📊 SOLLOL Status")
    logger.info("   Gateway: http://localhost:8000/api/health")
    logger.info("   Metrics: http://localhost:9090/metrics")
    logger.info("   Stats: http://localhost:8000/api/stats")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
