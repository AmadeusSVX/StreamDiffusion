"""
WebSocket server for img2img processing using StreamDiffusion.
"""

import os
import sys
import asyncio
import websockets
import json
import logging
import time
import base64
from io import BytesIO
from PIL import Image

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from utils.wrapper import StreamDiffusionWrapper

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global StreamDiffusion instance
stream = None


def initialize_stream():
    """Initialize StreamDiffusion for img2img processing."""
    global stream

    # Using exact same configuration from examples/img2img/single.py
    stream = StreamDiffusionWrapper(
        model_id_or_path="KBlueLeaf/kohaku-v2.1",
        lora_dict=None,
        t_index_list=[22, 32, 45],
        frame_buffer_size=1,
        width=512,
        height=512,
        warmup=10,
        acceleration="xformers",
        mode="img2img",
        use_denoising_batch=True,
        cfg_type="self",
        seed=2,
    )

    # Prepare with default prompt (will be updated per request)
    stream.prepare(
        prompt="1girl with brown dog hair, thick glasses, smiling",
        negative_prompt="low quality, bad quality, blurry, low resolution",
        num_inference_steps=50,
        guidance_scale=1.2,
        delta=0.5,
    )

    logger.info("StreamDiffusion initialized successfully")


async def handle_client(websocket):
    """Handle a client connection."""
    logger.info(f"Client connected from: {websocket.remote_address}")

    try:
        # Send welcome message (exactly like test_server.py)
        await websocket.send(json.dumps({
            "type": "welcome",
            "message": "Connected to img2img WebSocket server",
            "timestamp": time.time()
        }))
        logger.debug("Sent welcome message")

        # Handle messages
        async for message in websocket:
            logger.debug(f"Received message")

            try:
                data = json.loads(message)
                message_type = data.get("type")
                logger.info(f"Received message type: {message_type}")

                if message_type == "register":
                    # Client registration (like in test_server.py)
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
                    # Respond to ping (like in test_server.py)
                    await websocket.send(json.dumps({
                        "type": "pong",
                        "timestamp": time.time()
                    }))
                    logger.debug("Sent pong")

                elif message_type == "img2img":
                    # Process img2img request
                    image_data = data.get("image")
                    prompt = data.get("prompt", "1girl with brown dog hair, thick glasses, smiling")

                    if not image_data:
                        logger.error("No image data received")
                        continue

                    logger.info(f"Processing img2img with prompt: {prompt}")

                    # Decode base64 image
                    image_bytes = base64.b64decode(image_data)
                    input_image = Image.open(BytesIO(image_bytes))

                    # Prepare stream with prompt
                    stream.prepare(
                        prompt=prompt,
                        negative_prompt="low quality, bad quality, blurry, low resolution",
                        num_inference_steps=50,
                        guidance_scale=1.2,
                        delta=0.5,
                    )

                    # Process image using exact same method from single.py
                    image_tensor = stream.preprocess_image(input_image)

                    for _ in range(stream.batch_size - 1):
                        stream(image=image_tensor)

                    output_image = stream(image=image_tensor)

                    # Convert output image to base64 (JPEG format by default)
                    output_buffer = BytesIO()
                    output_image.save(output_buffer, format="JPEG", quality=85)
                    output_base64 = base64.b64encode(output_buffer.getvalue()).decode('utf-8')

                    # Send processed image back
                    await websocket.send(json.dumps({
                        "type": "img2img_result",
                        "image": output_base64,
                        "prompt": prompt,
                        "timestamp": time.time()
                    }))

                    logger.info("Sent processed image back to client")

                else:
                    logger.warning(f"Unknown message type: {message_type}")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
            except Exception as e:
                logger.error(f"Error handling message: {e}")
                import traceback
                logger.error(traceback.format_exc())

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected normally: {websocket.remote_address}")
    except Exception as e:
        logger.error(f"Error handling client: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def start_server(host="localhost", port=8765):
    """Start the WebSocket server."""
    logger.info(f"Starting img2img WebSocket server on {host}:{port}")

    # Initialize StreamDiffusion
    initialize_stream()

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
    """Start the img2img WebSocket server."""
    # Parse simple command line args
    host = "localhost"
    port = 8765

    for i, arg in enumerate(sys.argv[1:]):
        if arg == "--host" and i + 1 < len(sys.argv[1:]):
            host = sys.argv[i + 2]
        elif arg == "--port" and i + 1 < len(sys.argv[1:]):
            port = int(sys.argv[i + 2])

    logger.info("=" * 50)
    logger.info("Img2Img WebSocket Server")
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