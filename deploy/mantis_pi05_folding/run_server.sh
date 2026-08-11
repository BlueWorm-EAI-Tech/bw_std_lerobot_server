#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${PI05_ENV_FILE:-$SCRIPT_DIR/server.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing deployment config: $ENV_FILE"
  echo "Copy server.env.example to server.env and set PI05_MODEL_PATH."
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

PI05_PYTHON="${PI05_PYTHON:-$REPO_ROOT/.venv-pi05/bin/python}"
PI05_GPU="${PI05_GPU:-0}"
PI05_HOST="${PI05_HOST:-0.0.0.0}"
PI05_PORT="${PI05_PORT:-8005}"
PI05_TASK="${PI05_TASK:-Fold the black short-sleeve shirt.}"
PI05_HF_OFFLINE="${PI05_HF_OFFLINE:-1}"

if [[ "$PI05_PYTHON" != /* ]]; then
  PI05_PYTHON="$REPO_ROOT/$PI05_PYTHON"
fi

export CUDA_VISIBLE_DEVICES="$PI05_GPU"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE="$PI05_HF_OFFLINE"
export TOKENIZERS_PARALLELISM=false

exec "$PI05_PYTHON" \
  "$REPO_ROOT/scripts/websocket-server/pi05/websocket_pi05_server.py" \
  --host "$PI05_HOST" \
  --port "$PI05_PORT" \
  --model_path "$PI05_MODEL_PATH" \
  --device cuda \
  --task "$PI05_TASK" \
  --disable_joint_order_bridge
