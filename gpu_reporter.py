#!/usr/bin/env python3
"""
GPU Stats Reporter for SOLLOL
Runs on each Ollama node to publish accurate GPU metrics to Redis.

Requires: pip install gpustat redis requests

Usage:
    python3 gpu_reporter.py --redis-host 10.9.66.154 --node-id 10.9.66.90:11434
"""

import argparse
import json
import logging
import subprocess
import time
from typing import Dict, Optional

import redis
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GPUReporter:
    """Reports accurate GPU stats from gpustat (unified) or fallback to vendor tools."""

    def __init__(self, redis_host: str, redis_port: int, node_id: str, ollama_port: int = 11434):
        """
        Initialize GPU reporter.

        Args:
            redis_host: Redis server hostname
            redis_port: Redis server port
            node_id: Node identifier (e.g., "10.9.66.90:11434")
            ollama_port: Ollama API port (default: 11434)
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.node_id = node_id
        self.ollama_port = ollama_port
        self.redis_client = None
        self.gpu_type = self._detect_gpu_type()
        self.use_gpustat = self._check_gpustat_available()

    def _detect_gpu_type(self) -> str:
        """Detect GPU vendor (NVIDIA, AMD, Intel, or None)."""
        try:
            subprocess.run(["nvidia-smi", "--version"],
                         capture_output=True, check=True, timeout=2)
            return "nvidia"
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        try:
            subprocess.run(["rocm-smi", "--version"],
                         capture_output=True, check=True, timeout=2)
            return "amd"
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        try:
            # Try xpu-smi (Intel Arc GPUs)
            subprocess.run(["xpu-smi", "discovery"],
                         capture_output=True, check=True, timeout=2)
            return "intel"
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        try:
            # Try intel_gpu_top (integrated graphics)
            subprocess.run(["intel_gpu_top", "-h"],
                         capture_output=True, check=True, timeout=2)
            return "intel"
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return "none"

    def _check_gpustat_available(self) -> bool:
        """Check if gpustat is installed and working."""
        try:
            import gpustat
            # Test if it can actually get stats
            gpustat.new_query()
            return True
        except (ImportError, Exception):
            return False

    def check_ollama_gpu_usage(self) -> bool:
        """
        Check if Ollama is actually using the GPU.
        Returns True if any loaded models have size_vram > 0.
        """
        try:
            response = requests.get(
                f"http://localhost:{self.ollama_port}/api/ps",
                timeout=2
            )
            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])

                # Check if ANY model is using GPU
                for model in models:
                    if model.get("size_vram", 0) > 0:
                        return True

                # No models using GPU
                return False
            else:
                logger.warning(f"Ollama /api/ps returned {response.status_code}")
                return False

        except Exception as e:
            logger.debug(f"Failed to check Ollama GPU usage: {e}")
            return False

    def get_gpustat_stats(self) -> Optional[Dict]:
        """Get GPU stats using gpustat (unified across vendors)."""
        try:
            import gpustat

            gpu_query = gpustat.new_query()
            gpus = []

            for gpu in gpu_query.gpus:
                gpus.append({
                    "index": gpu.index,
                    "name": gpu.name,
                    "memory_total_mb": gpu.memory_total,
                    "memory_free_mb": gpu.memory_free,
                    "memory_used_mb": gpu.memory_used,
                    "utilization_percent": gpu.utilization,
                    "temperature_c": gpu.temperature if gpu.temperature else 0
                })

            return {
                "vendor": "nvidia" if gpus else "unknown",  # gpustat primarily for NVIDIA
                "gpus": gpus,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Failed to get gpustat stats: {e}")
            return None

    def get_nvidia_stats(self) -> Optional[Dict]:
        """Get GPU stats from nvidia-smi."""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,memory.total,memory.free,memory.used,utilization.gpu,temperature.gpu",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )

            lines = result.stdout.strip().split('\n')
            gpus = []

            for line in lines:
                parts = [p.strip() for p in line.split(',')]
                if len(parts) >= 7:
                    gpus.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "memory_total_mb": int(parts[2]),
                        "memory_free_mb": int(parts[3]),
                        "memory_used_mb": int(parts[4]),
                        "utilization_percent": int(parts[5]),
                        "temperature_c": int(parts[6])
                    })

            return {
                "vendor": "nvidia",
                "gpus": gpus,
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Failed to get NVIDIA GPU stats: {e}")
            return None

    def get_amd_stats(self) -> Optional[Dict]:
        """Get GPU stats from rocm-smi."""
        try:
            # rocm-smi output parsing (simplified)
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram", "--json"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )

            data = json.loads(result.stdout)
            # Parse AMD GPU stats (format varies by ROCm version)
            # This is a simplified version

            return {
                "vendor": "amd",
                "gpus": [],  # Would parse from rocm-smi JSON
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Failed to get AMD GPU stats: {e}")
            return None

    def get_intel_stats(self) -> Optional[Dict]:
        """Get GPU stats from Intel xpu-smi or intel_gpu_top."""
        try:
            # Try xpu-smi first (Arc GPUs)
            result = subprocess.run(
                ["xpu-smi", "dump", "-d", "0", "-m", "0,1,5,18"],
                # -m 0: Device ID
                # -m 1: Memory used/total
                # -m 5: GPU utilization
                # -m 18: Temperature
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )

            # Parse xpu-smi output (format varies, simplified here)
            # Would need proper parsing based on actual output format
            gpus = []

            # Try to get basic info from xpu-smi discovery
            discovery_result = subprocess.run(
                ["xpu-smi", "discovery", "--json"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5
            )

            if discovery_result.returncode == 0:
                try:
                    discovery_data = json.loads(discovery_result.stdout)
                    # Parse device info from discovery JSON
                    # Simplified - actual format depends on xpu-smi version
                except json.JSONDecodeError:
                    pass

            return {
                "vendor": "intel",
                "gpus": gpus,  # Would populate from parsed data
                "timestamp": time.time()
            }

        except Exception as e:
            logger.debug(f"xpu-smi failed, trying intel_gpu_top: {e}")

        try:
            # Fallback to intel_gpu_top (requires root or perf_event_paranoid=-1)
            # This is for integrated graphics
            result = subprocess.run(
                ["intel_gpu_top", "-l", "-s", "1000"],  # Single sample
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )

            # Parse intel_gpu_top output
            # Format: various lines with GPU utilization info
            # Simplified version

            return {
                "vendor": "intel",
                "gpus": [{
                    "index": 0,
                    "name": "Intel Integrated Graphics",
                    "memory_total_mb": 0,  # Often shared with system RAM
                    "memory_free_mb": 0,
                    "memory_used_mb": 0,
                    "utilization_percent": 0,
                    "temperature_c": 0
                }],
                "timestamp": time.time()
            }

        except Exception as e:
            logger.error(f"Failed to get Intel GPU stats: {e}")
            return None

    def get_gpu_stats(self) -> Optional[Dict]:
        """
        Get GPU stats with intelligent detection.

        Priority:
        1. Use gpustat (unified, if available)
        2. Fall back to vendor-specific tools
        3. Check if Ollama is actually using GPU
        """
        stats = None

        # Try gpustat first (easiest, works across vendors)
        if self.use_gpustat:
            stats = self.get_gpustat_stats()

        # Fall back to vendor-specific tools
        if not stats:
            if self.gpu_type == "nvidia":
                stats = self.get_nvidia_stats()
            elif self.gpu_type == "amd":
                stats = self.get_amd_stats()
            elif self.gpu_type == "intel":
                stats = self.get_intel_stats()

        # Critical check: Is Ollama actually using the GPU?
        if stats and stats.get("gpus"):
            ollama_using_gpu = self.check_ollama_gpu_usage()

            if not ollama_using_gpu:
                # GPU hardware exists but Ollama is NOT using it (CPU-only mode)
                logger.warning(
                    f"⚠️  GPU detected ({stats['gpus'][0]['name']}) but Ollama is running in CPU-only mode"
                )
                logger.warning("   All models have size_vram=0. Reporting as CPU-only to SOLLOL.")

                # Override to CPU-only
                return {
                    "vendor": "none",
                    "gpus": [],
                    "timestamp": time.time(),
                    "note": "GPU present but Ollama using CPU-only"
                }

        return stats

    def connect_redis(self):
        """Connect to Redis server."""
        try:
            self.redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            self.redis_client.ping()
            logger.info(f"✅ Connected to Redis at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self.redis_client = None

    def publish_stats(self, stats: Dict):
        """Publish GPU stats to Redis stream."""
        if not self.redis_client:
            logger.warning("Redis not connected, skipping publish")
            return

        try:
            # Publish to sollol:gpu:stats stream
            stream_key = "sollol:gpu:stats"

            # Add node_id to stats
            stats["node_id"] = self.node_id

            # Flatten stats for Redis stream (xadd requires string values)
            flat_stats = {}
            for key, value in stats.items():
                if isinstance(value, (list, dict)):
                    flat_stats[key] = json.dumps(value)
                else:
                    flat_stats[key] = str(value)

            # Publish to Redis stream
            message_id = self.redis_client.xadd(
                stream_key,
                flat_stats,
                maxlen=1000  # Keep last 1000 entries
            )

            logger.debug(f"Published GPU stats for {self.node_id}: {message_id}")

            # Also set as key for quick lookup (JSON format for easy retrieval)
            key = f"sollol:gpu:{self.node_id}"
            self.redis_client.setex(
                key,
                120,  # Expire after 120s (2 minutes - prevents stale data, allows for network hiccups)
                json.dumps(stats)
            )

        except Exception as e:
            logger.error(f"Failed to publish stats to Redis: {e}")

    def run(self, interval: int = 5):
        """
        Run reporter loop.

        Args:
            interval: Update interval in seconds (default: 5)
        """
        logger.info(f"🚀 Starting GPU reporter for {self.node_id}")
        logger.info(f"   GPU Type: {self.gpu_type}")
        logger.info(f"   Redis: {self.redis_host}:{self.redis_port}")
        logger.info(f"   Update Interval: {interval}s")

        if self.gpu_type == "none":
            logger.warning("⚠️  No GPU detected (nvidia-smi/rocm-smi not found)")
            logger.info("   Will report CPU-only status")

        # Initial connection
        self.connect_redis()

        while True:
            try:
                # Get GPU stats
                stats = self.get_gpu_stats()

                if stats:
                    # Publish to Redis
                    self.publish_stats(stats)

                    # Log summary
                    if stats.get("gpus"):
                        for gpu in stats["gpus"]:
                            logger.info(
                                f"GPU {gpu['index']}: {gpu['name']} | "
                                f"VRAM: {gpu['memory_used_mb']}/{gpu['memory_total_mb']}MB | "
                                f"Util: {gpu['utilization_percent']}% | "
                                f"Temp: {gpu['temperature_c']}°C"
                            )
                else:
                    # No GPU or failed to get stats
                    cpu_only_stats = {
                        "vendor": "none",
                        "gpus": [],
                        "timestamp": time.time(),
                        "node_id": self.node_id
                    }
                    self.publish_stats(cpu_only_stats)
                    logger.debug(f"Published CPU-only status for {self.node_id}")

                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("Shutting down GPU reporter...")
                break
            except Exception as e:
                logger.error(f"Error in reporter loop: {e}")
                time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        description="SOLLOL GPU Stats Reporter - Publishes accurate GPU metrics to Redis"
    )
    parser.add_argument(
        "--redis-host",
        required=True,
        help="Redis server hostname/IP"
    )
    parser.add_argument(
        "--redis-port",
        type=int,
        default=6379,
        help="Redis server port (default: 6379)"
    )
    parser.add_argument(
        "--node-id",
        required=True,
        help="Node identifier (e.g., 10.9.66.90:11434)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="Update interval in seconds (default: 5)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    reporter = GPUReporter(
        redis_host=args.redis_host,
        redis_port=args.redis_port,
        node_id=args.node_id
    )

    reporter.run(interval=args.interval)


if __name__ == "__main__":
    main()
