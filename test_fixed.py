#!/usr/bin/env python3
"""Test with fork mode fix"""
from sollol import SOLLOL, SOLLOLConfig

print("🔥 TESTING RAY + DASK (FORK MODE)")
print("=" * 60)

config = SOLLOLConfig(
    ray_workers=1,
    dask_workers=1,
    hosts=["127.0.0.1:11434"]
)

print("\n1. Creating SOLLOL...")
sollol = SOLLOL(config)

print("\n2. Initializing clusters...")
sollol._initialize_clusters()

print(f"\n3. Results:")
print(f"   Ray actors: {len(sollol._ray_actors)}")
print(f"   Dask client: {sollol._dask_client is not None}")

if sollol._ray_actors and sollol._dask_client:
    print("\n✅ FULL TEST PASSED - Ray AND Dask working!")
else:
    print("\n❌ Test incomplete")
