#!/bin/bash
# 评估训练好的 Pi0.5 模型

set -e

cd /home/lcjs-szw/repos/lerobot

# 配置参数
if [ -z "$1" ]; then
    echo "用法: $0 <checkpoint_path>"
    echo "示例: $0 outputs/train/pi05_mantis_20260212_120000/checkpoints/last/pretrained_model"
    exit 1
fi

CHECKPOINT_PATH="$1"
DATASET_PATH="/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"
OUTPUT_DIR="outputs/eval/pi05_mantis_$(date +%Y%m%d_%H%M%S)"

# 评估参数
NUM_EPISODES=10

echo "=========================================="
echo "评估 Pi0.5 模型"
echo "=========================================="
echo "模型路径: $CHECKPOINT_PATH"
echo "数据集: $DATASET_PATH"
echo "输出目录: $OUTPUT_DIR"
echo "评估轮数: $NUM_EPISODES"
echo "=========================================="
echo ""

# 检查模型
if [ ! -d "$CHECKPOINT_PATH" ]; then
    echo "❌ 错误: 模型不存在: $CHECKPOINT_PATH"
    exit 1
fi

# 开始评估
echo "开始评估..."
python -m lerobot.scripts.lerobot_eval \
    --policy.path="$CHECKPOINT_PATH" \
    --dataset.repo_id="$DATASET_PATH" \
    --output_dir="$OUTPUT_DIR" \
    --eval.n_episodes=$NUM_EPISODES \
    --eval.batch_size=1

echo ""
echo "=========================================="
echo "✅ 评估完成！"
echo "结果保存在: $OUTPUT_DIR"
echo "=========================================="
