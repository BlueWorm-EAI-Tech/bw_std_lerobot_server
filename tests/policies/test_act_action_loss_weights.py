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

import pytest
import torch
from torch import nn

from lerobot.policies.act.configuration_act import ACTConfig
from lerobot.policies.act.modeling_act import ACTPolicy
from lerobot.utils.constants import ACTION


class StubACTModel(nn.Module):
    def __init__(self, actions_hat: torch.Tensor):
        super().__init__()
        self.register_buffer("actions_hat", actions_hat)

    def forward(self, batch: dict[str, torch.Tensor]):
        return self.actions_hat, (None, None)


def make_stub_policy(
    actions_hat: torch.Tensor,
    action_loss_weights: list[float] | None = None,
    action_loss_weights_normalize: bool = True,
) -> ACTPolicy:
    policy = ACTPolicy.__new__(ACTPolicy)
    nn.Module.__init__(policy)
    policy.config = ACTConfig(
        use_vae=False,
        action_loss_weights=[] if action_loss_weights is None else action_loss_weights,
        action_loss_weights_normalize=action_loss_weights_normalize,
    )
    policy.model = StubACTModel(actions_hat)
    return policy


def make_batch() -> dict[str, torch.Tensor]:
    return {
        ACTION: torch.tensor([[[1.0, 2.0], [3.0, 4.0]]]),
        "action_is_pad": torch.tensor([[False, True]]),
    }


def test_empty_action_loss_weights_preserve_original_loss_behavior():
    policy = make_stub_policy(torch.zeros(1, 2, 2))

    loss, loss_dict = policy.forward(make_batch())

    # Original ACT behavior averages over batch, time, and action dimensions after masking padded steps.
    torch.testing.assert_close(loss, torch.tensor(0.75))
    assert loss_dict == {"l1_loss": pytest.approx(0.75)}


@pytest.mark.parametrize(
    "normalize,expected_weights,expected_loss",
    [
        (False, [1.0, 0.1], 0.3),
        (True, [20.0 / 11.0, 2.0 / 11.0], 6.0 / 11.0),
    ],
)
def test_action_loss_weights_are_applied_per_dimension(normalize, expected_weights, expected_loss):
    policy = make_stub_policy(
        torch.zeros(1, 2, 2),
        action_loss_weights=[1.0, 0.1],
        action_loss_weights_normalize=normalize,
    )

    loss, loss_dict = policy.forward(make_batch())

    torch.testing.assert_close(loss, torch.tensor(expected_loss))
    assert loss_dict["unweighted_l1_loss"] == pytest.approx(0.75)
    assert loss_dict["l1_loss_per_dim"] == pytest.approx([0.5, 1.0])
    assert loss_dict["action_loss_weights"] == pytest.approx(expected_weights)
    assert loss_dict["weighted_l1_loss_per_dim"] == pytest.approx(
        [0.5 * expected_weights[0], expected_weights[1]]
    )


def test_action_loss_weights_must_match_action_dimension():
    policy = make_stub_policy(torch.zeros(1, 2, 2), action_loss_weights=[1.0])

    with pytest.raises(ValueError, match="got 1 weights for action_dim=2"):
        policy.forward(make_batch())


@pytest.mark.parametrize(
    "weights,error",
    [
        ([1.0, -0.1], "action_loss_weights must be non-negative"),
        ([0.0, 0.0], "At least one action_loss_weights value must be greater than 0"),
    ],
)
def test_action_loss_weights_config_validation(weights, error):
    with pytest.raises(ValueError, match=error):
        ACTConfig(action_loss_weights=weights)
