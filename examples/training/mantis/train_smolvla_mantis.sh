#!/bin/bash
# 使用 LeRobot 框架微调 SmolVLA 模型 for Mantis 机器人
# 使用预训练模型 lerobot/smolvla_base 进行微调

set -e

cd /home/lcjs-szw/repos/lerobot

# ============ 配置参数 ============
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"
OUTPUT_DIR="outputs/train/smolvla_mantis_ft_$(date +%Y%m%d_%H%M%S)"

# 预训练模型 - 使用 smolvla_base 进行微调
PRETRAINED_PATH="lerobot/smolvla_base"

# 训练参数
BATCH_SIZE=2
STEPS=10000  # 微调 10000 步
EVAL_FREQ=2000
SAVE_FREQ=2000
LOG_FREQ=100

# SmolVLA 预训练模型使用 32 维
# 注意：推理时只使用前 16 维
CHUNK_SIZE=50
N_ACTION_STEPS=50
N_OBS_STEPS=1
MAX_STATE_DIM=32
MAX_ACTION_DIM=32

# 学习率 - 微调时使用较低学习率
LR=1e-5  # 比从零开始低 10 倍
WARMUP_STEPS=500
DECAY_STEPS=20000

# 模型配置
NUM_INFERENCE_STEPS=10

# 视频后端
VIDEO_BACKEND="pyav"

echo "=========================================="
echo "使用 LeRobot 微调 SmolVLA for Mantis"
echo "=========================================="
echo "数据集: $DATASET_PATH"
echo "预训练模型: $PRETRAINED_PATH"
echo "输出目录: $OUTPUT_DIR"
echo "批次大小: $BATCH_SIZE"
echo "训练步数: $STEPS"
echo "Chunk Size: $CHUNK_SIZE"
echo "State Dim: $MAX_STATE_DIM (预训练模型需要 32)"
echo "Action Dim: $MAX_ACTION_DIM (预训练模型需要 32)"
echo "学习率: $LR"
echo "归一化: MEAN_STD"
echo "注意: 推理时只使用前 16 维"
echo "=========================================="
echo ""

# 检查数据集
if [ ! -d "$DATASET_PATH" ]; then
    echo "错误: 数据集不存在: $DATASET_PATH"
    exit 1
fi

# 开始训练
echo "开始微调..."
python -m lerobot.scripts.lerobot_train \
    --policy.type smolvla \
    --policy.pretrained_path "$PRETRAINED_PATH" \
    --dataset.repo_id "$DATASET_PATH" \
    --output_dir "$OUTPUT_DIR" \
    --steps $STEPS \
    --batch_size $BATCH_SIZE \
    --eval_freq $EVAL_FREQ \
    --save_freq $SAVE_FREQ \
    --log_freq $LOG_FREQ \
    --save_checkpoint true \
    --policy.n_obs_steps $N_OBS_STEPS \
    --policy.chunk_size $CHUNK_SIZE \
    --policy.n_action_steps $N_ACTION_STEPS \
    --policy.max_state_dim $MAX_STATE_DIM \
    --policy.max_action_dim $MAX_ACTION_DIM \
    --policy.num_steps $NUM_INFERENCE_STEPS \
    --policy.freeze_vision_encoder true \
    --policy.train_expert_only true \
    --policy.optimizer_lr $LR \
    --policy.scheduler_warmup_steps $WARMUP_STEPS \
    --policy.scheduler_decay_steps $DECAY_STEPS \
    --dataset.video_backend $VIDEO_BACKEND \
    --policy.push_to_hub false \
    --wandb.enable false

echo ""
echo "=========================================="
echo "微调完成！"
echo "模型保存在: $OUTPUT_DIR"
echo "=========================================="
