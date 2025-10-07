# Known Issues

## ~~Dask Worker Logging Warnings~~ (SOLVED in v0.9.18)

**Issue**: When the UnifiedDashboard was initialized with `enable_dask=True`, Dask worker processes generated verbose "Task queue depth" warnings that spammed CLI output after clicking the dashboard link.

**Root Cause**: Dask worker **processes** run with completely isolated logging configurations that don't inherit from the main process. The warnings were triggered by HTTP requests to the Dask dashboard and logged at WARNING level from within worker processes.

**Solution** (Implemented in v0.9.18):
Use `processes=False` when creating LocalCluster to run workers as **threads** instead of separate processes:

```python
cluster = LocalCluster(
    n_workers=1,
    threads_per_worker=2,
    processes=False,  # Use threads, not processes
    dashboard_address=f":{dask_dashboard_port}",
    silence_logs=logging.CRITICAL,
)
```

**Why This Works**:
- Threaded workers run in the same process as the application
- They share the same logging configuration
- Application-level logging suppression (`logging.getLogger('distributed').setLevel(logging.ERROR)`) now works
- Dashboard functionality is unaffected

**Trade-offs**:
- Threaded workers share GIL (Global Interpreter Lock) with main process
- For SOLLOL's use case (lightweight dashboard observability), this is acceptable
- For compute-intensive tasks, process-based workers would be better

**Status**: ✅ RESOLVED - UnifiedDashboard now uses threaded workers by default.
