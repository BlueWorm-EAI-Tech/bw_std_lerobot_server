#!/usr/bin/env python3
"""
Quick test script to verify the WebSocket server is working.

This script performs a simple health check by:
1. Connecting to the server
2. Sending a single test observation
3. Verifying the response
4. Reporting success or failure

Usage:
    python test_websocket_server.py
    python test_websocket_server.py --server_url ws://localhost:8000
"""

import argparse
import asyncio
import logging
import sys

from websocket_act_client_example import ACTWebSocketClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("test_server")


async def test_server(server_url: str, state_dim: int = 16):
    """Test the WebSocket server with a single request.

    Args:
        server_url: WebSocket server URL
        state_dim: Dimension of robot state

    Returns:
        True if test passed, False otherwise
    """
    logger.info("=" * 60)
    logger.info("WebSocket ACT Server Test")
    logger.info("=" * 60)
    logger.info(f"Server URL: {server_url}")
    logger.info(f"State dimension: {state_dim}")
    logger.info("")

    try:
        # Create client
        client = ACTWebSocketClient(server_url=server_url)

        # Test 1: Connection
        logger.info("Test 1: Connecting to server...")
        try:
            await client.connect()
            logger.info("✓ Connection successful")
        except Exception as e:
            logger.error(f"✗ Connection failed: {e}")
            return False

        # Test 2: Send observation and receive response
        logger.info("\nTest 2: Sending observation...")
        try:
            # Create observation with correct camera configurations for ACT model
            camera_configs = {
                "env_cam": (240, 320),
                "left_wrist_cam": (240, 424),
                "right_wrist_cam": (240, 424),
            }
            observation = client.create_dummy_observation(
                state_dim=state_dim,
                camera_configs=camera_configs,
            )

            response = await client.send_observation(observation, timestep=0)

            # Check for errors
            if "error" in response:
                logger.error(f"✗ Server returned error: {response['error']}")
                logger.error(f"  Message: {response.get('message', 'No message')}")
                return False

            logger.info("✓ Observation sent and response received")

        except Exception as e:
            logger.error(f"✗ Failed to send observation: {e}")
            await client.disconnect()
            return False

        # Test 3: Validate response format
        logger.info("\nTest 3: Validating response format...")
        try:
            required_fields = ["action_chunk", "timestep", "inference_time_ms", "chunk_size", "action_dim"]
            missing_fields = [field for field in required_fields if field not in response]

            if missing_fields:
                logger.error(f"✗ Missing required fields: {missing_fields}")
                return False

            logger.info("✓ Response format valid")

        except Exception as e:
            logger.error(f"✗ Response validation failed: {e}")
            await client.disconnect()
            return False

        # Test 4: Validate action chunk
        logger.info("\nTest 4: Validating action chunk...")
        try:
            action_chunk = response["action_chunk"]
            chunk_size = response["chunk_size"]
            action_dim = response["action_dim"]

            if not isinstance(action_chunk, list):
                logger.error(f"✗ Action chunk is not a list: {type(action_chunk)}")
                return False

            if len(action_chunk) != chunk_size:
                logger.error(f"✗ Chunk size mismatch: expected {chunk_size}, got {len(action_chunk)}")
                return False

            if len(action_chunk) > 0 and len(action_chunk[0]) != action_dim:
                logger.error(f"✗ Action dimension mismatch: expected {action_dim}, got {len(action_chunk[0])}")
                return False

            logger.info(f"✓ Action chunk valid: {chunk_size} actions of dimension {action_dim}")

        except Exception as e:
            logger.error(f"✗ Action chunk validation failed: {e}")
            await client.disconnect()
            return False

        # Test 5: Check timing information
        logger.info("\nTest 5: Checking timing information...")
        try:
            inference_time = response["inference_time_ms"]
            timing = response.get("timing", {})

            logger.info(f"✓ Total inference time: {inference_time:.2f}ms")

            if timing:
                logger.info(f"  - Parse: {timing.get('parse_ms', 0):.2f}ms")
                logger.info(f"  - Preprocess: {timing.get('preprocess_ms', 0):.2f}ms")
                logger.info(f"  - Inference: {timing.get('inference_ms', 0):.2f}ms")
                logger.info(f"  - Postprocess: {timing.get('postprocess_ms', 0):.2f}ms")

        except Exception as e:
            logger.error(f"✗ Timing check failed: {e}")
            await client.disconnect()
            return False

        # Disconnect
        await client.disconnect()

        # All tests passed
        logger.info("\n" + "=" * 60)
        logger.info("✓ All tests passed!")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.error(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Test WebSocket ACT Server")
    parser.add_argument(
        "--server_url",
        type=str,
        default="ws://localhost:8000",
        help="WebSocket server URL (default: ws://localhost:8000)"
    )
    parser.add_argument(
        "--state_dim",
        type=int,
        default=16,
        help="Dimension of robot state (default: 16)"
    )

    args = parser.parse_args()

    # Run test
    success = await test_server(
        server_url=args.server_url,
        state_dim=args.state_dim,
    )

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
