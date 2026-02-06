# Quick Start Guide - WebSocket ACT Server

Get your ACT model serving predictions via WebSocket in 5 minutes!

## Prerequisites

- Trained ACT model at: `/home/lcjs-szw/repos/lerobot/outputs/train/act_your_dataset_20260117/checkpoints/last/pretrained_model`
- Python 3.8+
- LeRobot installed

## Step 1: Install Dependencies

```bash
pip install websockets
```

Or use the requirements file:

```bash
pip install -r requirements_websocket.txt
```

## Step 2: Start the Server

### Option A: Using the convenience script (recommended)

```bash
./start_websocket_server.sh
```

With custom settings:

```bash
./start_websocket_server.sh --device cuda --port 8000
```

### Option B: Direct Python command

```bash
python websocket_act_server.py \
    --port 8000 \
    --model_path /home/lcjs-szw/repos/lerobot/outputs/train/act_your_dataset_20260117/checkpoints/last/pretrained_model \
    --device cpu
```

You should see:

```
2026-01-17 10:00:00 - websocket_act_server - INFO - Initializing ACT WebSocket Server
2026-01-17 10:00:00 - websocket_act_server - INFO - Model path: /home/lcjs-szw/repos/lerobot/...
2026-01-17 10:00:00 - websocket_act_server - INFO - Device: cpu
2026-01-17 10:00:00 - websocket_act_server - INFO - Loading ACT model...
2026-01-17 10:00:05 - websocket_act_server - INFO - Model loaded successfully in 5.23s
2026-01-17 10:00:05 - websocket_act_server - INFO - Starting WebSocket server on 0.0.0.0:8000
2026-01-17 10:00:05 - websocket_act_server - INFO - Server is running and accepting connections
```

## Step 3: Test the Server

In a new terminal, run the test script:

```bash
python test_websocket_server.py
```

Expected output:

```
============================================================
WebSocket ACT Server Test
============================================================
Server URL: ws://localhost:8000
State dimension: 14
Image size: (480, 640)

Test 1: Connecting to server...
✓ Connection successful

Test 2: Sending observation...
✓ Observation sent and response received

Test 3: Validating response format...
✓ Response format valid

Test 4: Validating action chunk...
✓ Action chunk valid: 100 actions of dimension 14

Test 5: Checking timing information...
✓ Total inference time: 45.23ms
  - Parse: 5.12ms
  - Preprocess: 8.34ms
  - Inference: 25.67ms
  - Postprocess: 6.10ms

============================================================
✓ All tests passed!
============================================================
```

## Step 4: Run Example Client

Try the full example client:

```bash
python websocket_act_client_example.py --num_steps 5
```

This will send 5 observations and receive action chunks.

## Step 5: Integrate with Your Robot

### Python Integration

```python
import asyncio
import json
import websockets
import numpy as np

async def control_robot():
    async with websockets.connect("ws://localhost:8000") as ws:
        # Get robot state
        robot_state = get_robot_joint_positions()  # Your function
        
        # Get camera image
        camera_image = get_camera_image()  # Your function
        image_base64 = encode_image_to_base64(camera_image)
        
        # Prepare observation
        observation = {
            "observation.state": robot_state.tolist(),
            "observation.images.front": image_base64,
        }
        
        # Send request
        request = {"observation": observation, "timestep": 0}
        await ws.send(json.dumps(request))
        
        # Receive action chunk
        response = await ws.recv()
        data = json.loads(response)
        
        # Execute actions
        action_chunk = data["action_chunk"]
        for action in action_chunk:
            execute_robot_action(action)  # Your function
            await asyncio.sleep(0.01)  # Control frequency

asyncio.run(control_robot())
```

### JavaScript/Web Integration

```javascript
const ws = new WebSocket('ws://localhost:8000');

ws.onopen = () => {
    // Send observation
    const request = {
        observation: {
            "observation.state": [0.1, 0.2, 0.3, ...],
            "observation.images.front": imageBase64
        },
        timestep: 0
    };
    ws.send(JSON.stringify(request));
};

ws.onmessage = (event) => {
    const response = JSON.parse(event.data);
    const actions = response.action_chunk;
    // Execute actions on robot
    executeActions(actions);
};
```

## Common Issues

### Issue: Connection Refused

**Problem**: Cannot connect to server

**Solution**: 
1. Check if server is running
2. Verify port number (default: 8000)
3. Check firewall settings

### Issue: Model Not Found

**Problem**: `Error: Cannot load model from path`

**Solution**: 
1. Verify model path exists
2. Check that all required files are present:
   - `config.json`
   - `model.safetensors`
   - `policy_preprocessor.json`
   - `policy_postprocessor.json`

### Issue: Slow Inference

**Problem**: Inference takes too long (>100ms)

**Solution**:
1. Use GPU: `--device cuda`
2. Reduce image size
3. Use fewer cameras
4. Check system resources

### Issue: Shape Mismatch

**Problem**: `Error: Shape mismatch`

**Solution**:
1. Check that `observation.state` dimension matches model's expected input
2. Verify image dimensions match model's expected input
3. Review model config: `cat /path/to/model/config.json`

## Performance Tips

### For Best Latency

1. **Use GPU**: 3-5x faster than CPU
   ```bash
   ./start_websocket_server.sh --device cuda
   ```

2. **Optimize Image Size**: Smaller images = faster processing
   - Resize images before encoding
   - Use JPEG instead of PNG for compression

3. **Local Network**: Run server and client on same machine or LAN

4. **Batch Processing**: Send observations at consistent intervals

### Expected Performance

| Configuration | Latency | Throughput |
|--------------|---------|------------|
| CPU (Intel i9) | ~100-150ms | ~7-10 Hz |
| GPU (RTX 3090) | ~30-50ms | ~20-30 Hz |
| GPU (A100) | ~20-30ms | ~30-50 Hz |

## Next Steps

1. **Read Full Documentation**: See `README_WEBSOCKET_SERVER.md`
2. **Customize Server**: Modify preprocessing/postprocessing
3. **Deploy to Production**: Add SSL, authentication, monitoring
4. **Integrate with Robot**: Adapt examples to your robot platform

## Support

For issues:
1. Check server logs (set `--log_level DEBUG`)
2. Review this guide and README
3. Test with example client first
4. Check LeRobot documentation

## Files Overview

- `websocket_act_server.py` - Main server implementation
- `websocket_act_client_example.py` - Example client
- `test_websocket_server.py` - Quick test script
- `start_websocket_server.sh` - Convenience startup script
- `README_WEBSOCKET_SERVER.md` - Full documentation
- `requirements_websocket.txt` - Dependencies

Happy robot controlling! 🤖
