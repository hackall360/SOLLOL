"""
FastAPI gateway with three distribution modes.

This is the ONLY Ollama-compatible gateway with:
- Task Distribution: Intelligent load balancing across Ollama nodes with Ray parallelism
- Batch Processing: Distributed batch operations via Dask (embeddings, bulk inference)
- Model Sharding: Distribute large models via llama.cpp RPC backends (single model, multiple nodes)
- All modes can be enabled simultaneously for optimal performance
- 7-factor intelligent routing engine
- Automatic GGUF extraction from Ollama storage
- Zero-config setup
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import ray
from dask.distributed import Client as DaskClient
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from sollol.adaptive_parallelism import AdaptiveParallelismStrategy
from sollol.autobatch import autobatch_loop
from sollol.circuit_breaker import CircuitBreaker
from sollol.embedding_cache import EmbeddingCache
from sollol.graceful_shutdown import GracefulShutdown, GracefulShutdownMiddleware
from sollol.hybrid_router import HybridRouter
from sollol.pool import OllamaPool
from sollol.rate_limiter import RateLimiter, RateLimitExceeded
from sollol.retry_logic import RetryConfig, RetryableRequest
from sollol.vram_monitor import VRAMMonitor
from sollol.workers import OllamaWorker

logger = logging.getLogger(__name__)

# Version from pyproject.toml
__version__ = "0.5.0"


class SOLLOLHeadersMiddleware(BaseHTTPMiddleware):
    """Add SOLLOL identification headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Powered-By"] = "SOLLOL"
        response.headers["X-SOLLOL-Version"] = __version__
        return response


app = FastAPI(
    title="SOLLOL Gateway",
    description="Two independent distribution modes: task distribution (load balancing) OR model sharding (distributed inference) OR BOTH",
)

# Add SOLLOL identification headers to all responses
app.add_middleware(SOLLOLHeadersMiddleware)

# Global instances
_ollama_pool: Optional[OllamaPool] = None
_hybrid_router: Optional[HybridRouter] = None
_ray_actors: List = []
_dask_client: Optional[DaskClient] = None
_vram_monitor: Optional[VRAMMonitor] = None
_adaptive_parallelism: Optional[AdaptiveParallelismStrategy] = None
_embedding_cache: Optional[EmbeddingCache] = None
_rate_limiter: Optional[RateLimiter] = None
_graceful_shutdown: Optional[GracefulShutdown] = None
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_retry_config: Optional[RetryConfig] = None


def start_api(
    port: int = 11434,
    rpc_backends: Optional[List[Dict]] = None,
    ollama_nodes: Optional[List[Dict]] = None,
    ray_workers: int = 4,
    dask_workers: int = 2,
    enable_batch_processing: bool = True,
    autobatch_interval: int = 60,
):
    """
    Start SOLLOL gateway - Intelligent load balancer for Ollama clusters.

    SOLLOL runs on Ollama's port (11434) and routes requests to backend Ollama nodes.
    It provides:

    THREE DISTRIBUTION MODES (can be used together or separately):
    1. Task Distribution - Intelligent routing + Ray parallelism across Ollama nodes
    2. Batch Processing - Dask distributed batch operations (embeddings, bulk inference)
    3. Model Sharding - Distribute large models via llama.cpp RPC backends (single model across nodes)

    💡 Enable ALL THREE for maximum performance!

    Features:
    - 7-factor intelligent routing engine
    - Ray actors for parallel request execution
    - Dask for distributed batch processing
    - Model sharding for 70B+ models via llama.cpp
    - Automatic GGUF extraction from Ollama storage
    - Zero-config auto-discovery

    ENVIRONMENT CONFIGURATION:
        SOLLOL_PORT or PORT - Gateway port (default: 11434)
        SOLLOL_RAY_WORKERS or RAY_WORKERS - Ray actors for parallel execution (default: 4)
        SOLLOL_DASK_WORKERS or DASK_WORKERS - Dask workers for batch processing (default: 2)
        SOLLOL_BATCH_PROCESSING - Enable batch processing: true/false (default: true)
        SOLLOL_AUTOBATCH_INTERVAL or AUTOBATCH_INTERVAL - Autobatch cycle seconds (default: 60)
        RPC_BACKENDS - Comma-separated RPC servers for model sharding (e.g., "10.0.0.1:50052,10.0.0.2:50052")
        OLLAMA_NODES - Comma-separated Ollama nodes for task distribution (e.g., "10.0.0.3:11434,10.0.0.4:11434")

        Note: SOLLOL_* prefixed vars take precedence over legacy names for clarity

    Args:
        port: Port to run gateway on (default: 11434 - Ollama's port)
        rpc_backends: List of RPC backend dicts for model sharding [{"host": "ip", "port": 50052}]
        ollama_nodes: List of Ollama node dicts for task distribution (auto-discovers if None)
        ray_workers: Number of Ray actors for parallel execution (default: 4)
        dask_workers: Number of Dask workers for batch processing (default: 2)
        enable_batch_processing: Enable Dask batch processing and autobatch (default: True)
        autobatch_interval: Seconds between autobatch cycles (default: 60)

    Example:
        # Zero-config (auto-discovers everything):
        python -m sollol.gateway

        # Environment variable configuration:
        export SOLLOL_PORT=8000
        export SOLLOL_RAY_WORKERS=8
        export SOLLOL_DASK_WORKERS=4
        export SOLLOL_BATCH_PROCESSING=false
        export RPC_BACKENDS="192.168.1.10:50052,192.168.1.11:50052"
        export OLLAMA_NODES="192.168.1.20:11434,192.168.1.21:11434"
        python -m sollol.gateway

        # Docker/Kubernetes ready:
        docker run -e SOLLOL_RAY_WORKERS=16 sollol:latest

    Note: SOLLOL runs on port 11434 (Ollama's port). Make sure local Ollama
          is either disabled or running on a different port (e.g., 11435).
    """
    global _ollama_pool, _hybrid_router, _ray_actors, _dask_client, _vram_monitor, _adaptive_parallelism, _embedding_cache, _rate_limiter, _graceful_shutdown, _circuit_breakers, _retry_config

    # Parse ALL configuration from environment variables (for programmatic/container deployments)
    port = int(os.getenv("SOLLOL_PORT", os.getenv("PORT", port)))
    ray_workers = int(os.getenv("SOLLOL_RAY_WORKERS", os.getenv("RAY_WORKERS", ray_workers)))
    dask_workers = int(os.getenv("SOLLOL_DASK_WORKERS", os.getenv("DASK_WORKERS", dask_workers)))
    enable_batch_processing = os.getenv("SOLLOL_BATCH_PROCESSING", str(enable_batch_processing)).lower() in ("true", "1", "yes")
    autobatch_interval = int(os.getenv("SOLLOL_AUTOBATCH_INTERVAL", os.getenv("AUTOBATCH_INTERVAL", autobatch_interval)))

    # Initialize Ray cluster for parallel execution
    logger.info("🚀 Initializing Ray cluster for parallel request execution...")
    ray.init(ignore_reinit_error=True, logging_level=logging.WARNING)

    _ray_actors = [OllamaWorker.remote() for _ in range(ray_workers)]
    logger.info(f"✅ Ray initialized with {len(_ray_actors)} worker actors for parallel execution")

    # Initialize Dask for batch processing
    if enable_batch_processing:
        logger.info("🔄 Initializing Dask for batch processing...")
        try:
            from dask.distributed import LocalCluster

            cluster = LocalCluster(
                n_workers=dask_workers,
                threads_per_worker=4,
                processes=False,  # Use threads
                silence_logs=logging.WARNING,
            )
            _dask_client = DaskClient(cluster)
            logger.info(f"✅ Dask initialized with {dask_workers} workers for batch operations")

            # Start autobatch loop
            asyncio.create_task(autobatch_loop(_dask_client, interval_sec=autobatch_interval))
            logger.info(f"✅ Autobatch loop started (interval: {autobatch_interval}s)")
        except Exception as e:
            logger.warning(f"⚠️  Dask initialization failed: {e}")
            logger.warning("    Batch processing disabled")
            _dask_client = None

    # Parse RPC backends from environment if not provided
    if rpc_backends is None:
        rpc_env = os.getenv("RPC_BACKENDS", "")
        if rpc_env:
            rpc_backends = []
            for backend_str in rpc_env.split(","):
                backend_str = backend_str.strip()
                if ":" in backend_str:
                    host, port_str = backend_str.rsplit(":", 1)
                    rpc_backends.append({"host": host, "port": int(port_str)})
                else:
                    rpc_backends.append({"host": backend_str, "port": 50052})
        else:
            # Auto-discover RPC backends if not explicitly configured
            logger.info("🔍 Auto-discovering RPC backends on network (for model sharding)...")
            from sollol.rpc_discovery import auto_discover_rpc_backends

            rpc_backends = auto_discover_rpc_backends()

            if rpc_backends:
                logger.info(
                    f"✅ Auto-discovered {len(rpc_backends)} RPC backends for model sharding"
                )
            else:
                logger.info("📡 No RPC backends found (model sharding disabled)")

    # Initialize VRAM monitoring (nvidia-smi/rocm-smi)
    logger.info("🖥️  Initializing VRAM monitoring...")
    _vram_monitor = VRAMMonitor()
    if _vram_monitor.gpu_type != "none":
        logger.info(f"✅ VRAM monitoring enabled ({_vram_monitor.gpu_type.upper()} GPU detected)")
    else:
        logger.info("📊 No GPU detected (VRAM monitoring disabled, CPU-only mode)")

    # Initialize embedding cache
    logger.info("💾 Initializing embedding cache...")
    use_redis = os.getenv("SOLLOL_USE_REDIS_CACHE", "false").lower() in ("true", "1", "yes")
    redis_url = os.getenv("SOLLOL_REDIS_URL", "redis://localhost:6379/0")
    _embedding_cache = EmbeddingCache(use_redis=use_redis, redis_url=redis_url)
    logger.info(f"✅ Embedding cache initialized (backend: {'redis' if use_redis else 'memory'})")

    # Create Ollama pool for task distribution (auto-discovers remote nodes, excludes localhost)
    logger.info("🔍 Initializing Ollama pool (for task distribution / load balancing)...")
    logger.info("   Excluding localhost (SOLLOL running on this port)")
    _ollama_pool = OllamaPool(nodes=ollama_nodes, exclude_localhost=True)

    if len(_ollama_pool.nodes) > 0:
        logger.info(
            f"✅ Ollama pool initialized with {len(_ollama_pool.nodes)} remote nodes for task distribution"
        )
    else:
        logger.info("📡 No remote Ollama nodes found (task distribution disabled)")
        logger.info("   To enable task distribution: run Ollama on other machines in your network")

    # Initialize adaptive parallelism strategy
    logger.info("🔀 Initializing adaptive parallelism strategy...")
    _adaptive_parallelism = AdaptiveParallelismStrategy(_ollama_pool)
    logger.info("✅ Adaptive parallelism enabled (sequential vs parallel decision logic)")

    # Initialize resilience features
    logger.info("🛡️  Initializing resilience features...")

    # Rate limiter
    global_rate = float(os.getenv("SOLLOL_GLOBAL_RATE_LIMIT", "100"))  # 100 req/sec
    per_node_rate = float(os.getenv("SOLLOL_PER_NODE_RATE_LIMIT", "50"))  # 50 req/sec per node
    _rate_limiter = RateLimiter(
        global_rate=global_rate,
        global_capacity=int(global_rate * 2),  # Burst capacity
        per_node_rate=per_node_rate,
        per_node_capacity=int(per_node_rate * 2),
    )
    logger.info(f"✅ Rate limiter enabled (global: {global_rate}/s, per-node: {per_node_rate}/s)")

    # Retry configuration
    max_retries = int(os.getenv("SOLLOL_MAX_RETRIES", "3"))
    _retry_config = RetryConfig(max_retries=max_retries, base_delay=1.0, max_delay=30.0)
    logger.info(f"✅ Retry logic enabled (max retries: {max_retries}, exponential backoff)")

    # Circuit breakers (will be created per-node on first request)
    logger.info("✅ Circuit breakers enabled (failure threshold: 5, timeout: 60s)")

    # Graceful shutdown
    shutdown_timeout = int(os.getenv("SOLLOL_SHUTDOWN_TIMEOUT", "30"))
    _graceful_shutdown = GracefulShutdown(timeout=shutdown_timeout)
    _graceful_shutdown.setup_signal_handlers()
    logger.info(f"✅ Graceful shutdown enabled (timeout: {shutdown_timeout}s)")

    # Create hybrid router with model sharding support if RPC backends configured
    if rpc_backends:
        logger.info(f"🚀 Enabling MODEL SHARDING with {len(rpc_backends)} RPC backends")
        logger.info("   Large models (70B+) will be distributed via llama.cpp")
        logger.info("   GGUFs will be auto-extracted from Ollama storage!")
        _hybrid_router = HybridRouter(
            ollama_pool=_ollama_pool,
            rpc_backends=rpc_backends,
            enable_distributed=True,  # Enables model sharding
        )
        logger.info("✅ Hybrid routing enabled: small → Ollama, large → llama.cpp sharding")
    else:
        logger.info("📡 Running in Ollama-only mode (model sharding disabled)")
        logger.info("   Set RPC_BACKENDS environment variable to enable model sharding")
        _hybrid_router = None

    # Start FastAPI server
    import uvicorn

    logger.info(f"🌐 Starting gateway on port {port}")
    logger.info(f"   API docs: http://localhost:{port}/docs")
    logger.info(f"   Health check: http://localhost:{port}/api/health")

    uvicorn.run(app, host="0.0.0.0", port=port)


@app.post("/api/chat")
async def chat_endpoint(request: Request):
    """
    Chat completion with THREE distribution modes + production resilience.

    THREE ROUTING MODES:
    1. Intelligent Task Distribution - 7-factor routing + Ray parallel execution (Ollama nodes)
    2. Model Sharding - Large models (70B+) distributed via llama.cpp RPC backends
    3. Hybrid - Combines both based on model size

    Features:
    - 7-factor intelligent routing (performance, load, resources, priority, specialization)
    - Ray actors for parallel request execution
    - Automatic GGUF extraction from Ollama storage (for model sharding)
    - Zero configuration needed
    - Transparent routing metadata in response
    - Production resilience: rate limiting, circuit breaker, retry logic, graceful shutdown

    Request body:
        {
            "model": "llama3.2",  # Small model → intelligent routing + Ray execution
            # or "llama3.1:405b" for model sharding across RPC backends
            "messages": [
                {"role": "user", "content": "Hello!"}
            ]
        }

    Returns:
        {
            "model": "...",
            "message": {"role": "assistant", "content": "..."},
            "done": true,
            "_sollol_routing": {
                "mode": "ray-parallel" or "llama.cpp-distributed",
                "node": "selected host",
                "reasoning": "intelligent routing decision",
                ...
            }
        }
    """
    # Track request for graceful shutdown
    if _graceful_shutdown:
        try:
            _graceful_shutdown.increment_requests()
        except Exception as e:
            # Server is shutting down
            raise HTTPException(status_code=503, detail=str(e))

    try:
        # Rate limiting check
        if _rate_limiter:
            allowed, reason = _rate_limiter.allow_request(node=None)
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {reason}",
                    headers={"Retry-After": "1"}
                )

        if not _ollama_pool:
            raise HTTPException(status_code=503, detail="Gateway not initialized")

        payload = await request.json()
        model = payload.get("model", "llama3.2")
        messages = payload.get("messages", [])

        if not messages:
            raise HTTPException(status_code=400, detail="No messages provided")
        # Check if this should use llama.cpp model sharding (large models)
        if _hybrid_router:
            # HybridRouter decides: Ollama pool OR llama.cpp based on model size
            result = await _hybrid_router.route_request(model, messages)

            # If llama.cpp was used, it returns with routing metadata
            if isinstance(result, dict) and "_routing" in result:
                # llama.cpp model sharding was used
                result["_sollol_routing"] = {
                    "mode": "llama.cpp-distributed",
                    **result.get("_routing", {})
                }
                return result

            # Otherwise result is from Ollama pool, fall through to Ray execution

        # Adaptive parallelism decision: should we use Ray parallel or sequential?
        batch_size = len(messages) if isinstance(messages, list) else 1
        should_parallel, parallelism_reasoning = False, {}

        if _adaptive_parallelism:
            should_parallel, parallelism_reasoning = _adaptive_parallelism.should_parallelize(
                batch_size=batch_size
            )
            logger.info(f"🔀 Adaptive parallelism: {parallelism_reasoning.get('reason', 'unknown')}")
        else:
            should_parallel = True  # Default to parallel if no strategy

        # Use intelligent routing + Ray parallel OR sequential execution
        # OllamaPool selects best node using 7-factor scoring
        node, decision = _ollama_pool._select_node(payload=payload, priority=5)

        if not node:
            raise HTTPException(status_code=503, detail="No Ollama nodes available")

        node_key = f"{node['host']}:{node['port']}"

        # Get or create circuit breaker for this node
        if node_key not in _circuit_breakers:
            _circuit_breakers[node_key] = CircuitBreaker(
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=60,
                half_open_max_requests=3
            )
        breaker = _circuit_breakers[node_key]

        # Define execution function for circuit breaker + retry wrapping
        async def execute_request():
            if should_parallel and _ray_actors:
                # PARALLEL: Submit to Ray actor
                import random
                actor = random.choice(_ray_actors)
                result_future = actor.chat.remote(payload, node_key)
                return await result_future, "ray-parallel", str(actor)
            else:
                # SEQUENTIAL: Direct execution on fastest node
                result = _ollama_pool.chat(model=model, messages=messages)
                return result, "sequential", "none"

        # Execute with circuit breaker + retry logic
        if _retry_config:
            retrier = RetryableRequest(_retry_config)
            result, execution_mode, actor_info = await retrier.execute_async(
                lambda: breaker.call_async(execute_request),
                exceptions=(Exception,)
            )
        else:
            result, execution_mode, actor_info = await breaker.call_async(execute_request)

        # Add routing metadata
        if isinstance(result, dict):
            result["_sollol_routing"] = {
                "mode": execution_mode,
                "node": node_key,
                "actor_id": actor_info,
                "intelligent_routing": decision if decision else {"reasoning": "round-robin fallback"},
                "adaptive_parallelism": parallelism_reasoning
            }

        return result

    except FileNotFoundError as e:
        # Model not found in Ollama storage
        raise HTTPException(
            status_code=404, detail=f"Model not found: {str(e)}. Pull with: ollama pull {model}"
        )
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Decrement request counter for graceful shutdown
        if _graceful_shutdown:
            _graceful_shutdown.decrement_requests()


@app.post("/api/generate")
async def generate_endpoint(request: Request):
    """
    Text generation endpoint (non-chat) with production resilience.

    Request body:
        {
            "model": "llama3.2",
            "prompt": "Once upon a time"
        }
    """
    # Track request for graceful shutdown
    if _graceful_shutdown:
        try:
            _graceful_shutdown.increment_requests()
        except Exception as e:
            raise HTTPException(status_code=503, detail=str(e))

    try:
        # Rate limiting check
        if _rate_limiter:
            allowed, reason = _rate_limiter.allow_request(node=None)
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {reason}",
                    headers={"Retry-After": "1"}
                )

        if not _ollama_pool:
            raise HTTPException(status_code=503, detail="Gateway not initialized")

        payload = await request.json()
        model = payload.get("model", "llama3.2")
        prompt = payload.get("prompt", "")

        if not prompt:
            raise HTTPException(status_code=400, detail="No prompt provided")

        # Select best node
        node, decision = _ollama_pool._select_node(payload=payload, priority=5)
        if not node:
            raise HTTPException(status_code=503, detail="No Ollama nodes available")

        node_key = f"{node['host']}:{node['port']}"

        # Get or create circuit breaker for this node
        if node_key not in _circuit_breakers:
            _circuit_breakers[node_key] = CircuitBreaker(
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=60,
                half_open_max_requests=3
            )
        breaker = _circuit_breakers[node_key]

        # Define execution function
        async def execute_request():
            return _ollama_pool.generate(model=model, prompt=prompt)

        # Execute with circuit breaker + retry logic
        if _retry_config:
            retrier = RetryableRequest(_retry_config)
            result = await retrier.execute_async(
                lambda: breaker.call_async(execute_request),
                exceptions=(Exception,)
            )
        else:
            result = await breaker.call_async(execute_request)

        return result
    except Exception as e:
        logger.error(f"Generate endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Decrement request counter for graceful shutdown
        if _graceful_shutdown:
            _graceful_shutdown.decrement_requests()


@app.get("/api/health")
async def health_check():
    """
    Check health of gateway and all distribution backends.

    Returns status for:
    - Service identification (SOLLOL vs native Ollama)
    - Ray Parallel Execution (concurrent request handling)
    - Dask Batch Processing (distributed bulk operations)
    - Intelligent Task Distribution (7-factor routing)
    - Model Sharding (llama.cpp RPC backends for large models)

    This endpoint can be used to detect if SOLLOL is running vs native Ollama:
    - Check for "X-Powered-By: SOLLOL" header
    - Check response contains "service": "SOLLOL"
    """
    health_status = {
        "status": "healthy",
        "service": "SOLLOL",
        "version": __version__,
        "ray_parallel_execution": {
            "enabled": len(_ray_actors) > 0,
            "actors": len(_ray_actors),
            "description": "Ray actors for concurrent request handling",
        },
        "dask_batch_processing": {
            "enabled": _dask_client is not None,
            "workers": 0,
            "description": "Distributed batch operations via Dask",
        },
        "intelligent_routing": {
            "enabled": _ollama_pool is not None and _ollama_pool.enable_intelligent_routing,
            "factors": "7-factor scoring (availability, resources, performance, load, priority, specialization, duration)",
            "description": "Context-aware task routing engine",
        },
        "task_distribution": {
            "enabled": _ollama_pool is not None and len(_ollama_pool.nodes) > 0,
            "ollama_nodes": len(_ollama_pool.nodes) if _ollama_pool else 0,
            "description": "Load balance across Ollama nodes",
        },
        "model_sharding": {
            "enabled": _hybrid_router is not None,
            "coordinator_running": False,
            "rpc_backends": 0,
            "description": "Distribute large models via llama.cpp RPC backends",
        },
        "timestamp": datetime.now().isoformat(),
    }

    # Get Dask worker count
    if _dask_client:
        try:
            health_status["dask_batch_processing"]["workers"] = len(_dask_client.scheduler_info()["workers"])
        except:
            pass

    # Check model sharding coordinator status
    if _hybrid_router and _hybrid_router.coordinator:
        health_status["model_sharding"]["coordinator_running"] = True
        health_status["model_sharding"]["rpc_backends"] = len(
            _hybrid_router.coordinator.rpc_backends
        )
        health_status["model_sharding"]["model_loaded"] = _hybrid_router.coordinator_model

    # Add VRAM monitoring status
    if _vram_monitor:
        local_vram = _vram_monitor.get_local_vram_info()
        health_status["vram_monitoring"] = {
            "enabled": local_vram is not None,
            "gpu_type": _vram_monitor.gpu_type,
            "local_gpu": local_vram if local_vram else {},
        }

    # Add adaptive parallelism status
    if _adaptive_parallelism:
        health_status["adaptive_parallelism"] = {
            "enabled": True,
            "description": "Sequential vs parallel decision logic based on cluster state",
        }

    # Add embedding cache status
    if _embedding_cache:
        cache_stats = _embedding_cache.get_stats()
        health_status["embedding_cache"] = {
            "enabled": True,
            "backend": cache_stats.get("backend", "memory"),
            **cache_stats,
        }

    # Add resilience features status
    health_status["resilience"] = {
        "rate_limiting": {
            "enabled": _rate_limiter is not None,
            "global_rate": _rate_limiter.global_limiter.rate if _rate_limiter and _rate_limiter.global_limiter else None,
            "per_node_rate": _rate_limiter.per_node_rate if _rate_limiter else None,
        },
        "circuit_breaker": {
            "enabled": True,
            "nodes_tracked": len(_circuit_breakers),
            "failure_threshold": 5,
            "timeout_seconds": 60,
        },
        "retry_logic": {
            "enabled": _retry_config is not None,
            "max_retries": _retry_config.max_retries if _retry_config else None,
            "base_delay": _retry_config.base_delay if _retry_config else None,
            "exponential_backoff": True,
        },
        "graceful_shutdown": {
            "enabled": _graceful_shutdown is not None,
            "is_shutting_down": _graceful_shutdown.is_shutting_down if _graceful_shutdown else False,
            "active_requests": _graceful_shutdown.active_requests if _graceful_shutdown else 0,
            "timeout_seconds": _graceful_shutdown.timeout if _graceful_shutdown else None,
        },
    }

    return health_status


@app.get("/api/stats")
def stats_endpoint():
    """
    Get comprehensive performance statistics.

    Returns:
        - Task Distribution stats (Ollama pool load balancing, performance)
        - Model Sharding status (llama.cpp RPC backends)
        - Hybrid routing decisions
    """
    stats = {"timestamp": datetime.now().isoformat()}

    # Ollama pool stats
    if _ollama_pool:
        stats["ollama_pool"] = _ollama_pool.get_stats()

    # Hybrid router stats
    if _hybrid_router:
        stats["hybrid_routing"] = _hybrid_router.get_stats()

    # VRAM monitoring stats
    if _vram_monitor:
        stats["vram_monitoring"] = {
            "gpu_type": _vram_monitor.gpu_type,
            "local_gpu": _vram_monitor.get_local_vram_info(),
        }

    # Adaptive parallelism stats
    if _adaptive_parallelism:
        stats["adaptive_parallelism"] = {
            "enabled": True,
            "performance_history_entries": len(_adaptive_parallelism.performance_history),
        }

    # Embedding cache stats
    if _embedding_cache:
        stats["embedding_cache"] = _embedding_cache.get_stats()

    # Resilience features stats
    if _rate_limiter:
        stats["rate_limiter"] = _rate_limiter.get_stats()

    if _circuit_breakers:
        stats["circuit_breakers"] = {
            node_key: breaker.get_state()
            for node_key, breaker in _circuit_breakers.items()
        }

    if _graceful_shutdown:
        stats["graceful_shutdown"] = {
            "is_shutting_down": _graceful_shutdown.is_shutting_down,
            "active_requests": _graceful_shutdown.active_requests,
        }

    return stats


@app.get("/")
async def root():
    """Root endpoint with quick start guide."""
    return {
        "service": "SOLLOL",
        "name": "SOLLOL Gateway",
        "version": __version__,
        "distribution_modes": {
            "task_distribution": "Load balance agent requests across Ollama nodes (parallel execution)",
            "model_sharding": "Distribute large models via llama.cpp RPC backends (single model, multiple nodes)",
        },
        "features": [
            "Task Distribution - Load balance across Ollama nodes",
            "Model Sharding - Distribute 70B+ models via llama.cpp",
            "Automatic GGUF extraction from Ollama storage",
            "Intelligent routing (small → Ollama, large → llama.cpp)",
            "Zero-config setup",
        ],
        "endpoints": {
            "chat": "POST /api/chat",
            "generate": "POST /api/generate",
            "health": "GET /api/health",
            "stats": "GET /api/stats",
            "docs": "GET /docs",
        },
        "quick_start": {
            "1_pull_model": "ollama pull llama3.2",
            "2_start_gateway": "export RPC_BACKENDS=192.168.1.10:50052,192.168.1.11:50052 && python -m sollol.gateway",
            "3_make_request": 'curl -X POST http://localhost:8000/api/chat -d \'{"model": "llama3.1:405b", "messages": [{"role": "user", "content": "Hello!"}]}\'',
        },
    }


# CLI entry point
if __name__ == "__main__":
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Parse command line args
    port = int(os.getenv("PORT", "11434"))

    print("=" * 70)
    print(" SOLLOL Gateway - Drop-in Ollama Replacement")
    print("=" * 70)
    print()
    print("Distribution Modes (independent - use one, both, or neither):")
    print("  🔀 Task Distribution - Load balance across Ollama nodes (parallel execution)")
    print("  🔗 Model Sharding - Distribute large models via llama.cpp RPC (single model)")
    print("  💡 Enable BOTH for task distribution (small models) + model sharding (large models)")
    print()
    print("Features:")
    print("  ✅ Listens on port 11434 (standard Ollama port)")
    print("  ✅ Auto-discovers Ollama nodes (for task distribution)")
    print("  ✅ Auto-discovers RPC backends (for model sharding)")
    print("  ✅ Automatic GGUF extraction from Ollama storage")
    print("  ✅ Intelligent routing: small → Ollama, large → llama.cpp")
    print("  ✅ Zero-config setup")
    print()
    print("Configuration:")
    print(f"  PORT: {port} (Ollama's standard port)")

    rpc_env = os.getenv("RPC_BACKENDS", "")
    if rpc_env:
        print(f"  RPC_BACKENDS: {rpc_env}")
        print("  → Model Sharding ENABLED (manual config)")
    else:
        print("  RPC_BACKENDS: (not set)")
        print("  → Auto-discovery mode (scans network for RPC servers)")

    print()
    print("=" * 70)
    print()

    # Start gateway
    start_api(port=port)
