"""
SOLLOL - Super Ollama Load Balancer

Intelligent Load Balancing and Distributed Inference for Ollama

Features:
- Intelligent load balancing with adaptive routing
- Auto-discovery of Ollama nodes and RPC backends
- Hybrid routing: Ollama for small models, llama.cpp for large models
- Connection pooling and health monitoring
- Request hedging for lower latency

Example:
    ```python
    from sollol import OllamaPool, HybridRouter
    from sollol.discovery import discover_ollama_nodes
    from sollol.rpc_discovery import auto_discover_rpc_backends

    # Auto-discover Ollama nodes
    pool = OllamaPool.auto_configure()

    # Use hybrid routing for distributed inference
    rpc_backends = auto_discover_rpc_backends()
    router = HybridRouter(
        ollama_pool=pool,
        rpc_backends=rpc_backends,
        enable_distributed=True
    )

    # Make requests
    response = await router.route_request(
        model="llama3.1:405b",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    ```
"""

from sollol.client import SOLLOLClient
from sollol.config import SOLLOLConfig

# Discovery
from sollol.discovery import discover_ollama_nodes

# Distributed inference
from sollol.hybrid_router import HybridRouter
from sollol.llama_cpp_coordinator import LlamaCppCoordinator
from sollol.llama_cpp_rpc import LlamaCppDistributedCluster, LlamaCppRPCClient

# Distributed execution
from sollol.execution import AsyncDistributedExecutor, DistributedExecutor
from sollol.tasks import DistributedTask, ExecutionResult, TaskResult

# Core load balancing
from sollol.pool import OllamaPool
from sollol.rpc_auto_setup import RPCAutoSetup, auto_setup_rpc_backends
from sollol.rpc_discovery import auto_discover_rpc_backends, check_rpc_server
from sollol.rpc_registry import RPCBackendRegistry

# Legacy support
from sollol.sollol import SOLLOL

__version__ = "0.3.6"
__all__ = [
    # Core
    "OllamaPool",
    "SOLLOLClient",
    # Distributed inference
    "HybridRouter",
    "LlamaCppRPCClient",
    "LlamaCppDistributedCluster",
    "LlamaCppCoordinator",
    # Distributed execution
    "DistributedExecutor",
    "AsyncDistributedExecutor",
    "DistributedTask",
    "TaskResult",
    "ExecutionResult",
    # Discovery & Auto-Setup
    "discover_ollama_nodes",
    "auto_discover_rpc_backends",
    "auto_setup_rpc_backends",
    "check_rpc_server",
    "RPCAutoSetup",
    "RPCBackendRegistry",
    # Legacy
    "SOLLOL",
    "SOLLOLConfig",
]
