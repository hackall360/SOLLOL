"""
Example: Multi-machine SOLLOL setup.

This demonstrates how to configure SOLLOL for a distributed deployment
across multiple machines with multiple OLLOL instances.
"""
from sollol import SOLLOL, SOLLOLConfig


def machine_1_setup():
    """
    Machine 1: Primary gateway with local + remote OLLOL hosts.

    This machine runs the SOLLOL gateway and coordinates requests
    across all available OLLOL nodes in the cluster.
    """
    print("=" * 60)
    print("Machine 1: Primary SOLLOL Gateway")
    print("=" * 60)

    config = SOLLOLConfig(
        # Cluster resources
        ray_workers=6,  # More workers for high throughput
        dask_workers=4,

        # All OLLOL hosts in the cluster
        hosts=[
            "10.0.0.1:11434",  # Local (this machine)
            "10.0.0.2:11434",  # Remote machine 2
            "10.0.0.3:11434",  # Remote machine 3
            "10.0.0.4:11434",  # Remote GPU server
        ],

        # Performance tuning for production
        autobatch_interval=30,  # Fast batch processing
        adaptive_metrics_interval=20,  # Frequent metric updates
        routing_strategy="performance",  # Always use best node

        # Ports
        gateway_port=8000,
        metrics_port=9090,
    )

    sollol = SOLLOL(config)
    print("\n📋 Configuration:")
    print(f"  Gateway: http://10.0.0.1:8000")
    print(f"  Metrics: http://10.0.0.1:9090/metrics")
    print(f"  Hosts: {len(config.hosts)}")
    print()

    return sollol


def machine_2_setup():
    """
    Machine 2: Secondary gateway with shared Dask scheduler.

    This machine runs another SOLLOL gateway connected to a shared
    Dask scheduler for distributed batch processing.
    """
    print("=" * 60)
    print("Machine 2: Secondary SOLLOL Gateway")
    print("=" * 60)

    config = SOLLOLConfig(
        # Cluster resources
        ray_workers=4,
        dask_workers=4,
        dask_scheduler="tcp://10.0.0.1:8786",  # Connect to shared scheduler

        # Same OLLOL hosts
        hosts=[
            "10.0.0.1:11434",
            "10.0.0.2:11434",
            "10.0.0.3:11434",
            "10.0.0.4:11434",
        ],

        # Use different ports to avoid conflicts
        gateway_port=8001,  # Different port
        metrics_port=9091,  # Different metrics port

        routing_strategy="performance",
    )

    sollol = SOLLOL(config)
    print("\n📋 Configuration:")
    print(f"  Gateway: http://10.0.0.2:8001")
    print(f"  Metrics: http://10.0.0.2:9091/metrics")
    print(f"  Shared Dask: {config.dask_scheduler}")
    print()

    return sollol


def gpu_heavy_workload_setup():
    """
    Example: Configuration optimized for GPU-heavy workloads.

    This setup prioritizes GPU-equipped nodes and uses aggressive
    batch processing for embeddings.
    """
    print("=" * 60)
    print("GPU-Heavy Workload Configuration")
    print("=" * 60)

    config = SOLLOLConfig(
        # More Dask workers for batch embeddings
        ray_workers=2,
        dask_workers=8,  # Heavy batch processing

        # Prioritize GPU nodes (listed first)
        hosts=[
            "gpu-server-1:11434",  # Priority 0 (GPU)
            "gpu-server-2:11434",  # Priority 1 (GPU)
            "cpu-server-1:11434",  # Priority 2 (CPU fallback)
        ],

        # Aggressive batching for embeddings
        autobatch_interval=15,  # Batch every 15 seconds
        autobatch_min_batch_size=10,  # Wait for at least 10 docs
        autobatch_max_batch_size=500,  # Process up to 500 at once

        routing_strategy="priority",  # Prefer GPU nodes
    )

    sollol = SOLLOL(config)
    print("\n📋 Optimizations:")
    print(f"  Dask workers: {config.dask_workers} (heavy batch)")
    print(f"  Batch interval: {config.autobatch_interval}s")
    print(f"  Max batch size: {config.autobatch_max_batch_size}")
    print()

    return sollol


def low_latency_setup():
    """
    Example: Configuration optimized for low-latency live requests.

    This setup minimizes latency with more Ray workers and less
    aggressive batching.
    """
    print("=" * 60)
    print("Low-Latency Configuration")
    print("=" * 60)

    config = SOLLOLConfig(
        # Many Ray workers for concurrent requests
        ray_workers=8,  # High concurrency
        dask_workers=2,  # Minimal batch processing

        hosts=["127.0.0.1:11434"],

        # Minimal batching
        autobatch_enabled=False,  # Disable autobatch

        # Fast metric updates for responsive routing
        adaptive_metrics_interval=15,

        # Aggressive retries
        max_retries=5,
        retry_backoff_multiplier=0.3,

        routing_strategy="performance",
    )

    sollol = SOLLOL(config)
    print("\n📋 Optimizations:")
    print(f"  Ray workers: {config.ray_workers} (high concurrency)")
    print(f"  Autobatch: {config.autobatch_enabled}")
    print(f"  Metrics interval: {config.adaptive_metrics_interval}s")
    print()

    return sollol


# ============================================================================
# Main execution
# ============================================================================

if __name__ == "__main__":
    import sys

    print("SOLLOL Multi-Machine Setup Examples\n")

    if len(sys.argv) < 2:
        print("Usage: python multi_machine_setup.py <setup_type>")
        print("\nAvailable setups:")
        print("  machine1     - Primary gateway with full cluster")
        print("  machine2     - Secondary gateway with shared Dask")
        print("  gpu-heavy    - Optimized for GPU-heavy embeddings")
        print("  low-latency  - Optimized for low-latency requests")
        print()
        print("Example:")
        print("  python multi_machine_setup.py machine1")
        sys.exit(1)

    setup_type = sys.argv[1].lower()

    if setup_type == "machine1":
        sollol = machine_1_setup()
    elif setup_type == "machine2":
        sollol = machine_2_setup()
    elif setup_type == "gpu-heavy":
        sollol = gpu_heavy_workload_setup()
    elif setup_type == "low-latency":
        sollol = low_latency_setup()
    else:
        print(f"❌ Unknown setup type: {setup_type}")
        sys.exit(1)

    # Start SOLLOL
    print("🚀 Starting SOLLOL...\n")
    sollol.start(blocking=False)

    # Show status
    import time
    time.sleep(2)

    status = sollol.get_status()
    print("📊 Status:")
    print(f"  Running: {status['running']}")
    print(f"  Ray workers: {status['ray_workers']}")
    print(f"  Endpoints:")
    for name, url in status['endpoints'].items():
        print(f"    {name}: {url}")

    print("\nPress Ctrl+C to stop...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    sollol.stop()
    print("\n✅ Stopped")
