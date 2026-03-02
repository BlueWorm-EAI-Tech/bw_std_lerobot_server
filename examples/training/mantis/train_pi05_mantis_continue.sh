#!/bin/bash
# 从现有 PI05 checkpoint 继续训练到 60000 步
# 节省时间，从 5000 步继续

set -e

cd /home/lcjs-szw/repos/lerobot

# 使用现有的 checkpoint
CHECKPOINT_PATH="/home/lcjs-szw/repos/lerobot/outputs/train/pi05_mantis_final_20260212_182416/checkpoints/005000/pretrained_model"
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"

# 继续训练参数
STEPS=60000
BATCH_SIZE=2
LOG_FREQ=100

# 学习率参数 - 与原始训练一致
LR=1e-5
DECAY_STEPS=60000

echo "=========================================="
echo "从 checkpoint 继续训练 PI05"
echo "=========================================="
echo "Checkpoint: $CHECKPOINT_PATH"
echo "数据集: $DATASET_PATH"
echo "目标步数: $STEPS"
echo "=========================================="
echo ""

# 检查 checkpoint
if [ ! -d "$CHECKPOINT_PATH" ]; then
    echo "错误: Checkpoint 不存在: $CHECKPOINT_PATH"
    exit 1
fi

# 继续训练
echo "继续训练..."
python -m lerobot.scripts.lerobot_train \
    --config_path="$CHECKPOINT_PATH/train_config.json" \
    --resume=true \
    --steps=$STEPS \
    --batch_size=$BATCH_SIZE \
    --policy.optimizer_lr=$LR \
    --policy.scheduler_decay_steps=$DECAY_STEPS \
    --dataset.repo_id=$DATASET_PATH \
    --wandb.enable=false

echo ""
echo "=========================================="
echo "继续训练完成！"
echo "=========================================="
