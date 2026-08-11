import numpy as np
import pytest
import torch

from lerobot.datasets.compute_stats import compute_relative_action_stats
from lerobot.processor import (
    AbsoluteActionsProcessorStep,
    DeltaActionsProcessorStep,
    RelativeActionsProcessorStep,
    TransitionKey,
)
from lerobot.utils.constants import ACTION, OBS_STATE


def test_mantis_joint_relative_gripper_absolute_roundtrip() -> None:
    state = torch.arange(16, dtype=torch.float32).unsqueeze(0)
    action = state.unsqueeze(1).repeat(1, 3, 1) + 0.5
    action[..., 7] = 0.25
    action[..., 15] = 0.75

    relative_step = RelativeActionsProcessorStep(
        enabled=True,
        exclude_joints=["gripper"],
    )
    relative_transition = relative_step(
        {
            TransitionKey.OBSERVATION: {OBS_STATE: state},
            TransitionKey.ACTION: action,
        }
    )
    relative_action = relative_transition[TransitionKey.ACTION]

    joint_dims = [index for index in range(16) if index not in {7, 15}]
    torch.testing.assert_close(relative_action[..., joint_dims], torch.full((1, 3, 14), 0.5))
    torch.testing.assert_close(relative_action[..., 7], action[..., 7])
    torch.testing.assert_close(relative_action[..., 15], action[..., 15])

    absolute_step = AbsoluteActionsProcessorStep(enabled=True, relative_step=relative_step)
    recovered = absolute_step({TransitionKey.ACTION: relative_action})[TransitionKey.ACTION]
    torch.testing.assert_close(recovered, action)


def test_legacy_processor_names_and_manual_reference_state_remain_supported() -> None:
    names = ["left_joint", "left_gripper"]
    state = torch.tensor([[1.0, 0.9]])
    action = torch.tensor([[1.2, 0.1]])

    relative_step = DeltaActionsProcessorStep(
        enabled=True,
        exclude_joints=["gripper"],
        action_feature_names=names,
    )
    relative = relative_step(
        {
            TransitionKey.OBSERVATION: {OBS_STATE: state},
            TransitionKey.ACTION: action,
        }
    )[TransitionKey.ACTION]
    torch.testing.assert_close(relative, torch.tensor([[0.2, 0.1]]))

    absolute_step = AbsoluteActionsProcessorStep(
        enabled=True,
        exclude_joints=["gripper"],
        action_feature_names=names,
    )
    absolute_step.set_reference_state(state)
    recovered = absolute_step({TransitionKey.ACTION: relative})[TransitionKey.ACTION]
    torch.testing.assert_close(recovered, action)


def test_disabled_relative_actions_preserve_absolute_behavior() -> None:
    state = torch.tensor([[1.0, 2.0]])
    action = torch.tensor([[3.0, 4.0]])
    transition = {
        TransitionKey.OBSERVATION: {OBS_STATE: state},
        TransitionKey.ACTION: action,
    }

    result = RelativeActionsProcessorStep(enabled=False)(transition)
    torch.testing.assert_close(result[TransitionKey.ACTION], action)
    post_result = AbsoluteActionsProcessorStep(enabled=False)({TransitionKey.ACTION: action})
    torch.testing.assert_close(post_result[TransitionKey.ACTION], action)


def test_relative_stats_keep_gripper_absolute_and_respect_episode_boundaries() -> None:
    hf_dataset = {
        ACTION: [
            [10.0, 0.1],
            [11.0, 0.2],
            [20.0, 0.3],
            [21.0, 0.4],
        ],
        OBS_STATE: [
            [10.0, 0.9],
            [11.0, 0.8],
            [20.0, 0.7],
            [21.0, 0.6],
        ],
        "episode_index": [0, 0, 1, 1],
    }
    features = {
        ACTION: {
            "dtype": "float32",
            "shape": [2],
            "names": ["joint_0", "gripper"],
        },
        OBS_STATE: {
            "dtype": "float32",
            "shape": [2],
            "names": ["joint_0", "gripper"],
        },
    }

    stats = compute_relative_action_stats(
        hf_dataset,
        features,
        chunk_size=2,
        exclude_joints=["gripper"],
    )

    np.testing.assert_allclose(stats["mean"], np.array([0.5, 0.25]), atol=1e-5)
    np.testing.assert_array_equal(stats["count"], np.array([4]))


def test_relative_stats_reject_non_positive_chunk_size() -> None:
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        compute_relative_action_stats(
            {ACTION: [[0.0]], OBS_STATE: [[0.0]], "episode_index": [0]},
            {ACTION: {"shape": [1], "names": ["joint"]}},
            chunk_size=0,
        )
