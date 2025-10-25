# WebSocket Protocol Documentation

## Overview

The StreamDiffusion WebSocket server supports two protocols for img2img processing:

1. **Legacy Protocol (BASE64)** - JSON messages with BASE64-encoded images
2. **Binary Protocol** - Metadata in JSON + raw binary image data (33% more efficient)

Both protocols are supported simultaneously for backward compatibility.

## Binary Protocol (Recommended)

### Advantages
- **33% bandwidth reduction** - No BASE64 encoding overhead
- **Faster processing** - No encoding/decoding CPU overhead
- **Lower memory usage** - Direct binary transmission

### Message Flow

#### Client → Server (Image Processing Request)

**Frame 1 (Text/JSON):**
```json
{
    "type": "img2img_binary",
    "prompt": "your prompt here",
    "format": "jpeg",
    "timestamp": 1234567890.123
}
```

**Frame 2 (Binary):**
```
[Raw image bytes in JPEG/PNG format]
```

#### Server → Client (Processed Result)

**Frame 1 (Text/JSON):**
```json
{
    "type": "img2img_result_binary",
    "prompt": "prompt used for generation",
    "format": "jpeg",
    "timestamp": 1234567890.123
}
```

**Frame 2 (Binary):**
```
[Processed image bytes in JPEG format]
```

### Usage Examples

#### Python Client (Binary Protocol)
```bash
# Using updated client.py with --binary flag
python client.py --binary image.png "a beautiful landscape"

# Using dedicated binary client
python client_binary.py image.png "a beautiful landscape"
```

#### Python Code Example
```python
import asyncio
import websockets
import json
from PIL import Image
from io import BytesIO

async def send_binary_img2img(uri, image_path, prompt):
    async with websockets.connect(uri) as ws:
        # Load image
        with Image.open(image_path) as img:
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=90)
            image_bytes = buffer.getvalue()

        # Send metadata
        await ws.send(json.dumps({
            "type": "img2img_binary",
            "prompt": prompt,
            "format": "jpeg"
        }))

        # Send binary image
        await ws.send(image_bytes)

        # Receive metadata
        metadata = json.loads(await ws.recv())

        # Receive binary result
        result_bytes = await ws.recv()

        # Process result
        result_image = Image.open(BytesIO(result_bytes))
        return result_image
```

## Legacy Protocol (BASE64)

### Message Flow

#### Client → Server
```json
{
    "type": "img2img",
    "image": "iVBORw0KGgo...",  // BASE64 encoded image
    "prompt": "your prompt here",
    "timestamp": 1234567890.123
}
```

#### Server → Client
```json
{
    "type": "img2img_result",
    "image": "iVBORw0KGgo...",  // BASE64 encoded result
    "prompt": "prompt used",
    "timestamp": 1234567890.123
}
```

### Usage Examples

#### Python Client (Legacy Protocol)
```bash
# Default behavior (no --binary flag)
python client.py image.png "a beautiful landscape"

# Explicit legacy mode in binary client
python client_binary.py --legacy image.png "a beautiful landscape"
```

## Protocol Comparison

| Aspect | Binary Protocol | BASE64 Protocol |
|--------|-----------------|-----------------|
| **Image Size (512x512 RGB)** | ~200KB | ~270KB (+35%) |
| **Encoding Time** | 0ms | ~10-20ms |
| **Decoding Time** | 0ms | ~10-20ms |
| **Memory Usage** | Lower | Higher |
| **Network Efficiency** | Optimal | Suboptimal |
| **Debugging** | Harder | Easy (text-based) |
| **Browser Support** | Good | Good |

## Server Implementation

The server (`server.py`) automatically detects the protocol based on message type:

- `type: "img2img"` → Legacy BASE64 protocol
- `type: "img2img_binary"` → Binary protocol

```python
# Server handles both protocols
if isinstance(message, bytes):
    # Binary frame - process raw image data
    process_binary_image(message, pending_metadata)
else:
    # Text frame - parse JSON
    data = json.loads(message)
    if data["type"] == "img2img_binary":
        # Store metadata for next binary frame
        pending_metadata = data
    elif data["type"] == "img2img":
        # Legacy BASE64 processing
        process_base64_image(data)
```

## Common Message Types

### Connection
```json
{
    "type": "welcome",
    "message": "Connected to img2img WebSocket server",
    "timestamp": 1234567890.123
}
```

### Registration (Optional)
```json
// Client → Server
{
    "type": "register",
    "client_type": "producer"
}

// Server → Client
{
    "type": "registered",
    "client_type": "producer",
    "timestamp": 1234567890.123
}
```

### Keep-Alive
```json
// Client → Server
{
    "type": "ping"
}

// Server → Client
{
    "type": "pong",
    "timestamp": 1234567890.123
}
```

## Error Handling

### Binary Protocol Errors
- If binary data is received without metadata, it's ignored
- If metadata timeout occurs, pending metadata is cleared

### Connection Errors
- Connection timeout: 10 seconds (default)
- Processing timeout: 60 seconds (default)

## Performance Tips

1. **Use Binary Protocol** for production - 33% bandwidth savings
2. **Use JPEG format** for photos - smaller than PNG
3. **Adjust JPEG quality** - 85-90 is usually optimal
4. **Reuse connections** - avoid reconnecting for each image
5. **Send images in parallel** - if processing multiple images

## Migration Guide

### From BASE64 to Binary

**Before (BASE64):**
```python
# Encode image
image_base64 = base64.b64encode(image_bytes).decode()
await ws.send(json.dumps({
    "type": "img2img",
    "image": image_base64,
    "prompt": prompt
}))
```

**After (Binary):**
```python
# Send metadata
await ws.send(json.dumps({
    "type": "img2img_binary",
    "prompt": prompt,
    "format": "jpeg"
}))
# Send raw bytes
await ws.send(image_bytes)
```

## Testing

### Test Binary Protocol
```bash
# Start server
python server.py

# Test with binary protocol
python client.py --binary ../../images/inputs/input.png "test prompt"

# Compare with legacy
python client.py ../../images/inputs/input.png "test prompt"
```

### Performance Comparison
```bash
# Run performance test
python client_binary.py image.png "test" # Binary
python client_binary.py --legacy image.png "test" # BASE64

# Check output for efficiency stats
```

## Unity/C# Implementation

For Unity implementation (Img2ImgClient.cs), binary protocol support requires:

1. Sending WebSocket binary frames instead of text
2. Handling binary frame reception
3. Two-phase communication (metadata + binary)

Example update needed:
```csharp
// Send metadata (text frame)
await webSocket.SendAsync(
    Encoding.UTF8.GetBytes(metadataJson),
    WebSocketMessageType.Text,
    true,
    cancellationToken
);

// Send image (binary frame)
await webSocket.SendAsync(
    imageBytes,
    WebSocketMessageType.Binary,
    true,
    cancellationToken
);
```