"""
Simple WebSocket test server - minimal implementation for debugging connection issues.
"""

import asyncio
import websockets
import json
import logging
import time

# Setup logging
logging.basicConfig(level=logging.DEBUG)  # DEBUG level for testing
logger = logging.getLogger(__name__)


async def handle_client(websocket, path):
    """Handle a client connection."""
    logger.info(f"Client connected from: {websocket.remote_address}")

    try:
        # Send welcome message (exactly like server.py)
        await websocket.send(json.dumps({
            "type": "welcome",
            "message": "Connected to test WebSocket server",
            "timestamp": time.time()
        }))
        logger.debug("Sent welcome message")

        # Handle messages
        async for message in websocket:
            logger.debug(f"Received raw message: {message}")

            try:
                data = json.loads(message)
                message_type = data.get("type")
                logger.info(f"Received message type: {message_type}")

                if message_type == "register":
                    # Client registration (like in server.py)
                    client_type = data.get("client_type", "producer")
                    logger.info(f"Client registered as: {client_type}")

                    # Send confirmation
                    await websocket.send(json.dumps({
                        "type": "registered",
                        "client_type": client_type,
                        "timestamp": time.time()
                    }))
                    logger.debug("Sent registration confirmation")

                elif message_type == "ping":
                    # Respond to ping (like in server.py)
                    await websocket.send(json.dumps({
                        "type": "pong",
                        "timestamp": time.time()
                    }))
                    logger.debug("Sent pong")

                elif message_type == "test":
                    # Test message - echo back with timestamp
                    response = {
                        "type": "test_response",
                        "original_data": data.get("data"),
                        "timestamp": time.time()
                    }
                    await websocket.send(json.dumps(response))
                    logger.info(f"Echoed test message: {data.get('data')}")

                else:
                    logger.warning(f"Unknown message type: {message_type}")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
                logger.error(f"Raw message was: {message}")
            except Exception as e:
                logger.error(f"Error handling message: {e}")

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected normally: {websocket.remote_address}")
    except Exception as e:
        logger.error(f"Error handling client: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def start_server(host="localhost", port=8765):
    """Start the WebSocket server."""
    logger.info(f"Starting test WebSocket server on {host}:{port}")

    try:
        async with websockets.serve(handle_client, host, port):
            logger.info(f"✓ Server successfully listening on ws://{host}:{port}")
            logger.info("Waiting for client connections...")

            # Keep server running
            await asyncio.Future()
    except OSError as e:
        logger.error(f"Failed to start server: {e}")
        if "10048" in str(e) or "Address already in use" in str(e):
            logger.error(f"Port {port} is already in use. Try a different port.")
        raise


def main():
    """Start the test WebSocket server."""
    import sys

    # Parse simple command line args
    host = "localhost"
    port = 9000

    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--host" and i + 1 < len(sys.argv[1:]):
            host = sys.argv[i + 2]
        elif arg == "--port" and i + 1 < len(sys.argv[1:]):
            port = int(sys.argv[i + 2])

    logger.info("=" * 50)
    logger.info("WebSocket Test Server")
    logger.info("=" * 50)
    logger.info(f"Configuration:")
    logger.info(f"  Host: {host}")
    logger.info(f"  Port: {port}")
    logger.info(f"  URL: ws://{host}:{port}")
    logger.info("=" * 50)

    try:
        asyncio.run(start_server(host, port))
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()