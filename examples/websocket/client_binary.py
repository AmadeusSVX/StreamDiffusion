"""
WebSocket client for img2img processing using binary protocol.
Sends metadata as JSON and image as binary frame for improved efficiency.
"""

import asyncio
import websockets
import json
import time
import sys
from io import BytesIO
from PIL import Image
import os


async def send_image_binary(image_path, prompt):
    """Send image and prompt to server using binary protocol."""
    uri = "ws://localhost:8765"

    if len(sys.argv) > 3:
        uri = sys.argv[3]

    print(f"\n{'='*50}")
    print(f"Img2Img Binary WebSocket Client")
    print(f"{'='*50}")
    print(f"Protocol: Binary (no BASE64 encoding)")
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

                # Save to bytes buffer (JPEG format for efficiency)
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=90)
                buffer.seek(0)
                image_bytes = buffer.getvalue()
                print(f"   ✓ Image loaded ({len(image_bytes)} bytes)")

            # Send metadata first
            metadata = {
                "type": "img2img_binary",
                "prompt": prompt,
                "format": "jpeg",
                "timestamp": time.time()
            }

            print(f"\n3. Sending metadata...")
            await websocket.send(json.dumps(metadata))
            print(f"   ✓ Metadata sent")

            # Send binary image data
            print(f"\n4. Sending binary image data...")
            await websocket.send(image_bytes)
            print(f"   ✓ Binary image sent ({len(image_bytes)} bytes)")

            # Wait for response metadata
            print(f"\n5. Waiting for processed image...")
            try:
                # First, receive metadata
                response_metadata = await asyncio.wait_for(websocket.recv(), timeout=60.0)
                metadata_data = json.loads(response_metadata)

                if metadata_data.get("type") == "img2img_result_binary":
                    print(f"   ✓ Metadata received")
                    print(f"   Prompt used: {metadata_data.get('prompt')}")

                    # Then receive binary image data
                    response_image = await asyncio.wait_for(websocket.recv(), timeout=10.0)

                    if isinstance(response_image, bytes):
                        print(f"   ✓ Binary image received ({len(response_image)} bytes)")

                        # Load and save image
                        output_image = Image.open(BytesIO(response_image))

                        # Save with timestamp
                        timestamp = int(time.time())
                        output_path = f"output_binary_{timestamp}.jpg"
                        output_image.save(output_path)
                        print(f"   ✓ Image saved to {output_path}")

                        # Display image
                        print(f"\n6. Displaying result...")
                        output_image.show()
                        print(f"   ✓ Image window opened")

                        # Show efficiency stats
                        print(f"\n{'='*50}")
                        print(f"Efficiency Stats:")
                        print(f"  Input size: {len(image_bytes)} bytes (binary)")
                        print(f"  Output size: {len(response_image)} bytes (binary)")
                        print(f"  No BASE64 overhead (saved ~33% bandwidth)")
                        print(f"{'='*50}")
                    else:
                        print(f"   ✗ Expected binary data, got text")
                else:
                    print(f"   ✗ Unexpected response type: {metadata_data.get('type')}")

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


async def send_image_base64_legacy(image_path, prompt):
    """Send image using legacy BASE64 protocol for comparison."""
    uri = "ws://localhost:8765"

    if len(sys.argv) > 3:
        uri = sys.argv[3]

    print(f"\n{'='*50}")
    print(f"Using Legacy BASE64 Protocol")
    print(f"{'='*50}\n")

    try:
        async with websockets.connect(uri) as websocket:
            # Wait for welcome
            welcome = await websocket.recv()

            # Load and encode image
            with Image.open(image_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Encode to BASE64
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=90)
                import base64
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                print(f"   BASE64 size: {len(image_base64)} bytes")

            # Send as JSON
            request = {
                "type": "img2img",
                "image": image_base64,
                "prompt": prompt,
                "timestamp": time.time()
            }

            await websocket.send(json.dumps(request))
            print(f"   ✓ Legacy request sent")

            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=60.0)
            response_data = json.loads(response)

            if response_data.get("type") == "img2img_result":
                image_data = response_data.get("image")
                if image_data:
                    print(f"   ✓ BASE64 response received: {len(image_data)} bytes")

                    # Decode and save
                    import base64
                    image_bytes = base64.b64decode(image_data)
                    output_image = Image.open(BytesIO(image_bytes))

                    timestamp = int(time.time())
                    output_path = f"output_base64_{timestamp}.jpg"
                    output_image.save(output_path)
                    print(f"   ✓ Saved to {output_path}")

    except Exception as e:
        print(f"❌ Error in legacy mode: {e}")
        return False

    return True


def main():
    """Run the binary protocol client."""
    # Default values
    default_image = os.path.join(
        os.path.dirname(__file__), "..", "..", "images", "inputs", "input.png"
    )
    default_prompt = "1 girl with brown short hair and horns, thick glasses, smiling"

    # Parse command line arguments
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python client_binary.py <image_path> [prompt] [ws://host:port]")
        print("\nOptions:")
        print("  --legacy    Use BASE64 protocol for comparison")
        print("\nExamples:")
        print(f'  python client_binary.py "{default_image}"')
        print(f'  python client_binary.py image.png "a beautiful landscape"')
        print(f'  python client_binary.py image.png "cyberpunk city" ws://localhost:8765')
        print(f'  python client_binary.py --legacy image.png "test prompt"')
        print("\nUsing default values for demo...")
        image_path = default_image
        prompt = default_prompt
        use_legacy = False
    else:
        # Check for --legacy flag
        use_legacy = "--legacy" in sys.argv
        args = [arg for arg in sys.argv[1:] if arg != "--legacy"]

        image_path = args[0] if len(args) > 0 else default_image
        prompt = args[1] if len(args) > 1 else default_prompt

    # Run the appropriate protocol
    if use_legacy:
        result = asyncio.run(send_image_base64_legacy(image_path, prompt))
    else:
        result = asyncio.run(send_image_binary(image_path, prompt))

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()