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


async def send_image_for_processing(image_path, prompt):
    """Send image and prompt to server for img2img processing."""
    uri = "ws://localhost:8765"

    if len(sys.argv) > 3:
        uri = sys.argv[3]

    print(f"\n{'='*50}")
    print(f"Img2Img WebSocket Client")
    print(f"{'='*50}")
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

            # Load and encode image
            print(f"\n2. Loading image...")
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode != 'RGB':
                    img = img.convert('RGB')

                # Encode image to base64
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                print(f"   ✓ Image loaded and encoded")

            # Send img2img request
            request = {
                "type": "img2img",
                "image": image_base64,
                "prompt": prompt,
                "timestamp": time.time()
            }

            print(f"\n3. Sending image for processing...")
            await websocket.send(json.dumps(request))
            print(f"   ✓ Request sent")

            # Wait for response
            print(f"\n4. Waiting for processed image...")
            try:
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
                        output_path = "output_client2.png"
                        output_image.save(output_path)
                        print(f"   ✓ Image saved to {output_path}")

                        # Display image
                        print(f"\n5. Displaying result...")
                        output_image.show()
                        print(f"   ✓ Image window opened")

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
    default_prompt = "1girl with brown dog hair, thick glasses, smiling"

    # Parse command line arguments
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python client2.py <image_path> [prompt] [ws://host:port]")
        print("\nExamples:")
        print(f'  python client2.py "{default_image}"')
        print(f'  python client2.py image.png "a beautiful landscape"')
        print(f'  python client2.py image.png "cyberpunk city" ws://localhost:8765')
        print("\nUsing default values for demo...")
        image_path = default_image
        prompt = default_prompt
    else:
        image_path = sys.argv[1]
        prompt = sys.argv[2] if len(sys.argv) > 2 else default_prompt

    # Run the client
    result = asyncio.run(send_image_for_processing(image_path, prompt))

    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()