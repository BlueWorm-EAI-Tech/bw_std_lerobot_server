#!/bin/bash
# 启动 SmolVLA WebSocket 服务器

cd /home/lcjs-szw/repos/lerobot

MODEL_PATH="/home/lcjs-szw/repos/lerobot/outputs/train/smolvla_mantis_ft_20260214_163714/checkpoints/last/pretrained_model"
PORT=8001
DEVICE="cuda"
TASK="pick up the red block on each side of the white plate and place them into the white plate using both grippers alternately"

python scripts/websocket-act/websocket_smolvla_server.py \
    --model_path "$MODEL_PATH" \
    --port $PORT \
    --device $DEVICE \
    --task "$TASK"
