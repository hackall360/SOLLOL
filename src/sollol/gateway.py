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

from sollol.autobatch import autobatch_loop
from sollol.hybrid_router import HybridRouter
from sollol.pool import OllamaPool
from sollol.workers import OllamaWorker

logger = logging.getLogger(__name__)

# Version from pyproject.toml
__version__ = "0.3.6"


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
        PORT - Gateway port (default: 11434, the standard Ollama port)
        RPC_BACKENDS - Comma-separated RPC servers for model sharding (e.g., "192.168.1.10:50052,192.168.1.11:50052")
        OLLAMA_NODES - Comma-separated Ollama nodes for task distribution (optional, auto-discovers if not set)
        RAY_WORKERS - Number of Ray actors for parallel execution (default: 4)
        DASK_WORKERS - Number of Dask workers for batch processing (default: 2)

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

        # With manual configuration:
        export RPC_BACKENDS="192.168.1.10:50052,192.168.1.11:50052"
        python -m sollol.gateway

        # Custom Ray/Dask workers:
        export RAY_WORKERS=8
        export DASK_WORKERS=4
        python -m sollol.gateway

    Note: SOLLOL runs on port 11434 (Ollama's port). Make sure local Ollama
          is either disabled or running on a different port (e.g., 11435).
    """
    global _ollama_pool, _hybrid_router, _ray_actors, _dask_client

    # Parse environment overrides
    ray_workers = int(os.getenv("RAY_WORKERS", ray_workers))
    dask_workers = int(os.getenv("DASK_WORKERS", dask_workers))

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
    Chat completion with THREE distribution modes.

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
    if not _ollama_pool:
        raise HTTPException(status_code=503, detail="Gateway not initialized")

    payload = await request.json()
    model = payload.get("model", "llama3.2")
    messages = payload.get("messages", [])

    if not messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    try:
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

        # Use intelligent routing + Ray parallel execution for Ollama nodes
        # OllamaPool selects best node using 7-factor scoring
        node, decision = _ollama_pool._select_node(payload=payload, priority=5)

        if not node:
            raise HTTPException(status_code=503, detail="No Ollama nodes available")

        # Submit to Ray actor for parallel execution
        node_key = f"{node['host']}:{node['port']}"

        # Round-robin actor selection for load distribution
        if _ray_actors:
            import random
            actor = random.choice(_ray_actors)  # Random actor selection for load distribution
        else:
            actor = None

        if not actor:
            # Fallback to direct OllamaPool if no Ray actors
            logger.warning("No Ray actors available, falling back to direct execution")
            result = _ollama_pool.chat(model=model, messages=messages)
        else:
            # Parallel execution via Ray actor
            result_future = actor.chat.remote(payload, node_key)
            result = await result_future

        # Add routing metadata
        if isinstance(result, dict):
            result["_sollol_routing"] = {
                "mode": "ray-parallel",
                "node": node_key,
                "actor_id": str(actor) if actor else "none",
                "intelligent_routing": decision if decision else {"reasoning": "round-robin fallback"}
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


@app.post("/api/generate")
async def generate_endpoint(request: Request):
    """
    Text generation endpoint (non-chat).

    Request body:
        {
            "model": "llama3.2",
            "prompt": "Once upon a time"
        }
    """
    if not _ollama_pool:
        raise HTTPException(status_code=503, detail="Gateway not initialized")

    payload = await request.json()
    model = payload.get("model", "llama3.2")
    prompt = payload.get("prompt", "")

    if not prompt:
        raise HTTPException(status_code=400, detail="No prompt provided")

    try:
        result = _ollama_pool.generate(model=model, prompt=prompt)
        return result
    except Exception as e:
        logger.error(f"Generate endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
