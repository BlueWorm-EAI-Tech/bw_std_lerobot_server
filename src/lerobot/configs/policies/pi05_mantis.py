#!/usr/bin/env python

# Copyright 2025 HuggingFace Inc.
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

"""Configuration for PI05 policy specifically designed for Mantis robot."""

from dataclasses import dataclass, field

from lerobot.configs.policies import PreTrainedConfig
from lerobot.configs.types import FeatureType, NormalizationMode, PolicyFeature
from lerobot.optim.optimizers import AdamWConfig
from lerobot.optim.schedulers import CosineDecayWithWarmupSchedulerConfig
from lerobot.policies.rtc.configuration_rtc import RTCConfig
from lerobot.utils.constants import ACTION, OBS_IMAGES, OBS_LANGUAGE_ATTENTION_MASK, OBS_LANGUAGE_TOKENS, OBS_STATE


@PreTrainedConfig.register_subclass("pi05_mantis")
@dataclass
class PI05MantisConfig(PreTrainedConfig):
    """PI05 configuration optimized for Mantis robot training."""
    
    # Model architecture
    paligemma_variant: str = "gemma_2b"
    action_expert_variant: str = "gemma_300m"
    dtype: str = "float32"  # Options: "bfloat16", "float32"

    # Observation and action settings - MATCH ACT SUCCESS CONFIGURATION
    n_obs_steps: int = 1
    chunk_size: int = 100  # Match ACT successful configuration
    n_action_steps: int = 100  # Match ACT successful configuration

    # State and action dimensions - MATCH DATASET (16-dimensional)
    max_state_dim: int = 16  # Exact match with dataset
    max_action_dim: int = 16  # Exact match with dataset

    # Flow matching parameters
    num_inference_steps: int = 10
    time_sampling_beta_alpha: float = 1.5
    time_sampling_beta_beta: float = 1.0
    time_sampling_scale: float = 0.999
    time_sampling_offset: float = 0.001
    min_period: float = 4e-3
    max_period: float = 4.0

    # Image settings
    image_resolution: tuple[int, int] = (224, 224)
    empty_cameras: int = 0

    # Language processing - REQUIRED FOR MANTIS
    tokenizer_max_length: int = 200
    
    # Normalization - Use quantiles like ACT
    normalization_mapping: dict[str, NormalizationMode] = field(
        default_factory=lambda: {
            "VISUAL": NormalizationMode.IDENTITY,
            "STATE": NormalizationMode.QUANTILES,
            "ACTION": NormalizationMode.QUANTILES,
        }
    )

    # Training optimizations
    gradient_checkpointing: bool = False
    compile_model: bool = False
    compile_mode: str = "max-autotune"
    device: str | None = None

    # Fine-tuning settings
    freeze_vision_encoder: bool = False
    train_expert_only: bool = False

    # Optimizer settings - MATCH ACT LEARNING RATE
    optimizer_lr: float = 1e-5  # Conservative learning rate
    optimizer_betas: tuple[float, float] = (0.9, 0.95)
    optimizer_eps: float = 1e-8
    optimizer_weight_decay: float = 0.01
    optimizer_grad_clip_norm: float = 1.0

    # Scheduler settings
    scheduler_warmup_steps: int = 1000
    scheduler_decay_steps: int = 30000
    scheduler_decay_lr: float = 1e-6

    def __post_init__(self):
        super().__post_init__()

        # Validate configuration
        if self.n_action_steps > self.chunk_size:
            raise ValueError(
                f"n_action_steps ({self.n_action_steps}) cannot be greater than chunk_size ({self.chunk_size})"
            )

        if self.paligemma_variant not in ["gemma_300m", "gemma_2b"]:
            raise ValueError(f"Invalid paligemma_variant: {self.paligemma_variant}")

        if self.action_expert_variant not in ["gemma_300m", "gemma_2b"]:
            raise ValueError(f"Invalid action_expert_variant: {self.action_expert_variant}")

        if self.dtype not in ["bfloat16", "float32"]:
            raise ValueError(f"Invalid dtype: {self.dtype}")

    def validate_features(self) -> None:
        """Validate and set up input/output features for Mantis robot."""
        # Image features - match dataset cameras
        image_features = [
            "observation.images.env_cam",
            "observation.images.left_wrist_cam", 
            "observation.images.right_wrist_cam"
        ]
        
        for img_key in image_features:
            if img_key not in self.input_features:
                image_feature = PolicyFeature(
                    type=FeatureType.VISUAL,
                    shape=(3, *self.image_resolution),
                )
                self.input_features[img_key] = image_feature

        # Empty cameras
        for i in range(self.empty_cameras):
            key = OBS_IMAGES + f".empty_camera_{i}"
            empty_camera = PolicyFeature(
                type=FeatureType.VISUAL,
                shape=(3, *self.image_resolution),
            )
            self.input_features[key] = empty_camera

        # State feature - 16 dimensional like dataset
        if OBS_STATE not in self.input_features:
            state_feature = PolicyFeature(
                type=FeatureType.STATE,
                shape=(self.max_state_dim,),
            )
            self.input_features[OBS_STATE] = state_feature

        # Language features - REQUIRED FOR PI05
        if OBS_LANGUAGE_TOKENS not in self.input_features:
            language_tokens = PolicyFeature(
                type=FeatureType.LANGUAGE_TOKENS,
                shape=(self.tokenizer_max_length,),
            )
            self.input_features[OBS_LANGUAGE_TOKENS] = language_tokens
            
        if OBS_LANGUAGE_ATTENTION_MASK not in self.input_features:
            language_mask = PolicyFeature(
                type=FeatureType.LANGUAGE_ATTENTION_MASK,
                shape=(self.tokenizer_max_length,),
            )
            self.input_features[OBS_LANGUAGE_ATTENTION_MASK] = language_mask

        # Action feature - 16 dimensional like dataset
        if ACTION not in self.output_features:
            action_feature = PolicyFeature(
                type=FeatureType.ACTION,
                shape=(self.max_action_dim,),
            )
            self.output_features[ACTION] = action_feature

    def get_optimizer_preset(self) -> AdamWConfig:
        return AdamWConfig(
            lr=self.optimizer_lr,
            betas=self.optimizer_betas,
            eps=self.optimizer_eps,
            weight_decay=self.optimizer_weight_decay,
            grad_clip_norm=self.optimizer_grad_clip_norm,
        )

    def get_scheduler_preset(self):
        return CosineDecayWithWarmupSchedulerConfig(
            peak_lr=self.optimizer_lr,
            decay_lr=self.scheduler_decay_lr,
            num_warmup_steps=self.scheduler_warmup_steps,
            num_decay_steps=self.scheduler_decay_steps,
        )

    @property
    def observation_delta_indices(self) -> None:
        return None

    @property
    def action_delta_indices(self) -> list:
        return list(range(self.chunk_size))

    @property
    def reward_delta_indices(self) -> None:
        return None