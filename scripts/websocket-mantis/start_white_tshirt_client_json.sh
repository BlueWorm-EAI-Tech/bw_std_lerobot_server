#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="/home/lcjs-szw/repos/lerobot"
PYTHON_BIN="/home/lcjs-szw/miniforge3/pkgs/python-3.10.20-h3c07f61_0_cpython/bin/python3.10"
SITE_PACKAGES="/home/lcjs-szw/miniforge3/envs/lerobot/lib/python3.10/site-packages"
ENV_LIB="/home/lcjs-szw/miniforge3/envs/lerobot/lib"

SERVER="${SERVER:-ws://127.0.0.1:8005}"
FPS="${FPS:-10.0}"
ACTION_SPEED="${ACTION_SPEED:-0.3}"
MAX_ACTION_CHANGE="${MAX_ACTION_CHANGE:-0.1}"
JOINT_STATE_TOPIC="${JOINT_STATE_TOPIC:-/joint_states_fdb}"
JOINT_CMD_TOPIC="${JOINT_CMD_TOPIC:-/Teleop/joint_angle_solution}"

cd "$REPO_ROOT"

export PYTHONPATH="$SITE_PACKAGES:$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export LD_LIBRARY_PATH="$ENV_LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

ARGS=(
    scripts/websocket-mantis/mantis_websocket_client_json.py
    --server "$SERVER"
    --fps "$FPS"
    --action-speed "$ACTION_SPEED"
    --max-action-change "$MAX_ACTION_CHANGE"
    --joint-state-topic "$JOINT_STATE_TOPIC"
    --joint-cmd-topic "$JOINT_CMD_TOPIC"
)

exec "$PYTHON_BIN" "${ARGS[@]}"
