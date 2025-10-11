#!/usr/bin/env python3
"""Test script to generate activity logs for dashboard."""

import sys
import time
from sollol import OllamaPool

def main():
    print("🔧 Creating OllamaPool...")
    pool = OllamaPool()

    print(f"📍 Found {len(pool.nodes)} node(s)")
    for node in pool.nodes:
        print(f"  - {node}")

    print("\n🚀 Making test request...")
    try:
        response = pool.generate(
            model="llama3.2",
            prompt="Say hello in one word",
            stream=False
        )
        print(f"✅ Request completed")
        print(f"📝 Response: {response[:100]}..." if len(response) > 100 else f"📝 Response: {response}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    print("\n⏳ Waiting 2 seconds for Redis publish...")
    time.sleep(2)

    print("✅ Test complete - check dashboard at http://localhost:8080")
    return 0

if __name__ == "__main__":
    sys.exit(main())
