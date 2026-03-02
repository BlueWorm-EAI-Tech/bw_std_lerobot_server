# Mantis WebSocket 推理客户端

用于 Mantis 双臂机器人的 WebSocket 推理客户端，连接远程推理服务器进行策略推理。

## 架构

```
[本地工控机]                    [远程服务器]
┌─────────────────┐            ┌─────────────────┐
│  Mantis 机器人   │            │  推理服务器      │
│  ROS2 节点      │◄──WebSocket──►│  OpenPI/LeRobot │
│  相机           │            │  GPU 推理       │
└─────────────────┘            └─────────────────┘
```

## 文件说明

- `mantis_websocket_client.py` - 主客户端程序
- `config.yaml` - 配置文件
- `requirements.txt` - Python 依赖

## 安装

```bash
pip install -r requirements.txt
```

## 使用方法

```bash
# 基本用法
python mantis_websocket_client.py --server ws://SERVER_IP:8000

# 完整参数
python mantis_websocket_client.py \
    --server ws://192.168.1.100:8000 \
    --fps 10 \
    --action-speed 0.5 \
    --max-action-change 0.3 \
    --joint-state-topic /joint_states \
    --joint-cmd-topic /joint_commands \
    --env-cam-topic /env_cam/image_raw \
    --left-wrist-cam-topic /left_wrist_cam/image_raw \
    --right-wrist-cam-topic /right_wrist_cam/image_raw
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--server` | `ws://localhost:8000` | WebSocket 服务器地址 |
| `--timeout` | `5.0` | 请求超时时间 (秒) |
| `--fps` | `10.0` | 控制频率 (Hz) |
| `--action-speed` | `0.5` | 动作平滑系数 (0-1) |
| `--max-action-change` | `0.3` | 每步最大动作变化 (弧度) |

## 需要修改的部分

根据你的实际 ROS2 配置，需要修改 `MantisROS2Interface` 类中的：

1. **关节状态回调** (`_joint_state_callback`)
   - 根据你的 JointState 消息格式调整关节顺序

2. **图像转换** (`_ros_image_to_numpy`)
   - 根据你的图像编码格式调整 (rgb8/bgr8/其他)

3. **ROS2 Topic 名称**
   - 通过命令行参数或修改默认值

## Mantis 关节顺序 (16 DOF)

```
左臂 (8 joints):
  0: left_shoulder_pitch_joint
  1: left_shoulder_roll_joint
  2: left_shoulder_yaw_joint
  3: left_elbow_joint
  4: left_wrist_roll_joint
  5: left_wrist_pitch_joint
  6: left_wrist_yaw_joint
  7: left_gripper_joint

右臂 (8 joints):
  8: right_shoulder_pitch_joint
  9: right_shoulder_roll_joint
  10: right_shoulder_yaw_joint
  11: right_elbow_joint
  12: right_wrist_roll_joint
  13: right_wrist_pitch_joint
  14: right_wrist_yaw_joint
  15: right_gripper_joint
```

## 相机配置

| 相机 | 分辨率 |
|------|--------|
| env_cam | 240 x 320 |
| left_wrist_cam | 240 x 424 |
| right_wrist_cam | 240 x 424 |
