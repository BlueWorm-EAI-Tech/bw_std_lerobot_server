#!/usr/bin/env python3
"""Latency-focused PI05 WebSocket server.

This is a separate entry point that preserves the behavior of
``websocket_pi05_server.py`` while reducing avoidable server-side overhead and
reporting CUDA-synchronized timings. The original server is intentionally not
modified.
"""

import argparse
import asyncio
import json
import logging
import time
from typing import Any

import torch
import websockets
from websocket_pi05_server import PI05WebSocketServer

logger = logging.getLogger("websocket_pi05_server_optimized")


class OptimizedPI05WebSocketServer(PI05WebSocketServer):
    """PI05 server with a lower-overhead inference path and accurate timings."""

    def __init__(
        self,
        *args: Any,
        num_inference_steps: int | None = None,
        compile_model: bool = False,
        compile_mode: str = "reduce-overhead",
        attention_implementation: str = "eager",
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        if num_inference_steps is not None and num_inference_steps <= 0:
            raise ValueError("num_inference_steps must be greater than zero")
        if compile_model and attention_implementation != "eager":
            raise ValueError(
                "Test --compile_model and --attention_implementation=sdpa separately before combining them"
            )

        self.num_inference_steps_override = num_inference_steps
        self.compile_model_override = compile_model
        self.compile_mode_override = compile_mode
        self.attention_implementation = attention_implementation

    async def setup(self) -> None:
        """Load the unchanged checkpoint, then apply runtime-only optimizations."""
        await super().setup()

        if self.num_inference_steps_override is not None:
            old_steps = int(self.policy.config.num_inference_steps)
            self.policy.config.num_inference_steps = self.num_inference_steps_override
            logger.info(
                "Runtime num_inference_steps override: %d -> %d",
                old_steps,
                self.num_inference_steps_override,
            )

        model = self.policy.model
        if hasattr(model, "gradient_checkpointing_disable"):
            model.gradient_checkpointing_disable()

        self._configure_attention_implementation()

        if self.compile_model_override:
            if bool(getattr(self.policy.config, "compile_model", False)):
                logger.info("Checkpoint already enables torch.compile; skipping a second compilation")
            else:
                torch.set_float32_matmul_precision("high")
                model.sample_actions = torch.compile(
                    model.sample_actions,
                    mode=self.compile_mode_override,
                )
                logger.warning(
                    "torch.compile enabled for sample_actions with mode=%s; the first request can take "
                    "several minutes and needs a long client timeout",
                    self.compile_mode_override,
                )

        logger.info(
            "Optimized inference path ready: num_inference_steps=%d attention=%s compile=%s",
            int(self.policy.config.num_inference_steps),
            self.attention_implementation,
            self.compile_model_override or bool(getattr(self.policy.config, "compile_model", False)),
        )

    def _configure_attention_implementation(self) -> None:
        """Optionally override PI05's hard-coded eager attention at call time."""
        if self.attention_implementation == "eager":
            return
        if self.attention_implementation != "sdpa":
            raise ValueError(f"Unsupported attention implementation: {self.attention_implementation}")

        dual_model = self.policy.model.paligemma_with_expert
        original_forward = dual_model.forward

        def forward_with_sdpa(*args: Any, **kwargs: Any):
            # sample_actions and denoise_step set these back to eager immediately
            # before forward(), so the override must happen at the call boundary.
            dual_model.paligemma.language_model.config._attn_implementation = "sdpa"  # noqa: SLF001
            dual_model.gemma_expert.model.config._attn_implementation = "sdpa"  # noqa: SLF001
            return original_forward(*args, **kwargs)

        dual_model.forward = forward_with_sdpa
        logger.warning(
            "Experimental SDPA attention enabled. Compare actions and rollout behavior against eager "
            "before using it on the robot"
        )

    def _synchronize_device(self) -> None:
        """Wait for queued CUDA work so timing fields reflect actual GPU latency."""
        if str(self.device).startswith("cuda") and torch.cuda.is_available():
            torch.cuda.synchronize(torch.device(self.device))

    @torch.inference_mode()
    def predict_action_chunk(
        self,
        observation: dict[str, torch.Tensor],
        *,
        inference_delay: int | None = None,
        prev_chunk_left_over: torch.Tensor | None = None,
    ) -> torch.Tensor:
        policy_kwargs = {}
        if self.enable_rtc and inference_delay is not None:
            policy_kwargs["inference_delay"] = int(inference_delay)
            if prev_chunk_left_over is not None:
                policy_kwargs["prev_chunk_left_over"] = prev_chunk_left_over

        action_chunk = self.policy.predict_action_chunk(observation, **policy_kwargs)
        if action_chunk.ndim != 3:
            action_chunk = action_chunk.unsqueeze(0)
        return action_chunk

    def _postprocess_action_chunk(
        self,
        raw_action_chunk: torch.Tensor,
        current_state: torch.Tensor | None,
    ) -> torch.Tensor:
        """Postprocess a complete [1, chunk, action] tensor in one pipeline call."""
        if raw_action_chunk.ndim != 3 or raw_action_chunk.shape[0] != 1:
            raise ValueError(
                "PI05 WebSocket inference expects one observation per request; "
                f"received action shape {tuple(raw_action_chunk.shape)}"
            )

        self._set_postprocessor_reference_state(current_state)
        action_chunk = self.postprocessor(raw_action_chunk)
        if action_chunk.ndim == 3:
            if action_chunk.shape[0] != 1:
                raise ValueError(f"Unexpected postprocessor output shape {tuple(action_chunk.shape)}")
            action_chunk = action_chunk.squeeze(0)
        if action_chunk.ndim != 2:
            raise ValueError(f"Unexpected postprocessor output shape {tuple(action_chunk.shape)}")
        return self._reorder_policy_action_to_runtime(action_chunk)

    async def handle_client(self, websocket) -> None:
        """Serve requests with synchronized stage timings and vectorized postprocessing."""
        remote = websocket.remote_address or ("unknown", 0)
        client_id = f"{remote[0]}:{remote[1]}"
        logger.info("Client connected: %s", client_id)
        last_raw_action_chunk: torch.Tensor | None = None

        try:
            async for message in websocket:
                request_start = time.perf_counter()
                try:
                    json_start = time.perf_counter()
                    request = json.loads(message)
                    json_decode_time = time.perf_counter() - json_start
                    timestep = request.get("timestep", 0)
                    if request.get("reset", False):
                        last_raw_action_chunk = None

                    parse_start = time.perf_counter()
                    observation = self.parse_observation(request["observation"])
                    self.validate_image_keys(observation)
                    parse_time = time.perf_counter() - parse_start
                    current_state = observation.get("observation.state")

                    if self.task:
                        observation["task"] = self.task

                    try:
                        self._synchronize_device()
                        preprocess_start = time.perf_counter()
                        observation = self.preprocessor(observation)
                        self.validate_image_keys(observation)
                        self._synchronize_device()
                        preprocess_time = time.perf_counter() - preprocess_start
                    except Exception as preprocess_error:
                        error_response = {
                            "error": "Preprocessing failed",
                            "message": f"{type(preprocess_error).__name__}: {preprocess_error}",
                        }
                        await websocket.send(json.dumps(error_response))
                        logger.error(
                            "Preprocessing error for %s: %s",
                            client_id,
                            preprocess_error,
                            exc_info=True,
                        )
                        continue

                    rtc_request = request.get("rtc") if isinstance(request.get("rtc"), dict) else {}
                    request_rtc = bool(rtc_request.get("enabled", False))
                    use_rtc = bool(self.enable_rtc and request_rtc)
                    inference_delay = max(int(rtc_request.get("inference_delay", 0)), 0)
                    action_index_before_inference = max(
                        int(rtc_request.get("action_index_before_inference", 0)), 0
                    )
                    prev_chunk_left_over = None
                    prev_chunk_left_over_len = 0
                    if use_rtc and last_raw_action_chunk is not None:
                        chunk_size = int(last_raw_action_chunk.shape[1])
                        start_index = min(action_index_before_inference, chunk_size)
                        if start_index < chunk_size:
                            prev_chunk_left_over = last_raw_action_chunk[:, start_index:, :].detach()
                            prev_chunk_left_over_len = int(prev_chunk_left_over.shape[1])

                    self._synchronize_device()
                    inference_start = time.perf_counter()
                    raw_action_chunk = self.predict_action_chunk(
                        observation,
                        inference_delay=inference_delay if use_rtc else None,
                        prev_chunk_left_over=prev_chunk_left_over if use_rtc else None,
                    )
                    self._synchronize_device()
                    inference_time = time.perf_counter() - inference_start

                    # Only RTC needs the previous raw chunk. Avoid a GPU clone in the default path.
                    last_raw_action_chunk = raw_action_chunk.detach().clone() if self.enable_rtc else None

                    self._synchronize_device()
                    postprocess_start = time.perf_counter()
                    action_chunk = self._postprocess_action_chunk(raw_action_chunk, current_state)
                    self._synchronize_device()
                    postprocess_time = time.perf_counter() - postprocess_start

                    device_to_cpu_start = time.perf_counter()
                    action_cpu = action_chunk.detach().to(device="cpu")
                    self._synchronize_device()
                    action_list = action_cpu.numpy().tolist()
                    device_to_cpu_time = time.perf_counter() - device_to_cpu_start

                    total_time = time.perf_counter() - request_start
                    response = {
                        "action_chunk": action_list,
                        "timestep": timestep,
                        "inference_time_ms": total_time * 1000,
                        "chunk_size": len(action_list),
                        "action_dim": len(action_list[0]) if action_list else 0,
                        "rtc": {
                            "server_enabled": bool(self.enable_rtc),
                            "request_enabled": request_rtc,
                            "applied": use_rtc,
                            "inference_delay": inference_delay,
                            "action_index_before_inference": action_index_before_inference,
                            "prev_chunk_left_over_len": prev_chunk_left_over_len,
                        },
                        "timing": {
                            "json_decode_ms": json_decode_time * 1000,
                            "parse_observation_ms": parse_time * 1000,
                            "preprocess_ms": preprocess_time * 1000,
                            "inference_ms": inference_time * 1000,
                            "postprocess_ms": postprocess_time * 1000,
                            "device_to_cpu_ms": device_to_cpu_time * 1000,
                            "total_ms": total_time * 1000,
                            "cuda_synchronized": str(self.device).startswith("cuda"),
                        },
                    }
                    await websocket.send(json.dumps(response))

                    logger.info(
                        "Processed request from %s timestep=%s total=%.2fms infer=%.2fms "
                        "pre=%.2fms post=%.2fms d2h=%.2fms chunk=%d rtc=%s",
                        client_id,
                        timestep,
                        total_time * 1000,
                        inference_time * 1000,
                        preprocess_time * 1000,
                        postprocess_time * 1000,
                        device_to_cpu_time * 1000,
                        len(action_list),
                        use_rtc,
                    )

                except json.JSONDecodeError as error:
                    await websocket.send(json.dumps({"error": "Invalid JSON", "message": str(error)}))
                    logger.error("JSON decode error from %s: %s", client_id, error)
                except KeyError as error:
                    await websocket.send(
                        json.dumps({"error": "Missing required field", "message": f"Missing key: {error}"})
                    )
                    logger.error("Missing field from %s: %s", client_id, error)
                except Exception as error:
                    await websocket.send(
                        json.dumps({"error": "Internal server error", "message": str(error)})
                    )
                    logger.error("Error processing request from %s: %s", client_id, error, exc_info=True)

        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected: %s", client_id)
        except Exception as error:
            logger.error("Unexpected error with client %s: %s", client_id, error, exc_info=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Latency-focused PI05 WebSocket server")
    parser.add_argument("--port", type=int, default=8005)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--model_path", type=str, required=True)
    parser.add_argument("--device", type=str, default="cuda", choices=["cpu", "cuda", "mps"])
    parser.add_argument("--task", type=str, default="fold the t-shirt")
    parser.add_argument(
        "--log_level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    parser.add_argument("--disable_joint_order_bridge", action="store_true")
    parser.add_argument("--enable_rtc", action="store_true")
    parser.add_argument("--rtc_execution_horizon", type=int, default=10)
    parser.add_argument("--rtc_max_guidance_weight", type=float, default=10.0)
    parser.add_argument(
        "--rtc_prefix_attention_schedule",
        type=str,
        default="EXP",
        choices=["ZEROS", "ONES", "LINEAR", "EXP"],
    )
    parser.add_argument("--rtc_debug", action="store_true")
    parser.add_argument(
        "--num_inference_steps",
        type=int,
        default=None,
        help="Runtime-only denoising-step override; omitted means use the checkpoint value",
    )
    parser.add_argument(
        "--compile_model",
        action="store_true",
        help="Compile sample_actions at runtime; first request is very slow",
    )
    parser.add_argument(
        "--compile_mode",
        type=str,
        default="reduce-overhead",
        choices=["default", "reduce-overhead", "max-autotune"],
    )
    parser.add_argument(
        "--attention_implementation",
        type=str,
        default="eager",
        choices=["eager", "sdpa"],
        help="Keep eager for robot use until experimental SDPA has passed output and rollout checks",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    server = OptimizedPI05WebSocketServer(
        model_path=args.model_path,
        device=args.device,
        port=args.port,
        host=args.host,
        task=args.task,
        disable_joint_order_bridge=args.disable_joint_order_bridge,
        enable_rtc=args.enable_rtc,
        rtc_execution_horizon=args.rtc_execution_horizon,
        rtc_max_guidance_weight=args.rtc_max_guidance_weight,
        rtc_prefix_attention_schedule=args.rtc_prefix_attention_schedule,
        rtc_debug=args.rtc_debug,
        num_inference_steps=args.num_inference_steps,
        compile_model=args.compile_model,
        compile_mode=args.compile_mode,
        attention_implementation=args.attention_implementation,
    )

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as error:
        logger.error("Server error: %s", error, exc_info=True)


if __name__ == "__main__":
    main()
