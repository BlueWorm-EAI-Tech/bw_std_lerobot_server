#!/usr/bin/env python3
"""
ROS2 WebSocket ACT Client

Connects to WebSocket ACT inference server, reads observations from ROS2/robot,
sends inference requests, and executes actions.

Adapted from HTTP-based reference client to use WebSocket protocol.
"""

import argparse
import asyncio
import base64
import contextlib
import io
import json
import logging
import signal
import sys
import time
from collections import deque

import numpy as np
import websockets
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variables
running = True
robot = None


def signal_handler(sig, frame):
    """Handle Ctrl+C"""
    global running
    logger.info("Received exit signal, shutting down...")
    running = False


class WebSocketACTClient:
    """WebSocket-based ACT inference client"""

    def __init__(self, server_url: str, timeout: float = 5.0):
        """Initialize WebSocket client.

        Args:
            server_url: WebSocket server URL (e.g., ws://localhost:8000)
            timeout: Request timeout in seconds
        """
        self.server_url = server_url
        self.timeout = timeout
        self.websocket = None

        # Action queue management
        self.action_queue = deque()
        self.chunk_index = 0
        self.total_chunks_received = 0

        # Timing
        self.last_inference_time_ms = 0.0

        logger.info(f"WebSocket ACT Client initialized: {server_url}")

    async def connect(self):
        """Connect to WebSocket server"""
        try:
            logger.info(f"Connecting to WebSocket server: {self.server_url}")
            self.websocket = await websockets.connect(
                self.server_url,
                max_size=10 * 1024 * 1024  # 10MB for large images
            )
            logger.info("Connected to WebSocket server successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to server: {e}")
            return False

    async def disconnect(self):
        """Disconnect from server"""
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected from server")

    def _encode_image(self, image: np.ndarray) -> str | None:
        """Encode numpy image to base64 string.

        Args:
            image: Numpy array of shape (H, W, C) with values 0-255

        Returns:
            Base64 encoded string or None if image is None
        """
        if image is None:
            return None

        try:
            # Ensure uint8
            if image.dtype != np.uint8:
                image = (image * 255).astype(np.uint8) if image.max() <= 1.0 else image.astype(np.uint8)

            # Convert to PIL Image
            img = Image.fromarray(image)

            # Encode to PNG
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)

            # Convert to base64
            base64_str = base64.b64encode(buffer.read()).decode("utf-8")

            return base64_str
        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            return None

    async def _request_action_chunk(
        self,
        state: np.ndarray,
        env_cam: np.ndarray | None = None,
        left_wrist_cam: np.ndarray | None = None,
        right_wrist_cam: np.ndarray | None = None
    ) -> list:
        """Request action chunk from server.

        Args:
            state: Joint state array [16]
            env_cam: Environment camera image [H, W, C]
            left_wrist_cam: Left wrist camera image [H, W, C]
            right_wrist_cam: Right wrist camera image [H, W, C]

        Returns:
            List of actions
        """
        # Prepare observation
        observation = {
            "observation.state": state.tolist(),
        }

        # Add images if available
        if env_cam is not None:
            observation["observation.images.env_cam"] = self._encode_image(env_cam)
        if left_wrist_cam is not None:
            observation["observation.images.left_wrist_cam"] = self._encode_image(left_wrist_cam)
        if right_wrist_cam is not None:
            observation["observation.images.right_wrist_cam"] = self._encode_image(right_wrist_cam)

        # Prepare request
        request = {
            "observation": observation,
            "timestep": self.total_chunks_received
        }

        # Send request
        time.perf_counter()
        await self.websocket.send(json.dumps(request))

        # Receive response with timeout
        try:
            response_str = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=self.timeout
            )
        except asyncio.TimeoutError as err:
            raise RuntimeError(f"Server timeout after {self.timeout}s") from err

        # Parse response
        response = json.loads(response_str)

        # Check for errors
        if "error" in response:
            raise RuntimeError(f"Server error: {response['error']} - {response.get('message', '')}")

        # Extract timing
        self.last_inference_time_ms = response.get("inference_time_ms", 0.0)

        # Extract action chunk
        action_chunk = response["action_chunk"]
        self.total_chunks_received += 1

        logger.debug(f"Received action chunk: {len(action_chunk)} actions, "
                    f"inference time: {self.last_inference_time_ms:.1f}ms")

        return action_chunk

    async def infer(
        self,
        state: np.ndarray,
        env_cam: np.ndarray | None = None,
        left_wrist_cam: np.ndarray | None = None,
        right_wrist_cam: np.ndarray | None = None,
        reset: bool = False
    ) -> dict:
        """Get next action from server.

        This method manages the action queue internally. It requests a new chunk
        when the queue is empty, and returns one action at a time.

        Args:
            state: Joint state array [16]
            env_cam: Environment camera image [H, W, C]
            left_wrist_cam: Left wrist camera image [H, W, C]
            right_wrist_cam: Right wrist camera image [H, W, C]
            reset: Whether to reset the action queue (first step)

        Returns:
            Dictionary with:
                - action: Action array
                - inference_time_ms: Inference time
                - chunk_index: Current index in chunk
                - is_new_chunk: Whether this is the first action of a new chunk
        """
        # Reset queue if requested
        if reset:
            self.action_queue.clear()
            self.chunk_index = 0
            logger.info("Action queue reset")

        # Request new chunk if queue is empty
        is_new_chunk = False
        if len(self.action_queue) == 0:
            logger.debug("Action queue empty, requesting new chunk...")
            chunk = await self._request_action_chunk(
                state, env_cam, left_wrist_cam, right_wrist_cam
            )
            self.action_queue.extend(chunk)
            self.chunk_index = 0
            is_new_chunk = True
            logger.info(f"Received new action chunk with {len(chunk)} actions")

        # Pop next action from queue
        action = self.action_queue.popleft()
        self.chunk_index += 1

        return {
            "action": action,
            "inference_time_ms": self.last_inference_time_ms,
            "chunk_index": self.chunk_index,
            "is_new_chunk": is_new_chunk,
            "queue_size": len(self.action_queue)
        }

    async def reset(self):
        """Reset action queue"""
        self.action_queue.clear()
        self.chunk_index = 0
        logger.info("Action queue reset")


async def control_loop(client: WebSocketACTClient, robot, args):
    """Main control loop.

    Args:
        client: WebSocket ACT client
        robot: Robot instance
        args: Command line arguments
    """
    global running

    step_interval = 1.0 / args.fps
    logger.info(f"Starting control loop at {args.fps} Hz")
    logger.info("Press Ctrl+C to exit")

    step_count = 0
    next_step_time = time.time()

    while running:
        # Control frequency
        now = time.time()
        if now < next_step_time:
            await asyncio.sleep(next_step_time - now)
        next_step_time = max(next_step_time + step_interval, time.time())

        try:
            # 1. Read observation from robot
            obs = robot.get_observation()

            # 2. Extract state
            state = np.array(
                [obs.get(f"{name}.pos", 0.0) for name in robot.joint_names],
                dtype=np.float32
            )

            # 3. Extract images
            env_cam = obs.get("env_cam")
            left_wrist_cam = obs.get("left_wrist_cam")
            right_wrist_cam = obs.get("right_wrist_cam")

            # 4. Inference
            result = await client.infer(
                state=state,
                env_cam=env_cam,
                left_wrist_cam=left_wrist_cam,
                right_wrist_cam=right_wrist_cam,
                reset=(step_count == 0)
            )

            action = np.array(result["action"], dtype=np.float32)

            # 5. Action smoothing
            alpha = args.action_speed
            max_delta = args.max_action_change

            # Smooth: interpolate between current state and predicted action
            smoothed = state + alpha * (action - state)

            # Limit: clip maximum change per step
            delta = np.clip(smoothed - state, -max_delta, max_delta)
            final_action = state + delta

            # 6. Build action dictionary
            action_dict = {
                f"{name}.pos": float(final_action[i])
                for i, name in enumerate(robot.joint_names)
            }

            # 7. Send action to robot
            robot.send_action(action_dict)

            step_count += 1

            # 8. Logging
            if step_count % 10 == 0:
                logger.info(
                    f"Step {step_count}: "
                    f"inference={result['inference_time_ms']:.1f}ms, "
                    f"chunk_idx={result['chunk_index']}, "
                    f"new_chunk={result['is_new_chunk']}, "
                    f"queue_size={result['queue_size']}"
                )

        except websockets.exceptions.ConnectionClosed:
            logger.error("Connection to server lost, attempting to reconnect...")
            if await client.connect():
                logger.info("Reconnected successfully")
            else:
                logger.error("Failed to reconnect, exiting...")
                break

        except Exception as e:
            logger.error(f"Control loop error: {e}", exc_info=True)
            await asyncio.sleep(0.1)


async def async_main(args):
    """Async main function"""
    global running, robot

    try:
        # 1. Create WebSocket client
        logger.info(f"Connecting to ACT server: {args.server}")
        client = WebSocketACTClient(args.server, timeout=args.timeout)

        if not await client.connect():
            logger.error("Failed to connect to server")
            return 1

        # 2. Create robot
        logger.info(f"Initializing robot: {args.robot_id}")
        from lerobot_robot_bw import BWConfig, BWRobot

        config = BWConfig(id=args.robot_id)
        robot = BWRobot(config)
        robot.connect()
        logger.info("Robot connected")

        # 3. Run control loop
        await control_loop(client, robot, args)

        # 4. Cleanup
        await client.disconnect()

        return 0

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return 1


def main():
    """Main entry point"""
    global running, robot

    parser = argparse.ArgumentParser(description='ROS2 WebSocket ACT Inference Client')

    # Server configuration
    parser.add_argument(
        '--server',
        type=str,
        default='ws://localhost:8000',
        help='WebSocket server URL (default: ws://localhost:8000)'
    )
    parser.add_argument(
        '--timeout',
        type=float,
        default=5.0,
        help='Request timeout in seconds (default: 5.0)'
    )

    # Control configuration
    parser.add_argument(
        '--fps',
        type=float,
        default=10.0,
        help='Control frequency in Hz (default: 10.0)'
    )
    parser.add_argument(
        '--action-speed',
        type=float,
        default=0.5,
        help='Action smoothing factor 0-1 (default: 0.5)'
    )
    parser.add_argument(
        '--max-action-change',
        type=float,
        default=0.3,
        help='Max action change per step in radians (default: 0.3)'
    )

    # Robot configuration
    parser.add_argument(
        '--robot-id',
        type=str,
        default='bw_robot',
        help='Robot ID (default: bw_robot)'
    )

    args = parser.parse_args()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Initialize ROS2
    import rclpy
    if not rclpy.ok():
        rclpy.init()

    try:
        # Run async main
        exit_code = asyncio.run(async_main(args))
        sys.exit(exit_code)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        logger.info("Cleaning up...")
        if robot is not None:
            with contextlib.suppress(BaseException):
                robot.disconnect()

        if rclpy.ok():
            rclpy.shutdown()

        logger.info("Client exited")


if __name__ == "__main__":
    main()
