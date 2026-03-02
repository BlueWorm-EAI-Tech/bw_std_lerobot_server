#!/bin/bash
# 使用 LeRobot 原生框架训练 PI05 模型 for Mantis
# 参考成功 ACT 训练的配置

set -e

cd /home/lcjs-szw/repos/lerobot

# 激活 conda 环境
source /home/lcjs-szw/miniforge3/etc/profile.d/conda.sh
conda activate lerobot

# 配置参数
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"
OUTPUT_DIR="outputs/train/pi05_mantis_lerobot_$(date +%Y%m%d_%H%M%S)"

# 训练参数 - 匹配成功 ACT 配置
BATCH_SIZE=8
STEPS=100000  # 与 ACT 一致
EVAL_FREQ=20000
SAVE_FREQ=20000
LOG_FREQ=200

# PI05 特定参数 - 匹配 ACT 的 chunk_size 配置
CHUNK_SIZE=100
N_ACTION_STEPS=100
N_OBS_STEPS=1

# 学习率参数 - 保守设置用于微调
LR=1e-5  # 匹配 ACT 成功的学习率
WARMUP_STEPS=1000
DECAY_STEPS=30000

# 状态和动作维度 - 匹配数据集 (16维)
MAX_STATE_DIM=16
MAX_ACTION_DIM=16

# PI05 模型配置
PALIGEMMA_VARIANT="gemma_2b"
ACTION_EXPERT_VARIANT="gemma_300m"
DTYPE="float32"

# Flow matching 参数
NUM_INFERENCE_STEPS=10

# 数据集配置
VIDEO_BACKEND="torchcodec"

echo "=========================================="
echo "使用 LeRobot 原生框架训练 PI05 for Mantis"
echo "=========================================="
echo "数据集: $DATASET_PATH"
echo "输出目录: $OUTPUT_DIR"
echo "批次大小: $BATCH_SIZE"
echo "训练步数: $STEPS"
echo "Chunk Size: $CHUNK_SIZE"
echo "Action Steps: $N_ACTION_STEPS"
echo "Obs Steps: $N_OBS_STEPS"
echo "State Dim: $MAX_STATE_DIM"
echo "Action Dim: $MAX_ACTION_DIM"
echo "PaliGemma: $PALIGEMMA_VARIANT"
echo "Action Expert: $ACTION_EXPERT_VARIANT"
echo "Learning Rate: $LR"
echo "=========================================="
echo ""

# 检查数据集
if [ ! -d "$DATASET_PATH" ]; then
    echo "❌ 错误: 数据集不存在: $DATASET_PATH"
    exit 1
fi

# 检查是否有 GPU
if ! python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "⚠️  警告: 未检测到 GPU，训练将使用 CPU（速度会很慢）"
    read -p "是否继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 开始训练
echo "开始训练..."
python -m lerobot.scripts.lerobot_train \
    policy.type=pi05 \
    dataset.repo_id="$DATASET_PATH" \
    output_dir="$OUTPUT_DIR" \
    steps=$STEPS \
    batch_size=$BATCH_SIZE \
    eval_freq=$EVAL_FREQ \
    save_freq=$SAVE_FREQ \
    log_freq=$LOG_FREQ \
    save_checkpoint=true \
    resume=false \
    policy.n_obs_steps=$N_OBS_STEPS \
    policy.chunk_size=$CHUNK_SIZE \
    policy.n_action_steps=$N_ACTION_STEPS \
    policy.max_state_dim=$MAX_STATE_DIM \
    policy.max_action_dim=$MAX_ACTION_DIM \
    policy.paligemma_variant=$PALIGEMMA_VARIANT \
    policy.action_expert_variant=$ACTION_EXPERT_VARIANT \
    policy.dtype=$DTYPE \
    policy.num_inference_steps=$NUM_INFERENCE_STEPS \
    policy.gradient_checkpointing=false \
    policy.compile_model=false \
    policy.optimizer_lr=$LR \
    policy.scheduler_warmup_steps=$WARMUP_STEPS \
    policy.scheduler_decay_steps=$DECAY_STEPS \
    dataset.video_backend=$VIDEO_BACKEND \
    num_workers=4 \
    wandb.enable=false

echo ""
echo "=========================================="
echo "✅ 训练完成！"
echo "模型保存在: $OUTPUT_DIR"
echo "=========================================="
