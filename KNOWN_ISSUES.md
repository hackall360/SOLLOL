# Known Issues

## Dask Worker Logging Warnings (SOLLOL Issue)

**Issue**: When the UnifiedDashboard is initialized with `enable_dask=True`, Dask worker processes generate verbose "Task queue depth" warnings that spam the CLI output after clicking the dashboard link.

**Root Cause**: Dask worker processes run with completely isolated logging configurations that don't inherit from the main process. The warnings are triggered by HTTP requests to the Dask dashboard and are logged at the WARNING level from within worker processes.

**Impact**:
- Warnings don't affect functionality but clutter CLI output
- Makes it difficult to type commands in interactive applications
- Particularly noticeable in SynapticLlamas CLI after dashboard loads

**Attempted Solutions** (all unsuccessful):
1. Setting `logging.getLogger('distributed').setLevel(logging.ERROR)` in main process
2. Configuring Dask with `dask.config.set({'distributed.logging.distributed': 'error'})`
3. Setting environment variables (`DASK_DISTRIBUTED__LOGGING__DISTRIBUTED`)
4. Using `Client(silence_logs=logging.ERROR)` parameter (doesn't exist)
5. Creating LocalCluster with custom worker configuration
6. Using `client.run()` to suppress logging inside worker processes
7. Adding logging filters to root logger

**Workaround**: Disable Dask dashboard in applications where CLI output clarity is critical:
```python
dashboard = UnifiedDashboard(
    router=router,
    enable_dask=False,  # Disable to prevent worker warnings
)
```

**Status**: This is a fundamental Dask architecture limitation. Worker processes have independent logging configurations that cannot be controlled from the parent process. A proper fix would require changes to Dask itself.

**Recommendation**: Applications using SOLLOL's UnifiedDashboard should provide a config toggle to enable/disable Dask observability based on user preference.
