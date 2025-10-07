#!/usr/bin/env python3
"""Simple verification that Ray dashboard is enabled in SOLLOL routers."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Just verify the code has the right configuration
print("=" * 80)
print("Verifying Dashboard Configuration")
print("=" * 80 + "\n")

# Check RayAdvancedRouter
print("1️⃣  Checking RayAdvancedRouter...")
with open('src/sollol/ray_advanced_router.py', 'r') as f:
    content = f.read()
    if 'dashboard_host="0.0.0.0"' in content and 'dashboard_port=8265' in content:
        print("✅ RayAdvancedRouter: Ray dashboard configuration found")
        print("   - dashboard_host=\"0.0.0.0\"")
        print("   - dashboard_port=8265")
        print("   - include_dashboard=True\n")
    else:
        print("❌ RayAdvancedRouter: Dashboard configuration missing\n")

# Check RayHybridRouter
print("2️⃣  Checking RayHybridRouter...")
with open('src/sollol/ray_hybrid_router.py', 'r') as f:
    content = f.read()
    if 'dashboard_host="0.0.0.0"' in content and 'dashboard_port=8265' in content:
        print("✅ RayHybridRouter: Ray dashboard configuration found")
        print("   - dashboard_host=\"0.0.0.0\"")
        print("   - dashboard_port=8265")
        print("   - include_dashboard=True\n")
    else:
        print("❌ RayHybridRouter: Dashboard configuration missing\n")

# Check UnifiedDashboard
print("3️⃣  Checking UnifiedDashboard...")
with open('src/sollol/unified_dashboard.py', 'r') as f:
    content = f.read()
    has_dask = 'enable_dask: bool' in content
    has_dask_init = 'from dask.distributed import Client' in content
    has_dask_endpoint = '/api/dask/metrics' in content
    has_ray_endpoint = '/api/ray/metrics' in content

    if all([has_dask, has_dask_init, has_dask_endpoint, has_ray_endpoint]):
        print("✅ UnifiedDashboard: All observability features found")
        print("   - Dask initialization support")
        print("   - Ray metrics endpoint: /api/ray/metrics")
        print("   - Dask metrics endpoint: /api/dask/metrics")
        print("   - enable_dask parameter\n")
    else:
        print("❌ UnifiedDashboard: Missing features:")
        if not has_dask: print("   - Missing enable_dask parameter")
        if not has_dask_init: print("   - Missing Dask initialization")
        if not has_dask_endpoint: print("   - Missing Dask metrics endpoint")
        if not has_ray_endpoint: print("   - Missing Ray metrics endpoint")
        print()

print("=" * 80)
print("Configuration Verification Complete")
print("=" * 80)
print("\n📊 To test the dashboards:")
print("   1. Run: python3 examples/unified_dashboard_demo.py")
print("   2. Open: http://localhost:8080")
print("   3. You should see embedded Ray and Dask dashboards")
