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

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    import requests
    HTTPX_AVAILABLE = False

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
from .routing_logger import get_routing_logger

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
        enable_gpu_redis: bool = False,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        enable_cache: bool = True,
        cache_max_size: int = 1000,
        cache_ttl: int = 3600,
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
            enable_gpu_redis: Subscribe to accurate GPU stats from Redis (requires gpu_reporter.py on nodes)
            redis_host: Redis server hostname (default: localhost)
            redis_port: Redis server port (default: 6379)
            enable_cache: Enable response caching (default: True)
            cache_max_size: Maximum number of cached responses (default: 1000)
            cache_ttl: Cache TTL in seconds (default: 3600 = 1 hour)
        """
        self.nodes = nodes or []
        self.exclude_localhost = exclude_localhost
        self.discover_all_nodes = discover_all_nodes
        self.app_name = app_name  # Store custom app name for dashboard registration
        self.register_with_dashboard = register_with_dashboard  # Control dashboard registration
        self._lock = threading.Lock()
        self._current_index = 0

        # Persistent HTTP session for connection reuse with HTTP/2 support
        if HTTPX_AVAILABLE:
            # Use httpx with HTTP/2 multiplexing for better performance
            limits = httpx.Limits(
                max_keepalive_connections=max(20, len(self.nodes or []) * 20),
                max_connections=max(50, len(self.nodes or []) * 50),
                keepalive_expiry=30.0
            )

            # Configure retry transport
            transport = httpx.HTTPTransport(
                retries=3,
                limits=limits,
                http2=True  # Enable HTTP/2
            )

            self.session = httpx.Client(
                transport=transport,
                timeout=httpx.Timeout(300.0, connect=10.0),
                follow_redirects=True,
                headers={"Connection": "keep-alive"}
            )
            logger.info("🚀 HTTP/2 multiplexing enabled via httpx")
        else:
            # Fallback to requests (HTTP/1.1 only)
            from requests.adapters import HTTPAdapter
            from urllib3.util.retry import Retry

            self.session = requests.Session()
            self.session.headers.update({"Connection": "keep-alive"})

            retry_strategy = Retry(
                total=3,
                backoff_factor=0.1,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["POST", "GET"]
            )

            adapter = HTTPAdapter(
                pool_connections=max(10, len(self.nodes or []) * 10),
                pool_maxsize=max(20, len(self.nodes or []) * 20),
                max_retries=retry_strategy
            )

            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)
            logger.warning("⚠️  httpx not available, using requests (HTTP/1.1 only)")

        # Initialize async session for async I/O support (httpx only)
        self.async_session = None
        if HTTPX_AVAILABLE:
            limits = httpx.Limits(
                max_keepalive_connections=max(20, len(self.nodes or []) * 20),
                max_connections=max(50, len(self.nodes or []) * 50),
                keepalive_expiry=30.0
            )

            transport = httpx.AsyncHTTPTransport(
                retries=3,
                limits=limits,
                http2=True
            )

            self.async_session = httpx.AsyncClient(
                transport=transport,
                timeout=httpx.Timeout(300.0, connect=10.0),
                follow_redirects=True,
                headers={"Connection": "keep-alive"}
            )
            logger.info("⚡ Async I/O support enabled with httpx AsyncClient")

        # Auto-discover if no nodes provided
        if not self.nodes:
            self._auto_discover()

        # Initialize response cache
        from .response_cache import ResponseCache
        self.cache = ResponseCache(
            max_size=cache_max_size,
            ttl=cache_ttl,
            enabled=enable_cache
        )

        # Initialize intelligent routing
        self.enable_intelligent_routing = enable_intelligent_routing
        self.router = get_router() if enable_intelligent_routing else None

        # Initialize routing event logger (separate channel from regular logs)
        self.routing_logger = get_routing_logger()

        # Initialize health monitoring (FlockParser pattern)
        self.health_monitor = NodeHealthMonitor()

        # Initialize VRAM monitoring for GPU-aware routing
        self.vram_monitor = VRAMMonitor()
        self._vram_refresh_interval = 30  # seconds
        self._vram_refresh_enabled = True

        # Health check configuration
        self._health_check_base_interval = 30  # seconds - base interval for healthy nodes
        self._health_check_enabled = True
        self._adaptive_health_checks = True  # Enable adaptive intervals based on node stability

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

        # Start GPU Redis subscriber if enabled (accurate GPU stats from nodes)
        self.gpu_subscriber = None
        if enable_gpu_redis:
            try:
                from .gpu_redis_subscriber import GPURedisSubscriber
                self.gpu_subscriber = GPURedisSubscriber(
                    pool=self,
                    redis_host=redis_host,
                    redis_port=redis_port
                )
                self.gpu_subscriber.start(interval=5)  # Poll every 5 seconds
                logger.info(f"✅ GPU Redis subscriber enabled (Redis: {redis_host}:{redis_port})")
            except Exception as e:
                logger.warning(f"Failed to start GPU Redis subscriber: {e}")

        logger.info(
            f"OllamaPool initialized with {len(self.nodes)} nodes "
            f"(intelligent_routing={'enabled' if enable_intelligent_routing else 'disabled'}, "
            f"vram_monitoring=enabled, health_checks=enabled, gpu_type={self.vram_monitor.gpu_type}, "
            f"gpu_redis={'enabled' if enable_gpu_redis else 'disabled'})"
        )

        # Auto-register with SOLLOL dashboard if available
        self._auto_register_with_dashboard()

    @classmethod
    def auto_configure(cls, discover_all_nodes: bool = False, **kwargs) -> "OllamaPool":
        """
        Create pool with automatic discovery.

        Args:
            discover_all_nodes: If True, scan full network for ALL nodes (default: False for speed)
            **kwargs: Additional arguments passed to __init__ (e.g., enable_cache, cache_max_size, cache_ttl)

        Returns:
            OllamaPool instance ready to use
        """
        return cls(nodes=None, discover_all_nodes=discover_all_nodes, **kwargs)

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

                        # Log to SOLLOL routing stream (separate from regular logs)
                        model = payload.get('model', 'unknown') if payload else 'unknown'
                        node_url = f"{node['host']}:{node['port']}"
                        self.routing_logger.log_ollama_node_selected(
                            node_url=node_url,
                            model=model,
                            reason=decision['reasoning'],
                            confidence=decision.get('confidence', 0),
                            priority=priority
                        )
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
        # Check cache first (only for non-streaming, deterministic requests)
        cache_key = None
        if self.cache.enabled and not data.get("stream", False):
            cache_key = self.cache.get_cache_key(endpoint, data)
            cached_response = self.cache.get(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache hit for {endpoint} (key={cache_key[:16]}...)")
                return cached_response

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

                # Use persistent session for connection reuse
                response = self.session.post(url, json=data, timeout=timeout)

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

                    # Cache successful response
                    response_data = response.json()
                    if cache_key is not None:
                        self.cache.set(cache_key, response_data)

                    return response_data
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

    def _make_streaming_request(
        self, endpoint: str, data: Dict[str, Any], priority: int = 5, timeout: float = 300.0, node: Optional[Dict[str, Any]] = None
    ):
        """
        Make streaming HTTP request that yields response chunks.

        Args:
            endpoint: API endpoint (e.g., '/api/chat')
            data: Request payload
            priority: Request priority (1-10)
            timeout: Request timeout
            node: Specific node to use (None = auto-select)

        Yields:
            Response chunks as they arrive

        Raises:
            RuntimeError: If streaming fails
        """
        # Ensure stream is enabled in request
        data["stream"] = True

        # Track request
        with self._lock:
            self.stats["total_requests"] += 1

        # Select or use specified node
        if node is None:
            node, routing_decision = self._select_node(payload=data, priority=priority)
        else:
            routing_decision = None

        node_key = f"{node['host']}:{node['port']}"
        url = f"http://{node['host']}:{node['port']}{endpoint}"

        # Track active request
        with self._lock:
            if node_key in self.stats["node_performance"]:
                self.stats["node_performance"][node_key]["active_requests"] = (
                    self.stats["node_performance"][node_key].get("active_requests", 0) + 1
                )

        # Track request start time
        start_time = time.time()

        # Log request to observer
        model = data.get("model", "unknown")
        operation = endpoint.split("/")[-1]
        log_ollama_request(
            backend=node_key,
            model=model,
            operation=operation,
            priority=priority,
            streaming=True
        )

        try:
            logger.debug(f"Streaming request to {url}")

            # Use streaming response
            with self.session.post(url, json=data, timeout=timeout, stream=True) as response:
                if response.status_code == 200:
                    # Track success
                    with self._lock:
                        self.stats["successful_requests"] += 1
                        self.stats["nodes_used"][node_key] = (
                            self.stats["nodes_used"].get(node_key, 0) + 1
                        )

                    logger.info(f"🌊 Streaming from {node_key}...")

                    # Yield chunks as they arrive
                    for line in response.iter_lines():
                        if line:
                            try:
                                chunk = json.loads(line)
                                yield chunk
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to decode streaming chunk: {e}")
                                continue

                    # Calculate total latency
                    latency_ms = (time.time() - start_time) * 1000

                    # Update metrics
                    with self._lock:
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

                    # Log completion
                    log_ollama_response(
                        backend=node_key,
                        model=model,
                        latency_ms=latency_ms,
                        status_code=response.status_code,
                        streaming=True
                    )

                    logger.info(f"✅ Stream complete from {node_key} ({latency_ms:.1f}ms)")

                else:
                    latency_ms = (time.time() - start_time) * 1000
                    self._record_failure(node_key, latency_ms)

                    # Log error
                    log_ollama_error(
                        backend=node_key,
                        model=model,
                        error=f"HTTP {response.status_code}",
                        latency_ms=latency_ms
                    )

                    raise RuntimeError(f"Streaming failed: HTTP {response.status_code}")

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_failure(node_key, latency_ms)

            # Log error
            log_ollama_error(
                backend=node_key,
                model=model,
                error=str(e),
                latency_ms=latency_ms
            )

            raise RuntimeError(f"Streaming request failed: {e}")

        finally:
            # Decrement active request counter
            with self._lock:
                if node_key in self.stats["node_performance"]:
                    self.stats["node_performance"][node_key]["active_requests"] = max(
                        0,
                        self.stats["node_performance"][node_key].get("active_requests", 1) - 1
                    )

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
            # Also detect if GPU is actually being used (not just available)
            total_vram_used_mb = 0
            has_gpu_loaded_models = False
            for model in models:
                size_vram_bytes = model.get("size_vram", 0)
                total_vram_used_mb += size_vram_bytes / (1024 * 1024)
                if size_vram_bytes > 0:
                    has_gpu_loaded_models = True

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
                    # Model is loaded but we don't know GPU capacity (remote node without nvidia-smi)
                    # Assume at least 8GB for modern GPUs (most common: 3060/3070/4060/4070)
                    # If model uses more than 8GB, assume 2GB headroom above that
                    min_reasonable_vram = 8192  # 8GB minimum
                    total_vram_mb = max(min_reasonable_vram, total_vram_used_mb + 2048)
                    logger.debug(f"Unknown GPU capacity, assuming {total_vram_mb:.0f}MB (used: {total_vram_used_mb:.0f}MB)")
                else:
                    # Nothing loaded and unknown GPU - assume small GPU
                    total_vram_mb = 2048  # 2GB conservative default
                    logger.warning("Unknown GPU with no loaded models, assuming 2GB capacity")

            # If no models are using GPU (all size_vram=0), treat as CPU-only node
            # This prevents misidentifying CPU-only nodes that happen to have a GPU installed
            if not has_gpu_loaded_models:
                logger.debug("Node has no GPU-loaded models (all size_vram=0), treating as CPU-only")
                return 0

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

    def _get_adaptive_health_interval(self, node_key: str) -> int:
        """
        Calculate adaptive health check interval based on node stability.

        Args:
            node_key: Node identifier

        Returns:
            Health check interval in seconds
        """
        if not self._adaptive_health_checks:
            return self._health_check_base_interval

        perf_data = self.stats["node_performance"].get(node_key, {})
        total_requests = perf_data.get("total_requests", 0)
        failed_requests = perf_data.get("failed_requests", 0)

        if total_requests == 0:
            return self._health_check_base_interval

        failure_rate = failed_requests / total_requests

        # Adaptive intervals based on stability
        if failure_rate < 0.01:  # Very stable (<1% failures)
            return 60  # Check every 60s
        elif failure_rate < 0.05:  # Stable (<5% failures)
            return self._health_check_base_interval  # Check every 30s
        elif failure_rate < 0.15:  # Degraded (5-15% failures)
            return 15  # Check every 15s
        else:  # Unstable (>15% failures)
            return 5  # Check every 5s

    def _health_check_loop(self):
        """Background thread to periodically check node health for live dashboard updates."""
        logger.debug("Health check monitoring thread started")

        # Track last check time per node for adaptive intervals
        last_check_times = {}

        while self._health_check_enabled:
            try:
                time.sleep(5)  # Base loop interval

                # Check health of all nodes with adaptive intervals
                current_time = time.time()
                with self._lock:
                    for node in self.nodes:
                        node_key = f"{node['host']}:{node['port']}"

                        if node_key not in self.stats["node_performance"]:
                            continue

                        # Get adaptive interval for this node
                        interval = self._get_adaptive_health_interval(node_key)
                        last_check = last_check_times.get(node_key, 0)

                        # Skip if not enough time has passed
                        if current_time - last_check < interval:
                            continue

                        last_check_times[node_key] = current_time

                        # Get current performance data
                        perf_data = self.stats["node_performance"][node_key]

                        # Ping node with lightweight /api/tags request
                        start_time = time.time()
                        try:
                            url = f"http://{node['host']}:{node['port']}/api/tags"
                            response = self.session.get(url, timeout=2)
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
                                    f"✓ Health check {node_key}: {latency_ms:.0f}ms (interval={interval}s)"
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
    ):
        """
        Chat completion with intelligent routing and observability.

        Args:
            model: Model name (e.g., "llama3.2")
            messages: Chat messages
            stream: Stream response token-by-token (default: False)
            priority: Request priority 1-10 (default: 5)
            **kwargs: Additional Ollama parameters

        Returns:
            If stream=False: Chat response dict
            If stream=True: Generator yielding response chunks

        Example (streaming):
            for chunk in pool.chat("llama2", messages, stream=True):
                print(chunk.get("message", {}).get("content", ""), end="")
        """
        data = {"model": model, "messages": messages, "stream": stream, **kwargs}

        if stream:
            return self._make_streaming_request("/api/chat", data, priority=priority)
        else:
            return self._make_request("/api/chat", data, priority=priority)

    def generate(
        self, model: str, prompt: str, stream: bool = False, priority: int = 5, **kwargs
    ):
        """
        Generate text with intelligent routing and observability.

        Args:
            model: Model name
            prompt: Text prompt
            stream: Stream response token-by-token (default: False)
            priority: Request priority 1-10 (default: 5)
            **kwargs: Additional Ollama parameters

        Returns:
            If stream=False: Generation response dict
            If stream=True: Generator yielding response chunks

        Example (streaming):
            for chunk in pool.generate("llama2", "Tell me a story", stream=True):
                print(chunk.get("response", ""), end="")
        """
        data = {"model": model, "prompt": prompt, "stream": stream, **kwargs}

        if stream:
            return self._make_streaming_request("/api/generate", data, priority=priority)
        else:
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

    def embed_batch(
        self,
        model: str,
        inputs: List[str],
        max_workers: Optional[int] = None,
        priority: int = 5,
        use_adaptive: bool = True,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Generate embeddings for multiple texts in parallel across nodes.

        This method provides 10-12x speedup over serial processing by:
        - Parallelizing requests across multiple worker threads
        - Distributing load across available nodes
        - Adaptive parallelism strategy (sequential vs parallel based on cluster state)

        Args:
            model: Embedding model name
            inputs: List of texts to embed
            max_workers: Number of parallel workers (auto-calculated if None)
            priority: Request priority 1-10 (default: 5)
            use_adaptive: Use adaptive parallelism strategy (default: True)
            **kwargs: Additional Ollama parameters

        Returns:
            List of embedding responses in same order as inputs

        Example:
            texts = ["chunk 1", "chunk 2", "chunk 3"]
            embeddings = pool.embed_batch("mxbai-embed-large", texts)
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from .adaptive_parallelism import AdaptiveParallelismStrategy

        batch_size = len(inputs)
        if batch_size == 0:
            return []

        # Use adaptive parallelism strategy if enabled
        if use_adaptive:
            strategy = AdaptiveParallelismStrategy(pool=self)
            should_parallel, reasoning = strategy.should_parallelize(batch_size, model)

            # Log decision
            logger.info(f"🔀 Adaptive strategy: {reasoning['reason']} - {reasoning['detail']}")

            # Auto-calculate optimal workers if not specified
            if max_workers is None:
                max_workers = strategy.get_optimal_workers(batch_size)
        else:
            # Default behavior without adaptive strategy
            if max_workers is None:
                # Use 2 workers per node, capped at batch size
                max_workers = min(len(self.nodes) * 2, batch_size)
                max_workers = max(1, max_workers)  # At least 1 worker

        logger.info(f"🚀 Batch embedding {batch_size} texts with {max_workers} workers across {len(self.nodes)} nodes")

        results = [None] * batch_size
        completed = 0

        def embed_single(index: int, text: str):
            """Embed single text with error handling."""
            try:
                result = self.embed(model, text, priority=priority, **kwargs)
                return index, result, None
            except Exception as e:
                return index, None, e

        # Process in parallel
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(embed_single, i, text): i
                for i, text in enumerate(inputs)
            }

            # Collect results as they complete
            for future in as_completed(futures):
                index, result, error = future.result()
                completed += 1

                # Show progress every 50 embeddings or on completion
                if completed % 50 == 0 or completed == batch_size:
                    progress_pct = (completed * 100) // batch_size
                    logger.info(f"   Progress: {completed}/{batch_size} embeddings ({progress_pct}%)")

                if error:
                    logger.error(f"⚠️  Error embedding text {index}: {error}")
                else:
                    results[index] = result

        # Count successful embeddings
        success_count = sum(1 for r in results if r is not None)
        logger.info(f"✅ Batch complete: {success_count}/{batch_size} embeddings successful")

        return results

    # Async I/O methods (requires httpx)

    async def chat_async(
        self,
        model: str,
        messages: List[Dict[str, str]],
        priority: int = 5,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Async chat completion with non-blocking I/O.

        Args:
            model: Model name
            messages: Chat messages
            priority: Request priority 1-10
            **kwargs: Additional Ollama parameters

        Returns:
            Chat response dict

        Example:
            response = await pool.chat_async("llama2", messages)
        """
        if not self.async_session:
            raise RuntimeError("Async I/O requires httpx - install with: pip install httpx")

        data = {"model": model, "messages": messages, "stream": False, **kwargs}
        return await self._make_request_async("/api/chat", data, priority=priority)

    async def generate_async(
        self,
        model: str,
        prompt: str,
        priority: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Async text generation with non-blocking I/O.

        Args:
            model: Model name
            prompt: Text prompt
            priority: Request priority 1-10
            **kwargs: Additional Ollama parameters

        Returns:
            Generation response dict

        Example:
            response = await pool.generate_async("llama2", "Tell me a story")
        """
        if not self.async_session:
            raise RuntimeError("Async I/O requires httpx - install with: pip install httpx")

        data = {"model": model, "prompt": prompt, "stream": False, **kwargs}
        return await self._make_request_async("/api/generate", data, priority=priority)

    async def embed_async(
        self,
        model: str,
        input: str,
        priority: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Async embedding generation with non-blocking I/O.

        Args:
            model: Embedding model name
            input: Text to embed
            priority: Request priority 1-10
            **kwargs: Additional Ollama parameters

        Returns:
            Embedding response dict

        Example:
            response = await pool.embed_async("mxbai-embed-large", "Hello world")
        """
        if not self.async_session:
            raise RuntimeError("Async I/O requires httpx - install with: pip install httpx")

        data = {"model": model, "input": input, **kwargs}
        return await self._make_request_async("/api/embed", data, priority=priority)

    async def _make_request_async(
        self,
        endpoint: str,
        data: Dict[str, Any],
        priority: int = 5,
        timeout: float = 300.0
    ) -> Dict[str, Any]:
        """
        Make async HTTP request with intelligent routing (simplified version).

        Args:
            endpoint: API endpoint
            data: Request payload
            priority: Request priority
            timeout: Request timeout

        Returns:
            Response data
        """
        # Check cache first
        cache_key = None
        if self.cache.enabled and not data.get("stream", False):
            cache_key = self.cache.get_cache_key(endpoint, data)
            cached_response = self.cache.get(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache hit for {endpoint} (async)")
                return cached_response

        # Track request
        with self._lock:
            self.stats["total_requests"] += 1

        # Select node
        node, routing_decision = self._select_node(payload=data, priority=priority)
        node_key = f"{node['host']}:{node['port']}"
        url = f"http://{node['host']}:{node['port']}{endpoint}"

        # Track active request
        with self._lock:
            if node_key in self.stats["node_performance"]:
                self.stats["node_performance"][node_key]["active_requests"] = (
                    self.stats["node_performance"][node_key].get("active_requests", 0) + 1
                )

        start_time = time.time()

        # Log request
        model = data.get("model", "unknown")
        operation = endpoint.split("/")[-1]
        log_ollama_request(
            backend=node_key,
            model=model,
            operation=operation,
            priority=priority,
            async_io=True
        )

        try:
            # Make async request
            response = await self.async_session.post(url, json=data, timeout=timeout)
            latency_ms = (time.time() - start_time) * 1000

            if response.status_code == 200:
                # Success - update metrics
                with self._lock:
                    self.stats["successful_requests"] += 1
                    self.stats["nodes_used"][node_key] = (
                        self.stats["nodes_used"].get(node_key, 0) + 1
                    )

                    perf = self.stats["node_performance"][node_key]
                    perf["total_requests"] += 1

                    if perf["total_requests"] == 1:
                        perf["latency_ms"] = latency_ms
                    else:
                        perf["latency_ms"] = (
                            perf["latency_ms"] * (perf["total_requests"] - 1) + latency_ms
                        ) / perf["total_requests"]

                    perf["success_rate"] = (
                        perf["total_requests"] - perf["failed_requests"]
                    ) / perf["total_requests"]

                logger.info(f"✅ Async request succeeded: {node_key} ({latency_ms:.1f}ms)")

                # Log response
                log_ollama_response(
                    backend=node_key,
                    model=model,
                    latency_ms=latency_ms,
                    status_code=response.status_code,
                    async_io=True
                )

                # Cache and return
                response_data = response.json()
                if cache_key is not None:
                    self.cache.set(cache_key, response_data)

                return response_data
            else:
                self._record_failure(node_key, latency_ms)
                log_ollama_error(
                    backend=node_key,
                    model=model,
                    error=f"HTTP {response.status_code}",
                    latency_ms=latency_ms
                )
                raise RuntimeError(f"Request failed: HTTP {response.status_code}")

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self._record_failure(node_key, latency_ms)
            log_ollama_error(
                backend=node_key,
                model=model,
                error=str(e),
                latency_ms=latency_ms
            )
            raise RuntimeError(f"Async request failed: {e}")

        finally:
            # Decrement active request counter
            with self._lock:
                if node_key in self.stats["node_performance"]:
                    self.stats["node_performance"][node_key]["active_requests"] = max(
                        0,
                        self.stats["node_performance"][node_key].get("active_requests", 1) - 1
                    )

    def warm_model(self, model: str, node: Optional[Dict[str, Any]] = None) -> bool:
        """
        Warm up a model by pre-loading it on a node.

        This sends a minimal inference request to load the model into VRAM,
        reducing first-request latency by 1-5 seconds.

        Args:
            model: Model name to warm up
            node: Specific node to warm (None = all nodes)

        Returns:
            True if successful, False otherwise
        """
        try:
            target_nodes = [node] if node else self.nodes

            for n in target_nodes:
                node_key = f"{n['host']}:{n['port']}"
                logger.info(f"🔥 Warming model '{model}' on {node_key}...")

                # Send minimal generation request to load model
                try:
                    result = self._make_request(
                        "/api/generate",
                        {
                            "model": model,
                            "prompt": "",  # Empty prompt
                            "max_tokens": 1,  # Minimal tokens
                            "stream": False,
                        },
                        node=n,
                        timeout=30,  # Allow time for model loading
                    )

                    if result:
                        logger.info(f"✅ Model '{model}' warmed on {node_key}")
                    else:
                        logger.warning(f"⚠️  Failed to warm model '{model}' on {node_key}")
                        return False

                except Exception as e:
                    logger.warning(f"⚠️  Error warming model '{model}' on {node_key}: {e}")
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ Error in warm_model: {e}")
            return False

    def warm_models(self, models: List[str], parallel: bool = True) -> Dict[str, bool]:
        """
        Warm up multiple models across all nodes.

        This pre-loads models to reduce cold-start latency on first use.

        Args:
            models: List of model names to warm
            parallel: Warm models in parallel (default: True)

        Returns:
            Dict mapping model names to success status

        Example:
            pool.warm_models(["llama2", "codellama", "mistral"])
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = {}

        if not models:
            return results

        logger.info(f"🔥 Warming {len(models)} models across {len(self.nodes)} nodes...")

        if parallel:
            # Warm models in parallel
            with ThreadPoolExecutor(max_workers=min(len(models), 5)) as executor:
                futures = {
                    executor.submit(self.warm_model, model): model
                    for model in models
                }

                for future in as_completed(futures):
                    model = futures[future]
                    try:
                        success = future.result()
                        results[model] = success
                    except Exception as e:
                        logger.error(f"Error warming model {model}: {e}")
                        results[model] = False
        else:
            # Warm models sequentially
            for model in models:
                results[model] = self.warm_model(model)

        success_count = sum(1 for v in results.values() if v)
        logger.info(f"✅ Model warming complete: {success_count}/{len(models)} successful")

        return results

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
                "http2_enabled": HTTPX_AVAILABLE,
                "async_io_enabled": self.async_session is not None,
                "cache": self.cache.get_stats(),
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

    # Cache management methods
    def clear_cache(self) -> None:
        """Clear all cached responses."""
        self.cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_stats()

    def invalidate_cache_by_model(self, model: str) -> int:
        """
        Invalidate all cached responses for a specific model.

        Args:
            model: Model name

        Returns:
            Number of entries invalidated
        """
        return self.cache.invalidate_by_model(model)

    def export_cache(self) -> Dict[str, Any]:
        """
        Export cache for persistence.

        Returns:
            Cache data dictionary
        """
        return self.cache.export_cache()

    def import_cache(self, data: Dict[str, Any]) -> int:
        """
        Import cache from exported data.

        Args:
            data: Cache data from export_cache()

        Returns:
            Number of entries imported
        """
        return self.cache.import_cache(data)

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

        # Stop health check thread
        self._health_check_enabled = False
        if self._health_check_thread and self._health_check_thread.is_alive():
            self._health_check_thread.join(timeout=5.0)
            if self._health_check_thread.is_alive():
                logger.warning("Health check thread did not stop within timeout")
            else:
                logger.info("Health check thread stopped successfully")

        # Stop GPU subscriber if enabled
        if self.gpu_subscriber:
            try:
                self.gpu_subscriber.stop()
                logger.info("GPU subscriber stopped successfully")
            except Exception as e:
                logger.warning(f"Error stopping GPU subscriber: {e}")

        # Close persistent HTTP sessions
        if hasattr(self, 'session'):
            try:
                self.session.close()
                logger.info("HTTP session closed successfully")
            except Exception as e:
                logger.warning(f"Error closing HTTP session: {e}")

        if hasattr(self, 'async_session') and self.async_session:
            try:
                # Close async session (httpx AsyncClient)
                import asyncio
                loop = None
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                if loop.is_running():
                    # Schedule close task
                    asyncio.create_task(self.async_session.aclose())
                else:
                    # Run close in event loop
                    loop.run_until_complete(self.async_session.aclose())

                logger.info("Async HTTP session closed successfully")
            except Exception as e:
                logger.warning(f"Error closing async HTTP session: {e}")

        logger.info("OllamaPool stopped")

    def __del__(self):
        """Cleanup when object is destroyed."""
        try:
            # Close session if it exists
            if hasattr(self, 'session'):
                self.session.close()
        except Exception:
            pass  # Suppress errors during cleanup

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
