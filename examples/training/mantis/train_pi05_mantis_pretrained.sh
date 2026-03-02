#!/bin/bash
# 使用 LeRobot pi05_base 预训练模型训练 π0.5 for Mantis
# 基于 lerobot/pi05_base 进行微调

set -e

cd /home/lcjs-szw/repos/lerobot

# 配置参数
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"
OUTPUT_DIR="outputs/train/pi05_mantis_base_ft_$(date +%Y%m%d_%H%M%S)"

# 训练参数
BATCH_SIZE=2  # 根据 GPU 内存调整
STEPS=60000   # 目标步数
EVAL_FREQ=5000
SAVE_FREQ=5000
LOG_FREQ=100

# π0.5 特定参数
CHUNK_SIZE=100
N_ACTION_STEPS=100
N_OBS_STEPS=1

# 学习率参数 - 微调时使用较小的学习率
LR=1e-5
WARMUP_STEPS=1000
DECAY_STEPS=30000

# 状态和动作维度 - 精确匹配 Mantis 数据集（16维）
MAX_STATE_DIM=16
MAX_ACTION_DIM=16

# π0.5 模型配置 - 使用预训练模型 (本地缓存路径)
PRETRAINED_PATH="$HOME/.cache/huggingface/hub/models--lerobot--pi05_base/snapshots/9e55186ad36e66b95cda57bc47818d9e6237ae30"
DTYPE="bfloat16"

# Flow matching 参数
NUM_INFERENCE_STEPS=10

# 视频后端
VIDEO_BACKEND="pyav"

echo "=========================================="
echo "使用 pi05_base 预训练模型微调 π0.5 for Mantis"
echo "=========================================="
echo "数据集: $DATASET_PATH"
echo "输出目录: $OUTPUT_DIR"
echo "预训练模型: $PRETRAINED_PATH"
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
    echo "错误: 数据集不存在: $DATASET_PATH"
    exit 1
fi

# 检查 GPU
if ! python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "警告: 未检测到 GPU，训练将使用 CPU（速度会很慢）"
    read -p "是否继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 开始训练 - 使用 pi05_base 预训练模型
echo "开始训练..."
python -m lerobot.scripts.lerobot_train \
    --policy.type pi05 \
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
    --policy.dtype $DTYPE \
    --policy.num_inference_steps $NUM_INFERENCE_STEPS \
    --policy.gradient_checkpointing true \
    --policy.compile_model false \
    --policy.freeze_vision_encoder false \
    --policy.train_expert_only false \
    --policy.optimizer_lr $LR \
    --policy.scheduler_warmup_steps $WARMUP_STEPS \
    --policy.scheduler_decay_steps $DECAY_STEPS \
    --policy.push_to_hub false \
    --policy.repo_id "pi05_mantis" \
    --dataset.video_backend $VIDEO_BACKEND \
    --wandb.enable false

echo ""
echo "=========================================="
echo "训练完成！"
echo "模型保存在: $OUTPUT_DIR"
echo "=========================================="
