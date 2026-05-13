#!/usr/bin/env python

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

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch

from lerobot.configs.types import PipelineFeatureType, PolicyFeature
from lerobot.utils.constants import ACTION, OBS_STATE

from .core import EnvTransition, TransitionKey
from .pipeline import ProcessorStep, ProcessorStepRegistry


def _infer_excluded_dims_from_names(
    action_dim: int,
    exclude_joints: list[str],
    action_feature_names: list[str],
) -> set[int]:
    if not exclude_joints:
        return set()

    if action_feature_names:
        exclude_tokens = [token.lower() for token in exclude_joints]
        return {
            idx
            for idx, name in enumerate(action_feature_names[:action_dim])
            if any(token in str(name).lower() for token in exclude_tokens)
        }

    # Fallback for the common bimanual joint layout used by folding checkpoints:
    # the last joint in each arm block is the gripper.
    if any(token.lower() == "gripper" for token in exclude_joints) and action_dim >= 8 and action_dim % 2 == 0:
        arm_dim = action_dim // 2
        return {arm_dim - 1, action_dim - 1}

    return set()


def _apply_relative_transform(
    action: torch.Tensor,
    state: torch.Tensor,
    delta_dims: list[int],
    *,
    inverse: bool,
) -> torch.Tensor:
    if not delta_dims:
        return action

    result = action.clone()
    if action.dim() == 1:
        state_view = state
    elif action.dim() == 2:
        state_view = state if state.dim() == 2 else state.unsqueeze(0)
    elif action.dim() == 3:
        if state.dim() == 1:
            state_view = state.unsqueeze(0).unsqueeze(0)
        elif state.dim() == 2:
            state_view = state.unsqueeze(1)
        else:
            state_view = state
    else:
        raise ValueError(f"Unsupported action shape for relative transform: {tuple(action.shape)}")

    if inverse:
        result[..., delta_dims] = action[..., delta_dims] + state_view[..., delta_dims]
    else:
        result[..., delta_dims] = action[..., delta_dims] - state_view[..., delta_dims]
    return result


@dataclass
@ProcessorStepRegistry.register(name="delta_actions_processor")
class DeltaActionsProcessorStep(ProcessorStep):
    enabled: bool = True
    exclude_joints: list[str] = field(default_factory=list)
    action_feature_names: list[str] = field(default_factory=list)

    def get_config(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "exclude_joints": self.exclude_joints,
            "action_feature_names": self.action_feature_names,
        }

    def __call__(self, transition: EnvTransition) -> EnvTransition:
        self._current_transition = transition.copy()
        new_transition = self._current_transition

        if not self.enabled:
            return new_transition

        action = new_transition.get(TransitionKey.ACTION)
        observation = new_transition.get(TransitionKey.OBSERVATION)
        if action is None or observation is None or OBS_STATE not in observation:
            return new_transition

        action_tensor = torch.as_tensor(action)
        state_tensor = torch.as_tensor(observation[OBS_STATE], dtype=action_tensor.dtype, device=action_tensor.device)
        excluded = _infer_excluded_dims_from_names(
            action_tensor.shape[-1],
            self.exclude_joints,
            self.action_feature_names,
        )
        delta_dims = [idx for idx in range(action_tensor.shape[-1]) if idx not in excluded]
        new_transition[TransitionKey.ACTION] = _apply_relative_transform(
            action_tensor,
            state_tensor,
            delta_dims,
            inverse=False,
        )
        return new_transition

    def transform_features(
        self, features: dict[PipelineFeatureType, dict[str, PolicyFeature]]
    ) -> dict[PipelineFeatureType, dict[str, PolicyFeature]]:
        return features


@dataclass
@ProcessorStepRegistry.register(name="absolute_actions_processor")
class AbsoluteActionsProcessorStep(ProcessorStep):
    enabled: bool = True
    exclude_joints: list[str] = field(default_factory=list)
    action_feature_names: list[str] = field(default_factory=list)
    _reference_state: torch.Tensor | None = field(default=None, init=False, repr=False)

    def get_config(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "exclude_joints": self.exclude_joints,
            "action_feature_names": self.action_feature_names,
        }

    def set_reference_state(self, state: torch.Tensor | list[float]) -> None:
        self._reference_state = torch.as_tensor(state)

    def __call__(self, transition: EnvTransition) -> EnvTransition:
        self._current_transition = transition.copy()
        new_transition = self._current_transition

        if not self.enabled:
            return new_transition

        action = new_transition.get(TransitionKey.ACTION)
        if action is None:
            return new_transition

        reference_state = self._reference_state
        observation = new_transition.get(TransitionKey.OBSERVATION)
        if reference_state is None and observation is not None and OBS_STATE in observation:
            reference_state = torch.as_tensor(observation[OBS_STATE])
        if reference_state is None:
            return new_transition

        action_tensor = torch.as_tensor(action)
        state_tensor = reference_state.to(dtype=action_tensor.dtype, device=action_tensor.device)
        excluded = _infer_excluded_dims_from_names(
            action_tensor.shape[-1],
            self.exclude_joints,
            self.action_feature_names,
        )
        delta_dims = [idx for idx in range(action_tensor.shape[-1]) if idx not in excluded]
        new_transition[TransitionKey.ACTION] = _apply_relative_transform(
            action_tensor,
            state_tensor,
            delta_dims,
            inverse=True,
        )
        return new_transition

    def transform_features(
        self, features: dict[PipelineFeatureType, dict[str, PolicyFeature]]
    ) -> dict[PipelineFeatureType, dict[str, PolicyFeature]]:
        return features
