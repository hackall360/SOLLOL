#!/usr/bin/env python3
"""Debug script to test NetworkObserver Redis publishing."""

import logging
import time
from sollol import OllamaPool
from sollol.network_observer import get_observer

# Enable debug logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

def main():
    print("🔧 Getting NetworkObserver instance...")
    observer = get_observer()
    print(f"Observer: {observer}")
    print(f"Redis client: {observer.redis_client}")
    print(f"Redis connected: {observer.redis_client is not None}")

    if observer.redis_client:
        try:
            observer.redis_client.ping()
            print("✅ Redis PING successful")
        except Exception as e:
            print(f"❌ Redis PING failed: {e}")

    print("\n🔧 Creating OllamaPool...")
    pool = OllamaPool()
    print(f"📍 Found {len(pool.nodes)} node(s)")

    print("\n🚀 Making test request...")
    try:
        response = pool.generate(
            model="llama3.2",
            prompt="Hi",
            stream=False
        )
        print(f"✅ Request completed")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n⏳ Waiting 2 seconds...")
    time.sleep(2)

    print(f"\n📊 Observer stats: {observer.stats}")
    print(f"📊 Observer events: {len(observer.events)}")
    if observer.events:
        print("Recent events:")
        for event in list(observer.events)[-5:]:
            print(f"  - {event.event_type.value}: {event.backend}")

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
