"""
Zero-config Ollama connection pool with intelligent load balancing.

Auto-discovers nodes, manages connections, routes requests intelligently.
Thread-safe and ready to use immediately.

Features full SynapticLlamas observability:
- Intelligent routing with task analysis
- Performance tracking and learning
- Detailed logging of routing decisions
- Real-time VRAM monitoring for GPU-aware routing
"""

import asyncio
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import requests

from .intelligence import IntelligentRouter, get_router
from .node_health import NodeHealthMonitor, normalize_model_name
from .vram_monitor import VRAMMonitor

logger = logging.getLogger(__name__)


class OllamaPool:
    """
    Connection pool that automatically discovers and load balances across Ollama nodes.

    Usage:
        pool = OllamaPool.auto_configure()
        response = pool.chat("llama3.2", [{"role": "user", "content": "Hi"}])
    """

    # VRAM safety buffer (MB) - subtracted from reported free VRAM to prevent OOM
    VRAM_BUFFER_MB = 200  # 0.2GB cushion for system processes and safety margin

    def __init__(
        self,
        nodes: Optional[List[Dict[str, str]]] = None,
        enable_intelligent_routing: bool = True,
        exclude_localhost: bool = False,
    ):
        """
        Initialize connection pool with full observability.

        Args:
            nodes: List of node dicts. If None, auto-discovers.
            enable_intelligent_routing: Use intelligent routing (default: True)
            exclude_localhost: Skip localhost during discovery (for SOLLOL gateway)
        """
        self.nodes = nodes or []
        self.exclude_localhost = exclude_localhost
        self._lock = threading.Lock()
        self._current_index = 0

        # Auto-discover if no nodes provided
        if not self.nodes:
            self._auto_discover()

        # Initialize intelligent routing
        self.enable_intelligent_routing = enable_intelligent_routing
        self.router = get_router() if enable_intelligent_routing else None

        # Initialize health monitoring (FlockParser pattern)
        self.health_monitor = NodeHealthMonitor()

        # Initialize VRAM monitoring for GPU-aware routing
        self.vram_monitor = VRAMMonitor()
        self._vram_refresh_interval = 30  # seconds
        self._vram_refresh_enabled = True

        # Enhanced stats tracking with performance metrics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "nodes_used": {},
            "node_performance": {},  # Track performance per node
        }

        # Initialize node metadata for intelligent routing
        self._init_node_metadata()

        # Start background VRAM monitoring thread
        self._vram_refresh_thread = threading.Thread(
            target=self._refresh_vram_loop,
            daemon=True,
            name="OllamaPool-VRAM-Monitor"
        )
        self._vram_refresh_thread.start()

        logger.info(
            f"OllamaPool initialized with {len(self.nodes)} nodes "
            f"(intelligent_routing={'enabled' if enable_intelligent_routing else 'disabled'}, "
            f"vram_monitoring=enabled, gpu_type={self.vram_monitor.gpu_type})"
        )

    @classmethod
    def auto_configure(cls) -> "OllamaPool":
        """
        Create pool with automatic discovery.

        Returns:
            OllamaPool instance ready to use
        """
        return cls(nodes=None)

    def _auto_discover(self):
        """Discover Ollama nodes automatically."""
        from .discovery import discover_ollama_nodes

        if self.exclude_localhost:
            logger.debug("Auto-discovering Ollama nodes (excluding localhost)...")
        else:
            logger.debug("Auto-discovering Ollama nodes...")

        nodes = discover_ollama_nodes(timeout=0.5, exclude_localhost=self.exclude_localhost)

        with self._lock:
            self.nodes = nodes
            if self.exclude_localhost and len(nodes) == 0:
                logger.info("No remote Ollama nodes found (localhost excluded)")
            else:
                logger.info(f"Auto-discovered {len(nodes)} nodes: {nodes}")

    def _init_node_metadata(self):
        """Initialize metadata for each node with REAL VRAM data."""
        with self._lock:
            for node in self.nodes:
                node_key = f"{node['host']}:{node['port']}"
                if node_key not in self.stats["node_performance"]:
                    # Query VRAM for this node
                    gpu_free_mem = self._query_node_vram(node)

                    self.stats["node_performance"][node_key] = {
                        "host": node_key,
                        "latency_ms": 0.0,
                        "success_rate": 1.0,
                        "total_requests": 0,
                        "failed_requests": 0,
                        "available": True,
                        "active_requests": 0,  # Real-time concurrent load
                        "cpu_load": 0.5,  # Default assumption
                        "gpu_free_mem": gpu_free_mem,  # REAL VRAM DATA
                        "priority": 999,  # Default priority
                    }

                    logger.debug(
                        f"Initialized {node_key}: gpu_free_mem={gpu_free_mem}MB"
                    )

    def _select_node(
        self, payload: Optional[Dict[str, Any]] = None, priority: int = 5
    ) -> tuple[Dict[str, str], Optional[Dict[str, Any]]]:
        """
        Select best node for request using intelligent routing.

        Args:
            payload: Request payload for task analysis
            priority: Request priority (1-10)

        Returns:
            (selected_node, routing_decision) tuple
        """
        with self._lock:
            if not self.nodes:
                raise RuntimeError("No Ollama nodes available")

            # If intelligent routing is disabled or no payload, use round-robin
            if not self.enable_intelligent_routing or not payload:
                node = self.nodes[self._current_index % len(self.nodes)]
                self._current_index += 1
                return node, None

            # Use intelligent routing
            try:
                # Analyze request
                context = self.router.analyze_request(payload, priority=priority)

                # Get available hosts metadata
                available_hosts = list(self.stats["node_performance"].values())

                # Select optimal node
                selected_host, decision = self.router.select_optimal_node(context, available_hosts)

                # Find matching node dict
                for node in self.nodes:
                    node_key = f"{node['host']}:{node['port']}"
                    if node_key == selected_host:
                        # Log the routing decision
                        logger.info(f"🎯 Intelligent routing: {decision['reasoning']}")
                        return node, decision

                # Fallback if not found
                logger.warning(f"Selected host {selected_host} not in nodes, using fallback")
                node = self.nodes[self._current_index % len(self.nodes)]
                self._current_index += 1
                return node, None

            except Exception as e:
                logger.warning(f"Intelligent routing failed: {e}, falling back to round-robin")
                node = self.nodes[self._current_index % len(self.nodes)]
                self._current_index += 1
                return node, None

    def _make_request(
        self, endpoint: str, data: Dict[str, Any], priority: int = 5, timeout: float = 30.0
    ) -> Any:
        """
        Make HTTP request to selected node with intelligent routing and performance tracking.

        Args:
            endpoint: API endpoint (e.g., '/api/chat')
            data: Request payload
            priority: Request priority (1-10)
            timeout: Request timeout

        Returns:
            Response data

        Raises:
            RuntimeError: If all nodes fail
        """
        # Track request
        with self._lock:
            self.stats["total_requests"] += 1

        # Try nodes until one succeeds
        errors = []
        routing_decision = None

        for attempt in range(len(self.nodes)):
            # Select node with intelligent routing
            node, decision = self._select_node(payload=data, priority=priority)
            if decision:
                routing_decision = decision

            node_key = f"{node['host']}:{node['port']}"
            url = f"http://{node['host']}:{node['port']}{endpoint}"

            # Track active request (for load balancing)
            with self._lock:
                if node_key in self.stats["node_performance"]:
                    self.stats["node_performance"][node_key]["active_requests"] = (
                        self.stats["node_performance"][node_key].get("active_requests", 0) + 1
                    )

            # Track request start time
            start_time = time.time()

            try:
                logger.debug(f"Request to {url}")

                response = requests.post(url, json=data, timeout=timeout)

                # Calculate latency
                latency_ms = (time.time() - start_time) * 1000

                # Detect VRAM exhaustion (FlockParser pattern)
                vram_exhausted = self.health_monitor.detect_vram_exhaustion(node_key, latency_ms)
                if vram_exhausted:
                    # Mark node as degraded in performance tracking
                    with self._lock:
                        if node_key in self.stats["node_performance"]:
                            self.stats["node_performance"][node_key]["vram_exhausted"] = True

                # Update health baseline
                self.health_monitor.update_baseline(node_key, latency_ms)

                if response.status_code == 200:
                    # Success! Update metrics
                    with self._lock:
                        self.stats["successful_requests"] += 1
                        self.stats["nodes_used"][node_key] = (
                            self.stats["nodes_used"].get(node_key, 0) + 1
                        )

                        # Update node performance metrics
                        perf = self.stats["node_performance"][node_key]
                        perf["total_requests"] += 1

                        # Update running average latency
                        if perf["total_requests"] == 1:
                            perf["latency_ms"] = latency_ms
                        else:
                            perf["latency_ms"] = (
                                perf["latency_ms"] * (perf["total_requests"] - 1) + latency_ms
                            ) / perf["total_requests"]

                        # Update success rate
                        perf["success_rate"] = (
                            perf["total_requests"] - perf["failed_requests"]
                        ) / perf["total_requests"]

                    # Log performance
                    logger.info(
                        f"✅ Request succeeded: {node_key} "
                        f"(latency: {latency_ms:.1f}ms, "
                        f"avg: {self.stats['node_performance'][node_key]['latency_ms']:.1f}ms)"
                    )

                    # Record performance for router learning
                    if self.router and "model" in data:
                        task_type = (
                            routing_decision.get("task_type", "generation")
                            if routing_decision
                            else "generation"
                        )
                        self.router.record_performance(
                            task_type=task_type, model=data["model"], actual_duration_ms=latency_ms
                        )

                    return response.json()
                else:
                    errors.append(f"{url}: HTTP {response.status_code}")
                    self._record_failure(node_key, latency_ms)

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                errors.append(f"{url}: {str(e)}")
                logger.debug(f"Request failed: {e}")
                self._record_failure(node_key, latency_ms)

            finally:
                # Decrement active request counter (always runs)
                with self._lock:
                    if node_key in self.stats["node_performance"]:
                        self.stats["node_performance"][node_key]["active_requests"] = max(
                            0,
                            self.stats["node_performance"][node_key].get("active_requests", 1) - 1
                        )

        # All nodes failed
        with self._lock:
            self.stats["failed_requests"] += 1

        raise RuntimeError(f"All Ollama nodes failed. Errors: {'; '.join(errors)}")

    def _query_node_vram(self, node: Dict[str, str]) -> int:
        """
        Query VRAM for a specific node.

        For localhost: Use nvidia-smi/rocm-smi directly
        For remote: Query via Ollama /api/ps endpoint

        Args:
            node: Node dict with host and port

        Returns:
            Free VRAM in MB, or 0 if unknown
        """
        host = node["host"]
        port = node.get("port", "11434")

        # Check if this is localhost
        if host in ("localhost", "127.0.0.1"):
            # Try local VRAM monitoring (nvidia-smi, rocm-smi, etc.)
            local_vram = self.vram_monitor.get_local_vram_info()
            if local_vram and local_vram.get("free_vram_mb", 0) > 0:
                free_mb = local_vram.get("free_vram_mb", 0)
                # Apply VRAM buffer for safety margin
                free_mb_with_buffer = max(0, free_mb - self.VRAM_BUFFER_MB)
                logger.debug(f"Local VRAM: {free_mb}MB free, {free_mb_with_buffer}MB after {self.VRAM_BUFFER_MB}MB buffer ({local_vram['vendor']})")
                return free_mb_with_buffer
            else:
                # nvidia-smi failed or not installed (old GPUs, incompatible drivers)
                # Fall back to querying Ollama /api/ps for localhost
                logger.debug("nvidia-smi unavailable for localhost, falling back to Ollama /api/ps")
                # Fall through to remote query logic below (works for localhost too)

        # Remote node - query via Ollama API
        try:
            url = f"http://{host}:{port}/api/ps"
            response = requests.get(url, timeout=2.0)

            if response.status_code == 200:
                ps_data = response.json()
                # Parse GPU info from /api/ps response
                free_mb = self._parse_vram_from_ps(ps_data)
                logger.debug(f"Remote {host}:{port} VRAM: {free_mb}MB free")
                return free_mb
            else:
                logger.debug(f"Remote {host}:{port} /api/ps returned {response.status_code}")
                return 0

        except Exception as e:
            logger.debug(f"Failed to query VRAM for {host}:{port}: {e}")
            return 0

    def _estimate_gpu_vram_from_model(self) -> int:
        """
        Estimate GPU VRAM capacity from GPU model name (for GPUs without nvidia-smi).

        Uses lspci detection from VRAMMonitor to get GPU model, then looks up
        known VRAM capacity. Critical for old GPUs where nvidia-smi doesn't work.

        Returns:
            Estimated VRAM in MB, or 0 if unknown
        """
        # GPU Model → VRAM (MB) lookup table for common GPUs without nvidia-smi support
        GPU_VRAM_TABLE = {
            # NVIDIA GTX 10 series (mostly have nvidia-smi, but some old drivers don't)
            "GTX 1050": 2048,      # 2GB
            "GTX 1050 Ti": 4096,   # 4GB
            "GTX 1060": 6144,      # 6GB (also 3GB variant exists)
            "GTX 1070": 8192,      # 8GB
            "GTX 1080": 8192,      # 8GB
            "GTX 1080 Ti": 11264,  # 11GB

            # NVIDIA GTX 900 series
            "GTX 950": 2048,       # 2GB
            "GTX 960": 2048,       # 2GB (also 4GB variant)
            "GTX 970": 4096,       # 4GB
            "GTX 980": 4096,       # 4GB
            "GTX 980 Ti": 6144,    # 6GB

            # NVIDIA GTX 700 series
            "GTX 750": 1024,       # 1GB (also 2GB variant)
            "GTX 750 Ti": 2048,    # 2GB
            "GTX 760": 2048,       # 2GB
            "GTX 770": 2048,       # 2GB
            "GTX 780": 3072,       # 3GB
            "GTX 780 Ti": 3072,    # 3GB

            # NVIDIA GTX 600 series
            "GTX 650": 1024,       # 1GB
            "GTX 660": 2048,       # 2GB
            "GTX 670": 2048,       # 2GB
            "GTX 680": 2048,       # 2GB
            "GTX 690": 4096,       # 4GB (2GB per GPU, dual GPU)

            # NVIDIA GTX 500 series and older (nvidia-smi often unavailable)
            "GTX 580": 1536,       # 1.5GB
            "GTX 570": 1280,       # 1.25GB
            "GTX 560": 1024,       # 1GB
            "GTX 550 Ti": 1024,    # 1GB

            # Quadro cards (older ones)
            "Quadro K620": 2048,
            "Quadro K1200": 4096,
            "Quadro K2200": 4096,
            "Quadro P400": 2048,
            "Quadro P1000": 4096,
            "Quadro P2000": 5120,
        }

        # Try to get GPU info from VRAMMonitor
        local_vram = self.vram_monitor.get_local_vram_info()
        if not local_vram or local_vram.get("total_vram_mb", 0) == 0:
            # nvidia-smi failed, check if we have GPU names from lspci fallback
            if local_vram and "gpus" in local_vram:
                for gpu in local_vram["gpus"]:
                    gpu_name = gpu.get("name", "")

                    # Try to match GPU model in lookup table
                    for model_key, vram_mb in GPU_VRAM_TABLE.items():
                        if model_key.upper() in gpu_name.upper():
                            logger.info(f"Estimated VRAM for {gpu_name}: {vram_mb}MB (from model lookup)")
                            return vram_mb

        # Unknown GPU model, return 0 (will use conservative fallback)
        return 0

    def _parse_vram_from_ps(self, ps_data: Dict) -> int:
        """
        Parse VRAM info from Ollama /api/ps response.

        For GPUs where nvidia-smi doesn't work (old drivers, incompatible versions),
        this calculates VRAM based on loaded models + estimated GPU capacity.

        Args:
            ps_data: Response from /api/ps

        Returns:
            Estimated free VRAM in MB
        """
        try:
            # Ollama /api/ps format:
            # {
            #   "models": [
            #     {
            #       "name": "llama3.1:8b",
            #       "size": 4661211648,  # bytes
            #       "size_vram": 4661211648
            #     }
            #   ]
            # }

            models = ps_data.get("models", [])

            # Sum up VRAM used by loaded models
            total_vram_used_mb = 0
            for model in models:
                size_vram_bytes = model.get("size_vram", 0)
                total_vram_used_mb += size_vram_bytes / (1024 * 1024)

            # Determine total VRAM capacity (priority order):
            # 1. From nvidia-smi (if available)
            # 2. From GPU model lookup table (for old GPUs)
            # 3. Conservative fallback based on loaded models

            local_vram = self.vram_monitor.get_local_vram_info()
            if local_vram and local_vram.get("total_vram_mb", 0) > 0:
                # nvidia-smi worked - use accurate total
                total_vram_mb = local_vram.get("total_vram_mb", 0)
            else:
                # nvidia-smi failed - try model-based estimation
                estimated_vram = self._estimate_gpu_vram_from_model()
                if estimated_vram > 0:
                    total_vram_mb = estimated_vram
                elif total_vram_used_mb > 0:
                    # Model is loaded but we don't know GPU capacity
                    # Conservative: assume GPU is almost full (loaded + 512MB headroom)
                    total_vram_mb = total_vram_used_mb + 512
                    logger.warning(f"Unknown GPU capacity, assuming {total_vram_mb:.0f}MB based on loaded models")
                else:
                    # Nothing loaded and unknown GPU - assume small GPU
                    total_vram_mb = 2048  # 2GB conservative default
                    logger.warning("Unknown GPU with no loaded models, assuming 2GB capacity")

            # Calculate free VRAM with safety buffer
            free_vram_mb = max(0, total_vram_mb - total_vram_used_mb)
            # Apply VRAM buffer for safety margin to prevent OOM
            free_vram_mb_with_buffer = max(0, free_vram_mb - self.VRAM_BUFFER_MB)

            return int(free_vram_mb_with_buffer)

        except Exception as e:
            logger.debug(f"Failed to parse VRAM from /api/ps: {e}")
            return 0

    def _refresh_vram_loop(self):
        """Background thread to periodically refresh VRAM data."""
        logger.debug("VRAM monitoring thread started")

        while self._vram_refresh_enabled:
            try:
                time.sleep(self._vram_refresh_interval)

                # Refresh VRAM for all nodes
                with self._lock:
                    for node in self.nodes:
                        node_key = f"{node['host']}:{node['port']}"

                        if node_key in self.stats["node_performance"]:
                            # Query current VRAM
                            gpu_free_mem = self._query_node_vram(node)

                            # Update metadata
                            old_vram = self.stats["node_performance"][node_key].get("gpu_free_mem", 0)
                            self.stats["node_performance"][node_key]["gpu_free_mem"] = gpu_free_mem

                            # Log significant changes
                            if abs(gpu_free_mem - old_vram) > 1000:  # >1GB change
                                logger.info(
                                    f"🔄 VRAM changed on {node_key}: "
                                    f"{old_vram}MB → {gpu_free_mem}MB"
                                )

            except Exception as e:
                logger.error(f"VRAM refresh loop error: {e}")

        logger.debug("VRAM monitoring thread stopped")

    def _record_failure(self, node_key: str, latency_ms: float):
        """Record a failed request for a node."""
        with self._lock:
            if node_key in self.stats["node_performance"]:
                perf = self.stats["node_performance"][node_key]
                perf["failed_requests"] += 1
                perf["total_requests"] += 1

                # Update success rate
                if perf["total_requests"] > 0:
                    perf["success_rate"] = (
                        perf["total_requests"] - perf["failed_requests"]
                    ) / perf["total_requests"]

                logger.warning(
                    f"❌ Request failed: {node_key} " f"(success_rate: {perf['success_rate']:.1%})"
                )

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        priority: int = 5,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Chat completion with intelligent routing and observability.

        Args:
            model: Model name (e.g., "llama3.2")
            messages: Chat messages
            stream: Stream response (not supported yet)
            priority: Request priority 1-10 (default: 5)
            **kwargs: Additional Ollama parameters

        Returns:
            Chat response dict
        """
        if stream:
            raise NotImplementedError("Streaming not supported yet")

        data = {"model": model, "messages": messages, "stream": False, **kwargs}

        return self._make_request("/api/chat", data, priority=priority)

    def generate(
        self, model: str, prompt: str, stream: bool = False, priority: int = 5, **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text with intelligent routing and observability.

        Args:
            model: Model name
            prompt: Text prompt
            stream: Stream response (not supported yet)
            priority: Request priority 1-10 (default: 5)
            **kwargs: Additional Ollama parameters

        Returns:
            Generation response dict
        """
        if stream:
            raise NotImplementedError("Streaming not supported yet")

        data = {"model": model, "prompt": prompt, "stream": False, **kwargs}

        return self._make_request("/api/generate", data, priority=priority)

    def embed(self, model: str, input: str, priority: int = 5, **kwargs) -> Dict[str, Any]:
        """
        Generate embeddings with intelligent routing and observability.

        Args:
            model: Embedding model name
            input: Text to embed
            priority: Request priority 1-10 (default: 5)
            **kwargs: Additional Ollama parameters

        Returns:
            Embedding response dict
        """
        data = {"model": model, "input": input, **kwargs}

        return self._make_request("/api/embed", data, priority=priority)

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive pool statistics with performance metrics."""
        with self._lock:
            # Get real-time VRAM data
            local_vram = self.vram_monitor.get_local_vram_info()

            stats_data = {
                **self.stats,
                "nodes_configured": len(self.nodes),
                "nodes": [f"{n['host']}:{n['port']}" for n in self.nodes],
                "intelligent_routing_enabled": self.enable_intelligent_routing,
                "vram_monitoring": {
                    "enabled": True,
                    "gpu_type": self.vram_monitor.gpu_type,
                    "local_gpu": local_vram if local_vram else {},
                    "refresh_interval_seconds": self._vram_refresh_interval,
                    "health_monitoring": self.health_monitor.get_stats(),
                },
            }
            return stats_data

    def add_node(self, host: str, port: int = 11434):
        """
        Add a node to the pool.

        Args:
            host: Node hostname/IP
            port: Node port
        """
        with self._lock:
            node = {"host": host, "port": str(port)}
            if node not in self.nodes:
                self.nodes.append(node)
                logger.info(f"Added node: {host}:{port}")

    def remove_node(self, host: str, port: int = 11434):
        """
        Remove a node from the pool.

        Args:
            host: Node hostname/IP
            port: Node port
        """
        with self._lock:
            node = {"host": host, "port": str(port)}
            if node in self.nodes:
                self.nodes.remove(node)
                logger.info(f"Removed node: {host}:{port}")

    def stop(self):
        """
        Stop the pool and cleanup background threads.

        This method stops the VRAM refresh thread and performs cleanup.
        Call this when shutting down the pool to ensure proper resource cleanup.
        """
        logger.info("Stopping OllamaPool and cleaning up background threads...")

        # Stop VRAM refresh thread
        self._vram_refresh_enabled = False
        if self._vram_refresh_thread and self._vram_refresh_thread.is_alive():
            self._vram_refresh_thread.join(timeout=5.0)
            if self._vram_refresh_thread.is_alive():
                logger.warning("VRAM refresh thread did not stop within timeout")
            else:
                logger.info("VRAM refresh thread stopped successfully")

        logger.info("OllamaPool stopped")

    # Async methods for concurrent request handling
    async def chat_async(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        priority: int = 5,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Async chat completion with intelligent routing (enables parallel requests).

        Args:
            model: Model name (e.g., "llama3.2")
            messages: Chat messages
            stream: Stream response (not supported yet)
            priority: Request priority 1-10 (default: 5)
            **kwargs: Additional Ollama parameters

        Returns:
            Chat response dict

        Example:
            ```python
            import asyncio
            pool = OllamaPool.auto_configure()

            # Run multiple requests in parallel
            tasks = [
                pool.chat_async("llama3.2", [{"role": "user", "content": "Hello"}]),
                pool.chat_async("llama3.2", [{"role": "user", "content": "Hi"}]),
                pool.chat_async("llama3.2", [{"role": "user", "content": "Hey"}]),
            ]
            responses = await asyncio.gather(*tasks)
            ```
        """
        if stream:
            raise NotImplementedError("Streaming not supported yet")

        data = {"model": model, "messages": messages, "stream": False, **kwargs}

        # Run synchronous _make_request in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,  # Use default executor
            lambda: self._make_request("/api/chat", data, priority=priority)
        )

    async def generate_async(
        self, model: str, prompt: str, stream: bool = False, priority: int = 5, **kwargs
    ) -> Dict[str, Any]:
        """
        Async generation with intelligent routing (enables parallel requests).

        Args:
            model: Model name
            prompt: Text prompt
            stream: Stream response (not supported yet)
            priority: Request priority 1-10 (default: 5)
            **kwargs: Additional Ollama parameters

        Returns:
            Generation response dict

        Example:
            ```python
            import asyncio
            pool = OllamaPool.auto_configure()

            # Run multiple generations in parallel across heterogeneous GPUs
            prompts = ["Tell me a joke", "Explain AI", "Write a poem"]
            tasks = [pool.generate_async("llama3.2", p) for p in prompts]
            responses = await asyncio.gather(*tasks)
            ```
        """
        if stream:
            raise NotImplementedError("Streaming not supported yet")

        data = {"model": model, "prompt": prompt, "stream": False, **kwargs}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._make_request("/api/generate", data, priority=priority)
        )

    async def embed_async(
        self, model: str, input: str, priority: int = 5, **kwargs
    ) -> Dict[str, Any]:
        """
        Async embedding generation with intelligent routing.

        Args:
            model: Embedding model name
            input: Text to embed
            priority: Request priority 1-10 (default: 5)
            **kwargs: Additional Ollama parameters

        Returns:
            Embedding response dict
        """
        data = {"model": model, "input": input, **kwargs}

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._make_request("/api/embed", data, priority=priority)
        )

    def __repr__(self):
        return f"OllamaPool(nodes={len(self.nodes)}, requests={self.stats['total_requests']})"


# Global pool instance (lazy-initialized)
_global_pool: Optional[OllamaPool] = None
_pool_lock = threading.Lock()


def get_pool() -> OllamaPool:
    """
    Get or create the global Ollama connection pool.

    This is thread-safe and lazy-initializes the pool on first access.

    Returns:
        Global OllamaPool instance
    """
    global _global_pool

    if _global_pool is None:
        with _pool_lock:
            # Double-check locking
            if _global_pool is None:
                _global_pool = OllamaPool.auto_configure()

    return _global_pool
