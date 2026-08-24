# Mantis 机器人 LeRobot 训练与部署总结

## 目录
1. [项目背景](#1-项目背景)
2. [环境配置](#2-环境配置)
3. [数据集](#3-数据集)
4. [ACT 训练与部署](#4-act-训练与部署)
5. [SmolVLA 训练与部署](#5-smolvla-训练与部署)
6. [PI05 训练与部署](#6-pi05-训练与部署)
7. [PI05 问题排查 (历史)](#7-pi05-问题排查-历史)
8. [对比分析](#8-对比分析)
9. [经验总结](#9-经验总结)
10. [下一步计划](#10-下一步计划)

---

## 1. 项目背景

### 目标
- 在 Mantis 双臂机器人上训练视觉语言动作模型 (VLA)
- 实现从人类演示中学习并自主执行任务
- 对比不同策略模型 (ACT, SmolVLA, PI05) 的效果

### 硬件环境
- Mantis 双臂机器人 (16 个关节: 8 左手 + 8 右手)
- 3 个摄像头: 环境相机 + 左手腕相机 + 右手腕相机
- GPU: NVIDIA GPU (用于训练和推理)

### 软件环境
- LeRobot 框架
- ROS2 Humble
- Python 3.10
- Conda 环境: lerobot

---

## 2. 环境配置

### Conda 环境创建
```bash
conda create -n lerobot python=3.10
conda activate lerobot

# 安装 PyTorch
pip install torch torchvision torchaudio

# 安装 LeRobot
cd /path/to/lerobot
pip install -e .

# 安装其他依赖
pip install transformers accelerate peft
pip install ros-humble-rclpy ros-humble-geometry2
pip install websockets pillow numpy
```

### 目录结构
```
/home/lcjs-szw/repos/lerobot/          # LeRobot 源码
├── outputs/train/                       # 训练输出
├── scripts/websocket-act/               # WebSocket 服务器
└── train_*.sh                          # 训练脚本

/home/lcjs-szw/cc_test/act_client/      # ROS2 客户端
├── ros2_websocket_act_client.py        # ACT 客户端
├── ros2_websocket_smolvla_client.py    # SmolVLA 客户端
├── start.sh                            # ACT 启动脚本
└── start_smolvla.sh                   # SmolVLA 启动脚本

/home/lcjs-szw/datasets/               # 数据集目录
```

---

## 3. 数据集

### 数据集路径
```
/home/lcjs-szw/datasets/datasets/pick_place_cube_0121
```

### 数据集格式
LeRobot 数据集包含:
- 图像: env_cam, left_wrist_cam, right_wrist_cam
- 状态: joint positions (16 维)
- 动作: 16 维 (8 关节 × 2 手臂)
- 任务描述: task 字段

### 数据统计
- 动作维度: 16
- 状态维度: 16
- 图像: RGB, 约 240×320 (env_cam), 240×424 (wrist_cam)

### 重要: 数据归一化统计
训练时使用数据集自带的统计信息进行归一化:
- STATE 和 ACTION 使用 MEAN_STD 归一化
- VISUAL 使用 IDENTITY (不变)

---

## 4. ACT 训练与部署

### 4.1 训练

#### 训练脚本
```bash
cd /home/lcjs-szw/repos/lerobot

python -m lerobot.scripts.lerobot_train \
    --policy.path lerobot/act_real_aloha2_mantis_fixed \
    --dataset.repo_id /home/lcjs-szw/datasets/datasets/pick_place_cube_0121 \
    --steps 60000 \
    --batch_size 2 \
    --eval_freq 5000 \
    --save_freq 5000 \
    --log_freq 100 \
    --save_checkpoint true \
    --policy.n_obs_steps 1 \
    --policy.chunk_size 50 \
    --policy.n_action_steps 50 \
    --policy.freeze_vision_encoder false \
    --dataset.video_backend pyav \
    --wandb.enable false
```

#### 训练结果
- Checkpoint: `outputs/train/pi05_mantis_final_20260212_153042`
- 最终步数: 60000 步
- Loss: 约 0.16 (收敛良好)

### 4.2 部署

#### 启动 WebSocket 服务器
```bash
cd /home/lcjs-szw/repos/lerobot

python scripts/websocket-act/websocket_act_server.py \
    --port 8000 \
    --model_path /home/lcjs-szw/repos/lerobot/outputs/train/pi05_mantis_final_20260212_153042/checkpoints/060000/pretrained_model \
    --device cuda
```

#### 启动 ROS2 客户端
```bash
cd /home/lcjs-szw/cc_test/act_client

bash start.sh --server ws://<GPU服务器IP>:8000
```

#### 客户端参数
- `--fps`: 控制频率 (默认 10)
- `--action-speed`: 动作平滑因子 0-1 (默认 0.5)
- `--max-action-change`: 每步最大变化 (默认 0.3)
- `--raw-actions`: 禁用平滑，使用原始动作

### 4.3 ACT 推理效果
- ✅ 动作输出正确 (16 维)
- ✅ 实时性好 (10Hz 控制频率)
- ✅ 收敛良好，loss 降到 0.16

---

## 5. SmolVLA 训练与部署

### 5.1 训练

#### 训练脚本
```bash
cd /home/lcjs-szw/repos/lerobot

python -m lerobot.scripts.lerobot_train \
    --policy.path lerobot/smolvla_base \
    --dataset.repo_id /home/lcjs-szw/datasets/datasets/pick_place_cube_0121 \
    --steps 60000 \
    --batch_size 2 \
    --eval_freq 5000 \
    --save_freq 5000 \
    --log_freq 100 \
    --save_checkpoint true \
    --policy.n_obs_steps 1 \
    --policy.chunk_size 50 \
    --policy.n_action_steps 50 \
    --policy.max_state_dim 32 \
    --policy.max_action_dim 32 \
    --policy.num_steps 10 \
    --policy.freeze_vision_encoder true \
    --policy.train_expert_only true \
    --policy.optimizer_lr 1e-5 \
    --policy.scheduler_warmup_steps 500 \
    --policy.scheduler_decay_steps 60000 \
    --dataset.video_backend pyav \
    --wandb.enable false
```

#### 关键配置说明
| 参数 | 值 | 说明 |
|------|-----|------|
| `max_state_dim` | 32 | 预训练模型维度 (需适配) |
| `max_action_dim` | 32 | 预训练模型维度 (需适配) |
| `freeze_vision_encoder` | true | 冻结视觉编码器 |
| `train_expert_only` | true | 只训练专家层 |
| `num_steps` | 10 | 扩散推理步数 |

#### 训练结果
- Checkpoint: `outputs/train/smolvla_mantis_ft_20260214_163714`
- 最终步数: 60000 步
- Loss: 约 0.095 (收敛良好，最终约 0.088-0.102)

### 5.2 继续训练 (从 checkpoint 恢复)

#### 重要: 恢复训练参数格式
LeRobot 的 `parse_arg` 函数只支持 `--arg=value` 格式，不支持 `--arg value` 格式！

```bash
cd /home/lcjs-szw/repos/lerobot

python -m lerobot.scripts.lerobot_train \
    --config_path=/home/lcjs-szw/repos/lerobot/outputs/train/smolvla_mantis_ft_20260214_163714/checkpoints/030000/pretrained_model/train_config.json \
    --resume=true \
    --steps=60000 \
    --batch_size=2 \
    --policy.optimizer_lr=1e-5 \
    --policy.scheduler_decay_steps=60000 \
    --dataset.repo_id=/home/lcjs-szw/datasets/datasets/pick_place_cube_0121 \
    --wandb.enable=false
```

#### 训练日志示例
```
从 Checkpoint 恢复: .../checkpoints/030000/pretrained_model/train_config.json
当前步数: 30000
目标步数: 60000
批次大小: 2
学习率: 1e-5
```

### 5.3 部署

#### 启动 WebSocket 服务器
```bash
cd /home/lcjs-szw/repos/lerobot

python scripts/websocket-act/websocket_smolvla_server.py \
    --port 8001 \
    --model_path /home/lcjs-szw/repos/lerobot/outputs/train/smolvla_mantis_ft_20260214_163714/checkpoints/060000/pretrained_model \
    --task "pick up the red block on each side of the white plate and place them into the white plate using both grippers alternately" \
    --device cuda
```

#### 启动 ROS2 客户端
```bash
cd /home/lcjs-szw/cc_test/act_client

bash start_smolvla.sh --server ws://<GPU服务器IP>:8001
```

### 5.4 SmolVLA 推理效果
- ⚠️ 动作输出正常
- ⚠️ 推理效果一般 (数据量不足)
- 预训练模型是 32 维，Mantis 是 16 维，需要投影层适配

---

## 6. PI05 训练与部署

### 6.1 重要发现：必须使用预训练模型

PI05 **必须**使用预训练模型 `lerobot/pi05_base` 进行微调，不能从零开始训练！

#### 问题排查过程
1. **首次训练**：使用 `--policy.type pi05` 从零开始训练 5000 步
2. **推理失败**：动作输出异常，模型没有学到有效策略
3. **根本原因**：未加载预训练权重，模型是随机初始化

#### 解决方案
- 使用 `--policy.pretrained_path lerobot/pi05_base` 加载预训练权重
- 手动下载模型文件到本地缓存（因网络问题）
- 修复 transformers 版本兼容性问题

### 6.2 训练脚本

```bash
cd /home/lcjs-szw/repos/lerobot

# 使用 pi05_base 预训练模型微调
bash train_pi05_mantis_pretrained.sh
```

关键配置：
```bash
--policy.type pi05 \
--policy.pretrained_path "lerobot/pi05_base" \
--policy.max_state_dim 16 \
--policy.max_action_dim 16 \
--policy.chunk_size 100 \
--policy.n_action_steps 100 \
--steps 60000 \
--batch_size 2
```

### 6.3 训练结果

| 项目 | 值 |
|------|-----|
| 预训练模型 | lerobot/pi05_base (4B 参数) |
| 训练步数 | 15,000 / 60,000 (停止时) |
| 训练时长 | 约 3.7 小时 |
| 每步耗时 | 约 0.9 秒 |
| Checkpoint | `outputs/train/pi05_mantis_base_ft_20260215_162213/checkpoints/015000` |

### 6.4 部署

#### 启动服务器
```bash
cd /home/lcjs-szw/repos/lerobot

python scripts/websocket-act/websocket_pi05_server.py \
    --port 8004 \
    --model_path /home/lcjs-szw/repos/lerobot/outputs/train/pi05_mantis_base_ft_20260215_162213/checkpoints/015000/pretrained_model \
    --task "pick up the red block on each side of the white plate and place them into the white plate using both grippers alternately" \
    --device cuda
```

#### 启动客户端
```bash
cd ~/lerobot_mantis_v2/scripts

# 先设置控制模式
python ~/lerobot_mantis_v2/lerobot_robot_bw/set_control_mode.py 1
python ~/lerobot_mantis_v2/lerobot_robot_bw/set_ctrl_src.py 2

# 启动 PI05 客户端
bash start_pi05.sh --server ws://<GPU服务器IP>:8004
```

### 6.5 推理效果

- ✅ 成功加载预训练权重
- ✅ 服务器/客户端连接正常
- ✅ 图像输入正常 (3个相机)
- ✅ 动作输出正常 (100个动作的 chunk)
- ⚠️ **效果一般** - 可能是训练步数不够 (15K vs 60K)

### 6.6 模型文件位置

```
/home/lcjs-szw/repos/lerobot/outputs/train/pi05_mantis_base_ft_20260215_162213/
└── checkpoints/
    └── 015000/
        └── pretrained_model/
            ├── model.safetensors (7.0GB)
            ├── config.json
            ├── policy_preprocessor.json
            ├── policy_postprocessor.json
            └── train_config.json
```

---

## 7. PI05 问题排查 (历史)

### 问题描述
PI05 在 Mantis 机器人上训练后，推理输出动作异常。

### 排查过程

#### 6.1 数据集统计信息检查
```python
from lerobot.common.datasets.lerobot_dataset import LeRobotDataset

dataset = LeRobotDataset(
    repo_id="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121",
    episode_index=0,
)

# 查看统计信息
print(dataset.meta.stats)
```

#### 6.2 检查模型保存的归一化参数
SmolVLA 保存的 processor:
- `policy_preprocessor_step_5_normalizer_processor.safetensors` - 输入归一化
- `policy_postprocessor_step_0_unnormalizer_processor.safetensors` - 输出反归一化

#### 6.3 维度不匹配问题
- SmolVLA 预训练: state_dim=32, action_dim=32
- Mantis 机器人: state_dim=16, action_dim=16
- 解决: 投影层自动处理

#### 6.4 动作范围问题
- 检查推理输出的动作值是否在合理范围内
- 检查是否需要反归一化
- 对比训练数据的动作范围

---

## 8. 对比分析

### 7.1 训练对比

| 指标 | ACT | SmolVLA | PI05 |
|------|-----|---------|------|
| 预训练模型 | act_real_aloha2 | smolvla_base | pi05_base (4B) |
| 训练步数 | 60000 | 60000 | 15000 (未完成) |
| 最终 Loss | ~0.16 | ~0.095 | 进行中 |
| 推理效果 | ✅ 正常 | ⚠️ 一般 | ⚠️ 一般 |

### 7.2 数据集要求
- ACT: 需要大量演示数据
- SmolVLA: 预训练有更强泛化能力，但仍需足够数据

### 7.3 部署对比

| 组件 | ACT | SmolVLA | PI05 |
|------|-----|---------|------|
| 服务器端口 | 8000 | 8001 | 8004 |
| 服务器脚本 | `websocket_act_server.py` | `websocket_smolvla_server.py` | `websocket_pi05_server.py` |
| 客户端脚本 | `ros2_websocket_act_client.py` | `ros2_websocket_smolvla_client.py` | `ros2_websocket_pi05_client.py` |
| 客户端启动 | `start.sh` | `start_smolvla.sh` | `start_pi05.sh` |

---

## 9. 经验总结

### 8.1 训练注意事项

1. **参数格式**: LeRobot CLI 使用 `--arg=value` 格式
2. **恢复训练**: 使用 `--config_path` + `--resume=true`
3. **学习率**: 根据步数设置合理的衰减参数
4. **Batch Size**: 根据 GPU 显存调整 (Mantis: 2)
5. **PI05 必须使用预训练**: 必须指定 `--policy.pretrained_path lerobot/pi05_base`，不能从零训练

### 8.2 部署注意事项

1. **端口区分**: ACT=8000, SmolVLA=8001, PI05=8004
2. **控制模式**: 运行前设置机器人为位置控制模式
3. **动作平滑**: 可调整 `--action-speed` 和 `--max-action-change`

### 8.3 调试技巧

1. **查看 Checkpoint**:
   ```bash
   ls -la outputs/train/*/checkpoints/*/pretrained_model/
   ```

2. **查看训练步数**:
   ```bash
   cat outputs/train/*/checkpoints/*/training_state/training_step.json
   ```

3. **测试推理**: 使用 WebSocket 客户端单独测试

### 8.4 数据集建议

1. 数据量: 至少 100+ episodes
2. 质量: 动作流畅、目标明确
3. 多样性: 包含不同场景和失败案例
4. 归一化: 确保统计信息正确

---

## 附录: 快速命令参考

### 训练命令
```bash
# ACT 训练
bash train_pi05_mantis_complete.sh

# PI05 训练 (使用预训练模型)
bash train_pi05_mantis_pretrained.sh

# PI05 继续训练
bash train_pi05_mantis_continue.sh

# SmolVLA 训练 (首次)
bash train_smolvla_mantis.sh

# SmolVLA 继续训练
bash train_smolvla_continue.sh
```

### 部署命令
```bash
# 启动 ACT 服务器
python scripts/websocket-act/websocket_act_server.py --port 8000 --model_path <path> --device cuda

# 启动 PI05 服务器
python scripts/websocket-act/websocket_pi05_server.py --port 8004 --model_path <path> --task "<task>" --device cuda

# 启动 SmolVLA 服务器
python scripts/websocket-act/websocket_smolvla_server.py --port 8001 --model_path <path> --task "<task>" --device cuda

# 启动客户端
bash act_client/start.sh --server ws://<ip>:8000
bash act_client/start_pi05.sh --server ws://<ip>:8004
bash act_client/start_smolvla.sh --server ws://<ip>:8001
```

---

## 10. 下一步计划

### PI05 继续训练
当前 PI05 模型只训练了 15,000 步，需要继续训练到 60,000 步：

```bash
# 继续训练
cd /home/lcjs-szw/repos/lerobot
python -m lerobot.scripts.lerobot_train \
    --config_path=outputs/train/pi05_mantis_base_ft_20260215_162213/checkpoints/015000/pretrained_model/train_config.json \
    --resume=true \
    --steps=60000 \
    --batch_size=2
```

### 预期改进
- 更多的训练步数应该能显著提升 PI05 的推理效果
- 预训练模型 (4B 参数) + 充分微调 = 更好的泛化能力

---

*最后更新: 2026-02-15*
