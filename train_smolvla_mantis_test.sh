#!/bin/bash
# 使用 LeRobot 框架训练 SmolVLA 模型 for Mantis 机器人
# 测试版本：不使用预训练模型，验证流程

set -e

cd /home/lcjs-szw/repos/lerobot

# ============ 配置参数 ============
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"
OUTPUT_DIR="outputs/train/smolvla_mantis_notrain_$(date +%Y%m%d_%H%M%S)"

# 训练参数 - 减少步数用于快速测试
BATCH_SIZE=2
STEPS=1000  # 只训练 1000 步用于测试
EVAL_FREQ=500
SAVE_FREQ=500
LOG_FREQ=50

# SmolVLA 特定参数
CHUNK_SIZE=50
N_ACTION_STEPS=50
N_OBS_STEPS=1
MAX_STATE_DIM=16
MAX_ACTION_DIM=16

# 学习率
LR=1e-4
WARMUP_STEPS=100
DECAY_STEPS=1000

# 模型配置
NUM_INFERENCE_STEPS=10

# 视频后端
VIDEO_BACKEND="pyav"

echo "=========================================="
echo "SmolVLA 训练测试 (不使用预训练模型)"
echo "=========================================="
echo "数据集: $DATASET_PATH"
echo "输出目录: $OUTPUT_DIR"
echo "训练步数: $STEPS (快速测试)"
echo "=========================================="
echo ""

# 检查数据集
if [ ! -d "$DATASET_PATH" ]; then
    echo "错误: 数据集不存在: $DATASET_PATH"
    exit 1
fi

# 开始训练 - 不使用预训练模型
echo "开始训练..."
python -m lerobot.scripts.lerobot_train \
    --policy.type smolvla \
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
    --policy.freeze_vision_encoder false \
    --policy.train_expert_only false \
    --policy.optimizer_lr $LR \
    --policy.scheduler_warmup_steps $WARMUP_STEPS \
    --policy.scheduler_decay_steps $DECAY_STEPS \
    --dataset.video_backend $VIDEO_BACKEND \
    --policy.push_to_hub false \
    --wandb.enable false

echo ""
echo "=========================================="
echo "训练完成！"
echo "=========================================="
