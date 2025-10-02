"""
Example: Integrating SOLLOL with a Python application.

This shows how an application like SynapticLlamas or FlockParser
could embed SOLLOL entirely within its own configuration.
"""
import time
from sollol import SOLLOL, SOLLOLConfig


class MyApplication:
    """
    Example application that integrates SOLLOL.

    SOLLOL is fully contained within the application - no external
    config files or CLI commands needed.
    """

    def __init__(self, app_name: str = "MyApp"):
        self.app_name = app_name
        self.sollol = None

        # Application-specific SOLLOL configuration
        self.sollol_config = SOLLOLConfig(
            ray_workers=4,
            dask_workers=2,
            hosts=[
                "127.0.0.1:11434",
                # Add more hosts as your deployment grows
                # "10.0.0.2:11434",
                # "10.0.0.3:11434",
            ],
            autobatch_interval=45,  # App-specific: batch every 45 seconds
            routing_strategy="performance",  # Use adaptive routing
            metrics_enabled=True,
            gateway_port=8000,
        )

    def start(self):
        """Start the application and SOLLOL."""
        print(f"🚀 Starting {self.app_name}...")

        # Initialize and start SOLLOL
        print(f"[{self.app_name}] Initializing SOLLOL...")
        self.sollol = SOLLOL(self.sollol_config)
        self.sollol.start(blocking=False)  # Non-blocking

        print(f"[{self.app_name}] SOLLOL started")
        print(f"[{self.app_name}] Application ready")
        print()

    def do_work(self):
        """Simulate application work that uses SOLLOL."""
        print(f"[{self.app_name}] Performing application tasks...")

        # Your application can now use SOLLOL's API
        # Example: Send chat completion request
        import httpx

        try:
            response = httpx.post(
                "http://localhost:8000/api/chat",
                json={
                    "model": "llama3.2",
                    "messages": [
                        {"role": "user", "content": "Hello from my application!"}
                    ]
                },
                timeout=30.0
            )

            if response.status_code == 200:
                result = response.json()
                print(f"[{self.app_name}] ✅ Got response from SOLLOL")
                # Process result...
            else:
                print(f"[{self.app_name}] ⚠️  Request failed: {response.status_code}")

        except Exception as e:
            print(f"[{self.app_name}] ❌ Error: {e}")

        # Check SOLLOL status
        status = self.sollol.get_status()
        print(f"[{self.app_name}] SOLLOL status: {status['running']}")

    def adjust_resources(self, new_workers: int):
        """Dynamically adjust SOLLOL resources based on application load."""
        print(f"[{self.app_name}] Adjusting resources to {new_workers} workers...")

        self.sollol.update_config(ray_workers=new_workers)

        # Note: restart required for this change
        print(f"[{self.app_name}] Configuration updated")
        print(f"[{self.app_name}] ⚠️  Restart SOLLOL to apply changes")

    def monitor(self):
        """Monitor SOLLOL performance."""
        print(f"[{self.app_name}] Monitoring SOLLOL...")

        stats = self.sollol.get_stats()

        if "error" in stats:
            print(f"[{self.app_name}] ⚠️  Could not get stats: {stats['error']}")
            return

        print(f"[{self.app_name}] Host statistics:")
        for host_info in stats.get("hosts", []):
            print(f"  {host_info['host']}:")
            print(f"    Available: {host_info['available']}")
            print(f"    Latency: {host_info['latency_ms']:.1f}ms")
            print(f"    Success rate: {host_info['success_rate']:.1%}")

    def stop(self):
        """Stop the application and SOLLOL."""
        print(f"\n[{self.app_name}] Shutting down...")

        if self.sollol:
            self.sollol.stop()

        print(f"[{self.app_name}] Shutdown complete")


# ============================================================================
# Example usage
# ============================================================================

if __name__ == "__main__":
    # Create application instance
    app = MyApplication(app_name="SynapticLlamas")

    # Start application (includes SOLLOL)
    app.start()

    # Give SOLLOL a moment to fully start
    time.sleep(3)

    # Do application work
    app.do_work()

    # Monitor performance
    time.sleep(2)
    app.monitor()

    # Optionally adjust resources based on load
    # app.adjust_resources(new_workers=6)

    # Keep running
    print("\nPress Ctrl+C to stop...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    # Stop application
    app.stop()

    print("\n✅ Application stopped")
