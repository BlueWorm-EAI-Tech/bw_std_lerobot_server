# PI05 Mantis 机器人部署与调试记录

## 概述

本文档记录了使用 LeRobot 框架训练 PI05 模型并部署到 Mantis 双臂机器人的完整过程，包括训练、服务器部署、客户端开发、以及遇到的各种问题和解决方案。

## 目录

1. [训练阶段](#1-训练阶段)
2. [服务器部署](#2-服务器部署)
3. [客户端开发](#3-客户端开发)
4. [问题排查与解决](#4-问题排查与解决)
5. [当前状态](#5-当前状态)
6. [下一步计划](#6-下一步计划)

---

## 1. 训练阶段

### 1.1 背景
- 用户之前成功使用 LeRobot 框架训练了 ACT 策略并部署到 Mantis 机器人
- 现在希望使用相同的数据集和配置训练 PI05 策略

### 1.2 训练脚本
**文件**: `/home/lcjs-szw/repos/lerobot/train_pi05_mantis_final.sh`

```bash
python lerobot/scripts/train.py \
    policy=pi05 \
    env=mantis_dataset \
    dataset.repo_id=/home/lcjs-szw/datasets/datasets/pick_place_cube_0121 \
    hydra.job.chdir=False \
    device=cuda \
    training.offline_steps=5000 \
    training.save_freq=1000 \
    training.log_freq=100 \
    training.online_steps=0 \
    env.episode_length=100 \
    training.batch_size=2 \
    training.dtype=bfloat16 \
    training.gradient_checkpointing=true \
    training.learning_rate=1e-5 \
    training.warmup_steps_ratio=0.1 \
    training.lr_scheduler=cosine \
    policy.chunk_size=100 \
    policy.n_action_steps=100 \
    policy.state_dim=16 \
    policy.action_dim=16
```

### 1.3 训练参数说明
| 参数 | 值 | 说明 |
|------|-----|------|
| batch_size | 2 | 降低以避免 CUDA OOM |
| dtype | bfloat16 | 内存优化 |
| gradient_checkpointing | true | 内存优化 |
| chunk_size | 100 | PI05 动作块大小 |
| n_action_steps | 100 | 动作步数 |
| state_dim | 16 | 16个关节 |
| action_dim | 16 | 16个关节 |
| learning_rate | 1e-5 | 学习率 |
| offline_steps | 5000 | 训练步数 |
| save_freq | 1000 | 保存频率 |

### 1.4 代码修复

#### Bug 1: Task 处理问题
**文件**: `/home/lcjs-szw/repos/lerobot/src/lerobot/policies/pi05/processor_pi05.py`

添加了 `MoveTaskToComplementaryDataProcessorStep` 类来处理任务描述：

```python
@ProcessorStepRegistry.register(name="move_task_to_complementary_data")
@dataclass
class MoveTaskToComplementaryDataProcessorStep(ProcessorStep):
    def __call__(self, transition: EnvTransition) -> EnvTransition:
        transition = transition.copy()
        task_value = transition.get("task")
        if task_value is not None:
            complementary_data = transition.get(TransitionKey.COMPLEMENTARY_DATA, {})
            if complementary_data is None:
                complementary_data = {}
            complementary_data["task"] = task_value
        transition[TransitionKey.COMPLEMENTARY_DATA] = complementary_data
        return transition
```

#### Bug 2: Task 输入类型处理
修改了 `Pi05PrepareStateTokenizerProcessorStep` 来同时处理 tensor 和 string 类型的 task 输入。

### 1.5 训练结果
- 最终 loss: ~1.0
- 训练步数: 5000
- 模型保存位置: `/home/lcjs-szw/repos/lerobot/outputs/train/pi05_mantis_final_20260212_182416/checkpoints/last/pretrained_model`

---

## 2. 服务器部署

### 2.1 服务器架构
- **远程服务器**: <GPU服务器IP>:8000
- **本地机器**: 运行 Mantis 机器人的机器
- **通信方式**: WebSocket (JSON 协议)

### 2.2 服务器代码
**文件**: `/home/lcjs-szw/repos/lerobot/scripts/websocket-act/websocket_pi05_server.py`

#### 功能特性
1. 加载 PI05 模型并预处理/后处理器
2. 接收 JSON 格式的观测数据
3. 支持_base64 编码的图像
4. 支持任务描述（PI05 特有）
5. 返回带时间戳的响应

#### 客户端请求格式
```json
{
    "observation": {
        "observation.state": [0.1, 0.2, ...],
        "observation.images.env_cam": "base64...",
        "observation.images.left_wrist_cam": "base64...",
        "observation.images.right_wrist_cam": "base64..."
    },
    "timestep": 0
}
```

#### 服务器响应格式
```json
{
    "action_chunk": [[0.1, 0.2, ...], ...],
    "timestep": 0,
    "inference_time_ms": 33.5,
    "chunk_size": 100,
    "timing": {
        "parse_ms": 1.2,
        "preprocess_ms": 10.5,
        "inference_ms": 20.3,
        "postprocess_ms": 1.5
    }
}
```

### 2.3 服务器启动命令
```bash
python websocket_pi05_server.py \
    --port 8000 \
    --host 0.0.0.0 \
    --model_path /home/lcjs-szw/repos/lerobot/outputs/train/pi05_mantis_final_20260212_182416/checkpoints/last/pretrained_model \
    --task "pick up the red block on each side of the white plate and place them into the white plate using both grippers alternately"
```

### 2.4 网络配置问题

#### 问题 1: 端口冲突
- 错误: `address already in use`
- 原因: caddy 服务使用 8000 端口
- 解决: `sudo systemctl stop caddy`

#### 问题 2: 外部无法访问
- 错误: 客户端无法连接到服务器
- 原因: 绑定到 localhost 而不是 0.0.0.0
- 解决: 使用 `--host 0.0.0.0`

---

## 3. 客户端开发

### 3.1 客户端文件
**最终版本**: `/home/lcjs-szw/repos/lerobot/scripts/websocket-mantis/mantis_websocket_client_json.py`

### 3.2 客户端架构
```
┌─────────────────┐    WebSocket JSON    ┌──────────────────┐
│   Mantis Robot  │ ←─────────────────→  │  PI05 Server     │
│   (本地)        │                      │  (远程)          │
└─────────────────┘                      └──────────────────┘
```

### 3.3 核心组件

#### ROS2 接口 (MantisROS2Interface)
- 订阅关节状态: `/joint_states_fdb`
- 发布关节命令: `/Teleop/joint_angle_solution`
- 订阅相机图像（可选）:
  - 环境相机: `/env_camera/image_raw`
  - 左腕相机: `/camera/left_d405/color/image_raw`
  - 右腕相机: `/camera/right_d405/color/image_raw`

#### WebSocket 客户端 (PI05WebSocketClient)
- 连接到远程 PI05 服务器
- 发送观测数据（state + images）
- 接收动作块并提取第一个动作

#### 动作平滑函数 (smooth_action)
```python
def smooth_action(current_state, target_action, alpha=0.5, max_change=0.3):
    smoothed = current_state + alpha * (target_action - current_state)
    delta = np.clip(smoothed - current_state, -max_change, max_change)
    final_action = current_state + delta
    return final_action
```

### 3.4 Mantis 关节定义
```python
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
```

---

## 4. 问题排查与解决

### 4.1 协议不匹配问题

#### 问题描述
```
UnicodeDecodeError: 'utf-8' codec can't decode byte 0x81 in position 0
```

#### 根本原因
- 原客户端 (`mantis_websocket_client.py`) 使用 msgpack 二进制协议
- 服务器 (`websocket_pi05_server.py`) 期望 JSON 文本协议

#### 解决方案
完全重写客户端，改用 JSON 协议，创建新文件 `mantis_websocket_client_json.py`。

### 4.2 ROS2 Topic 不匹配

#### 问题描述
机器人不响应命令。

#### 排查结果
```bash
ros2 topic list | grep joint
# /joint_states_fdb
# /Teleop/joint_angle_solution
```

#### 解决方案
更新客户端默认话题:
- 关节状态: `/joint_states` → `/joint_states_fdb`
- 关节命令: `/joint_commands` → `/Teleop/joint_angle_solution`

### 4.3 ROS2 消息类型不匹配

#### 问题描述
```
TypeError: Expected <class 'std_msgs.msg._float64_multi_array.Float64MultiArray'>,
got <class 'sensor_msgs.msg._joint_state.JointState'>
```

#### 根本原因
- Publisher 创建为 `Float64MultiArray` 类型
- 但发布的是 `JointState` 类型消息

#### 解决方案
更新 `connect()` 方法使用 `JointState`:
```python
self._joint_pub = self._node.create_publisher(JointState, self.joint_cmd_topic, 10)
```

### 4.4 PI05 预处理器要求

#### 问题描述
服务器返回错误，提示缺少图像数据。

#### 根本原因
PI05 模型期望 `observation.images.*` 键，但客户端只发送 state。

#### 解决方案
添加虚拟黑色图像:
```python
def create_dummy_image() -> str:
    img = Image.new('RGB', (224, 224), color=(0, 0, 0))
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode()

observation = {
    "observation.state": state.tolist(),
    "observation.images.env_cam": create_dummy_image(),
    "observation.images.left_wrist_cam": create_dummy_image(),
    "observation.images.right_wrist_cam": create_dummy_image(),
}
```

### 4.5 机器人动作异常

#### 问题描述
- 机器人开始移动（订阅者数量 = 1）
- 但动作很奇怪，第一步是 -0.08
- 使用真实相机图像后，左臂剧烈甩动

#### 可能原因
1. **关节角度范围不匹配** - 训练数据的关节范围与实际机器人不同
2. **模型未充分收敛** - 训练 loss ~1.0 可能还需要更多训练
3. **缺乏视觉信息** - 虚拟黑色图像无法提供有用视觉输入
4. **归一化参数不一致** - 训练时和推理时的归一化方式不同

#### 已采取的措施
1. 添加动作平滑函数
2. 限制每步最大变化量
3. 降低控制频率
4. 暂时禁用真实相机图像

---

## 5. 当前状态

### 5.1 文件位置
| 文件 | 路径 |
|------|------|
| 训练脚本 | `/home/lcjs-szw/repos/lerobot/train_pi05_mantis_final.sh` |
| 模型 | `/home/lcjs-szw/repos/lerobot/outputs/train/pi05_mantis_final_20260212_182416/checkpoints/last/pretrained_model` |
| 服务器 | `/home/lcjs-szw/repos/lerobot/scripts/websocket-act/websocket_pi05_server.py` |
| 客户端 | `/home/lcjs-szw/repos/lerobot/scripts/websocket-mantis/mantis_websocket_client_json.py` |

### 5.2 机器人状态
- **ROS2 连接**: 成功
- **WebSocket 连接**: 成功
- **命令发布**: 成功（订阅者数量 = 1）
- **机器人运动**: 可以动，但动作异常剧烈

### 5.3 建议的保守参数
```bash
python mantis_websocket_client_json.py \
    --debug \
    --action-speed 0.05 \
    --max-action-change 0.02 \
    --fps 2
```

### 5.4 可用的相机话题
```bash
/env_camera/image_raw                           # 环境相机
/camera/left_d405/color/image_raw               # 左腕相机
/camera/right_d405/color/image_raw              # 右腕相机
```

---

## 6. 下一步计划

### 6.1 紧急任务（安全优先）
1. 检查模型配置文件 `config.json` 中的归一化参数
2. 对比训练数据的关节角度范围和实际机器人范围
3. 使用更保守的参数进行逐步测试

### 6.2 短期任务
1. 分析训练数据的统计信息
2. 检查数据集的关节角度分布
3. 调整训练或推理的归一化方式
4. 考虑重新训练或延长训练时间

### 6.3 中期任务
1. 添加安全限制（关节位置限制、速度限制）
2. 实现 emergency stop 功能
3. 添加动作幅度监控和告警

### 6.4 长期任务
1. 使用真实相机图像改进视觉输入
2. 优化控制频率和平滑参数
3. 添加任务描述的多语言支持

---

## 附录 A: 关键命令

### A.1 训练相关
```bash
# 训练模型
bash train_pi05_mantis_final.sh

# 查看训练日志（如果使用 Weights & Biases）
# 或直接查看输出目录
ls outputs/train/pi05_mantis_final_*/
```

### A.2 服务器相关
```bash
# 启动服务器
python websocket_pi05_server.py \
    --port 8000 \
    --host 0.0.0.0 \
    --model_path /path/to/model \
    --task "task description"

# 停止 caddy（端口冲突时）
sudo systemctl stop caddy
```

### A.3 客户端相关
```bash
# 基本运行（保守参数）
python mantis_websocket_client_json.py \
    --debug \
    --action-speed 0.05 \
    --max-action-change 0.02 \
    --fps 2

# 查看可用话题
ros2 topic list | grep joint
ros2 topic list | grep cam

# 查看话题信息
ros2 topic info /Teleop/joint_angle_solution
ros2 topic echo /joint_states_fdb
```

---

## 附录 B: 依赖项

### Python 依赖
```bash
pip install websockets numpy pillow torch
pip install rclpy  # ROS2
```

### ROS2 包
- `sensor_msgs`
- `std_msgs`

---

## 附录 C: PI05 模型说明

### C.1 模型架构
PI05 (π0.5) 是一个视觉-语言-动作模型，结合了：
- **PaliGemma**: 视觉-语言编码器
- **Gemma**: 动作专家模型
- **Flow Matching**: 基于扩散的动作生成技术

### C.2 输入要求
- **State**: 关节位置（16维）
- **Images**: 环境相机、左腕相机、右腕相机
- **Task**: 自然语言任务描述

### C.3 输出
- **Action Chunk**: 形状为 `[chunk_size, action_dim]` 的动作序列
- 通常取第一个动作用于实时控制

---

## 附录 D: 调试技巧

### D.1 启用调试日志
```bash
python mantis_websocket_client_json.py --debug
```

### D.2 检查模型配置
```bash
cat /path/to/model/config.json
```

### D.3 查看训练曲线
如果使用了 Weights & Biases，可以在网页界面查看 loss 曲线。

### D.4 逐步测试
1. 首先使用最小参数测试连接
2. 然后逐步提高控制频率
3. 最后添加相机图像

---

**文档创建时间**: 2026-02-12
**最后更新**: 2026-02-12
