#!/usr/bin/env python3
"""
WebSocket server for PI05 model inference.

This server loads a trained PI05 model and serves predictions via WebSocket.
It accepts raw observations (including base64-encoded images) and returns action chunks.

Usage:
    python websocket_pi05_server.py --port 8000 --model_path /path/to/model --task "pick up the red block..."

Example client request:
    {
        "observation": {
            "observation.state": [0.1, 0.2, ...],
            "observation.images.front": "base64_encoded_image_data",
        },
        "task": "pick up the red block...",
    }

Example server response:
    {
        "action_chunk": [[0.1, 0.2, ...], [0.15, 0.25, ...], ...],
        "timestep": 0,
        "inference_time_ms": 33.5,
        "chunk_size": 100
    }
"""

import argparse
import asyncio
import base64
import io
import json
import logging
import time
from typing import Any

import numpy as np
import torch
import websockets
from PIL import Image

from lerobot.policies.factory import get_policy_class, make_pre_post_processors
from lerobot.policies.pretrained import PreTrainedPolicy


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("websocket_pi05_server")


class PI05WebSocketServer:
    """WebSocket server for PI05 model inference."""

    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        port: int = 8000,
        host: str = "0.0.0.0",
        task: str = None,
    ):
        """Initialize the PI05 WebSocket server.

        Args:
            model_path: Path to the pretrained PI05 model directory
            device: Device to run inference on (cpu, cuda, mps)
            port: Port to bind the server to
            host: Host address to bind the server to
            task: Task description for PI05
        """
        self.model_path = model_path
        self.device = device
        self.port = port
        self.host = host
        self.task = task

        # Will be initialized in setup()
        self.policy = None
        self.preprocessor = None
        self.postprocessor = None
        self.policy_config = None

        logger.info(f"Initializing PI05 WebSocket Server")
        logger.info(f"Model path: {model_path}")
        logger.info(f"Device: {device}")
        logger.info(f"Task: {task}")
        logger.info(f"Server will bind to {host}:{port}")

    async def setup(self):
        """Load model and preprocessors."""
        logger.info("Loading PI05 model...")
        start_time = time.perf_counter()

        # Load policy
        policy_class = get_policy_class("pi05")
        self.policy = policy_class.from_pretrained(self.model_path)
        self.policy.to(self.device)
        self.policy.eval()

        # Store config for reference
        self.policy_config = self.policy.config

        # Load preprocessor and postprocessor
        device_override = {"device": self.device}
        self.preprocessor, self.postprocessor = make_pre_post_processors(
            self.policy_config,
            pretrained_path=self.model_path,
            preprocessor_overrides={"device_processor": device_override},
            postprocessor_overrides={"device_processor": device_override},
        )

        load_time = time.perf_counter() - start_time
        logger.info(f"Model loaded successfully in {load_time:.2f}s")
        logger.info(f"Model config: chunk_size={self.policy_config.chunk_size}, "
                   f"n_action_steps={self.policy_config.n_action_steps}")
        logger.info(f"Image features: {self.policy_config.image_features}")
        logger.info(f"State feature: {self.policy_config.robot_state_feature}")
        logger.info(f"Action feature: {self.policy_config.action_feature}")

    def decode_base64_image(self, base64_str: str) -> torch.Tensor:
        """Decode base64 string to image tensor.

        Args:
            base64_str: Base64 encoded image string

        Returns:
            Image tensor of shape (C, H, W)
        """
        # Remove data URL prefix if present
        if "," in base64_str:
            base64_str = base64_str.split(",", 1)[1]

        # Decode base64 to bytes
        image_bytes = base64.b64decode(base64_str)

        # Open image with PIL
        image = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if needed
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Convert to numpy array and normalize to [0, 1]
        image_np = np.array(image).astype(np.float32) / 255.0

        # Convert to tensor (H, W, C) -> (C, H, W)
        image_tensor = torch.from_numpy(image_np).permute(2, 0, 1)

        return image_tensor

    def parse_observation(self, obs_data: dict[str, Any]) -> dict[str, torch.Tensor]:
        """Parse raw observation data into LeRobot format.

        Args:
            obs_data: Dictionary containing observation data

        Returns:
            Dictionary with torch tensors ready for preprocessing
        """
        observation = {}

        # Process state (robot joint positions)
        if "observation.state" in obs_data:
            state = obs_data["observation.state"]
            if isinstance(state, list):
                state = torch.tensor(state, dtype=torch.float32)
            observation["observation.state"] = state

        # Process images
        for key, value in obs_data.items():
            if key.startswith("observation.images."):
                # Decode base64 image
                if isinstance(value, str):
                    image_tensor = self.decode_base64_image(value)
                    observation[key] = image_tensor
                elif isinstance(value, torch.Tensor):
                    observation[key] = value
                else:
                    raise ValueError(f"Unsupported image format for {key}: {type(value)}")

        return observation

    @torch.no_grad()
    def predict_action_chunk(self, observation: dict[str, torch.Tensor]) -> torch.Tensor:
        """Run inference to get action chunk.

        Args:
            observation: Preprocessed observation dictionary

        Returns:
            Action chunk tensor of shape (chunk_size, action_dim)
        """
        # Get action chunk from policy
        action_chunk = self.policy.predict_action_chunk(observation)

        # Ensure correct shape (batch_size, chunk_size, action_dim)
        if action_chunk.ndim != 3:
            action_chunk = action_chunk.unsqueeze(0)

        return action_chunk

    async def handle_client(self, websocket):
        """Handle a client connection.

        Args:
            websocket: WebSocket connection
        """
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"Client connected: {client_id}")

        try:
            async for message in websocket:
                try:
                    # Parse request
                    request = json.loads(message)
                    timestep = request.get("timestep", 0)

                    logger.debug(f"Received request from {client_id}, timestep={timestep}")

                    # Start timing
                    start_time = time.perf_counter()

                    # Parse observation
                    parse_start = time.perf_counter()
                    observation = self.parse_observation(request["observation"])
                    parse_time = time.perf_counter() - parse_start

                    # Add task to observation (PI05 requires task input)
                    if self.task:
                        observation["task"] = self.task

                    # Preprocess (with debug logging)
                    preprocess_start = time.perf_counter()
                    logger.debug(f"Preprocessing observation, keys: {list(observation.keys())}")
                    try:
                        observation = self.preprocessor(observation)
                        preprocess_time = time.perf_counter() - preprocess_start
                    except Exception as preprocess_error:
                        error_response = {
                            "error": "Preprocessing failed",
                            "message": f"{type(preprocess_error).__name__}: {str(preprocess_error)}"
                        }
                        await websocket.send(json.dumps(error_response))
                        logger.error(f"Preprocessing error for {client_id}: {preprocess_error}", exc_info=True)
                        continue

                    # Run inference
                    inference_start = time.perf_counter()
                    action_chunk = self.predict_action_chunk(observation)
                    inference_time = time.perf_counter() - inference_start

                    # Postprocess each action in chunk
                    postprocess_start = time.perf_counter()
                    batch_size, chunk_size, action_dim = action_chunk.shape

                    processed_actions = []
                    for i in range(chunk_size):
                        single_action = action_chunk[:, i, :]
                        processed_action = self.postprocessor(single_action)
                        processed_actions.append(processed_action)

                    # Stack back and remove batch dimension
                    action_chunk = torch.stack(processed_actions, dim=1).squeeze(0)
                    postprocess_time = time.perf_counter() - postprocess_start

                    # Convert to list for JSON serialization
                    action_list = action_chunk.cpu().numpy().tolist()

                    total_time = time.perf_counter() - start_time

                    # Prepare response
                    response = {
                        "action_chunk": action_list,
                        "timestep": timestep,
                        "inference_time_ms": total_time * 1000,
                        "chunk_size": len(action_list),
                        "action_dim": len(action_list[0]) if action_list else 0,
                        "timing": {
                            "parse_ms": parse_time * 1000,
                            "preprocess_ms": preprocess_time * 1000,
                            "inference_ms": inference_time * 1000,
                            "postprocess_ms": postprocess_time * 1000,
                            "total_ms": total_time * 1000,
                        }
                    }

                    # Send response
                    await websocket.send(json.dumps(response))

                    logger.info(f"Processed request from {client_id}, timestep={timestep}, "
                               f"time={total_time*1000:.2f}ms, chunk_size={len(action_list)}")

                except json.JSONDecodeError as e:
                    error_response = {
                        "error": "Invalid JSON",
                        "message": str(e)
                    }
                    await websocket.send(json.dumps(error_response))
                    logger.error(f"JSON decode error from {client_id}: {e}")

                except KeyError as e:
                    error_response = {
                        "error": "Missing required field",
                        "message": f"Missing key: {e}"
                    }
                    await websocket.send(json.dumps(error_response))
                    logger.error(f"Missing field from {client_id}: {e}")

                except Exception as e:
                    error_response = {
                        "error": "Internal server error",
                        "message": str(e)
                    }
                    await websocket.send(json.dumps(error_response))
                    logger.error(f"Error processing request from {client_id}: {e}", exc_info=True)

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        except Exception as e:
            logger.error(f"Unexpected error with client {client_id}: {e}", exc_info=True)

    async def start(self):
        """Start the WebSocket server."""
        await self.setup()

        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")

        # Set max_size to 10MB to handle large images
        async with websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            max_size=10 * 1024 * 1024,  # 10MB
        ):
            logger.info("Server is running and accepting connections")
            await asyncio.Future()  # Run forever


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="PI05 Model WebSocket Server")
    parser.add_argument(
        "--port",
        type=int,
        default=8005,
        help="Port to bind the server to (default: 8000)"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind the server to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--model_path",
        type=str,
        default="/home/lcjs-szw/repos/lerobot/outputs/train/pi05_mantis_final_20260212_182416/checkpoints/last/pretrained_model",
        help="Path to the pretrained PI05 model directory"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cuda",
        choices=["cpu", "cuda", "mps"],
        help="Device to run inference on (default: cpu)"
    )
    parser.add_argument(
        "--task",
        type=str,
        default="pick up the red block on each side of the white plate and place them into the white plate using both grippers alternately",
        help="Task description for PI05 model"
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

    # Create and start server
    server = PI05WebSocketServer(
        model_path=args.model_path,
        device=args.device,
        port=args.port,
        host=args.host,
        task=args.task,
    )

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
