"""
Routing strategies for OllamaPool load balancing.

Provides clean extension points for different routing algorithms:
- Round-robin: Simple rotation through nodes
- Latency-first: Choose node with lowest average latency
- Least-loaded: Choose node with fewest active requests
- Fairness: Distribute evenly based on total request count
- Intelligent: Task-aware routing with performance learning
"""

from enum import Enum


class RoutingStrategy(Enum):
    """
    Available routing strategies for node selection.

    Each strategy optimizes for different goals:

    - ROUND_ROBIN: Simple, predictable distribution (no intelligence)
    - LATENCY_FIRST: Minimize response time (prioritizes fastest nodes)
    - LEAST_LOADED: Maximize parallelism (prioritizes nodes with least active requests)
    - FAIRNESS: Even distribution (balances total request counts across nodes)
    - INTELLIGENT: Task-aware routing with performance learning (default, most sophisticated)
    """

    ROUND_ROBIN = "round_robin"
    LATENCY_FIRST = "latency_first"
    LEAST_LOADED = "least_loaded"
    FAIRNESS = "fairness"
    INTELLIGENT = "intelligent"


__all__ = ["RoutingStrategy"]
