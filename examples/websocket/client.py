"""
WebSocket client for img2img processing - sends image and prompt, displays result.
"""

import asyncio
import websockets
import json
import time
import sys
import base64
from io import BytesIO
from PIL import Image
import os


async def send_image_for_processing(image_path, prompt, use_binary=False):
    """Send image and prompt to server for img2img processing.

    Args:
        image_path: Path to the image file
        prompt: Text prompt for img2img generation
        use_binary: If True, use binary protocol (no BASE64 encoding)
    """
    uri = "ws://localhost:8765"

    # Check for custom URI
    for arg in sys.argv[3:]:
        if arg.startswith("ws://") or arg.startswith("wss://"):
            uri = arg
            break

    protocol_type = "Binary" if use_binary else "BASE64"
    print(f"\n{'='*50}")
    print(f"Img2Img WebSocket Client")
    print(f"{'='*50}")
    print(f"Protocol: {protocol_type}")
    print(f"Server: {uri}")
    print(f"Image: {image_path}")
    print(f"Prompt: {prompt}")
    print(f"{'='*50}\n")

    try:
        print(f"1. Connecting to {uri}...")

        async with websockets.connect(uri) as websocket:
            print(f"   ✓ Connected successfully!")

            # Wait for welcome message
            welcome = await websocket.recv()
            welcome_data = json.loads(welcome)
            print(f"   Server: {welcome_data.get('message')}")

            # Load image
            print(f"\n2. Loading image...")
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Save to buffer
                buffer = BytesIO()
                img.save(buffer, format="JPEG" if use_binary else "PNG", quality=90)
                buffer.seek(0)

                if use_binary:
                    # Binary protocol - no BASE64 encoding
                    image_bytes = buffer.getvalue()
                    print(f"   ✓ Image loaded ({len(image_bytes)} bytes)")
                else:
                    # Legacy BASE64 protocol
                    image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                    print(f"   ✓ Image loaded and encoded (BASE64: {len(image_base64)} chars)")

            if use_binary:
                # Binary protocol: Send metadata first, then binary data
                metadata = {
                    "type": "img2img_binary",
                    "prompt": prompt,
                    "format": "jpeg",
                    "timestamp": time.time()
                }

                print(f"\n3. Sending metadata...")
                await websocket.send(json.dumps(metadata))
                print(f"   ✓ Metadata sent")

                print(f"\n4. Sending binary image data...")
                await websocket.send(image_bytes)
                print(f"   ✓ Binary image sent ({len(image_bytes)} bytes)")

            else:
                # Legacy protocol: Send everything as JSON with BASE64
                request = {
                    "type": "img2img",
                    "image": image_base64,
                    "prompt": prompt,
                    "timestamp": time.time()
                }

                print(f"\n3. Sending image for processing...")
                await websocket.send(json.dumps(request))
                print(f"   ✓ Request sent (BASE64 encoded)")

            # Wait for response
            step = 5 if use_binary else 4
            print(f"\n{step}. Waiting for processed image...")
            try:
                if use_binary:
                    # Binary protocol: Receive metadata first, then binary data
                    response_metadata = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                    metadata_data = json.loads(response_metadata)

                    if metadata_data.get("type") == "img2img_result_binary":
                        print(f"   ✓ Metadata received")

                        # Receive binary image data
                        response_image = await asyncio.wait_for(websocket.recv(), timeout=10.0)

                        if isinstance(response_image, bytes):
                            print(f"   ✓ Binary image received ({len(response_image)} bytes)")

                            # Load image from binary data
                            output_image = Image.open(BytesIO(response_image))

                            # Save and display
                            output_path = "output_client_binary.jpg"
                            output_image.save(output_path)
                            print(f"   ✓ Image saved to {output_path}")

                            # Display image
                            print(f"\n{step + 1}. Displaying result...")
                            output_image.show()
                            print(f"   ✓ Image window opened")

                            # Show efficiency stats
                            print(f"\n{'='*50}")
                            print(f"Efficiency Stats (Binary Protocol):")
                            print(f"  Sent: {len(image_bytes)} bytes")
                            print(f"  Received: {len(response_image)} bytes")
                            print(f"  No BASE64 overhead (saved ~33% bandwidth)")
                        else:
                            print(f"   ✗ Expected binary data, got text")
                    else:
                        print(f"   ✗ Unexpected response type: {metadata_data.get('type')}")

                else:
                    # Legacy protocol: Receive JSON with BASE64
                    response = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                    response_data = json.loads(response)

                    if response_data.get("type") == "img2img_result":
                        print(f"   ✓ Processed image received")

                        # Decode and display image
                        image_data = response_data.get("image")
                        if image_data:
                            # Decode base64 image
                            image_bytes = base64.b64decode(image_data)
                            output_image = Image.open(BytesIO(image_bytes))

                            # Save and display
                            output_path = "output_client_base64.jpg"
                            output_image.save(output_path)
                            print(f"   ✓ Image saved to {output_path}")

                            # Display image
                            print(f"\n5. Displaying result...")
                            output_image.show()
                            print(f"   ✓ Image window opened")

                            print(f"\n{'='*50}")
                            print(f"Stats (BASE64 Protocol):")
                            print(f"  BASE64 size sent: {len(image_base64)} chars")
                            print(f"  BASE64 size received: {len(image_data)} chars")
                        else:
                            print(f"   ✗ No image data in response")
                    else:
                        print(f"   ✗ Unexpected response type: {response_data.get('type')}")

            except asyncio.TimeoutError:
                print(f"   ✗ Timeout waiting for response (60s)")

            print(f"\n{'='*50}")
            print(f"✓ Processing complete")
            print(f"{'='*50}\n")

    except ConnectionRefusedError as e:
        print(f"\n❌ ERROR: Connection refused")
        print(f"   {e}")
        print(f"\nMake sure the server is running:")
        print(f"   python server.py")
        print(f"{'='*50}\n")
        return False

    except FileNotFoundError:
        print(f"\n❌ ERROR: Image file not found: {image_path}")
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
    """Run the client."""
    # Default values
    default_image = os.path.join(
        os.path.dirname(__file__), "..", "..", "images", "inputs", "input.png"
    )
    default_prompt = "1 girl with brown short hair and horns, thick glasses, smiling"

    # Check for --binary flag
    use_binary = "--binary" in sys.argv

    # Remove flags from argv for easier parsing
    args = [arg for arg in sys.argv if not arg.startswith("--")]

    # Parse command line arguments
    if len(args) < 2:
        print("\nUsage:")
        print("  python client.py <image_path> [prompt] [ws://host:port]")
        print("\nOptions:")
        print("  --binary    Use binary protocol (no BASE64 encoding)")
        print("\nExamples:")
        print(f'  python client.py "{default_image}"')
        print(f'  python client.py --binary image.png "a beautiful landscape"')
        print(f'  python client.py image.png "cyberpunk city" ws://localhost:8765')
        print("\nUsing default values for demo...")
        image_path = default_image
        prompt = default_prompt
    else:
        image_path = args[1]
        prompt = args[2] if len(args) > 2 else default_prompt

    # Run the client
    result = asyncio.run(send_image_for_processing(image_path, prompt, use_binary))

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()