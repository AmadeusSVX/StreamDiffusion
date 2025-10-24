import os
import sys
import time
import asyncio
import threading
from multiprocessing import Process, Queue, get_context
from typing import List, Literal, Dict, Optional
import torch
import PIL.Image
import io
import base64
from streamdiffusion.image_utils import pil2tensor
import fire
import websockets
import json
import logging

sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from utils.viewer import receive_images
from utils.wrapper import StreamDiffusionWrapper

# Global variables for image buffer and prompt updates
inputs = []
inputs_lock = threading.Lock()
prompt_queue = Queue()  # Queue for thread-safe prompt updates

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_client(websocket):
    """
    Handle WebSocket client connection - receive images directly.
    """
    global inputs, inputs_lock

    logger.info(f"Client connected from: {websocket.remote_address}")

    try:
        # Send welcome message
        await websocket.send(json.dumps({
            "type": "welcome",
            "message": "Connected to StreamDiffusion WebSocket server",
            "timestamp": time.time()
        }))

        # Handle messages
        async for message in websocket:
            try:
                data = json.loads(message)
                message_type = data.get("type")

                if message_type == "image":
                    # Decode base64 image
                    image_data = base64.b64decode(data["data"])

                    # Convert to PIL Image
                    img = PIL.Image.open(io.BytesIO(image_data))

                    # Convert to RGB if necessary
                    if img.mode != "RGB":
                        img = img.convert("RGB")

                    # Resize to target dimensions (will be set later)
                    # For now, just add to buffer
                    with inputs_lock:
                        inputs.append(img)

                    logger.debug(f"Received image, buffer size: {len(inputs)}")

                    # Send acknowledgment
                    await websocket.send(json.dumps({
                        "type": "ack",
                        "status": "received",
                        "timestamp": time.time()
                    }))

                elif message_type == "ping":
                    # Respond to ping
                    await websocket.send(json.dumps({
                        "type": "pong",
                        "timestamp": time.time()
                    }))

                elif message_type == "register":
                    # Accept any registration but we don't need to track it
                    client_type = data.get("client_type", "producer")
                    await websocket.send(json.dumps({
                        "type": "registered",
                        "client_type": client_type,
                        "timestamp": time.time()
                    }))
                    logger.debug(f"Client registered as: {client_type}")

                else:
                    logger.warning(f"Unknown message type: {message_type}")

            except json.JSONDecodeError:
                logger.error("Invalid JSON received")
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {websocket.remote_address}")
    except Exception as e:
        logger.error(f"Error handling client: {e}")


async def websocket_server(port: int, width: int, height: int):
    """
    Start WebSocket server to receive images.
    """
    global inputs, inputs_lock

    # Create a handler that includes width and height
    async def handler(websocket):
        global inputs, inputs_lock

        logger.info(f"Client connected from: {websocket.remote_address}")

        try:
            # Send welcome message
            await websocket.send(json.dumps({
                "type": "welcome",
                "message": "Connected to StreamDiffusion WebSocket server",
                "timestamp": time.time()
            }))

            # Handle messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    message_type = data.get("type")

                    if message_type == "image":
                        # Decode base64 image
                        image_data = base64.b64decode(data["data"])

                        # Convert to PIL Image
                        img = PIL.Image.open(io.BytesIO(image_data))

                        # Convert to RGB if necessary
                        if img.mode != "RGB":
                            img = img.convert("RGB")

                        # Resize to target dimensions
                        img = img.resize((width, height), PIL.Image.LANCZOS)

                        # Convert to tensor and add to buffer
                        with inputs_lock:
                            inputs.append(pil2tensor(img))

                        logger.debug(f"Received image, buffer size: {len(inputs)}")

                        # Send acknowledgment
                        await websocket.send(json.dumps({
                            "type": "ack",
                            "status": "received",
                            "timestamp": time.time()
                        }))

                    elif message_type == "ping":
                        # Respond to ping
                        await websocket.send(json.dumps({
                            "type": "pong",
                            "timestamp": time.time()
                        }))

                    elif message_type == "prompt_update":
                        # Handle prompt update request
                        new_prompt = data.get("prompt")
                        if new_prompt:
                            prompt_queue.put(new_prompt)
                            logger.info(f"Prompt update queued: {new_prompt[:50]}...")

                            # Send acknowledgment
                            await websocket.send(json.dumps({
                                "type": "prompt_updated",
                                "status": "queued",
                                "prompt": new_prompt,
                                "timestamp": time.time()
                            }))
                        else:
                            logger.warning("Prompt update message missing 'prompt' field")
                            await websocket.send(json.dumps({
                                "type": "error",
                                "message": "Missing 'prompt' field",
                                "timestamp": time.time()
                            }))

                    elif message_type == "register":
                        # Accept any registration
                        client_type = data.get("client_type", "producer")
                        await websocket.send(json.dumps({
                            "type": "registered",
                            "client_type": client_type,
                            "timestamp": time.time()
                        }))
                        logger.debug(f"Client registered as: {client_type}")

                    else:
                        logger.warning(f"Unknown message type: {message_type}")

                except json.JSONDecodeError:
                    logger.error("Invalid JSON received")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {websocket.remote_address}")
        except Exception as e:
            logger.error(f"Error handling client: {e}")

    # Start server
    logger.info(f"Starting WebSocket server on port {port}")
    async with websockets.serve(handler, "localhost", port):
        logger.info(f"WebSocket server listening on ws://localhost:{port}")
        await asyncio.Future()  # Run forever


def websocket_server_thread(port: int, width: int, height: int):
    """
    Thread wrapper for WebSocket server.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(websocket_server(port, width, height))
    finally:
        loop.close()


def image_generation_process(
    queue: Queue,
    fps_queue: Queue,
    close_queue: Queue,
    model_id_or_path: str,
    lora_dict: Optional[Dict[str, float]],
    prompt: str,
    negative_prompt: str,
    frame_buffer_size: int,
    width: int,
    height: int,
    acceleration: Literal["none", "xformers", "tensorrt"],
    use_denoising_batch: bool,
    seed: int,
    cfg_type: Literal["none", "full", "self", "initialize"],
    guidance_scale: float,
    delta: float,
    do_add_noise: bool,
    enable_similar_image_filter: bool,
    similar_image_filter_threshold: float,
    similar_image_filter_max_skip_frame: float,
    websocket_port: int,
) -> None:
    """
    Process for generating images based on WebSocket input using img2img mode.

    Parameters
    ----------
    queue : Queue
        The queue to put the generated images in.
    fps_queue : Queue
        The queue to put the calculated fps.
    close_queue : Queue
        Queue for close signals.
    model_id_or_path : str
        The name of the model to use for image generation.
    lora_dict : Optional[Dict[str, float]]
        The lora_dict to load.
    prompt : str
        The prompt to generate images from.
    negative_prompt : str
        The negative prompt to use.
    frame_buffer_size : int
        The frame buffer size for denoising batch.
    width : int
        The width of the image.
    height : int
        The height of the image.
    acceleration : Literal["none", "xformers", "tensorrt"]
        The acceleration method.
    use_denoising_batch : bool
        Whether to use denoising batch or not.
    seed : int
        The seed for random generation.
    cfg_type : Literal["none", "full", "self", "initialize"]
        The cfg_type for img2img mode.
    guidance_scale : float
        The CFG scale.
    delta : float
        The delta multiplier of virtual residual noise.
    do_add_noise : bool
        Whether to add noise for following denoising steps.
    enable_similar_image_filter : bool
        Whether to enable similar image filter.
    similar_image_filter_threshold : float
        The threshold for similar image filter.
    similar_image_filter_max_skip_frame : int
        The max skip frame for similar image filter.
    websocket_port : int
        WebSocket server port.
    """

    global inputs, inputs_lock, prompt_queue

    # Initialize StreamDiffusion
    stream = StreamDiffusionWrapper(
        model_id_or_path=model_id_or_path,
        lora_dict=lora_dict,
        t_index_list=[32, 45],
        frame_buffer_size=frame_buffer_size,
        width=width,
        height=height,
        warmup=10,
        acceleration=acceleration,
        do_add_noise=do_add_noise,
        enable_similar_image_filter=enable_similar_image_filter,
        similar_image_filter_threshold=similar_image_filter_threshold,
        similar_image_filter_max_skip_frame=similar_image_filter_max_skip_frame,
        mode="img2img",
        use_denoising_batch=use_denoising_batch,
        cfg_type=cfg_type,
        seed=seed,
    )

    stream.prepare(
        prompt=prompt,
        negative_prompt=negative_prompt,
        num_inference_steps=50,
        guidance_scale=guidance_scale,
        delta=delta,
    )

    # Start WebSocket server in a thread
    ws_thread = threading.Thread(
        target=websocket_server_thread,
        args=(websocket_port, width, height),
        daemon=True
    )
    ws_thread.start()

    logger.info(f"Waiting for WebSocket images on port {websocket_port}...")

    # Main processing loop
    while True:
        try:
            if not close_queue.empty():
                break

            # Check for prompt updates before processing
            if not prompt_queue.empty():
                new_prompt = prompt_queue.get()
                try:
                    # Use update_prompt for fast, lightweight prompt change
                    stream.stream.update_prompt(new_prompt)
                    logger.info(f"Prompt updated to: {new_prompt[:50]}...")
                except Exception as e:
                    logger.error(f"Failed to update prompt: {e}")

            with inputs_lock:
                if len(inputs) < frame_buffer_size:
                    time.sleep(0.005)
                    continue

                # Sample inputs for batch processing
                sampled_inputs = []
                for i in range(frame_buffer_size):
                    index = (len(inputs) // frame_buffer_size) * i
                    sampled_inputs.append(inputs[len(inputs) - index - 1])

                # Create batch tensor
                input_batch = torch.cat(sampled_inputs)
                inputs.clear()

            # Process images
            start_time = time.time()

            output_images = stream.stream(
                input_batch.to(device=stream.device, dtype=stream.dtype)
            ).cpu()

            if frame_buffer_size == 1:
                output_images = [output_images]

            # Put processed images in queue
            for output_image in output_images:
                queue.put(output_image, block=False)

            # Calculate and report FPS
            fps = 1 / (time.time() - start_time)
            fps_queue.put(fps)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Processing error: {e}")
            continue

    logger.info("Closing image generation process...")
    logger.info(f"Final FPS: {fps if 'fps' in locals() else 'N/A'}")


def main(
    model_id_or_path: str = "KBlueLeaf/kohaku-v2.1",
    lora_dict: Optional[Dict[str, float]] = None,
    prompt: str = "1girl with brown hair, anime style, high quality",
    negative_prompt: str = "low quality, bad quality, blurry, low resolution",
    frame_buffer_size: int = 1,
    width: int = 512,
    height: int = 512,
    acceleration: Literal["none", "xformers", "tensorrt"] = "xformers",
    use_denoising_batch: bool = True,
    seed: int = 2,
    cfg_type: Literal["none", "full", "self", "initialize"] = "self",
    guidance_scale: float = 1.4,
    delta: float = 0.5,
    do_add_noise: bool = False,
    enable_similar_image_filter: bool = True,
    similar_image_filter_threshold: float = 0.99,
    similar_image_filter_max_skip_frame: float = 10,
    websocket_port: int = 8765,
) -> None:
    """
    Main function to start the WebSocket image processing pipeline.

    Parameters
    ----------
    model_id_or_path : str
        Model ID or path for image generation
    lora_dict : Optional[Dict[str, float]]
        LoRA weights dictionary
    prompt : str
        Positive prompt for image generation
    negative_prompt : str
        Negative prompt for image generation
    frame_buffer_size : int
        Number of frames to buffer
    width : int
        Image width
    height : int
        Image height
    acceleration : str
        Acceleration method (none, xformers, tensorrt)
    use_denoising_batch : bool
        Use denoising batch
    seed : int
        Random seed
    cfg_type : str
        CFG type for img2img
    guidance_scale : float
        Guidance scale
    delta : float
        Delta value
    do_add_noise : bool
        Add noise for denoising
    enable_similar_image_filter : bool
        Enable similar image filtering
    similar_image_filter_threshold : float
        Similarity threshold
    similar_image_filter_max_skip_frame : float
        Max frames to skip
    websocket_port : int
        WebSocket server port (default: 8765)
    """

    logger.info("=" * 50)
    logger.info("StreamDiffusion WebSocket Server")
    logger.info("=" * 50)
    logger.info(f"WebSocket Port: {websocket_port}")
    logger.info(f"Image Size: {width}x{height}")
    logger.info(f"Model: {model_id_or_path}")
    logger.info(f"Prompt: {prompt}")
    logger.info("=" * 50)

    # Setup multiprocessing
    ctx = get_context('spawn')
    queue = ctx.Queue()
    fps_queue = ctx.Queue()
    close_queue = Queue()

    # Start image generation process (which includes WebSocket server)
    process1 = ctx.Process(
        target=image_generation_process,
        args=(
            queue,
            fps_queue,
            close_queue,
            model_id_or_path,
            lora_dict,
            prompt,
            negative_prompt,
            frame_buffer_size,
            width,
            height,
            acceleration,
            use_denoising_batch,
            seed,
            cfg_type,
            guidance_scale,
            delta,
            do_add_noise,
            enable_similar_image_filter,
            similar_image_filter_threshold,
            similar_image_filter_max_skip_frame,
            websocket_port,
        ),
    )
    process1.start()

    # Start viewer process
    process2 = ctx.Process(target=receive_images, args=(queue, fps_queue))
    process2.start()

    # Wait for termination
    process2.join()
    logger.info("Viewer process terminated.")

    close_queue.put(True)
    logger.info("Terminating generation process...")

    process1.join(5)
    if process1.is_alive():
        logger.warning("Generation process still alive, force killing...")
        process1.terminate()

    process1.join()
    logger.info("All processes terminated.")


if __name__ == "__main__":
    fire.Fire(main)