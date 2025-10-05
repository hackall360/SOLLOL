#!/usr/bin/env python3
"""
REAL integration test - actually starts Ray/Dask
"""
import sys
from sollol import SOLLOL, SOLLOLConfig


def main():
    print("🔥 ACTUAL SOLLOL INTEGRATION TEST")
    print("=" * 60)

    try:
        config = SOLLOLConfig(
            ray_workers=1,
            dask_workers=1,
            hosts=["127.0.0.1:11434"],
            gateway_port=8888,
            metrics_port=9999
        )

        print("\n1. Creating SOLLOL instance...")
        sollol = SOLLOL(config)
        print("   ✅ Created")

        print("\n2. Initializing Ray + Dask clusters...")
        sollol._initialize_clusters()

        print(f"   ✅ Ray actors: {len(sollol._ray_actors)}")
        print(f"   ✅ Dask client: {sollol._dask_client is not None}")

        status = sollol.get_status()
        print(f"\n3. Status:")
        print(f"   Initialized: {status['initialized']}")
        print(f"   Ray workers: {status['ray_workers']}")

        print("\n✅ REAL TEST PASSED - Ray and Dask initialized successfully")
        sys.exit(0)

    except Exception as e:
        print(f"\n❌ REAL TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
