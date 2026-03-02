#!/bin/bash
# PI05训练包装脚本 - 处理目录冲突问题

set -e

cd /home/lcjs-szw/repos/lerobot

# 生成唯一的输出目录名
TIMESTAMP=$(date +%s%N)
OUTPUT_DIR="outputs/train/pi05_mantis_final_${TIMESTAMP}"

# 确保目录不存在
while [ -d "$OUTPUT_DIR" ]; do
    TIMESTAMP=$(date +%s%N)
    OUTPUT_DIR="outputs/train/pi05_mantis_final_${TIMESTAMP}"
done

echo "使用输出目录: $OUTPUT_DIR"

# 配置参数
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"

# 训练参数 - 匹配成功的 ACT 配置
BATCH_SIZE=8
STEPS=50000  # 50k步用于验证
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
echo "训练 π0.5 模型 (LeRobot 最终版本)"
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

# 开始训练 - 使用 lerobot 官方预训练模型和正确配置
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
    --policy.text_tokenizer_name "google/paligemma-3b-pt-224" \
    --policy.repo_id "pi05_mantis_trained" \
    --policy.push_to_hub false

echo "训练完成!"
echo "模型保存在: $OUTPUT_DIR"