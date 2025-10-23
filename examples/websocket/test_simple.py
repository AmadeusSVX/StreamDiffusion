"""
Ultra-simple WebSocket test - synchronous client for basic connection testing.
"""

import asyncio
import websockets
import json
import time
import sys


async def test_connection():
    """Simple connection test."""
    uri = "ws://localhost:9000"

    if len(sys.argv) > 1:
        uri = sys.argv[1]

    print(f"\n{'='*50}")
    print(f"Testing WebSocket connection to: {uri}")
    print(f"{'='*50}\n")

    try:
        print(f"1. Connecting to {uri}...")

        async with websockets.connect(uri) as websocket:
            print(f"   ✓ Connected successfully!")

            # Send a test message
            test_msg = {
                "type": "test",
                "data": "Hello from simple test",
                "timestamp": time.time()
            }

            print(f"\n2. Sending test message...")
            await websocket.send(json.dumps(test_msg))
            print(f"   ✓ Message sent: {test_msg['data']}")

            # Wait for response
            print(f"\n3. Waiting for response...")
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                response_data = json.loads(response)
                print(f"   ✓ Response received: {response_data.get('type')}")
                print(f"   Response data: {json.dumps(response_data, indent=2)}")
            except asyncio.TimeoutError:
                print(f"   ✗ No response received (timeout)")

            # Send ping
            print(f"\n4. Sending ping...")
            await websocket.send(json.dumps({"type": "ping"}))
            print(f"   ✓ Ping sent")

            # Wait for pong
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                response_data = json.loads(response)
                if response_data.get("type") == "pong":
                    print(f"   ✓ Pong received")
            except asyncio.TimeoutError:
                print(f"   ✗ No pong received")

            print(f"\n{'='*50}")
            print(f"✓ WebSocket connection test SUCCESSFUL")
            print(f"{'='*50}\n")

    except ConnectionRefusedError as e:
        print(f"\n❌ ERROR: Connection refused")
        print(f"   {e}")
        print(f"\nMake sure the server is running:")
        print(f"   python test_server.py")
        print(f"\nOr if using the main server:")
        print(f"   python server.py")
        print(f"{'='*50}\n")
        return False

    except OSError as e:
        if "10049" in str(e):
            print(f"\n❌ ERROR: Cannot assign requested address")
            print(f"   The address {uri} is not valid on this system")
            print(f"\nTry:")
            print(f"   ws://localhost:8765")
            print(f"   ws://127.0.0.1:8765")
        else:
            print(f"\n❌ ERROR: {e}")
        print(f"{'='*50}\n")
        return False

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}")
        print(f"   {e}")
        import traceback
        print(traceback.format_exc())
        print(f"{'='*50}\n")
        return False

    return True


def main():
    """Run the test."""
    print("\n" + "="*50)
    print("WebSocket Connection Tester")
    print("="*50)
    print("\nUsage:")
    print("  python test_simple.py [ws://host:port]")
    print("\nExamples:")
    print("  python test_simple.py")
    print("  python test_simple.py ws://localhost:8765")
    print("  python test_simple.py ws://192.168.1.100:8765")

    # Run the test
    result = asyncio.run(test_connection())

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()