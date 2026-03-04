#!/bin/bash
# 使用 LeRobot 框架训练 Pi0.5 模型 for Mantis
# 注意: 机器人类型从数据集元数据中自动推断，无需额外指定

set -e

cd /home/lcjs-szw/repos/lerobot

# 配置参数
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"
OUTPUT_DIR="outputs/train/pi05_mantis_$(date +%Y%m%d_%H%M%S)"
PRETRAINED_MODEL="lerobot/pi05_base"  # 使用 HuggingFace 上的预训练模型

# 训练参数
BATCH_SIZE=4
STEPS=10000
EVAL_FREQ=1000
SAVE_FREQ=1000
LOG_FREQ=100

# 学习率参数
LR=2.5e-5
WARMUP_STEPS=1000
DECAY_STEPS=10000

echo "=========================================="
echo "使用 LeRobot 训练 Pi0.5 for Mantis"
echo "=========================================="
echo "数据集: $DATASET_PATH"
echo "输出目录: $OUTPUT_DIR"
echo "预训练模型: $PRETRAINED_MODEL"
echo "批次大小: $BATCH_SIZE"
echo "训练步数: $STEPS"
echo "=========================================="
echo ""

# 检查数据集
if [ ! -d "$DATASET_PATH" ]; then
    echo "错误: 数据集不存在: $DATASET_PATH"
    exit 1
fi

# 检查是否有 GPU
if ! python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "警告: 未检测到 GPU，训练将使用 CPU（速度会很慢）"
fi

# 开始训练
# 机器人类型从数据集元数据自动推断
python -m lerobot.scripts.lerobot_train \
    --policy.type=pi05 \
    --dataset.repo_id="$DATASET_PATH" \
    --dataset.root="$DATASET_PATH" \
    --pretrained_policy_name_or_path="$PRETRAINED_MODEL" \
    --output_dir="$OUTPUT_DIR" \
    training.offline_steps=$STEPS \
    training.batch_size=$BATCH_SIZE \
    training.eval_freq=$EVAL_FREQ \
    training.save_freq=$SAVE_FREQ \
    training.log_freq=$LOG_FREQ \
    training.save_checkpoint=true \
    policy.optimizer_lr=$LR \
    policy.scheduler_warmup_steps=$WARMUP_STEPS \
    policy.scheduler_decay_steps=$DECAY_STEPS \
    policy.n_obs_steps=1 \
    policy.chunk_size=15 \
    policy.n_action_steps=15 \
    policy.max_state_dim=32 \
    policy.max_action_dim=32 \
    wandb.enable=false

echo ""
echo "=========================================="
echo "训练完成！"
echo "模型保存在: $OUTPUT_DIR"
echo "=========================================="
