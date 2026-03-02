#!/usr/bin/env python

# Copyright 2025 Mantis Robot Integration for LeRobot
# Licensed under the Apache License, Version 2.0

"""
Mantis Bimanual Robot Implementation for LeRobot

Mantis is a bimanual robot with 16 DOF (2 arms x 8 joints each).
"""

import logging
from functools import cached_property

import numpy as np

from lerobot.cameras.utils import make_cameras_from_configs

from ..robot import Robot
from .config_mantis import MantisConfig

logger = logging.getLogger(__name__)

# Joint names for Mantis robot
LEFT_ARM_JOINTS = [
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    "left_gripper_joint",
]

RIGHT_ARM_JOINTS = [
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
    "right_gripper_joint",
]

ALL_JOINTS = LEFT_ARM_JOINTS + RIGHT_ARM_JOINTS


class MantisHardwareInterface:
    """Abstract interface for Mantis hardware communication."""

    def connect(self) -> bool:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    @property
    def is_connected(self) -> bool:
        raise NotImplementedError

    def read_joint_positions(self) -> np.ndarray:
        raise NotImplementedError

    def write_joint_positions(self, positions: np.ndarray) -> np.ndarray:
        raise NotImplementedError


class MockMantisHardware(MantisHardwareInterface):
    """Mock hardware for testing without real robot."""

    def __init__(self):
        self._connected = False
        self._joint_positions = np.zeros(16)

    def connect(self) -> bool:
        self._connected = True
        logger.info("MockMantisHardware connected")
        return True

    def disconnect(self) -> None:
        self._connected = False
        logger.info("MockMantisHardware disconnected")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def read_joint_positions(self) -> np.ndarray:
        return self._joint_positions.copy()

    def write_joint_positions(self, positions: np.ndarray) -> np.ndarray:
        self._joint_positions = 0.9 * self._joint_positions + 0.1 * positions
        return self._joint_positions.copy()


class Mantis(Robot):
    """Mantis Bimanual Robot for LeRobot (16-DOF, 3 cameras)."""

    config_class = MantisConfig
    name = "mantis"

    def __init__(self, config: MantisConfig, hardware: MantisHardwareInterface | None = None):
        super().__init__(config)
        self.config = config

        if hardware is not None:
            self.hardware = hardware
        else:
            logger.warning("No hardware interface provided, using MockMantisHardware")
            self.hardware = MockMantisHardware()

        self.cameras = make_cameras_from_configs(config.cameras)
        self._last_joint_positions = np.zeros(16)

    @property
    def _motors_ft(self) -> dict[str, type]:
        return {f"{joint}.pos": float for joint in ALL_JOINTS}

    @property
    def _cameras_ft(self) -> dict[str, tuple]:
        return {
            cam: (self.config.cameras[cam].height, self.config.cameras[cam].width, 3)
            for cam in self.cameras
        }

    @cached_property
    def observation_features(self) -> dict[str, type | tuple]:
        return {**self._motors_ft, **self._cameras_ft}

    @cached_property
    def action_features(self) -> dict[str, type]:
        return self._motors_ft

    @property
    def is_connected(self) -> bool:
        cameras_connected = all(cam.is_connected for cam in self.cameras.values())
        return self.hardware.is_connected and cameras_connected

    def connect(self, calibrate: bool = True) -> None:
        if not self.hardware.connect():
            raise ConnectionError("Failed to connect to Mantis hardware")

        for cam in self.cameras.values():
            cam.connect()

        if not self.is_calibrated and calibrate:
            self.calibrate()

        self.configure()
        logger.info(f"{self} connected successfully")

    @property
    def is_calibrated(self) -> bool:
        return True

    def calibrate(self) -> None:
        pass

    def configure(self) -> None:
        self._last_joint_positions = self.hardware.read_joint_positions()

    def get_observation(self) -> dict:
        if not self.is_connected:
            raise ConnectionError(f"{self} is not connected")

        obs_dict = {}

        joint_positions = self.hardware.read_joint_positions()
        self._last_joint_positions = joint_positions

        for i, joint in enumerate(ALL_JOINTS):
            obs_dict[f"{joint}.pos"] = float(joint_positions[i])

        for cam_key, cam in self.cameras.items():
            obs_dict[cam_key] = cam.async_read()

        return obs_dict

    def send_action(self, action: dict) -> dict:
        if not self.is_connected:
            raise ConnectionError(f"{self} is not connected")

        goal_positions = np.zeros(16)
        for i, joint in enumerate(ALL_JOINTS):
            key = f"{joint}.pos"
            if key in action:
                goal_positions[i] = action[key]

        if self.config.max_relative_target is not None:
            delta = goal_positions - self._last_joint_positions
            delta = np.clip(delta, -self.config.max_relative_target, self.config.max_relative_target)
            goal_positions = self._last_joint_positions + delta

        sent_positions = self.hardware.write_joint_positions(goal_positions)

        sent_action = {}
        for i, joint in enumerate(ALL_JOINTS):
            sent_action[f"{joint}.pos"] = float(sent_positions[i])

        return sent_action

    def disconnect(self) -> None:
        for cam in self.cameras.values():
            cam.disconnect()
        self.hardware.disconnect()
        logger.info(f"{self} disconnected")
