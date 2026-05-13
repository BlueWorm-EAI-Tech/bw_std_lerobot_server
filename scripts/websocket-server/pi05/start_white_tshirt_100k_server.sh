#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="/home/lcjs-szw/repos/lerobot"
PYTHON_BIN="/home/lcjs-szw/miniforge3/pkgs/python-3.10.20-h3c07f61_0_cpython/bin/python3.10"
SITE_PACKAGES="/home/lcjs-szw/miniforge3/envs/lerobot/lib/python3.10/site-packages"
ENV_LIB="/home/lcjs-szw/miniforge3/envs/lerobot/lib"

MODEL_PATH="${MODEL_PATH:-/home/lcjs-szw/outputs/train/pi05_data20260428_white_tshirt_action_fixed_100k/checkpoints/last/pretrained_model}"
TASK="${TASK:-Fold the white t-shirt.}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8005}"
DEVICE="${DEVICE:-cuda}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

if [ ! -d "$MODEL_PATH" ]; then
    echo "错误: 模型目录不存在: $MODEL_PATH" >&2
    exit 1
fi

cd "$REPO_ROOT"

export PYTHONPATH="$SITE_PACKAGES:$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$ENV_LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export TOKENIZERS_PARALLELISM=false

exec "$PYTHON_BIN" scripts/websocket-server/pi05/websocket_pi05_server.py \
    --host "$HOST" \
    --port "$PORT" \
    --model_path "$MODEL_PATH" \
    --device "$DEVICE" \
    --task "$TASK" \
    --log_level "$LOG_LEVEL"
