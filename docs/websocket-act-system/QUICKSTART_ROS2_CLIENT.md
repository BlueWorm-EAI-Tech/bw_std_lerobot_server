# Quick Start - ROS2 WebSocket ACT Client

Get your robot running with the WebSocket ACT server in 5 minutes!

## Prerequisites

- ✅ WebSocket ACT server running (see `QUICKSTART_WEBSOCKET.md`)
- ✅ ROS2 installed (Humble or later)
- ✅ Robot with LeRobot interface
- ✅ Python 3.8+

## Step 1: Install Dependencies

```bash
pip install websockets pillow numpy
```

## Step 2: Start the Server

```bash
# In terminal 1
./start_websocket_server.sh
```

You should see:
```
Server is running and accepting connections
```

## Step 3: Run the Client

```bash
# In terminal 2
python ros2_websocket_act_client.py \
    --server ws://localhost:8000 \
    --robot-id bw_robot \
    --fps 10.0
```

## Step 4: Watch It Work!

You should see output like:
```
2026-01-17 14:00:00 - INFO - Connected to WebSocket server successfully
2026-01-17 14:00:00 - INFO - Robot connected
2026-01-17 14:00:00 - INFO - Starting control loop at 10.0 Hz
2026-01-17 14:00:01 - INFO - Received new action chunk with 100 actions
2026-01-17 14:00:02 - INFO - Step 10: inference=45.2ms, chunk_idx=10, new_chunk=False, queue_size=90
2026-01-17 14:00:03 - INFO - Step 20: inference=45.2ms, chunk_idx=20, new_chunk=False, queue_size=80
```

## Common Issues

### Issue: Connection Refused

**Solution**: Make sure server is running
```bash
ps aux | grep websocket_act_server
```

### Issue: Robot Not Found

**Solution**: Check robot ID
```bash
python ros2_websocket_act_client.py --robot-id YOUR_ROBOT_ID
```

### Issue: Slow Performance

**Solution**: Increase FPS
```bash
python ros2_websocket_act_client.py --fps 20.0
```

## Configuration Options

### Basic

```bash
# Default settings (good for most cases)
python ros2_websocket_act_client.py
```

### Safe Mode

```bash
# Slow and smooth (for testing)
python ros2_websocket_act_client.py \
    --fps 5.0 \
    --action-speed 0.2 \
    --max-action-change 0.1
```

### Performance Mode

```bash
# Fast and responsive (for production)
python ros2_websocket_act_client.py \
    --fps 20.0 \
    --action-speed 0.8 \
    --max-action-change 0.5
```

### Remote Server

```bash
# Connect to remote server
python ros2_websocket_act_client.py \
    --server ws://192.168.1.100:8000 \
    --timeout 10.0
```

## Next Steps

1. **Tune parameters**: Adjust `--action-speed` and `--max-action-change`
2. **Monitor performance**: Watch the logs for timing information
3. **Read full docs**: See `README_ROS2_CLIENT.md`

## Quick Reference

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--server` | `ws://localhost:8000` | Server URL |
| `--fps` | `10.0` | Control frequency |
| `--action-speed` | `0.5` | Smoothing (0-1) |
| `--max-action-change` | `0.3` | Max change (rad) |
| `--robot-id` | `bw_robot` | Robot ID |

## Stop the Client

Press `Ctrl+C` to stop gracefully.

## Summary

You now have:
- ✅ Client connected to server
- ✅ Robot receiving actions
- ✅ Control loop running

**Happy robot controlling! 🤖**
