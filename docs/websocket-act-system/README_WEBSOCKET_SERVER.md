# ACT Model WebSocket Server

A WebSocket server for serving trained ACT (Action Chunking Transformer) models for real-time robot control.

## Features

- **WebSocket Protocol**: Simple, real-time communication
- **JSON Format**: Human-readable request/response format
- **Base64 Image Support**: Send images directly in JSON
- **Action Chunking**: Returns full action chunks for efficient control
- **Preprocessing Pipeline**: Automatic normalization and batching
- **Multi-camera Support**: Handle multiple camera views
- **Error Handling**: Graceful error responses
- **Performance Metrics**: Detailed timing information

## Architecture

```
Client                          Server
  |                               |
  |  1. Connect (WebSocket)       |
  |------------------------------>|
  |                               |
  |  2. Send Observation (JSON)   |
  |------------------------------>|
  |                               | 3. Parse & Decode
  |                               | 4. Preprocess
  |                               | 5. Run ACT Inference
  |                               | 6. Postprocess
  |  7. Receive Actions (JSON)    |
  |<------------------------------|
  |                               |
```

## Installation

### Prerequisites

Make sure you have the LeRobot environment set up:

```bash
# Install LeRobot dependencies (if not already installed)
pip install -e .
```

### Additional Dependencies

Install WebSocket support:

```bash
pip install websockets
```

## Usage

### Starting the Server

Basic usage with default settings:

```bash
python websocket_act_server.py
```

With custom configuration:

```bash
python websocket_act_server.py \
    --port 8000 \
    --host 0.0.0.0 \
    --model_path /home/lcjs-szw/repos/lerobot/outputs/train/act_your_dataset_20260117/checkpoints/last/pretrained_model \
    --device cuda \
    --log_level INFO
```

### Command Line Arguments

- `--port`: Port to bind the server to (default: 8000)
- `--host`: Host address to bind to (default: 0.0.0.0)
- `--model_path`: Path to the pretrained ACT model directory
- `--device`: Device for inference (cpu, cuda, mps) (default: cpu)
- `--log_level`: Logging level (DEBUG, INFO, WARNING, ERROR) (default: INFO)

### Testing the Server

Run the example client:

```bash
python websocket_act_client_example.py --server_url ws://localhost:8000
```

With custom parameters:

```bash
python websocket_act_client_example.py \
    --server_url ws://localhost:8000 \
    --num_steps 10 \
    --state_dim 14 \
    --image_height 480 \
    --image_width 640 \
    --num_cameras 1 \
    --log_level INFO
```

## API Reference

### Request Format

Send a JSON message via WebSocket:

```json
{
    "observation": {
        "observation.state": [0.1, 0.2, 0.3, ...],
        "observation.images.front": "base64_encoded_image_data",
        "observation.images.wrist": "base64_encoded_image_data"
    },
    "timestep": 0
}
```

**Fields:**
- `observation` (required): Dictionary containing observation data
  - `observation.state` (optional): Robot joint positions as list of floats
  - `observation.environment_state` (optional): Environment state as list of floats
  - `observation.images.*` (optional): Base64-encoded images (PNG/JPEG)
- `timestep` (optional): Current timestep for tracking (default: 0)

### Response Format

Successful response:

```json
{
    "action_chunk": [
        [0.1, 0.2, 0.3, ...],
        [0.15, 0.25, 0.35, ...],
        ...
    ],
    "timestep": 0,
    "inference_time_ms": 33.5,
    "chunk_size": 100,
    "action_dim": 14,
    "timing": {
        "parse_ms": 5.2,
        "preprocess_ms": 8.1,
        "inference_ms": 15.3,
        "postprocess_ms": 4.9,
        "total_ms": 33.5
    }
}
```

**Fields:**
- `action_chunk`: List of actions, each action is a list of floats
- `timestep`: Echoed timestep from request
- `inference_time_ms`: Total processing time in milliseconds
- `chunk_size`: Number of actions in the chunk
- `action_dim`: Dimension of each action
- `timing`: Detailed timing breakdown

Error response:

```json
{
    "error": "Error type",
    "message": "Detailed error message"
}
```

## Python Client Example

```python
import asyncio
import json
import websockets
import base64
from PIL import Image
import io

async def send_observation():
    # Connect to server
    async with websockets.connect("ws://localhost:8000") as websocket:
        # Prepare observation
        observation = {
            "observation.state": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
        }
        
        # Add image (optional)
        image = Image.open("camera_image.png")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        observation["observation.images.front"] = image_base64
        
        # Send request
        request = {
            "observation": observation,
            "timestep": 0
        }
        await websocket.send(json.dumps(request))
        
        # Receive response
        response = await websocket.recv()
        data = json.loads(response)
        
        # Use action chunk
        action_chunk = data["action_chunk"]
        print(f"Received {len(action_chunk)} actions")
        print(f"First action: {action_chunk[0]}")

# Run
asyncio.run(send_observation())
```

## JavaScript Client Example

```javascript
const ws = new WebSocket('ws://localhost:8000');

ws.onopen = () => {
    console.log('Connected to ACT server');
    
    // Prepare observation
    const observation = {
        "observation.state": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
        // Add base64 encoded image if needed
        // "observation.images.front": "data:image/png;base64,..."
    };
    
    // Send request
    const request = {
        observation: observation,
        timestep: 0
    };
    ws.send(JSON.stringify(request));
};

ws.onmessage = (event) => {
    const response = JSON.parse(event.data);
    
    if (response.error) {
        console.error('Error:', response.error, response.message);
    } else {
        console.log('Received action chunk:', response.action_chunk);
        console.log('Inference time:', response.inference_time_ms, 'ms');
    }
};

ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};
```

## Performance Considerations

### Latency Optimization

1. **Use GPU**: Set `--device cuda` for faster inference
2. **Image Size**: Smaller images = faster encoding/decoding
3. **Compression**: Use JPEG for images instead of PNG (smaller size)
4. **Local Network**: Run server and client on same machine or local network

### Typical Latencies

On a modern GPU (e.g., RTX 3090):
- Parsing: ~5ms
- Preprocessing: ~8ms
- Inference: ~15-30ms
- Postprocessing: ~5ms
- **Total: ~30-50ms**

On CPU:
- **Total: ~100-200ms**

### Throughput

The server handles one request at a time per connection but supports multiple concurrent connections.

## Troubleshooting

### Connection Refused

```
Error: Connection refused
```

**Solution**: Make sure the server is running and the port is correct.

### Model Loading Error

```
Error: Cannot load model from path
```

**Solution**: Verify the model path exists and contains all required files:
- `config.json`
- `model.safetensors`
- `policy_preprocessor.json`
- `policy_postprocessor.json`

### Image Decoding Error

```
Error: Cannot decode base64 image
```

**Solution**: Ensure images are properly base64 encoded. Remove any data URL prefix.

### Shape Mismatch Error

```
Error: Shape mismatch
```

**Solution**: Verify that observation dimensions match the model's expected input shapes.

## Advanced Usage

### Custom Preprocessing

You can modify the preprocessing pipeline by editing the server code:

```python
# In websocket_act_server.py, modify the preprocessor initialization
self.preprocessor, self.postprocessor = make_pre_post_processors(
    self.policy_config,
    pretrained_path=self.model_path,
    preprocessor_overrides={
        "device_processor": device_override,
        # Add custom overrides here
    },
    postprocessor_overrides={"device_processor": device_override},
)
```

### Multiple Models

To serve multiple models, run multiple server instances on different ports:

```bash
# Server 1
python websocket_act_server.py --port 8000 --model_path /path/to/model1

# Server 2
python websocket_act_server.py --port 8001 --model_path /path/to/model2
```

### Production Deployment

For production use, consider:

1. **SSL/TLS**: Use `wss://` instead of `ws://`
2. **Authentication**: Add token-based authentication
3. **Rate Limiting**: Limit requests per client
4. **Monitoring**: Add metrics and logging
5. **Load Balancing**: Use multiple server instances behind a load balancer

## License

This code follows the same license as the LeRobot project (Apache 2.0).

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review the LeRobot documentation
3. Open an issue on the repository
