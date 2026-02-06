# ROS2 WebSocket ACT Client

A ROS2-compatible client for connecting to the WebSocket ACT inference server. This client reads observations from a robot, sends them to the server for inference, and executes the returned actions.

## Overview

This client is adapted from an HTTP-based reference implementation to use WebSocket protocol, providing:
- **Lower latency**: Persistent WebSocket connection
- **Action chunking**: Receives 100 actions at once, executes them sequentially
- **Action smoothing**: Interpolates between current state and predicted action
- **Action limiting**: Clips maximum change per step for safety
- **Automatic reconnection**: Handles connection drops gracefully

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ROS2 Robot System                         │
│  ┌──────────────┐         ┌──────────────┐                 │
│  │ Joint States │         │   Cameras    │                 │
│  └──────┬───────┘         └──────┬───────┘                 │
└─────────┼────────────────────────┼─────────────────────────┘
          │                        │
          │  get_observation()     │
          ▼                        ▼
┌─────────────────────────────────────────────────────────────┐
│              ROS2 WebSocket ACT Client                       │
│                                                              │
│  Control Loop (10Hz):                                        │
│  1. Read observation (state + images)                        │
│  2. Send to server (when queue empty)                        │
│  3. Receive action chunk (100 actions)                       │
│  4. Pop one action from queue                                │
│  5. Apply smoothing and limiting                             │
│  6. Send to robot                                            │
└─────────────────────┬───────────────────────────────────────┘
                      │ WebSocket
                      │ (JSON + Base64 images)
┌─────────────────────▼───────────────────────────────────────┐
│              WebSocket ACT Server                            │
│              (Port 8000)                                     │
└──────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

```bash
# ROS2 (Humble or later)
# Python 3.8+
# LeRobot environment

# Install WebSocket client
pip install websockets pillow numpy
```

### Setup

```bash
# Make executable
chmod +x ros2_websocket_act_client.py

# Test connection to server
python ros2_websocket_act_client.py --server ws://localhost:8000 --help
```

## Usage

### Basic Usage

```bash
# Start the WebSocket server first
./start_websocket_server.sh

# In another terminal, run the client
python ros2_websocket_act_client.py \
    --server ws://localhost:8000 \
    --robot-id bw_robot \
    --fps 10.0
```

### With Custom Parameters

```bash
python ros2_websocket_act_client.py \
    --server ws://192.168.1.100:8000 \
    --robot-id my_robot \
    --fps 10.0 \
    --action-speed 0.5 \
    --max-action-change 0.3 \
    --timeout 5.0
```

### Command Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--server` | `ws://localhost:8000` | WebSocket server URL |
| `--timeout` | `5.0` | Request timeout (seconds) |
| `--fps` | `10.0` | Control frequency (Hz) |
| `--action-speed` | `0.5` | Action smoothing factor (0-1) |
| `--max-action-change` | `0.3` | Max action change per step (rad) |
| `--robot-id` | `bw_robot` | Robot identifier |

## Configuration

### Action Smoothing

The client applies action smoothing to prevent jerky movements:

```python
# Interpolate between current state and predicted action
smoothed_action = current_state + alpha * (predicted_action - current_state)
```

- `alpha = 0.0`: No movement (ignore predictions)
- `alpha = 0.5`: Move halfway to predicted action (default)
- `alpha = 1.0`: Use predicted action directly

### Action Limiting

Maximum change per step is limited for safety:

```python
# Clip change to maximum allowed
delta = clip(smoothed_action - current_state, -max_delta, max_delta)
final_action = current_state + delta
```

- Prevents sudden large movements
- Default: 0.3 radians per step
- Adjust based on robot capabilities

## How It Works

### 1. Observation Collection

```python
# Read from robot
obs = robot.get_observation()

# Extract joint states
state = [obs[f"{name}.pos"] for name in robot.joint_names]

# Extract images
env_cam = obs["env_cam"]  # Environment camera
left_wrist_cam = obs["left_wrist_cam"]  # Left wrist camera
right_wrist_cam = obs["right_wrist_cam"]  # Right wrist camera
```

### 2. Inference Request

```python
# Send to server (only when action queue is empty)
result = await client.infer(
    state=state,
    env_cam=env_cam,
    left_wrist_cam=left_wrist_cam,
    right_wrist_cam=right_wrist_cam
)

# Receive action chunk (100 actions)
action = result["action"]  # One action from chunk
```

### 3. Action Execution

```python
# Apply smoothing
smoothed = state + alpha * (action - state)

# Apply limiting
delta = clip(smoothed - state, -max_delta, max_delta)
final_action = state + delta

# Send to robot
robot.send_action(final_action)
```

## Action Chunking

The ACT model predicts 100 actions at once (action chunking). The client manages this efficiently:

1. **Request chunk** when queue is empty (~every 10 seconds at 10Hz)
2. **Store chunk** in local queue
3. **Pop one action** per control step
4. **Execute action** on robot

This reduces network overhead from 10 requests/sec to 0.1 requests/sec!

## Timing Example

```
t=0.0s:   Request chunk → Receive 100 actions
t=0.1s:   Execute action 1
t=0.2s:   Execute action 2
...
t=9.9s:   Execute action 100
t=10.0s:  Request new chunk → Receive 100 actions
t=10.1s:  Execute action 1
...
```

## Error Handling

### Connection Lost

```python
# Automatic reconnection
try:
    result = await client.infer(...)
except websockets.ConnectionClosed:
    logger.error("Connection lost, reconnecting...")
    await client.connect()
```

### Server Timeout

```python
# Timeout after 5 seconds
try:
    response = await asyncio.wait_for(
        client.websocket.recv(),
        timeout=5.0
    )
except asyncio.TimeoutError:
    logger.error("Server timeout")
```

### Robot Errors

```python
# Graceful error handling
try:
    robot.send_action(action)
except Exception as e:
    logger.error(f"Robot error: {e}")
    # Continue or stop based on severity
```

## Comparison with HTTP Client

| Feature | HTTP Client (Reference) | WebSocket Client (This) |
|---------|------------------------|-------------------------|
| **Protocol** | HTTP REST | WebSocket |
| **Connection** | New per request | Persistent |
| **Requests/sec** | 10 (at 10Hz) | 0.1 (with chunking) |
| **Latency** | Higher (connection overhead) | Lower (persistent) |
| **Bandwidth** | Higher | Lower |
| **Code** | Synchronous | Asynchronous |
| **Action Management** | Server-side | Client-side queue |

## Migration from HTTP Client

### Old Code (HTTP)

```python
from requests import Session

client = ACTClient("http://localhost:8000")
result = client.infer(state, env_cam, ...)
action = result["action"]
```

### New Code (WebSocket)

```python
import asyncio
from websockets import connect

client = WebSocketACTClient("ws://localhost:8000")
await client.connect()
result = await client.infer(state, env_cam, ...)
action = result["action"]
```

### Key Changes

1. **URL**: `http://` → `ws://`
2. **Async**: Add `async`/`await`
3. **Connect**: Explicit `connect()` call
4. **Action Queue**: Managed automatically

## Troubleshooting

### Connection Refused

**Problem**: Cannot connect to server

**Solution**:
```bash
# Check server is running
ps aux | grep websocket_act_server

# Check server URL
# Use ws:// not http://
python ros2_websocket_act_client.py --server ws://localhost:8000
```

### Slow Performance

**Problem**: Actions are delayed

**Solution**:
```bash
# Increase control frequency
python ros2_websocket_act_client.py --fps 20.0

# Reduce action smoothing
python ros2_websocket_act_client.py --action-speed 0.8
```

### Jerky Movements

**Problem**: Robot moves in jerks

**Solution**:
```bash
# Increase action smoothing
python ros2_websocket_act_client.py --action-speed 0.3

# Reduce max change
python ros2_websocket_act_client.py --max-action-change 0.1
```

### Image Encoding Errors

**Problem**: Failed to encode image

**Solution**:
```python
# Check image format
print(f"Image shape: {env_cam.shape}")  # Should be (H, W, 3)
print(f"Image dtype: {env_cam.dtype}")  # Should be uint8
print(f"Image range: {env_cam.min()}-{env_cam.max()}")  # Should be 0-255
```

## Performance Tips

### 1. Optimize Control Frequency

```bash
# Lower frequency = less CPU, more latency
python ros2_websocket_act_client.py --fps 5.0

# Higher frequency = more CPU, less latency
python ros2_websocket_act_client.py --fps 20.0
```

### 2. Adjust Smoothing

```bash
# More smoothing = smoother but slower
python ros2_websocket_act_client.py --action-speed 0.3

# Less smoothing = faster but jerkier
python ros2_websocket_act_client.py --action-speed 0.8
```

### 3. Network Optimization

```bash
# Use local server for best performance
python ros2_websocket_act_client.py --server ws://localhost:8000

# Use wired connection for remote server
python ros2_websocket_act_client.py --server ws://192.168.1.100:8000
```

## Advanced Usage

### Custom Robot Integration

```python
# Implement robot interface
class MyRobot:
    def __init__(self, config):
        self.joint_names = ["joint1", "joint2", ...]
    
    def connect(self):
        # Connect to robot
        pass
    
    def get_observation(self):
        # Return dict with:
        # - "joint_name.pos": float
        # - "env_cam": np.ndarray
        # - "left_wrist_cam": np.ndarray
        # - "right_wrist_cam": np.ndarray
        return obs
    
    def send_action(self, action_dict):
        # Execute action
        pass
    
    def disconnect(self):
        # Disconnect from robot
        pass
```

### Logging

```python
# Enable debug logging
import logging
logging.getLogger().setLevel(logging.DEBUG)

# Log to file
logging.basicConfig(
    filename='client.log',
    level=logging.INFO
)
```

## Examples

### Example 1: Basic Usage

```bash
# Start server
./start_websocket_server.sh

# Run client
python ros2_websocket_act_client.py
```

### Example 2: Remote Server

```bash
# Connect to remote server
python ros2_websocket_act_client.py \
    --server ws://192.168.1.100:8000 \
    --timeout 10.0
```

### Example 3: High-Speed Control

```bash
# 20Hz control with aggressive smoothing
python ros2_websocket_act_client.py \
    --fps 20.0 \
    --action-speed 0.8 \
    --max-action-change 0.5
```

### Example 4: Safe Mode

```bash
# Slow and smooth for testing
python ros2_websocket_act_client.py \
    --fps 5.0 \
    --action-speed 0.2 \
    --max-action-change 0.1
```

## Testing

### Test Connection

```python
import asyncio
import websockets

async def test():
    async with websockets.connect("ws://localhost:8000") as ws:
        print("Connected!")

asyncio.run(test())
```

### Test with Mock Robot

```python
class MockRobot:
    def __init__(self):
        self.joint_names = [f"joint{i}" for i in range(16)]
    
    def connect(self):
        pass
    
    def get_observation(self):
        return {
            f"{name}.pos": 0.0 for name in self.joint_names
        } | {
            "env_cam": np.zeros((240, 320, 3), dtype=np.uint8),
            "left_wrist_cam": np.zeros((240, 424, 3), dtype=np.uint8),
            "right_wrist_cam": np.zeros((240, 424, 3), dtype=np.uint8),
        }
    
    def send_action(self, action):
        print(f"Action: {action}")
    
    def disconnect(self):
        pass
```

## Support

For issues or questions:
1. Check server is running: `ps aux | grep websocket_act_server`
2. Check server logs: `--log_level DEBUG`
3. Test connection: `python test_websocket_server.py`
4. Review this README

## License

Same as LeRobot project (Apache 2.0)

## Summary

This ROS2 WebSocket client provides:
- ✅ **Easy migration** from HTTP client
- ✅ **Better performance** with WebSocket
- ✅ **Action chunking** for efficiency
- ✅ **Action smoothing** for safety
- ✅ **Automatic reconnection** for reliability
- ✅ **Production ready** with error handling

**Get started:**
```bash
python ros2_websocket_act_client.py --server ws://localhost:8000
```
