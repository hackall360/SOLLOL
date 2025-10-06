"""
SOLLOL Main Orchestration Class - Application-friendly API.

This module provides a programmatic interface for applications to configure
and control SOLLOL entirely from within Python code, without CLI or external configs.
"""

import threading
from datetime import datetime
from typing import Any, Dict, List, Optional

from sollol.config import SOLLOLConfig


class SOLLOL:
    """
    Main SOLLOL orchestration class.

    Provides a simple, application-friendly API for managing SOLLOL entirely
    from within your application code.

    Example:
        ```python
        from sollol import SOLLOL

        # Zero-config startup (auto-discovers everything)
        sollol = SOLLOL()
        sollol.start()  # Runs gateway in background thread

        # Your app can now use SOLLOL via the gateway
        # http://localhost:11434/api/chat

        # Or with custom configuration
        sollol = SOLLOL(
            port=8000,
            ray_workers=8,
            dask_workers=4,
            ollama_nodes=["10.0.0.2:11434", "10.0.0.3:11434"],
            rpc_backends=["10.0.0.5:50052"]
        )
        sollol.start(blocking=False)

        # Check status
        status = sollol.get_status()
        print(status)

        # Stop when done
        sollol.stop()
        ```
    """

    def __init__(
        self,
        port: int = 11434,
        ray_workers: int = 4,
        dask_workers: int = 2,
        enable_batch_processing: bool = True,
        autobatch_interval: int = 60,
        ollama_nodes: Optional[List[Dict]] = None,
        rpc_backends: Optional[List[Dict]] = None,
    ):
        """
        Initialize SOLLOL with configuration.

        Args:
            port: Gateway port (default: 11434 - Ollama's port)
            ray_workers: Number of Ray actors for parallel execution
            dask_workers: Number of Dask workers for batch processing
            enable_batch_processing: Enable Dask batch processing
            autobatch_interval: Seconds between autobatch cycles
            ollama_nodes: List of Ollama node dicts (auto-discovers if None)
            rpc_backends: List of RPC backend dicts for model sharding (auto-discovers if None)
        """
        # Configure logging
        import logging

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )
        self.logger = logging.getLogger(__name__)

        # Store configuration
        self.port = port
        self.ray_workers = ray_workers
        self.dask_workers = dask_workers
        self.enable_batch_processing = enable_batch_processing
        self.autobatch_interval = autobatch_interval
        self.ollama_nodes = ollama_nodes
        self.rpc_backends = rpc_backends

        # Internal state
        self._gateway_thread: Optional[threading.Thread] = None
        self._running = False

        self.logger.info("SOLLOL initialized with configuration:")
        self.logger.info(f"  Port: {port}")
        self.logger.info(f"  Ray workers: {ray_workers}")
        self.logger.info(f"  Dask workers: {dask_workers}")
        self.logger.info(f"  Batch processing: {'enabled' if enable_batch_processing else 'disabled'}")
        self.logger.info(f"  Ollama nodes: {len(ollama_nodes) if ollama_nodes else 'auto-discover'}")
        self.logger.info(f"  RPC backends: {len(rpc_backends) if rpc_backends else 'auto-discover'}")

    def start(self, blocking: bool = False):
        """
        Start SOLLOL gateway.

        Args:
            blocking: If True, blocks until stopped. If False, runs in background thread.

        Example:
            ```python
            # Non-blocking (recommended for applications)
            sollol.start(blocking=False)
            # Your app code continues here...

            # Blocking (recommended for standalone SOLLOL service)
            sollol.start(blocking=True)
            ```
        """
        if self._running:
            self.logger.warning("SOLLOL is already running")
            return

        self.logger.info("Starting SOLLOL gateway...")

        if blocking:
            # Run gateway in current thread (blocks)
            self._start_gateway()
        else:
            # Run gateway in background thread
            self._gateway_thread = threading.Thread(target=self._start_gateway, daemon=True)
            self._gateway_thread.start()
            self._running = True
            self.logger.info(f"✅ Gateway started in background thread")
            self.logger.info(f"   API available at http://localhost:{self.port}")
            self.logger.info(f"   Health check: http://localhost:{self.port}/api/health")
            self.logger.info(f"   API docs: http://localhost:{self.port}/docs")

    def _start_gateway(self):
        """Internal method to start the FastAPI gateway."""
        from sollol.gateway import start_api

        self._running = True

        start_api(
            port=self.port,
            rpc_backends=self.rpc_backends,
            ollama_nodes=self.ollama_nodes,
            ray_workers=self.ray_workers,
            dask_workers=self.dask_workers,
            enable_batch_processing=self.enable_batch_processing,
            autobatch_interval=self.autobatch_interval,
        )

    def stop(self):
        """
        Stop SOLLOL gateway.

        Note: Gateway runs in a daemon thread and will stop when your application exits.
        Ray and Dask processes are initialized inside the gateway and will also stop.
        """
        self.logger.info("Stopping SOLLOL...")
        self._running = False

        if self._gateway_thread and self._gateway_thread.is_alive():
            self.logger.warning("⚠️  Gateway is running in a daemon thread")
            self.logger.warning("    It will stop when your application exits")
            self.logger.warning("    To force stop, restart your application")

        self.logger.info("Stopped")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current SOLLOL status.

        Returns:
            Dictionary containing current status information

        Example:
            ```python
            status = sollol.get_status()
            print(f"Running: {status['running']}")
            print(f"Port: {status['port']}")
            ```
        """
        return {
            "running": self._running,
            "port": self.port,
            "ray_workers": self.ray_workers,
            "dask_workers": self.dask_workers,
            "batch_processing_enabled": self.enable_batch_processing,
            "ollama_nodes": len(self.ollama_nodes) if self.ollama_nodes else "auto-discover",
            "rpc_backends": len(self.rpc_backends) if self.rpc_backends else "auto-discover",
            "timestamp": datetime.now().isoformat(),
            "endpoints": {
                "gateway": f"http://localhost:{self.port}",
                "api_docs": f"http://localhost:{self.port}/docs",
                "health": f"http://localhost:{self.port}/api/health",
                "stats": f"http://localhost:{self.port}/api/stats",
            },
        }

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status from the gateway.

        Returns:
            Health information from /api/health endpoint

        Note: Only works when SOLLOL is running.
        """
        if not self._running:
            return {"error": "SOLLOL is not running"}

        import httpx

        try:
            resp = httpx.get(f"http://localhost:{self.port}/api/health", timeout=5.0)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics from the gateway.

        Returns:
            Statistics from /api/stats endpoint

        Note: Only works when SOLLOL is running.
        """
        if not self._running:
            return {"error": "SOLLOL is not running"}

        import httpx

        try:
            resp = httpx.get(f"http://localhost:{self.port}/api/stats", timeout=5.0)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def __repr__(self) -> str:
        """String representation of SOLLOL instance."""
        return (
            f"SOLLOL(running={self._running}, "
            f"port={self.port}, "
            f"ray_workers={self.ray_workers}, "
            f"dask_workers={self.dask_workers})"
        )
