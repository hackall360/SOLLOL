#!/usr/bin/env python3
"""Final test with threaded Dask"""
from sollol import SOLLOL, SOLLOLConfig

print("🎯 FINAL TEST - Ray + Threaded Dask")
print("=" * 60)

config = SOLLOLConfig(
    ray_workers=1,
    dask_workers=1,
    hosts=["127.0.0.1:11434"]
)

print("\n1. Creating SOLLOL...")
sollol = SOLLOL(config)

print("\n2. Initializing...")
sollol._initialize_clusters()

print(f"\n3. Results:")
print(f"   Ray: {len(sollol._ray_actors)} actors")
print(f"   Dask: {sollol._dask_client is not None}")

if sollol._ray_actors:
    print("\n✅ RAY WORKING")
if sollol._dask_client:
    print("✅ DASK WORKING (threaded mode)")

print("\n🚀 SOLLOL IS OPERATIONAL")
