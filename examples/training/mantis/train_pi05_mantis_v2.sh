#!/bin/bash
# 使用 LeRobot 框架训练 Pi0.5 模型 for Mantis
# 参考成功的 ACT 训练配置

set -e

cd /home/lcjs-szw/repos/lerobot

# 配置参数
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"
OUTPUT_DIR="outputs/train/pi05_mantis_$(date +%Y%m%d_%H%M%S)"

# 训练参数 - 参考 ACT 的成功配置
BATCH_SIZE=8
STEPS=20000
EVAL_FREQ=2000
SAVE_FREQ=2000
LOG_FREQ=100

# 学习率参数 - 使用 π0.5 推荐的学习率
LR=2.5e-5
WARMUP_STEPS=1000
DECAY_STEPS=20000

# π0.5 特定参数
CHUNK_SIZE=50
N_ACTION_STEPS=50
N_OBS_STEPS=1

echo "=========================================="
echo "使用 LeRobot 训练 Pi0.5 for Mantis"
echo "=========================================="
echo "数据集: $DATASET_PATH"
echo "输出目录: $OUTPUT_DIR"
echo "批次大小: $BATCH_SIZE"
echo "训练步数: $STEPS"
echo "Chunk Size: $CHUNK_SIZE"
echo "Action Steps: $N_ACTION_STEPS"
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
    --policy.type=pi05 \
    --dataset.repo_id="$DATASET_PATH" \
    --output_dir="$OUTPUT_DIR" \
    --steps=$STEPS \
    --batch_size=$BATCH_SIZE \
    --eval_freq=$EVAL_FREQ \
    --save_freq=$SAVE_FREQ \
    --log_freq=$LOG_FREQ \
    --save_checkpoint=true \
    --policy.n_obs_steps=$N_OBS_STEPS \
    --policy.chunk_size=$CHUNK_SIZE \
    --policy.n_action_steps=$N_ACTION_STEPS \
    --policy.max_state_dim=16 \
    --policy.max_action_dim=16 \
    --policy.optimizer_lr=$LR \
    --policy.scheduler_warmup_steps=$WARMUP_STEPS \
    --policy.scheduler_decay_steps=$DECAY_STEPS \
    --policy.dtype="float32" \
    --policy.gradient_checkpointing=false \
    --policy.compile_model=false \
    --wandb.enable=false \
    --wandb.disable_artifact_upload=true

echo ""
echo "=========================================="
echo "✅ 训练完成！"
echo "模型保存在: $OUTPUT_DIR"
echo "=========================================="
