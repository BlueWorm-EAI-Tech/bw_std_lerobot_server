# Troubleshooting Guide - WebSocket ACT Server

Common issues and their solutions when using the WebSocket ACT server.

## Table of Contents

1. [Server Won't Start](#server-wont-start)
2. [Connection Issues](#connection-issues)
3. [Model Loading Errors](#model-loading-errors)
4. [Inference Errors](#inference-errors)
5. [Performance Issues](#performance-issues)
6. [Image Processing Errors](#image-processing-errors)
7. [Memory Issues](#memory-issues)
8. [Network Issues](#network-issues)

---

## Server Won't Start

### Issue: `ModuleNotFoundError: No module named 'websockets'`

**Cause**: WebSocket library not installed

**Solution**:
```bash
pip install websockets
# or
pip install -r requirements_websocket.txt
```

### Issue: `Address already in use`

**Cause**: Port 8000 is already in use

**Solution**:
```bash
# Option 1: Use a different port
python websocket_act_server.py --port 8001

# Option 2: Find and kill the process using port 8000
lsof -ti:8000 | xargs kill -9

# Option 3: Check what's using the port
lsof -i:8000
```

### Issue: `Permission denied` when binding to port

**Cause**: Trying to bind to a privileged port (<1024) without sudo

**Solution**:
```bash
# Option 1: Use a non-privileged port (recommended)
python websocket_act_server.py --port 8000

# Option 2: Use sudo (not recommended)
sudo python websocket_act_server.py --port 80
```

---

## Connection Issues

### Issue: `Connection refused` from client

**Cause**: Server not running or wrong address

**Solution**:
```bash
# 1. Check if server is running
ps aux | grep websocket_act_server

# 2. Check server logs
python websocket_act_server.py --log_level DEBUG

# 3. Verify server address
# If server is on same machine: ws://localhost:8000
# If server is on different machine: ws://SERVER_IP:8000

# 4. Test with curl
curl -i -N -H "Connection: Upgrade" \
     -H "Upgrade: websocket" \
     -H "Sec-WebSocket-Version: 13" \
     -H "Sec-WebSocket-Key: test" \
     http://localhost:8000
```

### Issue: `Connection timeout`

**Cause**: Firewall blocking connection or server not accessible

**Solution**:
```bash
# 1. Check firewall
sudo ufw status
sudo ufw allow 8000/tcp

# 2. Check if server is listening
netstat -tuln | grep 8000

# 3. Test connectivity
ping SERVER_IP
telnet SERVER_IP 8000
```

### Issue: `WebSocket connection closed unexpectedly`

**Cause**: Server error or network issue

**Solution**:
```bash
# 1. Check server logs for errors
python websocket_act_server.py --log_level DEBUG

# 2. Test with simple client
python test_websocket_server.py

# 3. Check network stability
ping -c 100 SERVER_IP
```

---

## Model Loading Errors

### Issue: `FileNotFoundError: Model path does not exist`

**Cause**: Incorrect model path

**Solution**:
```bash
# 1. Verify model path exists
ls -la /home/lcjs-szw/repos/lerobot/outputs/train/act_your_dataset_20260117/checkpoints/last/pretrained_model

# 2. Check required files
ls -la /path/to/model/
# Should contain:
# - config.json
# - model.safetensors
# - policy_preprocessor.json
# - policy_postprocessor.json

# 3. Use absolute path
python websocket_act_server.py --model_path /absolute/path/to/model
```

### Issue: `RuntimeError: Error loading model`

**Cause**: Corrupted model files or incompatible version

**Solution**:
```bash
# 1. Verify model files are not corrupted
python -c "import safetensors; safetensors.torch.load_file('/path/to/model/model.safetensors')"

# 2. Check LeRobot version
pip show lerobot

# 3. Re-download or re-train model if necessary
```

### Issue: `CUDA out of memory` during model loading

**Cause**: Model too large for GPU

**Solution**:
```bash
# Option 1: Use CPU
python websocket_act_server.py --device cpu

# Option 2: Clear GPU memory
python -c "import torch; torch.cuda.empty_cache()"

# Option 3: Use smaller batch size or model
```

---

## Inference Errors

### Issue: `Shape mismatch error`

**Cause**: Input dimensions don't match model expectations

**Solution**:
```python
# 1. Check model config
import json
with open('/path/to/model/config.json') as f:
    config = json.load(f)
    print("Expected state dim:", config.get('robot_state_feature'))
    print("Expected action dim:", config.get('action_feature'))
    print("Expected images:", config.get('image_features'))

# 2. Verify your observation matches
observation = {
    "observation.state": [0.1] * STATE_DIM,  # Must match config
    "observation.images.front": image_base64  # Must match config
}

# 3. Check image dimensions
from PIL import Image
img = Image.open("test.png")
print(f"Image size: {img.size}")  # Should match model's expected size
```

### Issue: `RuntimeError: Expected tensor on device cuda but got cpu`

**Cause**: Tensor device mismatch

**Solution**:
```bash
# This should be handled automatically by preprocessor
# If you see this error, it's a bug. Report it with:
python websocket_act_server.py --log_level DEBUG
```

### Issue: `KeyError: 'observation.state'`

**Cause**: Missing required observation field

**Solution**:
```python
# Check what fields your model expects
import json
with open('/path/to/model/config.json') as f:
    config = json.load(f)
    print("Required features:", config.get('features'))

# Ensure your observation includes all required fields
observation = {
    "observation.state": [...],  # If model expects state
    "observation.images.front": "...",  # If model expects images
}
```

---

## Performance Issues

### Issue: Inference is very slow (>200ms)

**Cause**: Running on CPU or inefficient processing

**Solution**:
```bash
# 1. Use GPU
python websocket_act_server.py --device cuda

# 2. Check GPU is being used
nvidia-smi  # Should show python process using GPU

# 3. Reduce image size
# Resize images before encoding to base64

# 4. Profile the code
python websocket_act_server.py --log_level DEBUG
# Check timing breakdown in logs
```

### Issue: High latency (>100ms on GPU)

**Cause**: Network latency or large images

**Solution**:
```bash
# 1. Check network latency
ping SERVER_IP

# 2. Reduce image size
# Use smaller images (e.g., 320x240 instead of 640x480)

# 3. Use JPEG instead of PNG
# JPEG is smaller and faster to encode/decode

# 4. Run server and client on same machine
# Eliminates network latency
```

### Issue: Server becomes unresponsive

**Cause**: Blocking operation or resource exhaustion

**Solution**:
```bash
# 1. Check server logs
python websocket_act_server.py --log_level DEBUG

# 2. Monitor resources
htop  # Check CPU/memory usage
nvidia-smi  # Check GPU usage

# 3. Restart server
pkill -f websocket_act_server
python websocket_act_server.py
```

---

## Image Processing Errors

### Issue: `Cannot decode base64 image`

**Cause**: Invalid base64 encoding

**Solution**:
```python
# Ensure proper encoding
import base64
import io
from PIL import Image

# Correct way to encode
image = Image.open("test.png")
buffer = io.BytesIO()
image.save(buffer, format="PNG")
image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

# Don't include data URL prefix
# WRONG: "data:image/png;base64,iVBORw0KG..."
# RIGHT: "iVBORw0KG..."
```

### Issue: `Image size mismatch`

**Cause**: Image dimensions don't match model expectations

**Solution**:
```python
from PIL import Image

# Resize image to match model expectations
image = Image.open("test.png")
image = image.resize((640, 480))  # Match model's expected size

# Then encode
buffer = io.BytesIO()
image.save(buffer, format="PNG")
image_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
```

### Issue: `PIL.UnidentifiedImageError`

**Cause**: Corrupted image data

**Solution**:
```python
# Verify image data before sending
try:
    image = Image.open("test.png")
    image.verify()  # Check if image is valid
    image = Image.open("test.png")  # Reopen after verify
except Exception as e:
    print(f"Invalid image: {e}")
```

---

## Memory Issues

### Issue: `CUDA out of memory` during inference

**Cause**: GPU memory exhausted

**Solution**:
```bash
# 1. Clear GPU cache
python -c "import torch; torch.cuda.empty_cache()"

# 2. Reduce batch size (if applicable)

# 3. Use CPU instead
python websocket_act_server.py --device cpu

# 4. Close other GPU processes
nvidia-smi  # Find other processes
kill -9 PID  # Kill unnecessary processes
```

### Issue: `MemoryError` or system becomes slow

**Cause**: RAM exhausted

**Solution**:
```bash
# 1. Check memory usage
free -h

# 2. Reduce image size
# Use smaller images to reduce memory usage

# 3. Restart server periodically
# If memory leak suspected

# 4. Increase swap space (temporary fix)
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

---

## Network Issues

### Issue: `Broken pipe` error

**Cause**: Client disconnected unexpectedly

**Solution**:
```python
# This is normal when clients disconnect
# Server handles this gracefully
# Check client-side code for issues
```

### Issue: Large messages fail to send

**Cause**: Message size exceeds WebSocket limits

**Solution**:
```python
# 1. Reduce image size
image = image.resize((320, 240))  # Smaller images

# 2. Use JPEG compression
buffer = io.BytesIO()
image.save(buffer, format="JPEG", quality=85)

# 3. Increase WebSocket max size (if needed)
# In websocket_act_server.py, modify:
# websockets.serve(..., max_size=10*1024*1024)  # 10MB
```

### Issue: Intermittent connection drops

**Cause**: Network instability or timeout

**Solution**:
```python
# Add ping/pong to keep connection alive
# In client code:
async def keep_alive(websocket):
    while True:
        await websocket.ping()
        await asyncio.sleep(30)

# Run alongside main loop
asyncio.create_task(keep_alive(websocket))
```

---

## Debugging Tips

### Enable Debug Logging

```bash
python websocket_act_server.py --log_level DEBUG
```

### Test with Simple Client

```bash
python test_websocket_server.py
```

### Check Server Health

```python
import asyncio
import websockets
import json

async def health_check():
    try:
        async with websockets.connect("ws://localhost:8000") as ws:
            # Send minimal observation
            obs = {
                "observation": {
                    "observation.state": [0.0] * 14
                }
            }
            await ws.send(json.dumps(obs))
            response = await ws.recv()
            print("Server is healthy:", json.loads(response))
    except Exception as e:
        print("Server is unhealthy:", e)

asyncio.run(health_check())
```

### Monitor Performance

```bash
# Terminal 1: Run server with debug logging
python websocket_act_server.py --log_level DEBUG

# Terminal 2: Monitor system resources
watch -n 1 nvidia-smi  # GPU
watch -n 1 'free -h'   # RAM

# Terminal 3: Run client
python websocket_act_client_example.py
```

### Capture Network Traffic

```bash
# Install tcpdump
sudo apt-get install tcpdump

# Capture WebSocket traffic
sudo tcpdump -i any -s 0 -w websocket.pcap port 8000

# Analyze with Wireshark
wireshark websocket.pcap
```

---

## Getting Help

If you're still experiencing issues:

1. **Check Logs**: Run with `--log_level DEBUG`
2. **Run Tests**: `python test_websocket_server.py`
3. **Verify Setup**: Check all prerequisites are installed
4. **Review Documentation**: See `README_WEBSOCKET_SERVER.md`
5. **Check Examples**: Compare with `websocket_act_client_example.py`
6. **Report Issue**: Include logs, error messages, and system info

### Information to Include When Reporting Issues

```bash
# System info
uname -a
python --version
pip list | grep -E "torch|websockets|lerobot"

# GPU info (if applicable)
nvidia-smi

# Server logs
python websocket_act_server.py --log_level DEBUG 2>&1 | tee server.log

# Test results
python test_websocket_server.py 2>&1 | tee test.log
```

---

## Quick Reference

### Common Commands

```bash
# Start server
python websocket_act_server.py --port 8000 --device cuda

# Test server
python test_websocket_server.py

# Run example
python websocket_act_client_example.py

# Check port
lsof -i:8000

# Kill server
pkill -f websocket_act_server

# Clear GPU
python -c "import torch; torch.cuda.empty_cache()"
```

### Common Fixes

| Problem | Quick Fix |
|---------|-----------|
| Connection refused | Check server is running |
| Port in use | Use different port or kill process |
| Model not found | Verify model path |
| Shape mismatch | Check observation dimensions |
| Slow inference | Use GPU (`--device cuda`) |
| Out of memory | Reduce image size or use CPU |
| Image decode error | Check base64 encoding |
| Network timeout | Check firewall and connectivity |

---

## Still Having Issues?

1. Review the [Quick Start Guide](QUICKSTART_WEBSOCKET.md)
2. Check the [Full Documentation](README_WEBSOCKET_SERVER.md)
3. Compare with [Working Examples](websocket_act_client_example.py)
4. Enable debug logging and analyze output
5. Test with minimal example first
