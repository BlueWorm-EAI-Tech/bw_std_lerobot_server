#!/usr/bin/env python3
"""
Mantis WebSocket Inference Client (msgpack 协议)

连接到 OpenPI WebSocket 推理服务器，使用 msgpack 协议通信。

使用方法:
    python mantis_websocket_client.py --server ws://SERVER_IP:8000

依赖:
    pip install websockets numpy pillow msgpack msgpack-numpy
"""

import argparse
import asyncio
import json
import logging
import signal
import sys
import time
from collections import deque

import numpy as np

try:
    import websockets
except ImportError:
    print("请安装 websockets: pip install websockets")
    sys.exit(1)

try:
    import msgpack
    import msgpack_numpy
    msgpack_numpy.patch()  # 让 msgpack 支持 numpy arrays
except ImportError:
    print("请安装 msgpack: pip install msgpack msgpack-numpy")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局变量
running = True


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


def signal_handler(sig, frame):
    """处理 Ctrl+C"""
    global running
    logger.info("收到退出信号，正在关闭...")
    running = False


# ============================================================================
# ROS2 Mantis 硬件接口
# ============================================================================

class MantisROS2Interface:
    """Mantis 机器人 ROS2 接口"""

    def __init__(
        self,
        joint_state_topic: str = "/joint_states",
        joint_cmd_topic: str = "/joint_commands",
        env_cam_topic: str = "/env_cam/image_raw",
        left_wrist_cam_topic: str = "/left_wrist_cam/image_raw",
        right_wrist_cam_topic: str = "/right_wrist_cam/image_raw",
    ):
        self.joint_state_topic = joint_state_topic
        self.joint_cmd_topic = joint_cmd_topic
        self.env_cam_topic = env_cam_topic
        self.left_wrist_cam_topic = left_wrist_cam_topic
        self.right_wrist_cam_topic = right_wrist_cam_topic

        self._connected = False
        self._current_positions = np.zeros(16, dtype=np.float32)
        self._env_cam_image = None
        self._left_wrist_cam_image = None
        self._right_wrist_cam_image = None

        self._node = None

    def connect(self) -> bool:
        """连接到 ROS2"""
        try:
            import rclpy
            from sensor_msgs.msg import Image, JointState
            from std_msgs.msg import Float64MultiArray

            if not rclpy.ok():
                rclpy.init()

            self._node = rclpy.create_node('mantis_inference_client')

            # 订阅关节状态
            self._node.create_subscription(
                JointState, self.joint_state_topic,
                self._joint_state_callback, 10
            )

            # 订阅相机图像
            self._node.create_subscription(
                Image, self.env_cam_topic,
                self._env_cam_callback, 10
            )
            self._node.create_subscription(
                Image, self.left_wrist_cam_topic,
                self._left_cam_callback, 10
            )
            self._node.create_subscription(
                Image, self.right_wrist_cam_topic,
                self._right_cam_callback, 10
            )

            # 发布关节命令
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
        """关节状态回调 - 根据你的实际消息格式调整"""
        if len(msg.position) >= 16:
            self._current_positions = np.array(msg.position[:16], dtype=np.float32)

    def _env_cam_callback(self, msg):
        self._env_cam_image = self._ros_image_to_numpy(msg)

    def _left_cam_callback(self, msg):
        self._left_wrist_cam_image = self._ros_image_to_numpy(msg)

    def _right_cam_callback(self, msg):
        self._right_wrist_cam_image = self._ros_image_to_numpy(msg)

    def _ros_image_to_numpy(self, msg) -> np.ndarray:
        """将 ROS Image 消息转换为 numpy 数组 (H, W, C) uint8"""
        if msg.encoding == 'rgb8':
            img = np.frombuffer(msg.data, dtype=np.uint8)
            img = img.reshape((msg.height, msg.width, 3))
        elif msg.encoding == 'bgr8':
            img = np.frombuffer(msg.data, dtype=np.uint8)
            img = img.reshape((msg.height, msg.width, 3))
            img = img[:, :, ::-1].copy()  # BGR -> RGB
        else:
            logger.warning(f"未知图像编码: {msg.encoding}")
            img = None
        return img

    def spin_once(self):
        if self._node:
            import rclpy
            rclpy.spin_once(self._node, timeout_sec=0.001)

    def disconnect(self):
        if self._node:
            self._node.destroy_node()
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def read_joint_positions(self) -> np.ndarray:
        self.spin_once()
        return self._current_positions.copy()

    def read_images(self) -> dict:
        self.spin_once()
        return {
            'env_cam': self._env_cam_image,
            'left_wrist_cam': self._left_wrist_cam_image,
            'right_wrist_cam': self._right_wrist_cam_image,
        }

    def write_joint_positions(self, positions: np.ndarray):
        if hasattr(self, '_joint_pub') and self._joint_pub:
            from std_msgs.msg import Float64MultiArray
            msg = Float64MultiArray()
            msg.data = positions.tolist()
            self._joint_pub.publish(msg)


# ============================================================================
# OpenPI WebSocket 客户端 (msgpack 协议)
# ============================================================================

class OpenPIWebSocketClient:
    """OpenPI WebSocket 推理客户端 - 使用 msgpack 协议"""

    def __init__(self, server_url: str, timeout: float = 5.0):
        self.server_url = server_url
        self.timeout = timeout
        self.websocket = None
        self.server_metadata = None

        # Action chunk 管理
        self.action_queue = deque()
        self.chunk_index = 0

        # 计时
        self.last_inference_time_ms = 0.0

        logger.info(f"OpenPI WebSocket 客户端初始化: {server_url}")

    async def connect(self) -> bool:
        """连接到 OpenPI WebSocket 服务器"""
        try:
            logger.info(f"正在连接服务器: {self.server_url}")
            self.websocket = await websockets.connect(
                self.server_url,
                max_size=50 * 1024 * 1024,  # 50MB
                compression=None,
            )

            # 接收服务器 metadata（带超时）
            try:
                metadata_bytes = await asyncio.wait_for(
                    self.websocket.recv(),
                    timeout=self.timeout
                )
                self.server_metadata = msgpack.unpackb(metadata_bytes, raw=False)
                logger.info(f"服务器 metadata: {self.server_metadata}")
            except asyncio.TimeoutError:
                logger.warning("未收到服务器 metadata（超时），使用默认配置")
                self.server_metadata = {}

            logger.info("WebSocket 连接成功")
            return True
        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False

    async def disconnect(self):
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket 已断开")

    def _prepare_image(self, image: np.ndarray) -> np.ndarray:
        """准备图像: (H, W, C) uint8 -> (C, H, W) uint8"""
        if image is None:
            return None

        # 确保是 uint8
        if image.dtype != np.uint8:
            image = (image * 255).astype(np.uint8) if image.max() <= 1.0 else image.astype(np.uint8)

        # HWC -> CHW
        if image.ndim == 3 and image.shape[2] in (1, 3, 4):
            image = np.transpose(image, (2, 0, 1))

        return image

    async def infer(
        self,
        state: np.ndarray,
        env_cam: np.ndarray | None = None,
        left_wrist_cam: np.ndarray | None = None,
        right_wrist_cam: np.ndarray | None = None,
    ) -> dict:
        """发送观测数据，获取动作

        OpenPI 期望的格式:
        {
            "observation": {
                "state": np.array([16]),
                "images": {
                    "env_cam": np.array([C, H, W]),
                    "left_wrist_cam": np.array([C, H, W]),
                    "right_wrist_cam": np.array([C, H, W]),
                }
            }
        }

        返回:
        {
            "actions": np.array([action_horizon, action_dim]),
            "state": np.array([state_dim]),
            ...
        }
        """

        # 构建观测数据（使用 JSON 格式）
        observation = {
            "observation": {
                "state": state.astype(np.float32).tolist(),
                "images": {},  # 暂时不发送图像
            }
        }

        # 使用 msgpack 序列化
        msgpack.packb(observation, default=msgpack_numpy.encode)

        # 发送请求（使用 JSON 格式）
        await self.websocket.send(json.dumps(observation))

        # 接收响应
        try:
            response_bytes = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=self.timeout
            )
        except asyncio.TimeoutError as err:
            raise RuntimeError(f"服务器超时 ({self.timeout}s)") from err

        # 检查是否是错误消息 (字符串)
        if isinstance(response_bytes, str):
            raise RuntimeError(f"服务器错误: {response_bytes}")

        # 解析响应
        response = json.loads(response_bytes)

        # 提取计时信息
        server_timing = response.get("server_timing", {})
        self.last_inference_time_ms = server_timing.get("infer_ms", 0.0)

        return response

    def get_action_from_response(self, response: dict) -> np.ndarray:
        """从响应中提取动作 (取第一个 action)"""
        actions = response.get("actions")
        if actions is None:
            raise ValueError("响应中没有 actions")

        actions = np.asarray(actions)

        # actions 形状: [action_horizon, action_dim]
        # 取第一个动作
        if actions.ndim == 2:
            return actions[0, :16].astype(np.float32)  # 只取前 16 维
        elif actions.ndim == 1:
            return actions[:16].astype(np.float32)
        else:
            raise ValueError(f"Unexpected actions shape: {actions.shape}")


# ============================================================================
# 主控制循环
# ============================================================================

async def control_loop(client: OpenPIWebSocketClient, robot: MantisROS2Interface, args):
    """主控制循环"""
    global running

    step_interval = 1.0 / args.fps
    logger.info(f"启动控制循环，频率: {args.fps} Hz")
    logger.info("按 Ctrl+C 退出")

    step_count = 0
    next_step_time = time.time()

    while running:
        # 控制频率
        now = time.time()
        if now < next_step_time:
            await asyncio.sleep(next_step_time - now)
        next_step_time = max(next_step_time + step_interval, time.time())

        try:
            # 1. 读取关节状态
            state = robot.read_joint_positions()

            # 2. 读取相机图像
            images = robot.read_images()

            # 3. 推理
            response = await client.infer(
                state=state,
                env_cam=images.get('env_cam'),
                left_wrist_cam=images.get('left_wrist_cam'),
                right_wrist_cam=images.get('right_wrist_cam'),
            )

            # 4. 提取动作
            action = client.get_action_from_response(response)

            # 5. 动作平滑
            alpha = args.action_speed
            max_delta = args.max_action_change

            smoothed = state + alpha * (action - state)
            delta = np.clip(smoothed - state, -max_delta, max_delta)
            final_action = state + delta

            # 6. 发送动作到机器人
            robot.write_joint_positions(final_action)

            step_count += 1

            # 7. 日志
            if step_count % 10 == 0:
                logger.info(
                    f"Step {step_count}: "
                    f"inference={client.last_inference_time_ms:.1f}ms"
                )
                if args.debug:
                    logger.info(f"  State: {state[:4].round(3)}...")
                    logger.info(f"  Action: {action[:4].round(3)}...")

        except websockets.exceptions.ConnectionClosed:
            logger.error("连接断开，尝试重连...")
            if await client.connect():
                logger.info("重连成功")
            else:
                logger.error("重连失败，退出")
                break

        except Exception as e:
            logger.error(f"控制循环错误: {e}", exc_info=True)
            await asyncio.sleep(0.1)


async def async_main(args):
    """异步主函数"""
    global running

    try:
        # 1. 创建 WebSocket 客户端
        client = OpenPIWebSocketClient(args.server, timeout=args.timeout)
        if not await client.connect():
            return 1

        # 2. 创建机器人接口
        robot = MantisROS2Interface(
            joint_state_topic=args.joint_state_topic,
            joint_cmd_topic=args.joint_cmd_topic,
            env_cam_topic=args.env_cam_topic,
            left_wrist_cam_topic=args.left_wrist_cam_topic,
            right_wrist_cam_topic=args.right_wrist_cam_topic,
        )

        if not robot.connect():
            return 1

        # 3. 运行控制循环
        await control_loop(client, robot, args)

        # 4. 清理
        await client.disconnect()
        robot.disconnect()

        return 0

    except Exception as e:
        logger.error(f"错误: {e}", exc_info=True)
        return 1


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description='Mantis OpenPI WebSocket 推理客户端')

    # 服务器配置
    parser.add_argument('--server', type=str, default='ws://localhost:8000',
                        help='WebSocket 服务器地址')
    parser.add_argument('--timeout', type=float, default=5.0,
                        help='请求超时时间 (秒)')

    # 控制配置
    parser.add_argument('--fps', type=float, default=10.0,
                        help='控制频率 (Hz)')
    parser.add_argument('--action-speed', type=float, default=0.5,
                        help='动作平滑系数 (0-1)')
    parser.add_argument('--max-action-change', type=float, default=0.3,
                        help='每步最大动作变化 (弧度)')

    # ROS2 Topic 配置
    parser.add_argument('--joint-state-topic', type=str, default='/joint_states')
    parser.add_argument('--joint-cmd-topic', type=str, default='/joint_commands')
    parser.add_argument('--env-cam-topic', type=str, default='/env_cam/image_raw')
    parser.add_argument('--left-wrist-cam-topic', type=str, default='/left_wrist_cam/image_raw')
    parser.add_argument('--right-wrist-cam-topic', type=str, default='/right_wrist_cam/image_raw')

    # 调试
    parser.add_argument('--debug', action='store_true', help='启用调试输出')

    args = parser.parse_args()

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 初始化 ROS2
    try:
        import rclpy
        if not rclpy.ok():
            rclpy.init()
    except ImportError:
        logger.error("请安装 ROS2 Python 包")
        sys.exit(1)

    try:
        exit_code = asyncio.run(async_main(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("用户中断")
        sys.exit(0)
    finally:
        import rclpy
        if rclpy.ok():
            rclpy.shutdown()
        logger.info("客户端退出")


if __name__ == "__main__":
    main()
