import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import torch

SERVER_DIR = Path(__file__).parents[1] / "scripts/websocket-server/pi05"
SERVER_PATH = SERVER_DIR / "websocket_pi05_server_optimized.py"
sys.path.insert(0, str(SERVER_DIR))
SPEC = importlib.util.spec_from_file_location("websocket_pi05_server_optimized_for_test", SERVER_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
OptimizedPI05WebSocketServer = MODULE.OptimizedPI05WebSocketServer


class ChunkPostprocessor:
    def __init__(self):
        self.steps = []
        self.calls = 0

    def __call__(self, action):
        self.calls += 1
        return action * 2 + 1


def make_server(**kwargs):
    return OptimizedPI05WebSocketServer(
        model_path="unused",
        device="cpu",
        disable_joint_order_bridge=True,
        **kwargs,
    )


def test_postprocesses_entire_action_chunk_in_one_call():
    server = make_server()
    server.postprocessor = ChunkPostprocessor()
    raw = torch.arange(1 * 30 * 16, dtype=torch.float32).reshape(1, 30, 16)

    result = server._postprocess_action_chunk(raw, current_state=None)

    assert result.shape == (30, 16)
    torch.testing.assert_close(result, raw.squeeze(0) * 2 + 1)
    assert server.postprocessor.calls == 1


def test_sdpa_override_runs_at_forward_call_boundary():
    server = make_server(attention_implementation="sdpa")
    seen = []

    class DualModel:
        def __init__(self):
            self.paligemma = SimpleNamespace(
                language_model=SimpleNamespace(config=SimpleNamespace(_attn_implementation="eager"))
            )
            self.gemma_expert = SimpleNamespace(
                model=SimpleNamespace(config=SimpleNamespace(_attn_implementation="eager"))
            )

        def forward(self, value):
            seen.append(
                (
                    self.paligemma.language_model.config._attn_implementation,
                    self.gemma_expert.model.config._attn_implementation,
                )
            )
            return value

    dual_model = DualModel()
    server.policy = SimpleNamespace(
        model=SimpleNamespace(paligemma_with_expert=dual_model)
    )

    server._configure_attention_implementation()
    assert dual_model.forward("result") == "result"
    assert seen == [("sdpa", "sdpa")]


def test_rejects_compile_and_sdpa_combination():
    try:
        make_server(compile_model=True, attention_implementation="sdpa")
    except ValueError as error:
        assert "separately" in str(error)
    else:
        raise AssertionError("Expected incompatible experimental options to be rejected")


def test_rejects_non_positive_inference_steps():
    try:
        make_server(num_inference_steps=0)
    except ValueError as error:
        assert "greater than zero" in str(error)
    else:
        raise AssertionError("Expected invalid denoising-step count to be rejected")
