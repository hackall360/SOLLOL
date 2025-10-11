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
from .metrics_logger import log_node_health, log_request
from .network_observer import (
    log_ollama_request,
    log_ollama_response,
    log_ollama_error,
    log_node_health_check,
    log_node_status_change,
)

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
        discover_all_nodes: bool = False,
        app_name: Optional[str] = None,
        register_with_dashboard: bool = True,
        enable_ray: bool = False,
    ):
        """
        Initialize connection pool with full observability.

        Args:
            nodes: List of node dicts. If None, auto-discovers.
            enable_intelligent_routing: Use intelligent routing (default: True)
            exclude_localhost: Skip localhost during discovery (for SOLLOL gateway)
            discover_all_nodes: Scan full network for ALL nodes (slower but comprehensive)
            app_name: Custom application name for dashboard registration (e.g., "FlockParser")
            register_with_dashboard: Whether to auto-register with dashboard (default: True)
            enable_ray: Initialize Ray cluster for multi-app coordination (default: False)
        """
        self.nodes = nodes or []
        self.exclude_localhost = exclude_localhost
        self.discover_all_nodes = discover_all_nodes
        self.app_name = app_name  # Store custom app name for dashboard registration
        self.register_with_dashboard = register_with_dashboard  # Control dashboard registration
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

        # Health check configuration
        self._health_check_interval = 30  # seconds - check node health every 30s
        self._health_check_enabled = True

        # Enhanced stats tracking with performance metrics
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "nodes_used": {},
            "node_performance": {},  # Track performance per node
        }

        # Deduplicate nodes (removes localhost if real IP exists)
        self._deduplicate_nodes()

        # Initialize node metadata for intelligent routing
        self._init_node_metadata()

        # Initialize Ray cluster if requested (for multi-app coordination)
        if enable_ray:
            self._init_ray_cluster()

        # Start background VRAM monitoring thread
        self._vram_refresh_thread = threading.Thread(
            target=self._refresh_vram_loop,
            daemon=True,
            name="OllamaPool-VRAM-Monitor"
        )
        self._vram_refresh_thread.start()

        # Start background health check thread for live dashboard updates
        self._health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="OllamaPool-Health-Monitor"
        )
        self._health_check_thread.start()

        logger.info(
            f"OllamaPool initialized with {len(self.nodes)} nodes "
            f"(intelligent_routing={'enabled' if enable_intelligent_routing else 'disabled'}, "
            f"vram_monitoring=enabled, health_checks=enabled, gpu_type={self.vram_monitor.gpu_type})"
        )

        # Auto-register with SOLLOL dashboard if available
        self._auto_register_with_dashboard()

    @classmethod
    def auto_configure(cls, discover_all_nodes: bool = False) -> "OllamaPool":
        """
        Create pool with automatic discovery.

        Args:
            discover_all_nodes: If True, scan full network for ALL nodes (default: False for speed)

        Returns:
            OllamaPool instance ready to use
        """
        return cls(nodes=None, discover_all_nodes=discover_all_nodes)

    def _auto_discover(self):
        """Discover Ollama nodes automatically."""
        from .discovery import discover_ollama_nodes

        if self.discover_all_nodes:
            logger.info("Auto-discovering ALL Ollama nodes on network (full subnet scan)...")
        elif self.exclude_localhost:
            logger.debug("Auto-discovering Ollama nodes (excluding localhost)...")
        else:
            logger.debug("Auto-discovering Ollama nodes...")

        nodes = discover_ollama_nodes(
            timeout=0.5,
            exclude_localhost=self.exclude_localhost,
            discover_all_nodes=self.discover_all_nodes
        )

        with self._lock:
            self.nodes = nodes
            if self.exclude_localhost and len(nodes) == 0:
                logger.info("No remote Ollama nodes found (localhost excluded)")
            else:
                logger.info(f"Auto-discovered {len(nodes)} nodes: {nodes}")

    def _deduplicate_nodes(self):
        """
        Remove duplicate nodes where localhost/127.0.0.1 refers to the same machine as a real IP.

        This handles cases where nodes are loaded from config files or manually added,
        ensuring localhost and the machine's real IP aren't both shown.
        """
        if not self.nodes:
            return

        import socket

        # Get this machine's actual IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("10.255.255.255", 1))  # Doesn't actually connect, just determines route
            local_ip = s.getsockname()[0]
            s.close()
        except:
            return  # Can't determine local IP, skip deduplication

        with self._lock:
            # Check if we have both localhost and the real IP
            has_localhost = any(
                node["host"] in ("localhost", "127.0.0.1")
                for node in self.nodes
            )
            has_real_ip = any(
                node["host"] == local_ip
                for node in self.nodes
            )

            # If we have both, filter out localhost entries
            if has_localhost and has_real_ip:
                original_count = len(self.nodes)
                self.nodes = [
                    node for node in self.nodes
                    if node["host"] not in ("localhost", "127.0.0.1")
                ]
                logger.info(f"🔍 Deduplicated nodes: removed localhost (same as {local_ip})")
                logger.debug(f"   Reduced from {original_count} to {len(self.nodes)} nodes")

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

    def _init_ray_cluster(self):
        """Initialize Ray cluster for multi-app coordination."""
        try:
            import ray
            import json
            import os

            if ray.is_initialized():
                logger.info("✅ Ray already initialized (shared cluster)")
                return

            # Disable Ray memory monitor
            os.environ['RAY_memory_monitor_refresh_ms'] = '0'

            # Try to connect to existing Ray cluster first (multi-app coordination)
            try:
                logger.info("🔍 Attempting to connect to existing Ray cluster...")
                ray.init(address='auto', ignore_reinit_error=True)
                logger.info("✅ Connected to existing Ray cluster")
            except (ConnectionError, Exception) as e:
                # No existing cluster, start a new one
                logger.info("🚀 Starting new Ray cluster for multi-app coordination")

                # Conservative memory settings
                ray.init(
                    ignore_reinit_error=True,
                    dashboard_host="0.0.0.0",
                    dashboard_port=8265,
                    include_dashboard=True,
                    num_cpus=1,  # Minimal workers
                    object_store_memory=256 * 1024 * 1024,  # 256MB for object store
                    _system_config={
                        "automatic_object_spilling_enabled": True,
                        "object_spilling_config": json.dumps({
                            "type": "filesystem",
                            "params": {"directory_path": "/tmp/ray_spill"}
                        })
                    }
                )
                logger.info("📊 Ray dashboard available at http://localhost:8265")
        except Exception as e:
            logger.warning(f"⚠️  Failed to initialize Ray cluster: {e}")
            logger.info("   Continuing without Ray (not required for OllamaPool)")

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
        self, endpoint: str, data: Dict[str, Any], priority: int = 5, timeout: float = 300.0
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

            # Log request to observer
            model = data.get("model", "unknown")
            operation = endpoint.split("/")[-1]  # "chat", "generate", etc.
            log_ollama_request(
                backend=node_key,
                model=model,
                operation=operation,
                priority=priority
            )

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

                    # Log response to observer
                    log_ollama_response(
                        backend=node_key,
                        model=model,
                        latency_ms=latency_ms,
                        status_code=response.status_code
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

                    # Log error to observer
                    log_ollama_error(
                        backend=node_key,
                        model=model,
                        error=f"HTTP {response.status_code}",
                        latency_ms=latency_ms
                    )

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                errors.append(f"{url}: {str(e)}")
                logger.debug(f"Request failed: {e}")
                self._record_failure(node_key, latency_ms)

                # Log error to observer
                log_ollama_error(
                    backend=node_key,
                    model=model,
                    error=str(e),
                    latency_ms=latency_ms
                )

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

    def _auto_register_with_dashboard(self):
        """
        Auto-register with SOLLOL dashboard if one is running.

        This provides automatic observability without requiring manual DashboardClient setup.
        Checks for dashboard on default port (8080) and registers silently if found.
        """
        try:
            import socket
            from .dashboard_client import DashboardClient

            # Check if dashboard is running (quick timeout to avoid blocking startup)
            dashboard_url = "http://localhost:8080"
            test_response = requests.get(f"{dashboard_url}/api/applications", timeout=0.5)

            if test_response.status_code == 200:
                # Dashboard is running, auto-register
                hostname = socket.gethostname()
                # Use custom app_name if provided, otherwise default to "OllamaPool (hostname)"
                app_name = self.app_name or f"OllamaPool ({hostname})"

                # Auto-discover RPC backends for metadata
                try:
                    from .rpc_discovery import auto_discover_rpc_backends
                    rpc_backends = auto_discover_rpc_backends()
                    self._rpc_backends = rpc_backends
                except Exception:
                    self._rpc_backends = []

                self._dashboard_client = DashboardClient(
                    app_name=app_name,
                    router_type="OllamaPool",
                    version="0.9.46",
                    dashboard_url=dashboard_url,
                    metadata={
                        "nodes": len(self.nodes),
                        "intelligent_routing": self.enable_intelligent_routing,
                        "vram_monitoring": True,
                        "health_checks": True,
                        "gpu_type": self.vram_monitor.gpu_type,
                        "model_sharding": len(self._rpc_backends) > 0,  # Simple boolean indicator
                        "rpc_backends": len(self._rpc_backends) if self._rpc_backends else None,
                    },
                    auto_register=True
                )
                logger.info(f"✅ Auto-registered with SOLLOL dashboard at {dashboard_url}")
        except (requests.exceptions.RequestException, ImportError, Exception) as e:
            # Dashboard not running or not available - silent failure is fine
            logger.debug(f"Dashboard auto-registration skipped: {e}")
            self._dashboard_client = None
            self._rpc_backends = []

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

    def _health_check_loop(self):
        """Background thread to periodically check node health for live dashboard updates."""
        logger.debug("Health check monitoring thread started")

        while self._health_check_enabled:
            try:
                time.sleep(self._health_check_interval)

                # Check health of all nodes
                with self._lock:
                    for node in self.nodes:
                        node_key = f"{node['host']}:{node['port']}"

                        if node_key in self.stats["node_performance"]:
                            # Get current performance data
                            perf_data = self.stats["node_performance"][node_key]

                            # Ping node with lightweight /api/tags request
                            start_time = time.time()
                            try:
                                url = f"http://{node['host']}:{node['port']}/api/tags"
                                response = requests.get(url, timeout=2)
                                latency_ms = (time.time() - start_time) * 1000

                                if response.ok:
                                    # Check for status change
                                    old_status = "offline" if not perf_data.get("available", True) else "healthy"
                                    new_status = "healthy"

                                    # Update health status
                                    self.stats["node_performance"][node_key]["available"] = True
                                    self.stats["node_performance"][node_key]["latency_ms"] = latency_ms

                                    # Update health monitor baseline
                                    self.health_monitor.update_baseline(
                                        node_key, latency_ms, is_gpu=True
                                    )

                                    # Log health check to observer
                                    log_node_health_check(
                                        backend=node_key,
                                        status=new_status,
                                        latency_ms=latency_ms
                                    )

                                    # Log to InfluxDB time-series metrics
                                    log_node_health(
                                        node_url=f"http://{node['host']}:{node['port']}",
                                        healthy=True,
                                        latency_ms=latency_ms,
                                        models_loaded=len(node.get('models', [])),
                                        vram_free_mb=perf_data.get('gpu_free_mem', 0),
                                        vram_total_mb=perf_data.get('gpu_total_mem', 0),
                                        failure_count=0
                                    )

                                    # Log status change if needed
                                    if old_status != new_status:
                                        log_node_status_change(
                                            backend=node_key,
                                            old_status=old_status,
                                            new_status=new_status
                                        )

                                    logger.debug(
                                        f"✓ Health check {node_key}: {latency_ms:.0f}ms"
                                    )
                                else:
                                    # Check for status change
                                    old_status = "healthy" if perf_data.get("available", True) else "offline"
                                    new_status = "offline"

                                    # Node returned error
                                    self.stats["node_performance"][node_key]["available"] = False

                                    # Log health check failure to observer
                                    log_node_health_check(
                                        backend=node_key,
                                        status=new_status,
                                        latency_ms=latency_ms,
                                        error=f"HTTP {response.status_code}"
                                    )

                                    # Log to InfluxDB time-series metrics
                                    log_node_health(
                                        node_url=f"http://{node['host']}:{node['port']}",
                                        healthy=False,
                                        latency_ms=latency_ms,
                                        failure_count=perf_data.get('failure_count', 0)
                                    )

                                    # Log status change if needed
                                    if old_status != new_status:
                                        log_node_status_change(
                                            backend=node_key,
                                            old_status=old_status,
                                            new_status=new_status
                                        )

                                    logger.warning(
                                        f"⚠️  Health check {node_key}: HTTP {response.status_code}"
                                    )

                            except requests.exceptions.Timeout:
                                # Node timed out
                                self.stats["node_performance"][node_key]["available"] = False
                                logger.warning(f"⚠️  Health check {node_key}: timeout (>2s)")

                            except requests.exceptions.RequestException as e:
                                # Node unreachable
                                self.stats["node_performance"][node_key]["available"] = False
                                logger.warning(f"⚠️  Health check {node_key}: unreachable ({e})")

            except Exception as e:
                logger.error(f"Health check loop error: {e}")

        logger.debug("Health check monitoring thread stopped")

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
