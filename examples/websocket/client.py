"""
WebSocket client for testing image streaming to StreamDiffusion server.
This client can send images from various sources:
1. Static image file
2. Directory of images
3. Screen capture (requires mss library)
"""

import asyncio
import websockets
import json
import base64
import io
import time
import os
import sys
from typing import Optional, List
import fire
import logging
from pathlib import Path

# Try to import optional dependencies
try:
    import PIL.Image
    from PIL import Image
except ImportError:
    print("PIL (Pillow) is required. Install with: pip install Pillow")
    sys.exit(1)

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False
    print("Warning: mss not available. Screen capture disabled.")

# Webcam support disabled - not needed for basic functionality
CV2_AVAILABLE = False

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def image_to_base64(image: PIL.Image.Image, format: str = "JPEG") -> str:
    """
    Convert PIL Image to base64 string.

    Parameters
    ----------
    image : PIL.Image.Image
        Image to convert
    format : str
        Image format (JPEG or PNG)

    Returns
    -------
    str
        Base64 encoded image string
    """
    buffered = io.BytesIO()
    image.save(buffered, format=format)
    return base64.b64encode(buffered.getvalue()).decode('utf-8')


async def send_image(websocket, image: PIL.Image.Image, format: str = "JPEG"):
    """
    Send a single image through WebSocket.

    Parameters
    ----------
    websocket : websockets.WebSocketClientProtocol
        WebSocket connection
    image : PIL.Image.Image
        Image to send
    format : str
        Image format (JPEG or PNG)
    """
    # Convert image to base64
    image_b64 = image_to_base64(image, format)

    # Create message
    message = json.dumps({
        "type": "image",
        "format": format.lower(),
        "data": image_b64,
        "timestamp": time.time()
    })

    # Send message
    await websocket.send(message)

    # Wait for acknowledgment
    try:
        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        response_data = json.loads(response)
        if response_data.get("type") == "ack":
            logger.debug("Image acknowledged by server")
    except asyncio.TimeoutError:
        logger.warning("No acknowledgment received from server")
    except Exception as e:
        logger.error(f"Error receiving acknowledgment: {e}")


async def send_prompt_update(websocket, prompt: str):
    """
    Send a prompt update message through WebSocket.

    Parameters
    ----------
    websocket : websockets.WebSocketClientProtocol
        WebSocket connection
    prompt : str
        New prompt text
    """
    # Create message
    message = json.dumps({
        "type": "prompt_update",
        "prompt": prompt,
        "timestamp": time.time()
    })

    # Send message
    await websocket.send(message)
    logger.info(f"Sent prompt update: {prompt[:50]}...")

    # Wait for acknowledgment
    try:
        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
        response_data = json.loads(response)
        if response_data.get("type") == "prompt_updated":
            logger.info(f"Prompt update confirmed: {response_data.get('status')}")
        elif response_data.get("type") == "error":
            logger.error(f"Prompt update error: {response_data.get('message')}")
    except asyncio.TimeoutError:
        logger.warning("No acknowledgment received for prompt update")
    except Exception as e:
        logger.error(f"Error receiving prompt update acknowledgment: {e}")


async def stream_static_image(
    websocket_uri: str,
    image_path: str,
    fps: float = 10.0,
    duration: float = 60.0,
    format: str = "JPEG"
):
    """
    Stream a static image repeatedly.

    Parameters
    ----------
    websocket_uri : str
        WebSocket server URI
    image_path : str
        Path to image file
    fps : float
        Frames per second to send
    duration : float
        Duration in seconds to stream
    format : str
        Image format (JPEG or PNG)
    """
    # Load image
    image = PIL.Image.open(image_path)
    if image.mode != "RGB":
        image = image.convert("RGB")

    logger.info(f"Loaded image: {image_path} ({image.size})")

    # Connect to WebSocket
    async with websockets.connect(websocket_uri) as websocket:
        logger.info(f"Connected to {websocket_uri}")

        # Register as producer
        await websocket.send(json.dumps({
            "type": "register",
            "client_type": "producer"
        }))
        logger.debug("Registered as producer")

        # Wait for registration confirmation
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            logger.debug(f"Registration response: {response_data.get('type')}")
        except asyncio.TimeoutError:
            logger.warning("No registration confirmation received")

        interval = 1.0 / fps
        start_time = time.time()

        while time.time() - start_time < duration:
            loop_start = time.time()

            await send_image(websocket, image, format)
            logger.info(f"Sent image (elapsed: {time.time() - start_time:.1f}s)")

            # Wait for next frame time
            elapsed = time.time() - loop_start
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)


async def stream_directory(
    websocket_uri: str,
    directory: str,
    fps: float = 10.0,
    loop: bool = True,
    format: str = "JPEG"
):
    """
    Stream images from a directory.

    Parameters
    ----------
    websocket_uri : str
        WebSocket server URI
    directory : str
        Directory containing images
    fps : float
        Frames per second to send
    loop : bool
        Whether to loop through images
    format : str
        Image format (JPEG or PNG)
    """
    # Get all image files
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp'}
    image_files = []

    for ext in image_extensions:
        image_files.extend(Path(directory).glob(f"*{ext}"))
        image_files.extend(Path(directory).glob(f"*{ext.upper()}"))

    if not image_files:
        logger.error(f"No images found in {directory}")
        return

    image_files.sort()
    logger.info(f"Found {len(image_files)} images in {directory}")

    # Connect to WebSocket
    async with websockets.connect(websocket_uri) as websocket:
        logger.info(f"Connected to {websocket_uri}")

        # Register as producer
        await websocket.send(json.dumps({
            "type": "register",
            "client_type": "producer"
        }))
        logger.debug("Registered as producer")

        # Wait for registration confirmation
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            logger.debug(f"Registration response: {response_data.get('type')}")
        except asyncio.TimeoutError:
            logger.warning("No registration confirmation received")

        interval = 1.0 / fps
        image_index = 0

        while True:
            loop_start = time.time()

            # Load and send current image
            image_path = image_files[image_index]
            image = PIL.Image.open(image_path)
            if image.mode != "RGB":
                image = image.convert("RGB")

            await send_image(websocket, image, format)
            logger.info(f"Sent image {image_index + 1}/{len(image_files)}: {image_path.name}")

            # Move to next image
            image_index += 1
            if image_index >= len(image_files):
                if loop:
                    image_index = 0
                    logger.info("Looping back to first image")
                else:
                    break

            # Wait for next frame time
            elapsed = time.time() - loop_start
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)


async def stream_screen(
    websocket_uri: str,
    monitor_index: int = 0,
    region: Optional[List[int]] = None,
    fps: float = 10.0,
    duration: float = 60.0,
    format: str = "JPEG"
):
    """
    Stream screen capture.

    Parameters
    ----------
    websocket_uri : str
        WebSocket server URI
    monitor_index : int
        Monitor index to capture (0 for primary)
    region : Optional[List[int]]
        Region to capture [x, y, width, height]
    fps : float
        Frames per second to send
    duration : float
        Duration in seconds to stream
    format : str
        Image format (JPEG or PNG)
    """
    if not MSS_AVAILABLE:
        logger.error("mss library not available. Install with: pip install mss")
        return

    # Connect to WebSocket
    async with websockets.connect(websocket_uri) as websocket:
        logger.info(f"Connected to {websocket_uri}")

        # Register as producer
        await websocket.send(json.dumps({
            "type": "register",
            "client_type": "producer"
        }))
        logger.debug("Registered as producer")

        # Wait for registration confirmation
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            logger.debug(f"Registration response: {response_data.get('type')}")
        except asyncio.TimeoutError:
            logger.warning("No registration confirmation received")

        with mss.mss() as sct:
            # Setup monitor region
            if region:
                monitor = {
                    "left": region[0],
                    "top": region[1],
                    "width": region[2],
                    "height": region[3]
                }
            else:
                monitor = sct.monitors[monitor_index + 1]  # 0 is all monitors

            logger.info(f"Capturing region: {monitor}")

            interval = 1.0 / fps
            start_time = time.time()

            while time.time() - start_time < duration:
                loop_start = time.time()

                # Capture screen
                img = sct.grab(monitor)
                # Convert to PIL Image
                image = PIL.Image.frombytes(
                    "RGB", img.size, img.bgra, "raw", "BGRX"
                )

                await send_image(websocket, image, format)
                logger.debug(f"Sent screen capture")

                # Wait for next frame time
                elapsed = time.time() - loop_start
                if elapsed < interval:
                    await asyncio.sleep(interval - elapsed)

        logger.info("Screen capture completed")


async def stream_webcam(
    websocket_uri: str,
    camera_index: int = 0,
    fps: float = 10.0,
    duration: float = 60.0,
    format: str = "JPEG"
):
    """
    Stream webcam capture - NOT IMPLEMENTED.

    Parameters
    ----------
    websocket_uri : str
        WebSocket server URI
    camera_index : int
        Camera index to use
    fps : float
        Frames per second to send
    duration : float
        Duration in seconds to stream
    format : str
        Image format (JPEG or PNG)
    """
    logger.error("Webcam capture is not implemented in this version")
    logger.error("Use 'static' or 'directory' mode instead")
    return


async def stream_with_prompt_interactive(
    websocket_uri: str,
    image_path: str,
    fps: float = 10.0,
    format: str = "JPEG"
):
    """
    Stream images with interactive prompt updates.

    Parameters
    ----------
    websocket_uri : str
        WebSocket server URI
    image_path : str
        Path to image file
    fps : float
        Frames per second to send
    format : str
        Image format (JPEG or PNG)
    """
    import asyncio

    # Load image
    image = PIL.Image.open(image_path)
    if image.mode != "RGB":
        image = image.convert("RGB")

    logger.info(f"Loaded image: {image_path} ({image.size})")

    # Connect to WebSocket
    async with websockets.connect(websocket_uri) as websocket:
        logger.info(f"Connected to {websocket_uri}")

        # Register as producer
        await websocket.send(json.dumps({
            "type": "register",
            "client_type": "producer"
        }))
        logger.debug("Registered as producer")

        # Wait for registration confirmation
        try:
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            logger.debug(f"Registration response: {response_data.get('type')}")
        except asyncio.TimeoutError:
            logger.warning("No registration confirmation received")

        logger.info("\nInteractive Prompt Mode")
        logger.info("=" * 50)
        logger.info("Enter prompts to update the generation style.")
        logger.info("Type 'quit' or 'exit' to stop.")
        logger.info("Press Ctrl+C to force quit.")
        logger.info("=" * 50 + "\n")

        # Create tasks for image sending and prompt input
        interval = 1.0 / fps

        async def send_images():
            """Continuously send images"""
            while True:
                try:
                    await send_image(websocket, image, format)
                    logger.debug(f"Sent image")
                    await asyncio.sleep(interval)
                except Exception as e:
                    logger.error(f"Error sending image: {e}")
                    break

        async def handle_prompts():
            """Handle prompt input from user"""
            loop = asyncio.get_event_loop()

            while True:
                try:
                    # Use run_in_executor to make input() non-blocking
                    prompt = await loop.run_in_executor(
                        None,
                        input,
                        "\nEnter new prompt (or 'quit' to exit): "
                    )

                    if prompt.lower() in ['quit', 'exit']:
                        logger.info("Exiting interactive mode...")
                        return

                    if prompt.strip():
                        await send_prompt_update(websocket, prompt)
                    else:
                        logger.warning("Empty prompt ignored")

                except EOFError:
                    logger.info("Input stream ended")
                    return
                except Exception as e:
                    logger.error(f"Error handling prompt: {e}")
                    return

        # Run both tasks concurrently
        try:
            image_task = asyncio.create_task(send_images())
            prompt_task = asyncio.create_task(handle_prompts())

            # Wait for prompt task to complete (user quits)
            await prompt_task

            # Cancel image sending
            image_task.cancel()
            try:
                await image_task
            except asyncio.CancelledError:
                pass

        except KeyboardInterrupt:
            logger.info("\nInterrupted by user")
        except Exception as e:
            logger.error(f"Error in interactive mode: {e}")


def main(
    mode: str = "static",
    websocket_uri: str = "ws://localhost:8765",
    source: str = None,
    fps: float = 10.0,
    duration: float = 60.0,
    format: str = "JPEG",
    loop: bool = True,
    camera_index: int = 0,
    monitor_index: int = 0,
    region: Optional[List[int]] = None,
):
    """
    WebSocket client for streaming images.

    Parameters
    ----------
    mode : str
        Streaming mode: static, directory, screen, or prompt-interactive
    websocket_uri : str
        WebSocket server URI
    source : str
        Source path for static/directory/prompt-interactive modes
    fps : float
        Frames per second to send
    duration : float
        Duration in seconds (for static/screen modes)
    format : str
        Image format (JPEG or PNG)
    loop : bool
        Loop through images (directory mode)
    camera_index : int
        Not used (webcam not supported)
    monitor_index : int
        Monitor index (screen mode)
    region : Optional[List[int]]
        Screen region [x, y, width, height] (screen mode)

    Examples
    --------
    # Stream a static image
    python client.py --mode=static --source=image.jpg

    # Stream images from directory
    python client.py --mode=directory --source=./images --fps=5

    # Stream screen capture
    python client.py --mode=screen --fps=15

    # Stream specific screen region
    python client.py --mode=screen --region=[100,100,512,512]

    # Interactive prompt mode
    python client.py --mode=prompt-interactive --source=image.jpg
    """

    if mode == "static":
        if not source:
            logger.error("Source image path required for static mode")
            return
        asyncio.run(stream_static_image(
            websocket_uri, source, fps, duration, format
        ))

    elif mode == "directory":
        if not source:
            logger.error("Source directory path required for directory mode")
            return
        asyncio.run(stream_directory(
            websocket_uri, source, fps, loop, format
        ))

    elif mode == "screen":
        asyncio.run(stream_screen(
            websocket_uri, monitor_index, region, fps, duration, format
        ))

    elif mode == "webcam":
        asyncio.run(stream_webcam(
            websocket_uri, camera_index, fps, duration, format
        ))

    elif mode == "prompt-interactive":
        if not source:
            logger.error("Source image path required for prompt-interactive mode")
            return
        asyncio.run(stream_with_prompt_interactive(
            websocket_uri, source, fps, format
        ))

    else:
        logger.error(f"Unknown mode: {mode}")
        logger.info("Available modes: static, directory, screen, prompt-interactive")


if __name__ == "__main__":
    fire.Fire(main)