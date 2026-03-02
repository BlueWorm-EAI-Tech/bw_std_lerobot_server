#!/bin/bash
# 使用纯 LeRobot 框架训练 π0.5 模型 for Mantis
# 完全按照 lerobot 标准，不依赖外部项目

set -e

cd /home/lcjs-szw/repos/lerobot

# 配置参数
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"
OUTPUT_DIR="outputs/train/pi05_mantis_clean_$(date +%Y%m%d_%H%M%S)"

# 训练参数 - 完全匹配成功的 ACT 配置
BATCH_SIZE=8
STEPS=50000  # 适中步数用于验证
EVAL_FREQ=10000
SAVE_FREQ=10000
LOG_FREQ=100

# π0.5 特定参数 - 严格匹配数据集和ACT配置
CHUNK_SIZE=100
N_ACTION_STEPS=100
N_OBS_STEPS=1

# 学习率参数 - 保守设置
LR=1e-5
WARMUP_STEPS=500
DECAY_STEPS=15000

# 状态和动作维度 - 精确匹配数据集（16维）
MAX_STATE_DIM=16
MAX_ACTION_DIM=16

# π0.5 模型配置
PALIGEMMA_VARIANT="gemma_2b"
ACTION_EXPERT_VARIANT="gemma_300m"
DTYPE="float32"

# Flow matching 参数
NUM_INFERENCE_STEPS=10

echo "=========================================="
echo "使用纯 LeRobot 框架训练 π0.5 for Mantis"
echo "完全按照 lerobot 标准配置"
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

# 检查GPU
if ! python -c "import torch; assert torch.cuda.is_available()" 2>/dev/null; then
    echo "⚠️  警告: 未检测到 GPU，训练将使用 CPU（速度会很慢）"
    read -p "是否继续? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 开始训练 - 纯 lerobot 方式，无预训练权重
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
    --policy.tokenizer_max_length 200 \
    --policy.text_tokenizer_name "google/paligemma-3b-pt-224" \
    --policy.gradient_checkpointing false \
    --policy.compile_model false \
    --policy.optimizer_lr $LR \
    --policy.scheduler_warmup_steps $WARMUP_STEPS \
    --policy.scheduler_decay_steps $DECAY_STEPS \
    --policy.push_to_hub false \
    --wandb.enable false \
    --wandb.disable_artifact false

echo ""
echo "=========================================="
echo "✅ 训练完成！"
echo "模型保存在: $OUTPUT_DIR"
echo "=========================================="