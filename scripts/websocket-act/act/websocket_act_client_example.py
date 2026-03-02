#!/usr/bin/env python3
"""
Example WebSocket client for testing the ACT model server.

This client demonstrates how to:
1. Connect to the WebSocket server
2. Send observations (with images)
3. Receive action chunks
4. Handle responses

Usage:
    python websocket_act_client_example.py --server_url ws://localhost:8000
"""

import argparse
import asyncio
import base64
import io
import json
import logging
import time

import numpy as np
import websockets
from PIL import Image

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("websocket_act_client")


class ACTWebSocketClient:
    """Example WebSocket client for ACT model server."""

    def __init__(self, server_url: str = "ws://localhost:8000"):
        """Initialize the client.

        Args:
            server_url: WebSocket server URL
        """
        self.server_url = server_url
        self.websocket = None

    async def connect(self):
        """Connect to the WebSocket server."""
        logger.info(f"Connecting to {self.server_url}...")
        # Set max_size to 10MB to handle large responses
        self.websocket = await websockets.connect(
            self.server_url,
            max_size=10 * 1024 * 1024  # 10MB
        )
        logger.info("Connected successfully")

    async def disconnect(self):
        """Disconnect from the server."""
        if self.websocket:
            await self.websocket.close()
            logger.info("Disconnected")

    def encode_image_to_base64(self, image: np.ndarray | Image.Image) -> str:
        """Encode an image to base64 string.

        Args:
            image: Image as numpy array (H, W, C) or PIL Image

        Returns:
            Base64 encoded string
        """
        # Convert numpy array to PIL Image if needed
        if isinstance(image, np.ndarray):
            # Ensure uint8
            if image.dtype != np.uint8:
                image = (image * 255).astype(np.uint8)
            image = Image.fromarray(image)

        # Save to bytes buffer
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)

        # Encode to base64
        base64_str = base64.b64encode(buffer.read()).decode("utf-8")

        return base64_str

    def create_dummy_observation(
        self,
        state_dim: int = 16,
        camera_configs: dict = None,
    ) -> dict:
        """Create a dummy observation for testing.

        Args:
            state_dim: Dimension of robot state
            camera_configs: Dictionary mapping camera names to (height, width) tuples
                          Default creates images matching typical ACT model expectations

        Returns:
            Observation dictionary
        """
        observation = {}

        # Create dummy state
        observation["observation.state"] = np.random.randn(state_dim).tolist()

        # Default camera configurations for ACT models
        if camera_configs is None:
            camera_configs = {
                "env_cam": (240, 320),
                "left_wrist_cam": (240, 424),
                "right_wrist_cam": (240, 424),
            }

        # Create dummy images for each camera
        for cam_name, (height, width) in camera_configs.items():
            # Create random image
            image = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
            # Encode to base64
            observation[f"observation.images.{cam_name}"] = self.encode_image_to_base64(image)

        return observation

    def load_image_from_file(self, image_path: str) -> str:
        """Load an image from file and encode to base64.

        Args:
            image_path: Path to image file

        Returns:
            Base64 encoded string
        """
        image = Image.open(image_path)
        return self.encode_image_to_base64(image)

    async def send_observation(
        self,
        observation: dict,
        timestep: int = 0,
    ) -> dict:
        """Send an observation and receive action chunk.

        Args:
            observation: Observation dictionary
            timestep: Current timestep

        Returns:
            Response dictionary with action chunk
        """
        if not self.websocket:
            raise RuntimeError("Not connected. Call connect() first.")

        # Prepare request
        request = {
            "observation": observation,
            "timestep": timestep,
        }

        # Send request
        logger.debug(f"Sending observation for timestep {timestep}")
        send_time = time.perf_counter()
        await self.websocket.send(json.dumps(request))

        # Receive response
        response_str = await self.websocket.recv()
        receive_time = time.perf_counter()

        response = json.loads(response_str)

        # Check for errors
        if "error" in response:
            logger.error(f"Server error: {response['error']} - {response.get('message', '')}")
            return response

        # Log timing
        round_trip_time = (receive_time - send_time) * 1000
        server_time = response.get("inference_time_ms", 0)
        network_time = round_trip_time - server_time

        logger.info(
            f"Received action chunk for timestep {timestep}: "
            f"chunk_size={response.get('chunk_size', 0)}, "
            f"action_dim={response.get('action_dim', 0)}, "
            f"server_time={server_time:.2f}ms, "
            f"network_time={network_time:.2f}ms, "
            f"total_time={round_trip_time:.2f}ms"
        )

        return response

    async def run_test_sequence(
        self,
        num_steps: int = 10,
        state_dim: int = 16,
        camera_configs: dict = None,
    ):
        """Run a test sequence of observations.

        Args:
            num_steps: Number of steps to run
            state_dim: Dimension of robot state
            camera_configs: Dictionary mapping camera names to (height, width) tuples
        """
        logger.info(f"Running test sequence with {num_steps} steps")

        await self.connect()

        try:
            for step in range(num_steps):
                # Create observation
                observation = self.create_dummy_observation(
                    state_dim=state_dim,
                    camera_configs=camera_configs,
                )

                # Send and receive
                response = await self.send_observation(observation, timestep=step)

                # Check response
                if "error" in response:
                    logger.error(f"Step {step} failed: {response['error']}")
                    break

                # Print first action in chunk
                if "action_chunk" in response and response["action_chunk"]:
                    first_action = response["action_chunk"][0]
                    logger.debug(f"First action: {first_action[:5]}...")  # Print first 5 dims

                # Small delay between requests
                await asyncio.sleep(0.1)

        finally:
            await self.disconnect()

        logger.info("Test sequence completed")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="ACT Model WebSocket Client Example")
    parser.add_argument(
        "--server_url",
        type=str,
        default="ws://localhost:8000",
        help="WebSocket server URL (default: ws://localhost:8000)"
    )
    parser.add_argument(
        "--num_steps",
        type=int,
        default=10,
        help="Number of test steps to run (default: 10)"
    )
    parser.add_argument(
        "--state_dim",
        type=int,
        default=16,
        help="Dimension of robot state (default: 16)"
    )
    parser.add_argument(
        "--cameras",
        type=str,
        default="env_cam:240x320,left_wrist_cam:240x424,right_wrist_cam:240x424",
        help="Camera configurations as name:HxW,name:HxW,... (default: ACT model cameras)"
    )
    parser.add_argument(
        "--log_level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Parse camera configurations
    camera_configs = {}
    for cam_spec in args.cameras.split(","):
        name, size = cam_spec.split(":")
        height, width = map(int, size.split("x"))
        camera_configs[name] = (height, width)

    # Create client
    client = ACTWebSocketClient(server_url=args.server_url)

    # Run test sequence
    try:
        await client.run_test_sequence(
            num_steps=args.num_steps,
            state_dim=args.state_dim,
            camera_configs=camera_configs,
        )
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Test error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
