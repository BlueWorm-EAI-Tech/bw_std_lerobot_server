#!/usr/bin/env python3
"""
Mantis PI05 WebSocket 客户端 (JSON 协议)

连接到 PI05 WebSocket 服务器，控制本地 Mantis 机器人。
"""

import argparse
import asyncio
import base64
import io
import json
import logging
import signal
import sys
import time
from typing import Optional
from PIL import Image
import numpy as np

try:
    import websockets
except ImportError:
    print("请安装 websockets: pip install websockets")
    sys.exit(1)

try:
    import json
except ImportError:
    print("请安装 json: Python 3.10+ 包含 json")
    sys.exit(1)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# 动作平滑函数
# ============================================================================
def smooth_action(
    current_state: np.ndarray,
    target_action: np.ndarray,
    alpha: float = 0.5,
    max_change: float = 0.3,
) -> np.ndarray:
    """平滑动作，限制每步最大变化

    Args:
        current_state: 当前关节位置
        target_action: 目标动作
        alpha: 平滑系数 (0-1)，越小越保守
        max_change: 每步最大变化量（弧度）

    Returns:
        平滑后的动作
    """
    # 1. Alpha 平滑: new = state + alpha * (action - state)
    smoothed = current_state + alpha * (target_action - current_state)

    # 2. 限制最大变化
    delta = smoothed - current_state
    delta = np.clip(delta, -max_change, max_change)

    final_action = current_state + delta
    return final_action


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
        env_cam_topic: str = None,
        left_wrist_cam_topic: str = None,
        right_wrist_cam_topic: str = None,
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

    def connect(self) -> bool:
        """连接到 ROS2"""
        try:
            import rclpy
            from sensor_msgs.msg import JointState, Image

            if not rclpy.ok():
                rclpy.init()

            self._node = rclpy.create_node('mantis_pi05_inference_client')

            # 订阅关节状态
            self._node.create_subscription(
                JointState, self.joint_state_topic,
                self._joint_state_callback, 10
            )

            # 订阅相机图像（如果配置了）
            if self.env_cam_topic:
                self._node.create_subscription(
                    Image, self.env_cam_topic,
                    self._env_cam_callback, 10
                )
                logger.info(f"订阅环境相机: {self.env_cam_topic}")
            if self.left_wrist_cam_topic:
                self._node.create_subscription(
                    Image, self.left_wrist_cam_topic,
                    self._left_cam_callback, 10
                )
                logger.info(f"订阅左腕相机: {self.left_wrist_cam_topic}")
            if self.right_wrist_cam_topic:
                self._node.create_subscription(
                    Image, self.right_wrist_cam_topic,
                    self._right_cam_callback, 10
                )
                logger.info(f"订阅右腕相机: {self.right_wrist_cam_topic}")

            # 发布关节命令 (使用 JointState 消息类型)
            self._joint_pub = self._node.create_publisher(
                JointState, self.joint_cmd_topic, 10
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

    def _env_cam_callback(self, msg):
        """环境相机回调"""
        self._env_cam_image = self._ros_image_to_numpy(msg)

    def _left_cam_callback(self, msg):
        """左腕相机回调"""
        self._left_wrist_cam_image = self._ros_image_to_numpy(msg)

    def _right_cam_callback(self, msg):
        """右腕相机回调"""
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
            return None
        return img

    def write_joint_positions(self, positions: np.ndarray):
        """发送关节命令到机器人"""
        if hasattr(self, '_joint_pub') and self._joint_pub:
            from sensor_msgs.msg import JointState
            msg = JointState()
            msg.name = ALL_JOINTS  # 发送所有 16 个关节名称
            msg.position = positions.tolist()
            self._joint_pub.publish(msg)
            # 调用 spin_once 确保 message 被发送
            self.spin_once()
            logger.debug(f"发布关节命令: {positions[:4].round(3)}... (订阅者数量: {self._joint_pub.get_subscription_count()})")
        else:
            logger.warning("无法发布命令: publisher 未初始化")

    def disconnect(self):
        """断开 ROS2 连接"""
        if self._node:
            self._node.destroy_node()
        self._connected = False
        logger.info("ROS2 已断开")

    def spin_once(self):
        """处理 ROS2 消息"""
        if self._node:
            import rclpy
            rclpy.spin_once(self._node, timeout_sec=0.001)

    @property
    def is_connected(self) -> bool:
        return self._connected

    def read_joint_positions(self) -> np.ndarray:
        self.spin_once()
        return self._current_positions.copy()

    def read_images(self) -> dict:
        """读取相机图像"""
        self.spin_once()
        return {
            'env_cam': self._env_cam_image,
            'left_wrist_cam': self._left_wrist_cam_image,
            'right_wrist_cam': self._right_wrist_cam_image,
        }


# ============================================================================
# PI05 WebSocket 客户端（JSON 协议）
# ============================================================================
class PI05WebSocketClient:
    """PI05 WebSocket 客户端 - 使用 JSON 协议"""

    def __init__(
        self,
        server_url: str,
        timeout: float = 5.0,
    ):
        self.server_url = server_url
        self.timeout = timeout

        self.websocket = None
        self.server_metadata = None

        # 计时
        self.last_inference_time_ms = 0.0

        logger.info(f"PI05 WebSocket 客户端初始化: {server_url}")

    async def connect(self) -> bool:
        """连接到 PI05 WebSocket 服务器"""
        try:
            logger.info(f"正在连接服务器: {self.server_url}")
            self.websocket = await websockets.connect(
                self.server_url,
                max_size=50 * 1024 * 1024,  # 50MB
                compression=None,
            )

            logger.info("WebSocket 连接成功")
            return True

        except Exception as e:
            logger.error(f"连接失败: {e}")
            return False

    async def disconnect(self):
        """断开 WebSocket 连接"""
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket 已断开")

    async def infer(
        self,
        state: np.ndarray,
        env_cam: Optional[np.ndarray] = None,
        left_wrist_cam: Optional[np.ndarray] = None,
        right_wrist_cam: Optional[np.ndarray] = None,
    ) -> dict:
        """发送观测数据，获取动作

        PI05 服务器期望的 JSON 格式：
            {
                "observation": {
                    "observation.state": [0.1, 0.2, ...],
                    "observation.images.env_cam": "base64...",
                    "observation.images.left_wrist_cam": "base64...",
                    "observation.images.right_wrist_cam": "base64...",
                },
                "timestep": 0
            }
        """
        import base64
        from PIL import Image
        import io

        # 将 numpy 图像转换为 base64 JPEG
        def image_to_base64(image: np.ndarray) -> str:
            if image is None:
                return None
            img = Image.fromarray(image)
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            return img_str

        # 构建 dummy 图像（224x224 RGB，纯黑色）- 用于没有真实图像时
        def create_dummy_image() -> str:
            img = Image.new('RGB', (224, 224), color=(0, 0, 0))
            buffered = io.BytesIO()
            img.save(buffered, format="JPEG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            return img_str

        # 构建观测数据（JSON 格式）- 优先使用真实图像
        observation = {
            "observation.state": state.astype(np.float32).tolist(),
        }

        # 添加相机图像
        env_cam_b64 = image_to_base64(env_cam) or create_dummy_image()
        left_cam_b64 = image_to_base64(left_wrist_cam) or create_dummy_image()
        right_cam_b64 = image_to_base64(right_wrist_cam) or create_dummy_image()

        observation["observation.images.env_cam"] = env_cam_b64
        observation["observation.images.left_wrist_cam"] = left_cam_b64
        observation["observation.images.right_wrist_cam"] = right_cam_b64

        # 日志：显示是否使用了真实图像
        if env_cam is not None or left_wrist_cam is not None or right_wrist_cam is not None:
            logger.debug("使用真实相机图像")
        else:
            logger.debug("使用虚拟黑色图像")

        # 发送请求
        request = {
            "observation": observation,
            "timestep": 0,
        }

        start_time = time.perf_counter()
        await self.websocket.send(json.dumps(request))

        # 接收响应
        try:
            response_str = await asyncio.wait_for(
                self.websocket.recv(),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"服务器超时 ({self.timeout}s)")

        # 解析响应
        response = json.loads(response_str)

        # Debug: 打印服务器响应
        logger.debug(f"服务器响应 keys: {list(response.keys())}")
        if "error" in response:
            logger.warning(f"服务器返回错误: {response}")
        else:
            logger.debug(f"服务器响应: {response}")

        # 提取计时信息 - 服务器返回 "timing" 而不是 "server_timing"
        timing = response.get("timing", {})
        self.last_inference_time_ms = timing.get("inference_ms", 0.0)

        return response

    def get_action_from_response(self, response: dict) -> np.ndarray:
        """从响应中提取动作"""
        # 首先检查是否有错误
        if "error" in response:
            error_msg = response.get("message", "未知错误")
            logger.error(f"服务器返回错误: {response.get('error')}: {error_msg}")
            raise RuntimeError(f"服务器错误: {response.get('error')}: {error_msg}")

        # 提取 action_chunk
        actions = response.get("action_chunk")
        if actions is None:
            logger.error(f"响应中找不到 action_chunk，响应 keys: {list(response.keys())}")
            logger.error(f"完整响应: {response}")
            raise ValueError(f"响应中没有 action_chunk，响应 keys: {list(response.keys())}")

        actions = np.asarray(actions)

        # actions 形状: [action_horizon, action_dim]
        # 取第一个动作
        if actions.ndim == 2:
            return actions[0].flatten()
        elif actions.ndim == 1:
            return actions[:16].flatten()
        else:
            raise ValueError(f"Unexpected actions shape: {actions.shape}")


# ============================================================================
# 主控制循环
# ============================================================================
running = True


def signal_handler(sig, frame):
    """处理 Ctrl+C"""
    global running
    logger.info("收到退出信号，正在关闭...")
    running = False


async def control_loop(client: PI05WebSocketClient, robot: MantisROS2Interface, args):
    """主控制循环"""
    global running

    step_interval = 1.0 / args.fps
    logger.info(f"启动控制循环，频率: {args.fps} Hz")
    logger.info("按 Ctrl+C 退出")

    step_count = 0
    last_state = None
    next_step_time = time.time()

    try:
        while running:
            # 控制频率
            now = time.time()
            if now < next_step_time:
                await asyncio.sleep(next_step_time - now)
            next_step_time = max(next_step_time + step_interval, time.time())

            try:
                # 1. 读取关节状态
                state = robot.read_joint_positions()

                # 2. 推理动作（暂时不使用相机图像，先用 dummy 黑色图像）
                response = await client.infer(state=state)

                # 3. 提取目标动作
                target_action = client.get_action_from_response(response)

                # 4. 动作平滑
                smoothed_action = smooth_action(
                    state, target_action,
                    alpha=args.action_speed,
                    max_change=args.max_action_change
                )

                # 5. 发送平滑后的动作到机器人
                robot.write_joint_positions(smoothed_action)

                # 6. 详细调试日志
                if args.debug:
                    logger.debug(f"Step {step_count}:")
                    logger.debug(f"  State:    {state[:4].round(4)}...")
                    logger.debug(f"  Target:   {target_action[:4].round(4)}...")
                    logger.debug(f"  Smoothed: {smoothed_action[:4].round(4)}...")
                    logger.debug(f"  Delta:    {(smoothed_action - state)[:4].round(4)}...")

                step_count += 1
                last_state = state

                # 7. 常规日志
                if step_count % 10 == 0:
                    logger.info(
                        f"Step {step_count}: "
                        f"state={state[:4].round(3)}..., "
                        f"action={target_action[:4].round(3)}..., "
                        f"final={smoothed_action[:4].round(3)}..., "
                        f"inference={client.last_inference_time_ms:.1f}ms"
                    )

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

    finally:
        robot.disconnect()


async def main(args):
    """异步主函数"""
    global running

    # 1. 创建 WebSocket 客户端
    client = PI05WebSocketClient(args.server, timeout=args.timeout)
    if not await client.connect():
        logger.error("无法连接到 WebSocket 服务器")
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
        logger.error("无法连接到机器人")
        return 1

    # 3. 运行控制循环
    try:
        await control_loop(client, robot, args)
    finally:
        await client.disconnect()
        robot.disconnect()

    return 0


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='Mantis PI05 WebSocket 客户端（JSON 协议）')

    # 服务器配置
    parser.add_argument('--server', type=str, default='ws://123.56.216.162:8000',
                        help='WebSocket 服务器地址')
    parser.add_argument('--timeout', type=float, default=5.0,
                        help='请求超时时间（秒）')

    # 控制配置
    parser.add_argument('--fps', type=float, default=10.0,
                        help='控制频率 (Hz)')
    parser.add_argument('--action-speed', type=float, default=0.3,
                        help='动作平滑系数 (0-1)，值越小动作越保守')
    parser.add_argument('--max-action-change', type=float, default=0.1,
                        help='每步最大动作变化（弧度），建议 0.05-0.2')

    # ROS2 Topic 配置
    parser.add_argument('--joint-state-topic', type=str, default='/joint_states_fdb',
                        help='关节状态话题')
    parser.add_argument('--joint-cmd-topic', type=str, default='/Teleop/joint_angle_solution',
                        help='关节命令话题')
    parser.add_argument('--env-cam-topic', type=str, default=None,
                        help='环境相机话题（留空则使用虚拟黑色图像）')
    parser.add_argument('--left-wrist-cam-topic', type=str, default=None,
                        help='左腕相机话题')
    parser.add_argument('--right-wrist-cam-topic', type=str, default=None,
                        help='右腕相机话题')

    # 调试选项
    parser.add_argument('--debug', action='store_true',
                        help='启用调试输出')

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # 设置日志级别
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 50)
    logger.info("Mantis PI05 WebSocket 客户端（JSON 协议）")
    logger.info("=" * 50)
    logger.info(f"服务器: {args.server}")
    logger.info(f"控制频率: {args.fps} Hz")
    logger.info(f"动作平滑: alpha={args.action_speed}, max_change={args.max_action_change} rad")
    logger.info("=" * 50)

    # 初始化 ROS2
    try:
        import rclpy
        if not rclpy.ok():
            rclpy.init()
    except ImportError:
        logger.error("请安装 ROS2 Python 包")
        sys.exit(1)

    try:
        exit_code = asyncio.run(main(args))
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("用户中断")
        sys.exit(0)
    finally:
        try:
            import rclpy
            if rclpy.ok():
                rclpy.shutdown()
        except:
            pass
        logger.info("客户端退出")
