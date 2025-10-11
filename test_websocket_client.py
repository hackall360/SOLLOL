#!/usr/bin/env python3
"""Test WebSocket client to verify dashboard is sending messages."""

import json
import time
import threading
from websocket import create_connection

def test_websocket():
    print("🔌 Connecting to WebSocket...")
    ws = create_connection("ws://localhost:8080/ws/network/ollama_activity")
    print("✅ Connected to WebSocket")

    def receive_messages():
        """Receive messages in a thread."""
        try:
            while True:
                message = ws.recv()
                print(f"📥 Received: {message}")
                data = json.loads(message)
                print(f"   Type: {data.get('type')}")
                print(f"   Message: {data.get('message')}")
        except Exception as e:
            print(f"❌ Error receiving: {e}")

    # Start receiver thread
    receiver = threading.Thread(target=receive_messages, daemon=True)
    receiver.start()

    # Wait for messages
    print("\n⏳ Waiting 30 seconds for messages...")
    print("   (Make a request with: python3 test_activity.py)")
    time.sleep(30)

    ws.close()
    print("\n✅ Test complete")

if __name__ == "__main__":
    try:
        test_websocket()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
