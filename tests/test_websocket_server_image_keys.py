# Copyright 2026 The HuggingFace Inc. team. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import importlib.util
import io
import sys
from enum import Enum
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest
import torch
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
FOUR_CAMERA_KEYS = (
    "observation.images.env_cam",
    "observation.images.left_wrist_cam",
    "observation.images.right_wrist_cam",
    "observation.images.front_cam",
)
THREE_CAMERA_KEYS = FOUR_CAMERA_KEYS[:3]


class _RTCAttentionSchedule(Enum):
    EXP = "EXP"


class _RTCConfig:
    pass


def _unused_dependency(*args, **kwargs):
    return None


def _server_import_stubs() -> dict[str, ModuleType]:
    stubs = {
        name: ModuleType(name)
        for name in (
            "lerobot",
            "lerobot.configs",
            "lerobot.configs.types",
            "lerobot.policies",
            "lerobot.policies.factory",
            "lerobot.policies.rtc",
            "lerobot.policies.rtc.configuration_rtc",
        )
    }
    for name in ("lerobot", "lerobot.configs", "lerobot.policies", "lerobot.policies.rtc"):
        stubs[name].__path__ = []
    stubs["lerobot.configs.types"].RTCAttentionSchedule = _RTCAttentionSchedule
    stubs["lerobot.policies.factory"].get_policy_class = _unused_dependency
    stubs["lerobot.policies.factory"].make_pre_post_processors = _unused_dependency
    stubs["lerobot.policies.rtc.configuration_rtc"].RTCConfig = _RTCConfig
    return stubs


def _load_server_class(module_name: str, relative_path: str, class_name: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load WebSocket server module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, _server_import_stubs()):
        spec.loader.exec_module(module)
    return getattr(module, class_name)


ACT_SERVER_CLASS = _load_server_class(
    "websocket_act_server_for_test",
    "scripts/websocket-server/act/websocket_act_server.py",
    "ACTWebSocketServer",
)
PI05_SERVER_CLASS = _load_server_class(
    "websocket_pi05_server_for_test",
    "scripts/websocket-server/pi05/websocket_pi05_server.py",
    "PI05WebSocketServer",
)


@pytest.fixture(params=(ACT_SERVER_CLASS, PI05_SERVER_CLASS), ids=("act", "pi05"))
def server(request):
    return request.param(model_path="unused-for-unit-test", device="cpu")


@pytest.fixture
def encoded_image() -> str:
    image = Image.new("RGB", (2, 2), color=(12, 34, 56))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _set_checkpoint_image_features(server, image_keys: tuple[str, ...]) -> None:
    server.policy_config = SimpleNamespace(image_features={key: object() for key in image_keys})


def _request_observation(image_keys: tuple[str, ...], encoded_image: str) -> dict:
    return {
        "observation.state": [0.0] * 16,
        **dict.fromkeys(image_keys, encoded_image),
    }


def test_four_camera_request_uses_checkpoint_image_features(server, encoded_image):
    _set_checkpoint_image_features(server, FOUR_CAMERA_KEYS)

    observation = server.parse_observation(_request_observation(FOUR_CAMERA_KEYS, encoded_image))
    server.validate_image_keys(observation)

    assert server.expected_image_keys() == set(FOUR_CAMERA_KEYS)
    for key in FOUR_CAMERA_KEYS:
        assert isinstance(observation[key], torch.Tensor)
        assert observation[key].shape == (3, 2, 2)


def test_missing_front_camera_reports_checkpoint_image_features(server, encoded_image):
    _set_checkpoint_image_features(server, FOUR_CAMERA_KEYS)
    observation = server.parse_observation(_request_observation(THREE_CAMERA_KEYS, encoded_image))

    with pytest.raises(KeyError) as exc_info:
        server.validate_image_keys(observation)

    message = str(exc_info.value)
    assert "observation.images.front_cam" in message
    assert "loaded checkpoint's image_features" in message
    assert "send every key listed in checkpoint_expected" in message


def test_three_camera_checkpoint_remains_backward_compatible(server, encoded_image):
    _set_checkpoint_image_features(server, THREE_CAMERA_KEYS)

    observation = server.parse_observation(_request_observation(THREE_CAMERA_KEYS, encoded_image))
    server.validate_image_keys(observation)

    assert server.expected_image_keys() == set(THREE_CAMERA_KEYS)
    assert "observation.images.front_cam" not in observation


def test_pi05_preprocessor_keeps_checkpoint_legacy_image_keys():
    server = PI05_SERVER_CLASS(model_path="unused-for-unit-test", device="cpu")
    _set_checkpoint_image_features(server, THREE_CAMERA_KEYS)

    assert server.preprocessor_image_rename_map() == {}


def test_pi05_preprocessor_renames_only_to_checkpoint_canonical_keys():
    server = PI05_SERVER_CLASS(model_path="unused-for-unit-test", device="cpu")
    canonical_keys = (
        "observation.images.base",
        "observation.images.left_wrist",
        "observation.images.right_wrist",
    )
    _set_checkpoint_image_features(server, canonical_keys)

    assert server.preprocessor_image_rename_map() == {
        "observation.images.env_cam": "observation.images.base",
        "observation.images.left_wrist_cam": "observation.images.left_wrist",
        "observation.images.right_wrist_cam": "observation.images.right_wrist",
    }
