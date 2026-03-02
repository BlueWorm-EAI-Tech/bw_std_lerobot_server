#!/bin/bash
# 使用 LeRobot 框架训练 PI05 模型 for Mantis 机器人
# 正确配置 Robot Processors 和数据集

set -e

cd /home/lcjs-szw/repos/lerobot

# ============ 配置参数 ============
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"
OUTPUT_DIR="outputs/train/pi05_mantis_$(date +%Y%m%d_%H%M%S)"

# 训练参数
BATCH_SIZE=2
STEPS=10000
EVAL_FREQ=2000
SAVE_FREQ=2000
LOG_FREQ=100

# PI05 特定参数（匹配 Mantis 16 DOF）
CHUNK_SIZE=100
N_ACTION_STEPS=100
N_OBS_STEPS=1
MAX_STATE_DIM=16
MAX_ACTION_DIM=16

# 学习率
LR=1e-5
WARMUP_STEPS=1000
DECAY_STEPS=30000

# 模型配置
PALIGEMMA_VARIANT="gemma_2b"
ACTION_EXPERT_VARIANT="gemma_300m"
DTYPE="bfloat16"
NUM_INFERENCE_STEPS=10

# 视频后端
VIDEO_BACKEND="pyav"

echo "=========================================="
echo "使用 LeRobot 框架训练 PI05 for Mantis"
echo "=========================================="
echo "数据集: $DATASET_PATH"
echo "输出目录: $OUTPUT_DIR"
echo "批次大小: $BATCH_SIZE"
echo "训练步数: $STEPS"
echo "Chunk Size: $CHUNK_SIZE"
echo "State Dim: $MAX_STATE_DIM"
echo "Action Dim: $MAX_ACTION_DIM"
echo "归一化: QUANTILES (PI05 默认)"
echo "=========================================="
echo ""

# 检查数据集
if [ ! -d "$DATASET_PATH" ]; then
    echo "错误: 数据集不存在: $DATASET_PATH"
    exit 1
fi

# 开始训练
echo "开始训练..."
python -m lerobot.scripts.lerobot_train \
    --policy.type pi05 \
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
    --policy.paligemma_variant $PALIGEMMA_VARIANT \
    --policy.action_expert_variant $ACTION_EXPERT_VARIANT \
    --policy.dtype $DTYPE \
    --policy.num_inference_steps $NUM_INFERENCE_STEPS \
    --policy.gradient_checkpointing true \
    --policy.compile_model false \
    --policy.optimizer_lr $LR \
    --policy.scheduler_warmup_steps $WARMUP_STEPS \
    --policy.scheduler_decay_steps $DECAY_STEPS \
    --dataset.video_backend $VIDEO_BACKEND \
    --policy.push_to_hub false \
    --wandb.enable false

echo ""
echo "=========================================="
echo "训练完成！"
echo "模型保存在: $OUTPUT_DIR"
echo "=========================================="
