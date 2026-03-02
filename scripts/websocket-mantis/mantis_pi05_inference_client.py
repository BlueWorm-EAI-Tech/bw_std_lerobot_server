#!/usr/bin/env python3
"""
Mantis PI05 本地推理客户端

直接加载 PI05 模型进行本地推理，然后通过 ROS2 控制机器人。
不依赖 OpenPI WebSocket 服务器。
"""

import argparse
import asyncio
import logging
import signal
import sys
import time
from typing import Optional
import numpy as np

try:
    import torch
except ImportError:
    print("请安装 PyTorch: pip install torch")
    sys.exit(1)

try:
    import cv2
except ImportError:
    print("请安装 opencv: pip install opencv-python")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# Mantis 机器人关节定义
# ============================================================================
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

ALL_JOINTS = LEFT_ARM_JOINTS + RIGHT_ARM_JOINTS  # 16 joints total


# ============================================================================
# ROS2 Mantis 接口
# ============================================================================
class MantisROS2Interface:
    """Mantis 机器人 ROS2 接口"""

    def __init__(
        self,
        joint_state_topic: str = "/joint_states",
        joint_cmd_topic: str = "/joint_commands",
    ):
        self.joint_state_topic = joint_state_topic
        self.joint_cmd_topic = joint_cmd_topic

        self._connected = False
        self._current_positions = np.zeros(16, dtype=np.float32)

    def connect(self) -> bool:
        """连接到 ROS2"""
        try:
            import rclpy
            from sensor_msgs.msg import JointState
            from std_msgs.msg import Float64MultiArray

            if not rclpy.ok():
                rclpy.init()

            self._node = rclpy.create_node('mantis_pi05_inference_client')

            # 订阅关节状态
            self._node.create_subscription(
                JointState, self.joint_state_topic,
                self._joint_state_callback, 10
            )

            # 发布关节命令
            from std_msgs.msg import Float64MultiArray
            self._joint_pub = self._node.create_publisher(
                Float64MultiArray, self.joint_cmd_topic, 10
            )

            self._connected = True
            logger.info("ROS2 连接成功")
            return True

        except Exception as e:
            logger.error(f"ROS2 连接失败: {e}")
            return False

    def _joint_state_callback(self, msg):
        """关节状态回调"""
        if len(msg.position) >= 16:
            self._current_positions = np.array(msg.position[:16], dtype=np.float32)

    def write_joint_positions(self, positions: np.ndarray):
        """发送关节命令到机器人"""
        if hasattr(self, '_joint_pub') and self._joint_pub:
            from std_msgs.msg import Float64MultiArray
            msg = Float64MultiArray()
            msg.data = positions.tolist()
            self._joint_pub.publish(msg)

    def disconnect(self):
        """断开 ROS2 连接"""
        if self._node:
            self._node.destroy_node()
            self._connected = False
            logger.info("ROS2 已断开")


# ============================================================================
# PI05 模型推理
# ============================================================================
class PI05Model:
    """PI05 模型加载器"""

    def __init__(self, policy_path: str):
        from lerobot.policies.factory import make_policy
        from lerobot.policies.pi05.configuration_pi05 import PI05Config

        logger.info(f"加载 PI05 模型: {policy_path}")

        # 加载配置
        from lerobot.policies.pretrained import PreTrainedPolicy
        self.policy = PreTrainedPolicy.from_pretrained(policy_path)

        # 获取模型
        self.model = self.policy.model

        # 设置为评估模式
        self.model.eval()

        # 移动到设备
        self.device = self.policy.device

        logger.info(f"模型已加载到设备: {self.device}")

    def get_action(self, state: np.ndarray, task: str) -> np.ndarray:
        """获取动作预测"""
        import torch

        # 准备输入
        state_tensor = torch.from_numpy(state, dtype=torch.float32).unsqueeze(0)  # [1, 16]

        # 构建输入字典
        observation = {
            "observation.state": state_tensor,
        }

        # 添加任务描述
        observation["task"] = task

        # 移动到模型设备
        for key in observation:
            if isinstance(observation[key], torch.Tensor):
                observation[key] = observation[key].to(self.device)

        # 不需要计算梯度
        with torch.no_grad():
            # 获取动作
            action = self.model.select_action(observation)

        # 转回 numpy
        if hasattr(action, 'cpu'):
            action = action.numpy()
        elif hasattr(action, 'numpy'):
            pass
        else:
            action = action.cpu().numpy()

        # PI05 返回 [action_horizon, action_dim]，需要取第一个
        if action.ndim == 2:
            return action[0].flatten()
        else:
            return action.flatten()

    def get_image_action(self, image: np.ndarray, state: np.ndarray) -> np.ndarray:
        """基于图像的动作（用于相机图像输入）"""
        import cv2

        # 简单的图像处理 - 调整大小用于显示
        # 实际动作仍然来自 PI05 模型

        # 返回当前状态（保持当前姿态）
        return self._current_positions


# ============================================================================
# 主控制循环
# ============================================================================
running = True
step_count = 0
last_inference_time_ms = 0


def signal_handler(sig, frame):
    """处理 Ctrl+C"""
    global running
    logger.info("收到退出信号，正在关闭...")
    running = False


async def control_loop(client: PI05Model, robot: MantisROS2Interface, args):
    """主控制循环"""
    global running, step_count, last_inference_time_ms

    logger.info("启动控制循环")

    # 从 lerobot datasets 加载图像（用于相机输入）
    from lerobot.datasets.factory import make_dataset
    dataset_cfg = {
        'repo_id': args.dataset,
        'video_backend': 'pyav',
        'streaming': False,
    }

    dataset = make_dataset(dataset_cfg)

    # 初始化任务描述
    task_description = args.task

    step_interval = 1.0 / args.fps

    try:
        while running:
            start_time = time.time()

            # 1. 读取关节状态
            state = robot.read_joint_positions()

            # 2. 读取相机图像（可选，用于显示）
            if args.enable_camera:
                try:
                    idx = step_count % len(dataset)
                    frame_data = dataset[idx]
                    # 获取环境相机图像
                    env_cam_key = 'observation.images.env_cam'
                    if env_cam_key in frame_data:
                        env_cam = frame_data[env_cam_key]
                        # 调整图像大小用于显示
                        display_cam = cv2.resize(env_cam, (320, 240))
                        logger.info(f"环境相机: {display_cam.shape}")
                except Exception as e:
                    logger.warning(f"读取相机图像失败: {e}")

            # 3. 推理动作
            start_inference = time.perf_counter()
            action = client.get_action(state, task_description)
            inference_time_ms = (time.perf_counter() - start_inference) * 1000
            last_inference_time_ms = inference_time_ms

            # 4. 发送动作到机器人
            robot.write_joint_positions(action)

            # 5. 日志
            step_count += 1
            elapsed = time.time() - start_time

            logger.info(
                f"Step {step_count}: action={action[:4].round(3)}..., "
                f"inference={inference_time_ms:.1f}ms, "
                f"loop={elapsed:.3f}s"
            )

            # 控制频率
            sleep_time = max(0, step_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    except Exception as e:
        logger.error(f"控制循环错误: {e}", exc_info=True)
    finally:
        robot.disconnect()


async def main(args):
    """异步主函数"""
    global running

    # 1. 加载 PI05 模型
    client = PI05Model(args.policy_path)

    # 2. 连接到机器人
    robot = MantisROS2Interface(
        joint_state_topic=args.joint_state_topic,
        joint_cmd_topic=args.joint_cmd_topic,
    )

    if not robot.connect():
        logger.error("无法连接到机器人")
        return 1

    # 3. 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 4. 启动控制循环
    try:
        await control_loop(client, robot, args)
    finally:
        robot.disconnect()


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Mantis PI05 本地推理客户端')

    # 模型配置
    parser.add_argument('--policy-path', type=str,
                        default='/home/lcjs-szw/repos/lerobot/outputs/train/pi05_mantis_final_20260212_182416/checkpoints/last/pretrained_model/',
                        help='PI05 模型路径')
    parser.add_argument('--dataset', type=str,
                        default='/home/lcjs-szw/datasets/datasets/pick_place_cube_0121',
                        help='数据集路径（用于相机输入）')

    # ROS2 Topic 配置
    parser.add_argument('--joint-state-topic', type=str, default='/joint_states',
                        help='关节状态话题')
    parser.add_argument('--joint-cmd-topic', type=str, default='/joint_commands',
                        help='关节命令话题')

    # 控制配置
    parser.add_argument('--fps', type=float, default=10.0,
                        help='控制频率 (Hz)')
    parser.add_argument('--task', type=str,
                        default='pick up the red block on each side of the white plate and place them into the white plate using both grippers alternately',
                        help='任务描述')

    # 调试选项
    parser.add_argument('--enable-camera', action='store_true',
                        help='启用相机输入显示')

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    logger.info("=" * 50)
    logger.info("Mantis PI05 本地推理客户端")
    logger.info("=" * 50)
    logger.info(f"模型路径: {args.policy_path}")
    logger.info(f"数据集: {args.dataset}")
    logger.info(f"任务: {args.task}")
    logger.info(f"控制频率: {args.fps} Hz")
    logger.info("=" * 50)

    exit_code = asyncio.run(main(args))

    sys.exit(exit_code)
