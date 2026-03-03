# ROS2 WebSocket Client Template

This is a **template** for connecting ROS2-based robots to WebSocket inference servers.

## Usage

This client connects to a WebSocket inference server, receives observations from the robot via ROS2, sends inference requests, and executes actions on the robot.

See `deploy_ros2_client.sh` for deployment instructions.

## Files

- `ros2_websocket_act_client.py` - Main client script (adapted from HTTP-based reference)
- `deploy_ros2_client.sh` - Deployment script
- `ros2_client_config.yaml` - Configuration file

## For Other Robots

This template can be adapted for other ROS2-based robots by modifying:
- Robot-specific observation/action handling
- Joint configuration
- Camera topics
