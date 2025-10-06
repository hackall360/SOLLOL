"""
Example: Wrapping SOLLOL around existing infrastructure.

This example shows how to integrate SOLLOL into existing load balancing
or orchestration systems. Based on the pattern used in SynapticLlamas.

Demonstrates:
- Wrapping SOLLOL around existing node registry
- Adapting existing infrastructure to use SOLLOL
- Migration path from custom load balancers
- Gradual adoption strategy
"""

from typing import Dict, List, Optional
from sollol.sync_wrapper import OllamaPool, HybridRouter
from sollol.priority_helpers import Priority, get_priority_for_role


class LegacyNodeRegistry:
    """
    Simulated legacy node registry.

    This represents an existing infrastructure component that SOLLOL
    will wrap around.
    """

    def __init__(self):
        self.nodes = [
            {"host": "192.168.1.10", "port": 11434, "capabilities": ["llama3.2"]},
            {"host": "192.168.1.11", "port": 11434, "capabilities": ["llama3.2"]},
            {"host": "192.168.1.12", "port": 11434, "capabilities": ["llama3.2"]},
        ]

    def get_available_nodes(self) -> List[Dict]:
        """Get list of available nodes."""
        return self.nodes

    def get_node_for_model(self, model: str) -> Optional[Dict]:
        """Simple round-robin node selection (legacy behavior)."""
        for node in self.nodes:
            if model in node.get("capabilities", []):
                return node
        return None


class SOLLOLEnhancedLoadBalancer:
    """
    Enhanced load balancer that wraps SOLLOL around existing infrastructure.

    This shows how to gradually migrate from a custom load balancer to SOLLOL
    while maintaining compatibility with existing systems.

    Pattern from SynapticLlamas:
    - Keep existing node registry
    - Add SOLLOL intelligence on top
    - Provide backward-compatible interface
    - Enable gradual migration
    """

    def __init__(
        self,
        legacy_registry: LegacyNodeRegistry,
        enable_sollol: bool = True,
        enable_distributed: bool = False,
    ):
        """
        Initialize enhanced load balancer.

        Args:
            legacy_registry: Existing node registry
            enable_sollol: Enable SOLLOL intelligent routing
            enable_distributed: Enable model sharding (if RPC backends available)
        """
        self.legacy_registry = legacy_registry
        self.enable_sollol = enable_sollol

        if enable_sollol:
            # Create SOLLOL pool using nodes from legacy registry
            nodes = [
                {"host": node["host"], "port": node["port"]}
                for node in legacy_registry.get_available_nodes()
            ]

            # Initialize SOLLOL components
            self.sollol_pool = OllamaPool(nodes=nodes)

            if enable_distributed:
                self.sollol_router = HybridRouter(
                    ollama_pool=self.sollol_pool, enable_distributed=True
                )
            else:
                self.sollol_router = None

            print(
                f"✓ SOLLOL enabled with {len(nodes)} nodes from legacy registry"
            )
        else:
            self.sollol_pool = None
            self.sollol_router = None
            print("✓ Running in legacy mode (SOLLOL disabled)")

    def route_request(
        self,
        model: str,
        messages: List[Dict],
        agent_role: Optional[str] = None,
        use_sollol: bool = True,
    ) -> Dict:
        """
        Route a request using SOLLOL or legacy method.

        Args:
            model: Model name
            messages: Chat messages
            agent_role: Optional agent role for priority mapping
            use_sollol: Use SOLLOL routing (vs legacy)

        Returns:
            Response dict
        """
        # Determine if we should use SOLLOL
        should_use_sollol = self.enable_sollol and use_sollol

        if should_use_sollol:
            return self._route_with_sollol(model, messages, agent_role)
        else:
            return self._route_legacy(model, messages)

    def _route_with_sollol(
        self, model: str, messages: List[Dict], agent_role: Optional[str]
    ) -> Dict:
        """Route using SOLLOL with intelligent load balancing."""
        print(f"  → Routing via SOLLOL")

        # Get priority from agent role
        priority = (
            get_priority_for_role(agent_role) if agent_role else Priority.NORMAL
        )

        # Use hybrid router if available, otherwise use pool
        if self.sollol_router:
            response = self.sollol_router.route_request(
                model=model, messages=messages, timeout=60
            )
        else:
            response = self.sollol_pool.chat(
                model=model, messages=messages, priority=priority, timeout=60
            )

        return response

    def _route_legacy(self, model: str, messages: List[Dict]) -> Dict:
        """Route using legacy round-robin method."""
        print(f"  → Routing via legacy method")

        # Use legacy node selection
        node = self.legacy_registry.get_node_for_model(model)

        if not node:
            raise ValueError(f"No node available for model {model}")

        # Simulate making request to node (would be actual HTTP request)
        # In real implementation, this would call the Ollama API
        return {
            "model": model,
            "message": {"role": "assistant", "content": "Legacy response"},
            "done": True,
            "_routing": {"backend": "legacy", "node": node["host"]},
        }

    def get_stats(self) -> Dict:
        """Get statistics from SOLLOL or legacy system."""
        stats = {"mode": "sollol" if self.enable_sollol else "legacy"}

        if self.sollol_pool:
            stats["sollol_pool"] = self.sollol_pool.get_stats()

        if self.sollol_router:
            stats["sollol_router"] = self.sollol_router.get_stats()

        return stats

    def check_sollol_available(self) -> bool:
        """Check if SOLLOL is available and working."""
        return self.enable_sollol and self.sollol_pool is not None


class SOLLOLDetector:
    """
    Utility to detect if SOLLOL is running vs native Ollama.

    Based on SynapticLlamas sollol_adapter.py pattern.
    """

    @staticmethod
    def is_sollol(base_url: str = "http://localhost:11434") -> bool:
        """
        Detect if SOLLOL is running at the given URL.

        Args:
            base_url: Base URL to check

        Returns:
            True if SOLLOL detected, False if native Ollama

        Detection methods:
        1. Check X-Powered-By header
        2. Check /api/health for service identification
        """
        import requests

        try:
            # Method 1: Check headers on root endpoint
            response = requests.get(base_url, timeout=5)
            if response.headers.get("X-Powered-By") == "SOLLOL":
                return True

            # Method 2: Check health endpoint
            response = requests.get(f"{base_url}/api/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("service") == "SOLLOL":
                    return True

            return False

        except Exception:
            return False


def gradual_migration_example():
    """Example of gradual migration from legacy to SOLLOL."""
    print("=== Gradual Migration Example ===\n")

    # Start with legacy system
    legacy_registry = LegacyNodeRegistry()

    # Phase 1: Wrap SOLLOL around legacy system (backward compatible)
    print("Phase 1: SOLLOL enabled, can still use legacy method\n")
    lb = SOLLOLEnhancedLoadBalancer(
        legacy_registry, enable_sollol=True, enable_distributed=False
    )

    # Can still use legacy routing if needed
    print("Using legacy routing:")
    response = lb.route_request(
        model="llama3.2",
        messages=[{"role": "user", "content": "Test"}],
        use_sollol=False,
    )
    print(f"  Backend: {response.get('_routing', {}).get('backend')}\n")

    # Or use SOLLOL routing
    print("Using SOLLOL routing:")
    try:
        response = lb.route_request(
            model="llama3.2",
            messages=[{"role": "user", "content": "Test"}],
            agent_role="researcher",
            use_sollol=True,
        )
        print(f"  Backend: {response.get('_routing', {}).get('backend')}\n")
    except Exception as e:
        print(f"  Failed: {e}\n")

    # Phase 2: Gradually switch to SOLLOL-only
    print("Phase 2: All traffic routed through SOLLOL")
    # At this point, remove use_sollol parameter and always use SOLLOL


def detection_example():
    """Example of detecting SOLLOL vs native Ollama."""
    print("\n=== SOLLOL Detection Example ===\n")

    urls_to_check = [
        "http://localhost:11434",  # Default Ollama port
        "http://localhost:8000",  # Alternative port
    ]

    for url in urls_to_check:
        is_sollol = SOLLOLDetector.is_sollol(url)
        service_type = "SOLLOL" if is_sollol else "Native Ollama"
        print(f"{url}: {service_type}")


def multi_tier_routing_example():
    """Example with multi-tier routing strategy."""
    print("\n=== Multi-Tier Routing Example ===\n")

    legacy_registry = LegacyNodeRegistry()
    lb = SOLLOLEnhancedLoadBalancer(
        legacy_registry, enable_sollol=True, enable_distributed=False
    )

    # Define routing tiers
    routing_tiers = [
        {
            "name": "Premium Users",
            "use_sollol": True,
            "role": "assistant",
            "description": "Get SOLLOL intelligent routing",
        },
        {
            "name": "Free Users",
            "use_sollol": True,
            "role": "background",
            "description": "Lower priority but still intelligent",
        },
        {
            "name": "Legacy Clients",
            "use_sollol": False,
            "role": None,
            "description": "Backward compatible legacy routing",
        },
    ]

    for tier in routing_tiers:
        print(f"\n{tier['name']}: {tier['description']}")
        try:
            response = lb.route_request(
                model="llama3.2",
                messages=[{"role": "user", "content": f"Request from {tier['name']}"}],
                agent_role=tier.get("role"),
                use_sollol=tier["use_sollol"],
            )
            backend = response.get("_routing", {}).get("backend", "unknown")
            print(f"  Routed via: {backend}")
        except Exception as e:
            print(f"  Failed: {e}")

    # Show statistics
    stats = lb.get_stats()
    print(f"\nLoad balancer stats: {stats}")


if __name__ == "__main__":
    try:
        gradual_migration_example()
    except Exception as e:
        print(f"Migration example failed: {e}")

    try:
        detection_example()
    except Exception as e:
        print(f"Detection example failed: {e}")

    try:
        multi_tier_routing_example()
    except Exception as e:
        print(f"Multi-tier routing example failed: {e}")

    print("\n=== Integration Pattern Summary ===")
    print("""
This pattern allows you to:
1. Keep existing infrastructure (node registry, etc.)
2. Add SOLLOL intelligence incrementally
3. Maintain backward compatibility
4. Gradually migrate traffic to SOLLOL
5. Detect SOLLOL vs native Ollama

Benefits:
- Low risk migration path
- Can roll back if needed
- Test SOLLOL on subset of traffic
- Preserve existing monitoring/tooling
""")
