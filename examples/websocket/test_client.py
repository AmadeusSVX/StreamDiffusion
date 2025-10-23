"""
Simple WebSocket test client - minimal implementation for debugging connection issues.
Uses the exact same connection pattern as main.py
"""

import asyncio
import websockets
import json
import logging
import time
import threading

# Setup logging
logging.basicConfig(level=logging.DEBUG)  # DEBUG level for testing
logger = logging.getLogger(__name__)

# Global test data storage (like inputs in main.py)
test_messages = []
test_lock = threading.Lock()


async def websocket_receiver(
    websocket_uri: str,
    event: threading.Event,
):
    """
    Receive messages from WebSocket connection continuously.
    This uses the EXACT same pattern as main.py's websocket_receiver.
    """
    global test_messages, test_lock

    while not event.is_set():
        logger.debug(f"Attempting to connect to: {websocket_uri}")

        try:
            # EXACT same connection pattern as main.py
            async with websockets.connect(websocket_uri) as websocket:
                logger.info(f"✓ Connected to WebSocket server: {websocket_uri}")

                # Register as consumer (exactly like main.py)
                await websocket.send(json.dumps({
                    "type": "register",
                    "client_type": "consumer"
                }))
                logger.debug("Sent registration as consumer")

                # Send initial test message
                await websocket.send(json.dumps({
                    "type": "test",
                    "data": "Hello from test client",
                    "timestamp": time.time()
                }))
                logger.info("Sent test message")

                while not event.is_set():
                    try:
                        # Receive message with timeout (exactly like main.py)
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=1.0
                        )

                        # Parse JSON message
                        data = json.loads(message)
                        logger.info(f"Received message type: {data.get('type')}")
                        logger.debug(f"Full message: {json.dumps(data, indent=2)}")

                        if data.get("type") == "test_response":
                            with test_lock:
                                test_messages.append(data)
                            logger.info(f"✓ Test response received: {data.get('original_data')}")

                        elif data.get("type") in ["welcome", "registered", "pong"]:
                            logger.debug(f"Received: {data.get('type')}")

                    except asyncio.TimeoutError:
                        # Send ping to keep connection alive (exactly like main.py)
                        await websocket.send(json.dumps({
                            "type": "ping"
                        }))
                        logger.debug("Sent ping (timeout)")
                        continue
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("WebSocket connection closed, reconnecting...")
                        break
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON received: {e}")
                        continue
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        continue

        except ConnectionRefusedError as e:
            logger.error(f"❌ Connection refused: {e}")
            logger.error(f"   Make sure server is running on {websocket_uri}")
            if not event.is_set():
                logger.info("Retrying connection in 5 seconds...")
                await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"❌ WebSocket connection error: {e}")
            logger.error(f"   Error type: {type(e).__name__}")
            import traceback
            logger.error(traceback.format_exc())
            if not event.is_set():
                logger.info("Retrying connection in 5 seconds...")
                await asyncio.sleep(5)

    logger.info("WebSocket receiver thread terminated")


def websocket_thread(
    websocket_uri: str,
    event: threading.Event,
):
    """
    Thread wrapper for async WebSocket receiver.
    EXACT same pattern as main.py
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(
            websocket_receiver(websocket_uri, event)
        )
    finally:
        loop.close()


def main():
    """Test WebSocket client - sends test messages."""
    import sys

    # Parse simple command line args
    websocket_uri = "ws://localhost:8765"

    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--uri" and i + 1 < len(sys.argv[1:]):
            websocket_uri = sys.argv[i + 2]

    logger.info("=" * 50)
    logger.info("WebSocket Test Client")
    logger.info("=" * 50)
    logger.info(f"Target server: {websocket_uri}")
    logger.info("=" * 50)

    # Start WebSocket receiver thread (exactly like main.py)
    event = threading.Event()
    ws_thread = threading.Thread(
        target=websocket_thread,
        args=(websocket_uri, event)
    )
    ws_thread.start()

    # Run for 10 seconds then stop
    try:
        logger.info("Running for 10 seconds (press Ctrl+C to stop earlier)...")
        time.sleep(10)
    except KeyboardInterrupt:
        logger.info("\nStopping client...")

    # Stop the thread
    event.set()
    ws_thread.join(timeout=5)

    # Report results
    logger.info("=" * 50)
    logger.info("Test Results:")
    with test_lock:
        logger.info(f"Received {len(test_messages)} test responses")
        for msg in test_messages:
            logger.info(f"  - {msg.get('original_data')}")
    logger.info("=" * 50)

    if test_messages:
        logger.info("✓ WebSocket connection test SUCCESSFUL")
    else:
        logger.error("❌ WebSocket connection test FAILED - no messages received")


if __name__ == "__main__":
    main()