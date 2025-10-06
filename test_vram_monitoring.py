#!/usr/bin/env python3
"""
Test script for FlockParser-inspired VRAM monitoring and node health detection.

Tests:
1. VRAM exhaustion detection
2. Node health monitoring
3. Model name normalization
4. GPU capability estimation
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sollol.node_health import (
    NodeHealthMonitor,
    normalize_model_name,
    estimate_gpu_capability,
    should_force_cpu,
    estimate_model_size_mb,
    can_model_fit_vram,
)


def test_vram_exhaustion_detection():
    """Test VRAM exhaustion detection."""
    print("\n🧪 Testing VRAM Exhaustion Detection...")

    monitor = NodeHealthMonitor()
    node_key = "gpu-node-1:11434"

    # Simulate healthy GPU performance (baseline)
    print("   Setting baseline (healthy GPU performance)...")
    for i in range(5):
        monitor.update_baseline(node_key, 300.0, is_gpu=True)  # 300ms - healthy

    assert node_key in monitor.node_baselines
    baseline = monitor.node_baselines[node_key]
    print(f"   ✅ Baseline established: {baseline['baseline_latency_ms']:.0f}ms")

    # Simulate sudden latency spike (VRAM exhaustion → CPU fallback)
    print("   Simulating VRAM exhaustion (GPU → CPU fallback)...")
    exhausted = monitor.detect_vram_exhaustion(node_key, 2500.0)  # 2.5s - CPU fallback

    assert exhausted, "Should detect VRAM exhaustion"
    print(f"   ✅ VRAM exhaustion detected! (2500ms >> {baseline['baseline_latency_ms']:.0f}ms)")

    # Check health penalty
    penalty = monitor.get_health_penalty(node_key)
    assert penalty == 100.0, "Should apply heavy penalty"
    print(f"   ✅ Health penalty applied: {penalty}")

    # Check degraded status
    assert monitor.is_node_degraded(node_key)
    print("   ✅ Node marked as degraded")

    # Simulate recovery (latency back to normal)
    print("   Simulating recovery...")
    monitor.detect_vram_exhaustion(node_key, 350.0)  # Back to normal

    assert not monitor.is_node_degraded(node_key)
    print("   ✅ Node recovered from VRAM exhaustion")


def test_model_name_normalization():
    """Test model name normalization."""
    print("\n🧪 Testing Model Name Normalization...")

    test_cases = [
        ("llama3.1:latest", "llama3.1"),
        ("llama3.1:8b", "llama3.1:8b"),
        ("llama3.1:70b", "llama3.1:70b"),
        ("nomic-embed-text", "nomic-embed-text"),
        ("codellama:latest", "codellama"),
    ]

    for input_name, expected in test_cases:
        result = normalize_model_name(input_name)
        assert result == expected, f"Expected {expected}, got {result}"
        print(f"   ✅ '{input_name}' → '{result}'")


def test_gpu_capability_estimation():
    """Test GPU capability estimation."""
    print("\n🧪 Testing GPU Capability Estimation...")

    # Full GPU (fast performance)
    capability = estimate_gpu_capability(0.2, 1.5)
    assert capability == "Full GPU"
    print(f"   ✅ Fast performance (0.2s, 1.5s) → {capability}")

    # GPU with VRAM constraints (medium performance)
    capability = estimate_gpu_capability(0.4, 3.0)
    assert capability == "GPU (VRAM constrained)"
    print(f"   ✅ Medium performance (0.4s, 3.0s) → {capability}")

    # CPU only (slow performance)
    capability = estimate_gpu_capability(0.8, 8.0)
    assert capability == "CPU only"
    print(f"   ✅ Slow performance (0.8s, 8.0s) → {capability}")


def test_force_cpu_flag():
    """Test force_cpu flag parsing."""
    print("\n🧪 Testing Force CPU Flag...")

    # Node with force_cpu=true
    config = {"url": "http://10.9.66.124:11434", "force_cpu": True}
    assert should_force_cpu(config)
    print("   ✅ force_cpu=True detected")

    # Node without force_cpu
    config = {"url": "http://10.9.66.124:11434"}
    assert not should_force_cpu(config)
    print("   ✅ force_cpu=False (default)")


def test_health_monitoring_stats():
    """Test health monitoring statistics."""
    print("\n🧪 Testing Health Monitoring Stats...")

    monitor = NodeHealthMonitor()

    # Add some baselines
    monitor.update_baseline("node1:11434", 300.0, is_gpu=True)
    monitor.update_baseline("node2:11434", 500.0, is_gpu=True)
    monitor.update_baseline("node3:11434", 1500.0, is_gpu=False)  # CPU

    # Trigger VRAM exhaustion on node1
    monitor.detect_vram_exhaustion("node1:11434", 2500.0)

    stats = monitor.get_stats()

    assert stats["monitored_nodes"] == 3
    assert "node1:11434" in stats["degraded_nodes"]
    assert len(stats["degraded_nodes"]) == 1

    print(f"   ✅ Monitored nodes: {stats['monitored_nodes']}")
    print(f"   ✅ Degraded nodes: {stats['degraded_nodes']}")
    print(f"   ✅ Baselines tracked: {len(stats['baselines'])}")


def test_model_size_estimation():
    """Test model size estimation."""
    print("\n🧪 Testing Model Size Estimation...")

    test_cases = [
        ("llama3.1:8b", 8500),
        ("llama3.1:70b", 72000),
        ("llama3.2:1b", 1300),
        ("llama3.2:3b", 3300),
        ("nomic-embed-text", 500),
        ("mistral:7b", 7500),
        ("mixtral:8x7b", 48000),
        ("codellama:70b", 72000),
    ]

    for model, expected_size in test_cases:
        size = estimate_model_size_mb(model)
        assert size == expected_size, f"Expected {expected_size}MB, got {size}MB for {model}"
        print(f"   ✅ {model}: {size}MB")

    # Test unknown model (should infer from suffix)
    size = estimate_model_size_mb("custom-model:13b")
    assert size == 13500
    print(f"   ✅ custom-model:13b: {size}MB (inferred from :13b suffix)")


def test_vram_fit_check():
    """Test VRAM fitting checks."""
    print("\n🧪 Testing VRAM Fit Checks...")

    # Test 1: 8B model on 16GB GPU (should fit)
    can_fit, reason = can_model_fit_vram("llama3.1:8b", available_vram_mb=16000)
    assert can_fit, f"8B should fit in 16GB: {reason}"
    print(f"   ✅ llama3.1:8b on 16GB GPU: {reason}")

    # Test 2: 70B model on 16GB GPU (should NOT fit)
    can_fit, reason = can_model_fit_vram("llama3.1:70b", available_vram_mb=16000)
    assert not can_fit, f"70B should NOT fit in 16GB: {reason}"
    print(f"   ✅ llama3.1:70b on 16GB GPU: BLOCKED - {reason}")

    # Test 3: 70B model on 80GB GPU (should fit)
    can_fit, reason = can_model_fit_vram("llama3.1:70b", available_vram_mb=80000)
    assert can_fit, f"70B should fit in 80GB: {reason}"
    print(f"   ✅ llama3.1:70b on 80GB GPU: {reason}")

    # Test 4: Embedding model on 8GB GPU (should fit)
    can_fit, reason = can_model_fit_vram("nomic-embed-text", available_vram_mb=8000)
    assert can_fit, f"Embedding model should fit in 8GB: {reason}"
    print(f"   ✅ nomic-embed-text on 8GB GPU: {reason}")

    # Test 5: With custom safety margin
    can_fit, reason = can_model_fit_vram(
        "llama3.1:8b", available_vram_mb=10000, safety_margin_mb=2000
    )
    assert not can_fit, f"8B with 2GB margin should NOT fit in 10GB"
    print(f"   ✅ llama3.1:8b on 10GB GPU (2GB margin): BLOCKED - {reason}")


def main():
    print("=" * 70)
    print("🧪 SOLLOL FlockParser-Inspired Features Test Suite")
    print("=" * 70)

    try:
        test_vram_exhaustion_detection()
        test_model_name_normalization()
        test_gpu_capability_estimation()
        test_force_cpu_flag()
        test_health_monitoring_stats()
        test_model_size_estimation()
        test_vram_fit_check()

        print("\n" + "=" * 70)
        print("✅ All FlockParser feature tests passed!")
        print("=" * 70)
        print("\nBattle-tested features from FlockParser production usage:")
        print("  • VRAM Exhaustion Detection - Detects GPU → CPU fallback")
        print("  • Performance Baseline Tracking - 10-sample moving window")
        print("  • Health Penalty System - 100-point penalty for degraded nodes")
        print("  • Model Name Normalization - Handles :latest, :8b variations")
        print("  • GPU Capability Estimation - Small + batch performance tests")
        print("  • Per-Node Force CPU Mode - Debug/testing/thermal management")
        print("  • Model Size Estimation - 20+ common models (1B to 70B)")
        print("  • Pre-Routing VRAM Checks - Prevents OOM crashes (70B on 8GB GPU)")

        return 0

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
