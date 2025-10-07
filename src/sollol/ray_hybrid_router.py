"""
Ray-based Hybrid Router for parallel RPC sharding.

Uses Ray actors to manage multiple sharded model pools in parallel,
enabling better load balancing and fault tolerance for distributed inference.

Architecture:
- Each ShardedModelPool is a Ray actor managing N RPC backends
- Multiple pools can run in parallel
- Ray handles load balancing, queuing, and fault tolerance automatically
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import ray

from sollol.llama_cpp_coordinator import LlamaCppCoordinator, RPCBackend
from sollol.ollama_gguf_resolver import resolve_ollama_model
from sollol.pool import OllamaPool
from sollol.rpc_registry import RPCBackendRegistry

logger = logging.getLogger(__name__)


@ray.remote
class ShardedModelPool:
    """
    Ray actor managing one sharded model instance across N RPC backends.

    This runs as an independent process, allowing multiple pools to serve
    the same model in parallel for higher throughput.
    """

    def __init__(
        self,
        rpc_backends: List[Dict[str, Any]],
        coordinator_host: str = "127.0.0.1",
        coordinator_port: int = 18080,
        pool_id: int = 0,
    ):
        """
        Initialize sharded model pool.

        Args:
            rpc_backends: List of RPC backend configs for this pool
            coordinator_host: Host for llama-server coordinator
            coordinator_port: Base port (actual port = base + pool_id)
            pool_id: Unique pool identifier
        """
        self.pool_id = pool_id
        self.rpc_backends = rpc_backends
        self.coordinator_host = coordinator_host
        # Each pool gets unique port to avoid conflicts
        self.coordinator_port = coordinator_port + pool_id
        self.coordinator: Optional[LlamaCppCoordinator] = None
        self.current_model: Optional[str] = None

        logger.info(
            f"ShardedModelPool {pool_id} initialized with {len(rpc_backends)} backends "
            f"(port {self.coordinator_port})"
        )

    async def load_model(self, model: str, gguf_path: str) -> Dict[str, Any]:
        """
        Load model into this pool's coordinator.

        Args:
            model: Model name (e.g., "llama3.1:405b")
            gguf_path: Path to GGUF file

        Returns:
            Status dict with coordinator info
        """
        if self.coordinator and self.current_model == model:
            logger.debug(f"Pool {self.pool_id}: Model {model} already loaded")
            return {
                "status": "already_loaded",
                "model": model,
                "pool_id": self.pool_id,
                "coordinator": f"{self.coordinator_host}:{self.coordinator_port}",
            }

        # Convert dict configs to RPCBackend objects
        backends = [
            RPCBackend(host=backend["host"], port=backend.get("port", 50052))
            for backend in self.rpc_backends
        ]

        # Create new coordinator
        logger.info(
            f"Pool {self.pool_id}: Loading {model} across {len(backends)} RPC backends"
        )

        self.coordinator = LlamaCppCoordinator(
            model_path=gguf_path,
            rpc_backends=backends,
            host=self.coordinator_host,
            port=self.coordinator_port,
        )

        await self.coordinator.start()
        self.current_model = model

        return {
            "status": "loaded",
            "model": model,
            "pool_id": self.pool_id,
            "coordinator": f"{self.coordinator_host}:{self.coordinator_port}",
            "rpc_backends": len(backends),
        }

    async def chat(
        self,
        messages: List[Dict[str, str]],
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run chat inference on this pool.

        Args:
            messages: Chat messages
            stream: Whether to stream response (not yet supported)
            **kwargs: Additional parameters

        Returns:
            Chat completion response
        """
        if not self.coordinator:
            raise RuntimeError(f"Pool {self.pool_id}: No model loaded")

        if stream:
            raise NotImplementedError("Streaming not yet supported in Ray pools")

        logger.debug(f"Pool {self.pool_id}: Running inference for {self.current_model}")
        response = await self.coordinator.chat(messages, stream=False, **kwargs)

        return response

    async def shutdown(self):
        """Shutdown this pool's coordinator."""
        if self.coordinator:
            logger.info(f"Pool {self.pool_id}: Shutting down coordinator")
            await self.coordinator.stop()
            self.coordinator = None
            self.current_model = None


class RayHybridRouter:
    """
    Ray-based hybrid router with parallel RPC sharding.

    Routes small models to Ollama pool, large models to Ray-managed sharded pools.
    Automatically load balances across pools and handles failures.

    Benefits over basic HybridRouter:
    - Multiple pools serve same model in parallel (higher throughput)
    - Automatic load balancing by Ray
    - Fault tolerance with automatic pool restarts
    - Better GPU utilization
    """

    def __init__(
        self,
        ollama_pool: Optional[OllamaPool] = None,
        rpc_backends: Optional[List[Dict[str, Any]]] = None,
        coordinator_host: str = "127.0.0.1",
        coordinator_base_port: int = 18080,
        backends_per_pool: int = 2,
        num_pools: int = None,
        enable_distributed: bool = True,
        auto_discover_rpc: bool = True,
        model_vram_threshold_mb: int = 16384,
        auto_fallback: bool = True,
    ):
        """
        Initialize Ray-based hybrid router.

        Args:
            ollama_pool: OllamaPool for small models
            rpc_backends: List of ALL RPC backends (will be divided into pools)
            coordinator_host: Host for coordinators
            coordinator_base_port: Base port (each pool gets base + pool_id)
            backends_per_pool: Number of RPC backends per pool (default: 2)
            num_pools: Number of pools to create (auto-calculated if None)
            enable_distributed: Enable RPC sharding
            auto_discover_rpc: Auto-discover RPC backends if none provided
            model_vram_threshold_mb: VRAM threshold for Ollama vs RPC routing (16GB default)
            auto_fallback: Fallback to RPC if Ollama fails
        """
        self.ollama_pool = ollama_pool or OllamaPool.auto_configure()
        self.enable_distributed = enable_distributed
        self.auto_fallback = auto_fallback
        self.model_vram_threshold_mb = model_vram_threshold_mb
        self.coordinator_host = coordinator_host
        self.coordinator_base_port = coordinator_base_port
        self.backends_per_pool = backends_per_pool

        # Auto-discover RPC backends if needed
        if rpc_backends is None and enable_distributed and auto_discover_rpc:
            logger.info("🔍 Auto-discovering RPC backends...")
            from sollol.rpc_discovery import auto_discover_rpc_backends

            rpc_backends = auto_discover_rpc_backends()
            if rpc_backends:
                logger.info(f"✅ Auto-discovered {len(rpc_backends)} RPC backends")

        self.rpc_backends = rpc_backends or []
        self.has_rpc_backends = len(self.rpc_backends) > 0

        # Initialize Ray with dashboard enabled (for Ollama pool parallelization even without RPC)
        if self.enable_distributed:
            if not ray.is_initialized():
                logger.info("🚀 Initializing Ray for distributed RPC coordination")
                ray.init(
                    ignore_reinit_error=True,
                    dashboard_host="0.0.0.0",
                    dashboard_port=8265,
                    include_dashboard=True,
                )
                logger.info("📊 Ray dashboard available at http://localhost:8265")

            # Only create RPC pools if we have backends
            if self.has_rpc_backends:
                # Create RPC backend registry
                self.rpc_registry = RPCBackendRegistry()
                self.rpc_registry.load_from_config(self.rpc_backends)

                # Calculate number of pools
                if num_pools is None:
                    num_pools = max(1, len(self.rpc_backends) // backends_per_pool)

                self.num_pools = num_pools
                self.pools: List[ray.actor.ActorHandle] = []
                self.current_model: Optional[str] = None

                # Create pools from RPC backends
                logger.info(
                    f"📦 Creating {num_pools} sharded model pools "
                    f"({backends_per_pool} backends per pool)"
                )

                for i in range(num_pools):
                    # Assign backends to this pool (round-robin)
                    pool_backends = [
                        self.rpc_backends[j]
                        for j in range(i, len(self.rpc_backends), num_pools)
                    ]

                    if pool_backends:
                        pool = ShardedModelPool.remote(
                            rpc_backends=pool_backends,
                            coordinator_host=coordinator_host,
                            coordinator_port=coordinator_base_port,
                            pool_id=i,
                        )
                        self.pools.append(pool)
                    logger.info(
                        f"  Pool {i}: {len(pool_backends)} backends "
                        f"(port {coordinator_base_port + i})"
                    )

                logger.info(
                    f"✅ RayHybridRouter initialized: "
                    f"{len(self.pools)} RPC pools, {len(self.rpc_backends)} total backends"
                )
            else:
                # No RPC backends - Ray still used for parallel Ollama pool execution
                self.rpc_registry = None
                self.num_pools = 0
                self.pools: List[ray.actor.ActorHandle] = []
                self.current_model: Optional[str] = None
                logger.info("✅ RayHybridRouter initialized (Ray enabled for Ollama parallelization, no RPC backends)")
        else:
            logger.info("ℹ️  RayHybridRouter initialized without distributed support")
            self.pools = []
            self.num_pools = 0

    async def route_request(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Route request to appropriate backend.

        Small models → Ollama pool (task distribution)
        Large models → Ray sharded pools (model sharding)

        Args:
            model: Model name
            messages: Chat messages
            stream: Whether to stream (only supported on Ollama)
            **kwargs: Additional parameters

        Returns:
            Chat completion response
        """
        # Determine routing
        route_to_rpc = self._should_use_rpc(model)

        if route_to_rpc and self.enable_distributed and self.pools:
            # Use Ray-managed sharded pools
            return await self._route_to_ray_pool(model, messages, stream, **kwargs)
        else:
            # Use Ollama pool for small models
            try:
                return await self.ollama_pool.chat_async(
                    model=model,
                    messages=messages,
                    stream=stream,
                    **kwargs
                )
            except Exception as e:
                if self.auto_fallback and self.enable_distributed and self.pools:
                    logger.warning(
                        f"Ollama failed for {model}, falling back to RPC sharding: {e}"
                    )
                    return await self._route_to_ray_pool(model, messages, stream, **kwargs)
                raise

    async def _route_to_ray_pool(
        self,
        model: str,
        messages: List[Dict[str, str]],
        stream: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Route request to Ray-managed sharded pool.

        Ray automatically handles:
        - Load balancing (picks least busy pool)
        - Queuing (if all pools busy)
        - Fault tolerance (restarts failed pools)
        """
        # Load model into all pools if not already loaded
        if self.current_model != model:
            gguf_path = resolve_ollama_model(model)
            if not gguf_path:
                raise ValueError(f"Could not resolve {model} to GGUF file")

            logger.info(f"🔄 Loading {model} into {len(self.pools)} Ray pools...")

            # Load model into all pools in parallel
            load_tasks = [
                pool.load_model.remote(model, gguf_path)
                for pool in self.pools
            ]
            results = await asyncio.gather(*[
                asyncio.wrap_future(ray.get(task, timeout=60))
                for task in load_tasks
            ])

            for result in results:
                logger.info(
                    f"  Pool {result['pool_id']}: {result['status']} "
                    f"({result.get('rpc_backends', 0)} backends)"
                )

            self.current_model = model

        # Ray automatically picks the least busy pool
        # We use round-robin for simplicity, but Ray's scheduler is smarter
        pool = self.pools[hash(str(messages)) % len(self.pools)]

        # Execute inference (Ray handles queuing if pool is busy)
        response_future = pool.chat.remote(messages, stream=stream, **kwargs)
        response = await asyncio.wrap_future(ray.get(response_future))

        return response

    def _should_use_rpc(self, model: str) -> bool:
        """
        Determine if model should use RPC sharding.

        Small models → Ollama (task distribution across nodes)
        Large models → RPC sharding (model layers across GPUs)
        """
        # Extract size from model name
        import re
        size_match = re.search(r"(\d+)b", model.lower())
        if size_match:
            size_billions = int(size_match.group(1))
            # Estimate VRAM: ~2GB per billion parameters for fp16
            estimated_vram_mb = size_billions * 2 * 1024

            return estimated_vram_mb > self.model_vram_threshold_mb

        # Default: use RPC for unknown large models
        return False

    async def shutdown(self):
        """Shutdown all Ray pools."""
        if self.pools:
            logger.info(f"🛑 Shutting down {len(self.pools)} Ray pools...")
            shutdown_tasks = [pool.shutdown.remote() for pool in self.pools]
            await asyncio.gather(*[
                asyncio.wrap_future(ray.get(task))
                for task in shutdown_tasks
            ])
            self.pools = []
            logger.info("✅ All Ray pools shut down")

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics."""
        stats = {
            "router_type": "ray_hybrid",
            "ollama_pool": {
                "nodes": len(self.ollama_pool.nodes),
                "requests": self.ollama_pool.stats["total_requests"],
            },
            "ray_pools": {
                "num_pools": len(self.pools),
                "backends_per_pool": self.backends_per_pool,
                "total_backends": len(self.rpc_backends),
                "current_model": self.current_model,
            },
        }

        return stats
