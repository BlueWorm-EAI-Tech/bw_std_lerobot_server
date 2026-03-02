#!/bin/bash
# 使用 LeRobot 原生框架训练 π0.5 模型 for Mantis
# 完全仿照成功的 ACT 配置，确保参数一致性

set -e

cd /home/lcjs-szw/repos/lerobot

# 配置参数
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"
OUTPUT_DIR="outputs/train/pi05_mantis_final_$(date +%Y%m%d_%H%M%S)"

# 训练参数 - 调整 batch size 以适应 GPU 内存
BATCH_SIZE=2  # 减少到 2 以避免 CUDA OOM
STEPS=5000  # 快速验证训练
EVAL_FREQ=1000
SAVE_FREQ=1000
LOG_FREQ=200

# π0.5 特定参数 - 匹配 ACT 成功配置
CHUNK_SIZE=100
N_ACTION_STEPS=100
N_OBS_STEPS=1

# 学习率参数 - 使用保守的学习率
LR=1e-5
WARMUP_STEPS=1000
DECAY_STEPS=30000

# 状态和动作维度 - 精确匹配数据集（16维）
MAX_STATE_DIM=16
MAX_ACTION_DIM=16

# π0.5 模型配置
PALIGEMMA_VARIANT="gemma_2b"
ACTION_EXPERT_VARIANT="gemma_300m"
DTYPE="bfloat16"  # 使用 bfloat16 减少内存使用

# 视频后端 - 使用 pyav 而不是 torchcodec
VIDEO_BACKEND="pyav"

# Flow matching 参数
NUM_INFERENCE_STEPS=10

echo "=========================================="
echo "使用 LeRobot 原生框架训练 π0.5 for Mantis"
echo "完全仿照成功的 ACT 配置"
echo "=========================================="
echo "数据集: $DATASET_PATH"
echo "输出目录: $OUTPUT_DIR"
echo "批次大小: $BATCH_SIZE"
echo "训练步数: $STEPS"
echo "Chunk Size: $CHUNK_SIZE"
echo "Action Steps: $N_ACTION_STEPS"
echo "State Dim: $MAX_STATE_DIM"
echo "Action Dim: $MAX_ACTION_DIM"
echo "学习率: $LR"
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

# 开始训练 - 使用现有的 pi05 配置，通过参数覆盖实现自定义
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
    --wandb.enable false \
    --wandb.disable_artifact false

echo ""
echo "=========================================="
echo "✅ 训练完成！"
echo "模型保存在: $OUTPUT_DIR"
echo "=========================================="