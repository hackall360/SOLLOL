"""
Node Health Detection and VRAM Monitoring.

Battle-tested patterns from FlockParser for detecting GPU exhaustion
and performance degradation in production Ollama clusters.
"""

import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)


# Thresholds from FlockParser production usage
VRAM_EXHAUSTION_THRESHOLD_MS = 2000.0  # GPU node suddenly >2s (was <0.5s)
GPU_HEALTHY_LATENCY_MS = 500.0  # Healthy GPU response time
CPU_FALLBACK_LATENCY_MS = 2000.0  # CPU fallback is much slower


class NodeHealthMonitor:
    """
    Monitor node health and detect VRAM exhaustion.

    Patterns from FlockParser:
    - Detect runtime VRAM exhaustion (GPU → CPU fallback)
    - Track performance baseline per node
    - Identify degraded GPU nodes
    """

    def __init__(self):
        """Initialize health monitor."""
        self.node_baselines: Dict[str, Dict] = {}  # Performance baselines
        self.vram_exhaustion_detected: Dict[str, bool] = {}  # VRAM exhaustion flags

    def update_baseline(self, node_key: str, latency_ms: float, is_gpu: bool = True):
        """
        Update performance baseline for a node.

        Args:
            node_key: Node identifier (host:port)
            latency_ms: Request latency in milliseconds
            is_gpu: Whether node is using GPU
        """
        if node_key not in self.node_baselines:
            self.node_baselines[node_key] = {
                "baseline_latency_ms": latency_ms,
                "recent_latencies": [latency_ms],
                "is_gpu": is_gpu,
                "samples": 1,
            }
        else:
            baseline = self.node_baselines[node_key]

            # Update recent latencies (keep last 10)
            baseline["recent_latencies"].append(latency_ms)
            if len(baseline["recent_latencies"]) > 10:
                baseline["recent_latencies"].pop(0)

            # Update baseline with exponential moving average
            baseline["baseline_latency_ms"] = (
                baseline["baseline_latency_ms"] * 0.9 + latency_ms * 0.1
            )
            baseline["samples"] += 1

    def detect_vram_exhaustion(self, node_key: str, latency_ms: float) -> bool:
        """
        Detect VRAM exhaustion based on sudden latency increase.

        FlockParser pattern:
        - GPU nodes normally respond in <500ms
        - VRAM exhaustion causes CPU fallback → >2000ms
        - This is a critical production issue to detect

        Args:
            node_key: Node identifier
            latency_ms: Current request latency

        Returns:
            True if VRAM exhaustion detected
        """
        if node_key not in self.node_baselines:
            # No baseline yet
            return False

        baseline = self.node_baselines[node_key]

        # Only check GPU nodes
        if not baseline.get("is_gpu", True):
            return False

        baseline_latency = baseline["baseline_latency_ms"]

        # Detect sudden latency spike (>4x baseline)
        if latency_ms > max(baseline_latency * 4, VRAM_EXHAUSTION_THRESHOLD_MS):
            if not self.vram_exhaustion_detected.get(node_key, False):
                logger.warning(
                    f"⚠️  VRAM exhaustion detected on {node_key}: "
                    f"latency jumped from {baseline_latency:.0f}ms → {latency_ms:.0f}ms "
                    f"(likely GPU → CPU fallback)"
                )
                self.vram_exhaustion_detected[node_key] = True

            return True

        # Recovery: latency back to normal
        if self.vram_exhaustion_detected.get(node_key, False):
            if latency_ms < baseline_latency * 1.5:
                logger.info(
                    f"✅ {node_key} recovered from VRAM exhaustion "
                    f"(latency: {latency_ms:.0f}ms)"
                )
                self.vram_exhaustion_detected[node_key] = False

        return False

    def get_health_penalty(self, node_key: str) -> float:
        """
        Get health penalty for routing decisions.

        Returns:
            Penalty to subtract from health score (0-100)
        """
        if self.vram_exhaustion_detected.get(node_key, False):
            return 100.0  # Heavy penalty - avoid this node

        return 0.0

    def is_node_degraded(self, node_key: str) -> bool:
        """Check if node is degraded."""
        return self.vram_exhaustion_detected.get(node_key, False)

    def get_stats(self) -> Dict:
        """Get health monitoring statistics."""
        degraded_nodes = [
            node for node, degraded in self.vram_exhaustion_detected.items() if degraded
        ]

        return {
            "monitored_nodes": len(self.node_baselines),
            "degraded_nodes": degraded_nodes,
            "baselines": {
                node: {
                    "baseline_latency_ms": data["baseline_latency_ms"],
                    "is_gpu": data["is_gpu"],
                    "samples": data["samples"],
                }
                for node, data in self.node_baselines.items()
            },
        }


def normalize_model_name(model: str) -> str:
    """
    Normalize model name for flexible matching.

    FlockParser pattern:
    - Handles llama3.1, llama3.1:latest, llama3.1:8b
    - Removes :latest suffix
    - Preserves size suffixes (8b, 70b)

    Examples:
        "llama3.1:latest" → "llama3.1"
        "llama3.1:8b" → "llama3.1:8b"
        "nomic-embed-text" → "nomic-embed-text"

    Args:
        model: Model name from request

    Returns:
        Normalized model name
    """
    if not model:
        return model

    # Remove :latest suffix
    if model.endswith(":latest"):
        return model[:-7]

    return model


def estimate_gpu_capability(
    small_embedding_time: float, batch_embedding_time: float
) -> str:
    """
    Estimate GPU capability based on embedding performance.

    FlockParser pattern:
    - Run small test: embed("test")
    - Run batch test: embed(["test"] * 50)
    - Compare timings to infer GPU status

    Args:
        small_embedding_time: Time for single embedding (seconds)
        batch_embedding_time: Time for 50 embeddings (seconds)

    Returns:
        GPU capability level:
        - "Full GPU" - Fast performance
        - "GPU (VRAM constrained)" - Has GPU but limited
        - "CPU only" - No GPU or exhausted
    """
    if small_embedding_time < 0.3 and batch_embedding_time < 2.0:
        return "Full GPU"
    elif small_embedding_time < 0.5 and batch_embedding_time < 4.0:
        return "GPU (VRAM constrained)"
    else:
        return "CPU only"


def should_force_cpu(node_config: Dict) -> bool:
    """
    Check if node should be forced to use CPU.

    FlockParser pattern:
    - Support per-node force_cpu flag
    - Useful for debugging, testing, thermal issues

    Example:
        {"url": "http://10.9.66.124:11434", "force_cpu": true}

    Args:
        node_config: Node configuration dict

    Returns:
        True if should force CPU mode
    """
    return node_config.get("force_cpu", False)
