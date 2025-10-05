"""
FastAPI gateway with two independent distribution modes.

This is the ONLY Ollama-compatible gateway with:
- Task Distribution: Load balance agent requests across Ollama nodes (parallel execution)
- Model Sharding: Distribute large models via llama.cpp RPC backends (single model, multiple nodes)
- Both modes can be enabled simultaneously for optimal performance
- Automatic GGUF extraction from Ollama storage
- Intelligent routing (small models → Ollama, large models → llama.cpp)
- Zero-config setup
"""
from fastapi import FastAPI, Request, HTTPException
import asyncio
import os
from datetime import datetime
from typing import Optional, Dict, List
import logging

from sollol.pool import OllamaPool
from sollol.hybrid_router import HybridRouter

logger = logging.getLogger(__name__)

app = FastAPI(
    title="SOLLOL Gateway",
    description="Two independent distribution modes: task distribution (load balancing) OR model sharding (distributed inference) OR BOTH"
)

# Global instances
_ollama_pool: Optional[OllamaPool] = None
_hybrid_router: Optional[HybridRouter] = None

def start_api(
    port: int = 11434,
    rpc_backends: Optional[List[Dict]] = None,
    ollama_nodes: Optional[List[Dict]] = None
):
    """
    Start SOLLOL gateway - Drop-in Ollama replacement with two distribution modes.

    SOLLOL listens on port 11434 (standard Ollama port) and provides:

    TWO INDEPENDENT DISTRIBUTION MODES (can be used together or separately):
    1. Task Distribution - Load balance agent requests across Ollama nodes (parallel execution)
    2. Model Sharding - Distribute large models via llama.cpp RPC backends (single model across nodes)

    💡 Enable BOTH modes to get task distribution for small models AND model sharding for large models!

    Features:
    - Intelligent load balancing across Ollama nodes (task distribution)
    - Model sharding for 70B+ models via llama.cpp (model distribution)
    - Automatic GGUF extraction from Ollama storage
    - Zero-config auto-discovery

    ENVIRONMENT CONFIGURATION:
        PORT - Gateway port (default: 11434, the standard Ollama port)
        RPC_BACKENDS - Comma-separated RPC servers for model sharding (e.g., "192.168.1.10:50052,192.168.1.11:50052")
        OLLAMA_NODES - Comma-separated Ollama nodes for task distribution (optional, auto-discovers if not set)

    Args:
        port: Port to run gateway on (default: 11434 - Ollama's port)
        rpc_backends: List of RPC backend dicts for model sharding [{"host": "ip", "port": 50052}]
        ollama_nodes: List of Ollama node dicts for task distribution (auto-discovers if None)

    Example:
        # Zero-config (auto-discovers everything):
        python -m sollol.gateway

        # With manual RPC backends for model sharding:
        export RPC_BACKENDS="192.168.1.10:50052,192.168.1.11:50052"
        python -m sollol.gateway

    Note: SOLLOL runs on port 11434 (Ollama's port). Make sure local Ollama
          is either disabled or running on a different port (e.g., 11435).
    """
    global _ollama_pool, _hybrid_router

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
                logger.info(f"✅ Auto-discovered {len(rpc_backends)} RPC backends for model sharding")
            else:
                logger.info("📡 No RPC backends found (model sharding disabled)")

    # Create Ollama pool for task distribution (auto-discovers remote nodes, excludes localhost)
    logger.info("🔍 Initializing Ollama pool (for task distribution / load balancing)...")
    logger.info("   Excluding localhost (SOLLOL running on this port)")
    _ollama_pool = OllamaPool(nodes=ollama_nodes, exclude_localhost=True)

    if len(_ollama_pool.nodes) > 0:
        logger.info(f"✅ Ollama pool initialized with {len(_ollama_pool.nodes)} remote nodes for task distribution")
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
            enable_distributed=True  # Enables model sharding
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
    Chat completion with automatic routing between task distribution and model sharding.

    TWO ROUTING MODES:
    1. Task Distribution - Small/medium models routed to Ollama pool (load balanced)
    2. Model Sharding - Large models (70B+) distributed via llama.cpp RPC backends

    Features:
    - Automatic GGUF extraction from Ollama storage (for model sharding)
    - Intelligent routing: small models → Ollama pool, large models → llama.cpp sharding
    - Zero configuration needed
    - Transparent routing metadata in response

    Request body:
        {
            "model": "llama3.2",  # Small model → Ollama pool (task distribution)
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
            "_routing": {
                "backend": "ollama-pool" or "llama.cpp-distributed",
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
        # Use hybrid router if available (handles distributed), otherwise use Ollama pool
        if _hybrid_router:
            result = await _hybrid_router.route_request(model, messages)
        else:
            # Ollama-only mode
            result = _ollama_pool.chat(model=model, messages=messages)

        return result

    except FileNotFoundError as e:
        # Model not found in Ollama storage
        raise HTTPException(
            status_code=404,
            detail=f"Model not found: {str(e)}. Pull with: ollama pull {model}"
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
    Check health of gateway and distribution backends.

    Returns status for:
    - Task Distribution (Ollama pool for load balancing)
    - Model Sharding (llama.cpp RPC backends for large models)
    """
    health_status = {
        "status": "healthy",
        "task_distribution": {
            "enabled": _ollama_pool is not None and len(_ollama_pool.nodes) > 0,
            "ollama_nodes": len(_ollama_pool.nodes) if _ollama_pool else 0,
            "description": "Load balance agent requests across Ollama nodes"
        },
        "model_sharding": {
            "enabled": _hybrid_router is not None,
            "coordinator_running": False,
            "rpc_backends": 0,
            "description": "Distribute large models via llama.cpp RPC backends"
        },
        "timestamp": datetime.now().isoformat()
    }

    # Check model sharding coordinator status
    if _hybrid_router and _hybrid_router.coordinator:
        health_status["model_sharding"]["coordinator_running"] = True
        health_status["model_sharding"]["rpc_backends"] = len(_hybrid_router.coordinator.rpc_backends)
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
    stats = {
        "timestamp": datetime.now().isoformat()
    }

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
        "name": "SOLLOL Gateway",
        "version": "2.0",
        "distribution_modes": {
            "task_distribution": "Load balance agent requests across Ollama nodes (parallel execution)",
            "model_sharding": "Distribute large models via llama.cpp RPC backends (single model, multiple nodes)"
        },
        "features": [
            "Task Distribution - Load balance across Ollama nodes",
            "Model Sharding - Distribute 70B+ models via llama.cpp",
            "Automatic GGUF extraction from Ollama storage",
            "Intelligent routing (small → Ollama, large → llama.cpp)",
            "Zero-config setup"
        ],
        "endpoints": {
            "chat": "POST /api/chat",
            "generate": "POST /api/generate",
            "health": "GET /api/health",
            "stats": "GET /api/stats",
            "docs": "GET /docs"
        },
        "quick_start": {
            "1_pull_model": "ollama pull llama3.2",
            "2_start_gateway": "export RPC_BACKENDS=192.168.1.10:50052,192.168.1.11:50052 && python -m sollol.gateway",
            "3_make_request": "curl -X POST http://localhost:8000/api/chat -d '{\"model\": \"llama3.1:405b\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]}'"
        }
    }


# CLI entry point
if __name__ == "__main__":
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
