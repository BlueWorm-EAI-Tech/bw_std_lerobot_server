# Policies config module
# This module re-exports PreTrainedConfig from policies
# Individual policy configs are in their respective policy directories

from lerobot.policies import PreTrainedConfig

__all__ = ["PreTrainedConfig"]
