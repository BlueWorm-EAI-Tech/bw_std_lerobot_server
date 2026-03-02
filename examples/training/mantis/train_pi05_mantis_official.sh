#!/bin/bash
# 使用 LeRobot 官方框架和预训练模型训练 π0.5 模型 for Mantis
# 完全遵循 lerobot 标准，不使用任何外部项目代码

set -e

cd /home/lcjs-szw/repos/lerobot

# 配置参数
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"
OUTPUT_DIR="outputs/train/pi05_mantis_official_$(date +%s)"

# 训练参数 - 匹配成功的 ACT 配置
BATCH_SIZE=8
STEPS=50000  # 减少步数用于快速验证
EVAL_FREQ=10000
SAVE_FREQ=10000
LOG_FREQ=100

# π0.5 特定参数 - 匹配数据集
CHUNK_SIZE=100
N_ACTION_STEPS=100
N_OBS_STEPS=1

# 学习率参数 - 微调设置
LR=1e-5
WARMUP_STEPS=500
DECAY_STEPS=15000

# 状态和动作维度 - 精确匹配数据集
MAX_STATE_DIM=16
MAX_ACTION_DIM=16

# π0.5 模型配置 - 使用 lerobot 官方预训练模型
PRETRAINED_PATH="lerobot/pi05_base"
DTYPE="bfloat16"

# Flow matching 参数
NUM_INFERENCE_STEPS=10

echo "=============================="
echo "训练 π0.5 模型 (LeRobot 官方版本)"
echo "=============================="
echo "数据集: $DATASET_PATH"
echo "输出目录: $OUTPUT_DIR"
echo "预训练模型: $PRETRAINED_PATH"
echo "批次大小: $BATCH_SIZE"
echo "训练步数: $STEPS"
echo "学习率: $LR"
echo "=============================="

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

# 开始训练 - 使用 lerobot 官方预训练模型
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
    --resume false \
    --policy.n_obs_steps $N_OBS_STEPS \
    --policy.chunk_size $CHUNK_SIZE \
    --policy.n_action_steps $N_ACTION_STEPS \
    --policy.max_state_dim $MAX_STATE_DIM \
    --policy.max_action_dim $MAX_ACTION_DIM \
    --policy.pretrained_path $PRETRAINED_PATH \
    --policy.dtype $DTYPE \
    --policy.num_inference_steps $NUM_INFERENCE_STEPS \
    --policy.gradient_checkpointing true \
    --policy.compile_model true \
    --policy.optimizer_lr $LR \
    --policy.scheduler_warmup_steps $WARMUP_STEPS \
    --policy.scheduler_decay_steps $DECAY_STEPS \
    --policy.text_tokenizer_name "google/paligemma-3b-pt-224"

echo "训练完成!"
echo "模型保存在: $OUTPUT_DIR"