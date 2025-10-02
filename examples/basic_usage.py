"""
Basic SOLLOL usage example.

This demonstrates the simplest way to use SOLLOL in your application.
"""
from sollol import SOLLOL, SOLLOLConfig

# Example 1: Default configuration (localhost only)
print("=" * 60)
print("Example 1: Default Configuration")
print("=" * 60)

sollol = SOLLOL()  # Uses default config
sollol.start(blocking=False)

# Get status
status = sollol.get_status()
print(f"\nSOLLOL Status:")
print(f"  Running: {status['running']}")
print(f"  Ray workers: {status['ray_workers']}")
print(f"  Gateway: {status['endpoints']['gateway']}")
print(f"  API docs: {status['endpoints']['api_docs']}")

# Stop
input("\nPress Enter to stop SOLLOL...")
sollol.stop()

print("\n" + "=" * 60)
print("Example 2: Custom Configuration")
print("=" * 60)

# Example 2: Custom configuration for production
config = SOLLOLConfig(
    ray_workers=4,
    dask_workers=4,
    hosts=["127.0.0.1:11434"],  # Add your hosts here
    autobatch_interval=30,
    routing_strategy="performance",
    metrics_enabled=True
)

sollol = SOLLOL(config)
sollol.start(blocking=False)

# Check health
import time
time.sleep(2)  # Give it a moment to start

health = sollol.get_health()
print(f"\nHealth Check:")
print(f"  Status: {health.get('status', 'unknown')}")
print(f"  Ray workers: {health.get('ray_workers', 0)}")

# Get statistics
stats = sollol.get_stats()
print(f"\nStatistics:")
print(f"  Hosts: {len(stats.get('hosts', []))}")

# Stop
input("\nPress Enter to stop SOLLOL...")
sollol.stop()

print("\n✅ Examples complete!")
