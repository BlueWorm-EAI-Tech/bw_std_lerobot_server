#!/bin/bash
# 继续微调 SmolVLA 模型 for Mantis 机器人

set -e

cd /home/lcjs-szw/repos/lerobot

# ============ 配置参数 ============
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"

# Checkpoint 配置 - 指向 step 30000 的 train_config.json (继续训练)
CONFIG_PATH="/home/lcjs-szw/repos/lerobot/outputs/train/smolvla_mantis_ft_20260214_163714/checkpoints/030000/pretrained_model/train_config.json"

# 训练参数
BATCH_SIZE=2
STEPS=60000
EVAL_FREQ=5000
SAVE_FREQ=5000
LOG_FREQ=100

# SmolVLA 配置
CHUNK_SIZE=50
N_ACTION_STEPS=50
N_OBS_STEPS=1
MAX_STATE_DIM=32
MAX_ACTION_DIM=32

# 学习率
LR=1e-5
WARMUP_STEPS=500
DECAY_STEPS=60000

# 模型配置
NUM_INFERENCE_STEPS=10
VIDEO_BACKEND="pyav"

echo "=========================================="
echo "继续微调 SmolVLA for Mantis"
echo "=========================================="
echo "从 Checkpoint 恢复: $CONFIG_PATH"
echo "当前步数: 30000"
echo "目标步数: $STEPS"
echo "批次大小: $BATCH_SIZE"
echo "学习率: $LR"
echo "=========================================="

# 开始继续训练
python -m lerobot.scripts.lerobot_train \
    --config_path="$CONFIG_PATH" \
    --resume=true \
    --dataset.repo_id="$DATASET_PATH" \
    --steps=$STEPS \
    --batch_size=$BATCH_SIZE \
    --eval_freq=$EVAL_FREQ \
    --save_freq=$SAVE_FREQ \
    --log_freq=$LOG_FREQ \
    --save_checkpoint=true \
    --policy.n_obs_steps=$N_OBS_STEPS \
    --policy.chunk_size=$CHUNK_SIZE \
    --policy.n_action_steps=$N_ACTION_STEPS \
    --policy.max_state_dim=$MAX_STATE_DIM \
    --policy.max_action_dim=$MAX_ACTION_DIM \
    --policy.num_steps=$NUM_INFERENCE_STEPS \
    --policy.freeze_vision_encoder=true \
    --policy.train_expert_only=true \
    --policy.optimizer_lr=$LR \
    --policy.scheduler_warmup_steps=$WARMUP_STEPS \
    --policy.scheduler_decay_steps=$DECAY_STEPS \
    --dataset.video_backend=$VIDEO_BACKEND \
    --policy.push_to_hub=false \
    --wandb.enable=false
