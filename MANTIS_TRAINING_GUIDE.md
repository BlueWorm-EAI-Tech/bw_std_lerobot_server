# LeRobot 框架中 Mantis Robot 训练指南

## 1. Mantis Robot 已在 LeRobot 中存在

LeRobot 框架已经包含 Mantis Robot 的实现：

| 文件 | 描述 |
|------|------|
| `src/lerobot/robots/mantis/mantis.py` | Mantis Robot 类实现 |
| `src/lerobot/robots/mantis/config_mantis.py` | Mantis 配置类 |

### Mantis Robot 规格

- **DOF**: 16 (每臂 8 个关节)
- **关节**: shoulder_pitch, shoulder_roll, shoulder_yaw, elbow, wrist_roll, wrist_pitch, wrist_yaw, gripper
- **相机**: env_cam (320x240), left_wrist_cam (424x240), right_wrist_cam (424x240)

## 2. Robot Processors 概念

LeRobot 使用 **Processor 管道**处理数据，而不是专门的"Robot Processor"。核心概念：

### 数据处理流程

```
原始数据 (RobotObservation/RobotAction)
        ↓
[DataProcessorPipeline / PolicyProcessorPipeline]
        ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. RenameObservationsProcessorStep (重命名观察)            │
│ 2. MoveTaskToComplementaryDataProcessorStep (PI05 需要)   │
│ 3. AddBatchDimensionProcessorStep (添加批次维度)           │
│ 4. NormalizerProcessorStep ← 关键：使用 dataset.stats      │
│ 5. TokenizerProcessorStep (PI05/SmolVLA 需要)            │
│ 6. DeviceProcessorStep (设备转换)                         │
└─────────────────────────────────────────────────────────────┘
        ↓
模型推理
        ↓
[Postprocessor Pipeline]
        ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. UnnormalizerProcessorStep ← 反归一化                    │
│ 2. DeviceProcessorStep                                     │
└─────────────────────────────────────────────────────────────┘
        ↓
RobotAction (执行)
```

### 归一化处理器 (NormalizerProcessorStep)

这是 **Robot Processors** 的核心，负责：
- 使用数据集统计信息 (`dataset.meta.stats`) 进行归一化
- 支持多种归一化模式

**归一化模式**：

| 模式 | 公式 | 用途 |
|------|------|------|
| MEAN_STD | `(x - mean) / std` | SmolVLA, ACT |
| MIN_MAX | `2*(x-min)/(max-min) - 1` | 很少使用 |
| QUANTILES | `2*(x-q01)/(q99-q01) - 1` | PI05 |
| QUANTILE10 | `2*(x-q10)/(q90-q10) - 1` | 很少使用 |

## 3. PI05 vs SmolVLA 关键差异

| 特性 | PI05 | SmolVLA |
|------|------|---------|
| **归一化** | QUANTILES | MEAN_STD |
| **VLM 基础** | PaliGemma (Gemma) | SmolVLM2 |
| **参数规模** | ~2B | ~500M |
| **动作生成** | Flow Matching | Diffusion |
| **推理步数** | 10 | 10 |
| **输入** | State + Image + Task | State + Image + Task |

### 归一化差异对训练的影响

**PI05 (QUANTILES)**:
```python
# 归一化到 [-1, 1]
normalized = 2.0 * (x - q01) / (q99 - q01) - 1.0
# 需要 q01, q99 统计信息
```

**SmolVLA (MEAN_STD)**:
```python
# 标准化
normalized = (x - mean) / std
# 需要 mean, std 统计信息
```

## 4. 数据集要求

确保数据集包含正确的统计信息：

```bash
# 数据集 meta/info.json 应包含：
{
    "robot_type": "mantis",  # 重要：标识机器人类型
    ...
}

# 数据集 meta/stats.json 应包含：
{
    "observation.state": {
        "mean": [...],
        "std": [...],
        "q01": [...],
        "q99": [...],
        ...
    },
    "action": {
        "mean": [...],
        "std": [...],
        "q01": [...],
        "q99": [...],
        ...
    }
}
```

## 5. 训练脚本

### PI05 训练

```bash
bash train_pi05_mantis_v4.sh
```

关键参数：
- `--policy.type pi05`
- `--policy.normalization_mapping` 默认使用 QUANTILES
- `--policy.n_action_steps 100`
- `--policy.max_state_dim 16`
- `--policy.max_action_dim 16`

### SmolVLA 训练

```bash
bash train_smolvla_mantis.sh
```

关键参数：
- `--policy.type smolvla`
- `--policy.normalization_mapping` 默认使用 MEAN_STD
- `--policy.n_action_steps 50`
- `--policy.vlm_model_name HuggingFaceTB/SmolVLM2-500M-Video-Instruct`

## 6. 排查问题

### 问题：动作输出不正确

1. **检查归一化配置**
   ```python
   # 确认 config.json 中的归一化映射
   "normalization_mapping": {
       "VISUAL": "IDENTITY",
       "STATE": "QUANTILES",  # PI05
       "ACTION": "QUANTILES"
   }
   ```

2. **验证统计信息**
   ```bash
   # 对比数据集和模型的统计信息
   python -c "
   import json
   from safetensors import safe_open

   # 加载两者并对比
   "
   ```

3. **检查预处理流程**
   - 确认 preprocessor 正确加载了数据集统计信息
   - 验证输入数据的范围

## 7. 推理部署

### 使用 WebSocket 服务器

**PI05 服务器**:
```bash
python scripts/websocket-act/websocket_pi05_server.py \
    --port 8000 \
    --model_path outputs/train/pi05_mantis_*/checkpoints/last/pretrained_model \
    --task "pick up the red block..."
```

**SmolVLA 服务器**:
```bash
# 需要创建类似的 WebSocket 服务器
```

## 8. 总结

| 步骤 | 操作 |
|------|------|
| 1. 确认 Mantis Robot 存在 | `ls src/lerobot/robots/mantis/` |
| 2. 准备数据集 | 确保 stats.json 包含 q01/q99 和 mean/std |
| 3. 选择策略 | PI05 (QUANTILES) vs SmolVLA (MEAN_STD) |
| 4. 训练 | 使用对应脚本 |
| 5. 验证 | 检查输出动作范围是否合理 |
| 6. 部署 | 使用 WebSocket 服务器 |
