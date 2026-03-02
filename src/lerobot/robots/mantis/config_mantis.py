#!/usr/bin/env python

# Copyright 2025 Mantis Robot Integration for LeRobot
# Licensed under the Apache License, Version 2.0

from dataclasses import dataclass, field

from lerobot.cameras import CameraConfig
from lerobot.cameras.opencv import OpenCVCameraConfig

from ..config import RobotConfig


@RobotConfig.register_subclass("mantis")
@dataclass
class MantisConfig(RobotConfig):
    """Configuration class for Mantis bimanual robot.
    
    Mantis is a bimanual robot with:
    - 2 arms, each with 7 joints + 1 gripper = 16 DOF total
    - 3 cameras: env_cam, left_wrist_cam, right_wrist_cam
    
    Joint names (per arm):
    - shoulder_pitch_joint
    - shoulder_roll_joint  
    - shoulder_yaw_joint
    - elbow_joint
    - wrist_roll_joint
    - wrist_pitch_joint
    - wrist_yaw_joint
    - gripper_joint
    """
    
    # Hardware connection settings
    host: str = "localhost"
    port: int = 8765
    
    # Control settings
    control_freq: float = 30.0  # Hz
    max_relative_target: float | None = None  # Max relative position change per step
    
    # Camera configurations
    cameras: dict[str, CameraConfig] = field(default_factory=lambda: {
        "env_cam": OpenCVCameraConfig(
            index_or_path=0,
            fps=30,
            width=320,
            height=240,
        ),
        "left_wrist_cam": OpenCVCameraConfig(
            index_or_path=1,
            fps=30,
            width=424,
            height=240,
        ),
        "right_wrist_cam": OpenCVCameraConfig(
            index_or_path=2,
            fps=30,
            width=424,
            height=240,
        ),
    })
