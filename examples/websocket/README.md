# WebSocket Image Streaming Example

This example demonstrates how to use StreamDiffusion with WebSocket for real-time image streaming and transformation using img2img mode.

## Overview

This implementation replaces the screen capture functionality from `examples/screen/main.py` with WebSocket-based image reception, allowing for more flexible image sources including:
- Remote image streams
- Network-based image sources
- Multiple client connections
- Various image formats (JPEG, PNG)

## Installation

First, install the required dependencies:

```bash
pip install -r requirements.txt
```

## Files

- `server.py` - WebSocket relay server that forwards images between clients
- `main.py` - StreamDiffusion client that receives and processes images
- `client.py` - Test client for sending images via WebSocket
- `requirements.txt` - Python dependencies

## Usage

### Basic Usage (3-Step Process)

This example uses a 3-component architecture:
1. **WebSocket Server** (server.py) - Relays images between clients
2. **StreamDiffusion Client** (main.py) - Receives and processes images
3. **Image Producer Client** (client.py) - Sends images to server

#### Step 1: Start the WebSocket Server

```bash
# Terminal 1: Start the WebSocket relay server
python server.py
```

This starts a WebSocket server on `ws://localhost:8765` that relays images between clients.

#### Step 2: Start the StreamDiffusion Processing Client

```bash
# Terminal 2: Start the image processing pipeline
python main.py
```

This connects to the WebSocket server and waits for images to process through the img2img pipeline.

#### Step 3: Send Images Using the Producer Client

```bash
# Terminal 3: Send images to be processed

# Send a static image repeatedly
python client.py --mode=static --source=path/to/image.jpg

# Stream images from a directory
python client.py --mode=directory --source=path/to/images/

# Stream screen capture
python client.py --mode=screen

# Stream webcam (if available)
python client.py --mode=webcam
```

### Alternative: Start Server on Different Host/Port

```bash
# Start server on all interfaces and custom port
python server.py --host=0.0.0.0 --port=9000

# Connect main.py to custom server
python main.py --websocket_uri=ws://localhost:9000

# Connect client to custom server
python client.py --websocket_uri=ws://localhost:9000 --mode=static --source=image.jpg
```

### Advanced Configuration

#### Main.py Parameters

- `model_id_or_path`: Model to use (default: "KBlueLeaf/kohaku-v2.1")
- `prompt`: Positive prompt for img2img transformation
- `negative_prompt`: Negative prompt
- `width`, `height`: Image dimensions (default: 512x512)
- `frame_buffer_size`: Number of frames to buffer (default: 1)
- `acceleration`: Acceleration method ("none", "xformers", "tensorrt")
- `websocket_uri`: WebSocket URI to connect to (default: "ws://localhost:8765")

Example with custom settings:

```bash
python main.py \
    --prompt="anime style illustration, high quality" \
    --width=768 \
    --height=768 \
    --frame_buffer_size=4 \
    --acceleration=tensorrt
```

#### Client.py Parameters

- `mode`: Streaming mode (static, directory, screen, webcam)
- `websocket_uri`: Server URI (default: "ws://localhost:8765")
- `source`: Source path for static/directory modes
- `fps`: Frames per second (default: 10.0)
- `duration`: Stream duration in seconds (default: 60.0)
- `format`: Image format (JPEG or PNG)

Example streaming configurations:

```bash
# Stream at 30 FPS for 120 seconds
python client.py --mode=static --source=image.jpg --fps=30 --duration=120

# Stream PNG images from directory
python client.py --mode=directory --source=./images --format=PNG

# Capture specific screen region
python client.py --mode=screen --region=[100,100,512,512]
```

## WebSocket Protocol

The WebSocket communication uses JSON messages with the following format:

### Image Message (Client → Server)
```json
{
    "type": "image",
    "format": "jpeg",
    "data": "base64_encoded_image_data",
    "timestamp": 1234567890.123
}
```

### Acknowledgment (Server → Client)
```json
{
    "type": "ack",
    "status": "received"
}
```

## Architecture

The example uses a 3-component architecture with multi-process support:

1. **WebSocket Relay Server (server.py)**:
   - Accepts connections from multiple clients
   - Relays images from producers to consumers
   - Handles client registration and message routing

2. **Image Processing Client (main.py)**:
   - Connects to WebSocket server as a consumer
   - Runs two processes:
     - **Image Generation Process**: Receives and processes images through StreamDiffusion
     - **Viewer Process**: Displays transformed images in real-time
   - Uses threading for WebSocket communication

3. **Image Producer Client (client.py)**:
   - Connects to WebSocket server as a producer
   - Sends images from various sources (file, directory, screen, webcam)
   - Supports multiple image formats and streaming modes

## Performance Tips

1. **Batch Processing**: Increase `frame_buffer_size` for better throughput:
   ```bash
   python main.py --frame_buffer_size=8
   ```

2. **Acceleration**: Use TensorRT for best performance (requires setup):
   ```bash
   python main.py --acceleration=tensorrt
   ```

3. **Image Format**: JPEG is faster for network transmission, PNG for quality:
   ```bash
   python client.py --format=JPEG  # Faster
   python client.py --format=PNG    # Better quality
   ```

4. **Network Optimization**: For remote connections, consider:
   - Reducing image resolution
   - Lowering FPS
   - Using JPEG with quality settings

## Troubleshooting

1. **Connection Refused Error**:
   - Make sure to start `server.py` first before running `main.py` or `client.py`
   - Check if port 8765 is not already in use
   - Verify the WebSocket URI matches between server and clients

2. **No Images Received**:
   - Ensure all three components are running (server.py, main.py, client.py)
   - Check that client.py has a valid image source
   - Verify network connectivity if using remote hosts

3. **Performance Issues**:
   - Reduce `fps` in client.py
   - Decrease image resolution in main.py
   - Use `frame_buffer_size=1` for lowest latency

4. **Memory Issues**:
   - Monitor the input buffer size
   - Reduce `frame_buffer_size`
   - Use smaller image dimensions

## Extending the Example

You can extend this example to:

1. **Add authentication** to the WebSocket connection
2. **Implement bi-directional streaming** (send processed images back)
3. **Support multiple concurrent clients**
4. **Add image preprocessing** (resize, crop, filters)
5. **Integrate with web applications** using JavaScript WebSocket API

## Comparison with Screen Example

| Feature | Screen Example | WebSocket Example |
|---------|---------------|-------------------|
| Image Source | Screen capture (mss) | Network stream |
| Flexibility | Single machine | Network/distributed |
| Latency | Very low | Network dependent |
| Scalability | Single source | Multiple sources |
| Use Cases | Local screen effects | Remote processing, streaming |

## License

Same as StreamDiffusion project.