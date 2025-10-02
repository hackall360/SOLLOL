"""
FastAPI gateway with performance-aware routing, metrics, and autobatch integration.
"""
from fastapi import FastAPI, Request, HTTPException
import random
import asyncio
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from sollol.metrics import record_request, start_metrics_server
from sollol.autobatch import autobatch_loop
from sollol.memory import get_best_host, get_all_hosts_meta, health_check_all_hosts, queue_document
from sollol.adaptive_metrics import adaptive_metrics_loop

app = FastAPI(title="SOLLOL", description="Super Ollama Load Balancer")
_ray_actors = []
_dask_client = None

def start_api(
    ray_actors,
    dask_client,
    port=8000,
    enable_autobatch=True,
    autobatch_interval=60,
    enable_adaptive_metrics=True,
    adaptive_metrics_interval=30
):
    """
    Start FastAPI gateway with integrated metrics and autobatch.

    Args:
        ray_actors: List of Ray OllamaWorker actors
        dask_client: Dask distributed client
        port: Port to run the gateway on
        enable_autobatch: Whether to enable autonomous batch processing
        autobatch_interval: Seconds between autobatch cycles
        enable_adaptive_metrics: Whether to enable dynamic metrics feedback loop
        adaptive_metrics_interval: Seconds between adaptive metrics updates
    """
    global _ray_actors, _dask_client
    _ray_actors = ray_actors
    _dask_client = dask_client

    # Start Prometheus metrics server
    start_metrics_server(port=9090)

    # Start autobatch pipeline if enabled and Dask is available
    if enable_autobatch and _dask_client:
        asyncio.create_task(autobatch_loop(_dask_client, interval_sec=autobatch_interval))
        print(f"🛠️  Autobatch pipeline started (interval: {autobatch_interval}s)")
    elif enable_autobatch and not _dask_client:
        print(f"⚠️  Autobatch disabled (Dask not available)")

    # Start adaptive metrics feedback loop if enabled
    if enable_adaptive_metrics:
        asyncio.create_task(adaptive_metrics_loop(interval_sec=adaptive_metrics_interval))
        print(f"📊 Adaptive metrics loop started (interval: {adaptive_metrics_interval}s)")

    # Start periodic health checks
    asyncio.create_task(periodic_health_check())

    import uvicorn
    print(f"🌐 Starting FastAPI gateway on port {port}")
    print(f"   API docs: http://localhost:{port}/docs")
    uvicorn.run(app, host="0.0.0.0", port=port)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=2))
async def call_worker(worker, payload: dict):
    """
    Call Ray worker with performance-aware host selection and retry logic.

    Args:
        worker: Ray OllamaWorker actor
        payload: Request payload

    Returns:
        Response from OLLOL host
    """
    host = get_best_host(task_type=payload.get("task_type", "default"))

    if not host:
        raise HTTPException(status_code=503, detail="No available OLLOL hosts")

    result = await worker.chat.remote(payload, host)
    return result

@app.post("/api/chat")
@record_request
async def chat_endpoint(request: Request):
    """
    Chat completion endpoint with performance-aware routing.
    """
    payload = await request.json()

    if not _ray_actors:
        raise HTTPException(status_code=503, detail="No Ollama workers running")

    # Use random Ray actor (Ray handles actor load balancing)
    # Host selection happens inside the actor based on performance metrics
    worker = random.choice(_ray_actors)

    try:
        result = await call_worker(worker, payload)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/embed")
@record_request
async def embed_endpoint(request: Request):
    """
    Embedding endpoint (synchronous).
    """
    payload = await request.json()
    text = payload.get("text", "")
    model = payload.get("model", "nomic-embed-text")

    if not _ray_actors:
        raise HTTPException(status_code=503, detail="No Ollama workers running")

    host = get_best_host(task_type="embedding")
    if not host:
        raise HTTPException(status_code=503, detail="No available OLLOL hosts")

    worker = random.choice(_ray_actors)

    try:
        result = await worker.embed.remote(text, host, model)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/embed/batch")
@record_request
async def embed_batch_endpoint(request: Request):
    """
    Queue documents for batch embedding via Dask autobatch pipeline.
    """
    payload = await request.json()
    docs = payload.get("docs", [])

    if not docs:
        raise HTTPException(status_code=400, detail="No documents provided")

    if not _dask_client:
        raise HTTPException(status_code=503, detail="Dask not running")

    # Queue documents for autobatch processing
    for doc in docs:
        queue_document(doc)

    return {
        "status": "queued",
        "count": len(docs),
        "message": "Documents queued for batch embedding"
    }

@app.get("/api/health")
async def health_check():
    """
    Check health of SOLLOL gateway and OLLOL hosts.
    """
    host_health = await health_check_all_hosts()

    return {
        "status": "healthy",
        "ray_workers": len(_ray_actors),
        "dask_available": _dask_client is not None,
        "hosts": host_health,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/stats")
def stats_endpoint():
    """
    Get performance statistics for all OLLOL hosts.
    """
    hosts_meta = get_all_hosts_meta()

    return {
        "hosts": [
            {
                "host": meta["host"],
                "available": meta["available"],
                "latency_ms": meta["latency_ms"],
                "success_rate": meta["success_rate"],
                "cpu_load": meta["cpu_load"],
                "gpu_free_mem": meta["gpu_free_mem"],
                "priority": meta["priority"],
                "last_updated": meta["last_updated"].isoformat()
            }
            for meta in hosts_meta
        ],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/batch-status")
def batch_status():
    """
    Get Dask batch processing status.
    """
    if _dask_client:
        try:
            scheduler_info = _dask_client.scheduler_info()
            return {
                "status": "running",
                "n_tasks": len(scheduler_info.get("tasks", {})),
                "n_workers": len(scheduler_info.get("workers", {})),
            }
        except Exception as e:
            return {"error": f"Could not get Dask status: {e}"}
    return {"status": "Dask not running"}

async def periodic_health_check(interval_sec: int = 120):
    """
    Periodically check health of all OLLOL hosts.

    Args:
        interval_sec: Seconds between health checks
    """
    while True:
        try:
            await asyncio.sleep(interval_sec)
            await health_check_all_hosts()
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Health check completed")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️  Health check error: {e}")
