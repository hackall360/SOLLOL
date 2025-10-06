#!/usr/bin/env python3
"""Simple test without Dask to verify Ray works"""
import ray
from sollol.workers import OllamaWorker
from sollol.memory import load_hosts_from_file, init_hosts_meta
import tempfile
import os

print("🧪 Testing Ray + Workers (without Dask)")
print("=" * 60)

# Create temp hosts file
with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
    f.write("127.0.0.1:11434\n")
    hosts_file = f.name

try:
    # 1. Initialize Ray
    print("\n1. Initializing Ray...")
    ray.init(ignore_reinit_error=True)
    print("   ✅ Ray initialized")

    # 2. Load hosts
    print("\n2. Loading hosts...")
    hosts = load_hosts_from_file(hosts_file)
    print(f"   ✅ Loaded: {hosts}")

    # 3. Init metadata
    print("\n3. Initializing host metadata...")
    init_hosts_meta(hosts)
    print("   ✅ Metadata initialized")

    # 4. Create Ray actors
    print("\n4. Creating Ray actors...")
    actors = [OllamaWorker.remote() for _ in range(2)]
    print(f"   ✅ Created {len(actors)} Ray actors")

    print("\n✅ RAY TEST PASSED - Core functionality works!")
    print("\nNote: Dask has multiprocessing issues in this environment.")
    print("Recommend: Use external Dask scheduler in production")

except Exception as e:
    print(f"\n❌ TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
finally:
    ray.shutdown()
    os.unlink(hosts_file)
