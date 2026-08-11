#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="${PI05_ENV_FILE:-$SCRIPT_DIR/server.env}"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

PI05_PYTHON="${PI05_PYTHON:-$REPO_ROOT/.venv-pi05/bin/python}"
PI05_MODEL_PATH="${PI05_MODEL_PATH:-}"
PI05_GPU="${PI05_GPU:-0}"
PI05_PORT="${PI05_PORT:-8005}"
PI05_HF_OFFLINE="${PI05_HF_OFFLINE:-1}"

if [[ "$PI05_PYTHON" != /* ]]; then
  PI05_PYTHON="$REPO_ROOT/$PI05_PYTHON"
fi

if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "nvidia-smi was not found. Install the NVIDIA driver first."
  exit 1
fi
if [ ! -x "$PI05_PYTHON" ]; then
  echo "PI05 Python does not exist: $PI05_PYTHON"
  echo "Run $SCRIPT_DIR/install_server.sh first."
  exit 1
fi
if [ -z "$PI05_MODEL_PATH" ] || [ ! -d "$PI05_MODEL_PATH" ]; then
  echo "PI05_MODEL_PATH is not a model directory: ${PI05_MODEL_PATH:-<empty>}"
  exit 1
fi

echo "NVIDIA GPUs:"
nvidia-smi --query-gpu=index,name,memory.total,driver_version --format=csv,noheader

if command -v ss >/dev/null 2>&1 && ss -ltn | awk '{print $4}' | grep -Eq "(^|:)${PI05_PORT}$"; then
  echo "Port $PI05_PORT is already in use. Choose another PI05_PORT."
  exit 1
fi

export CUDA_VISIBLE_DEVICES="$PI05_GPU"
export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export HF_HUB_OFFLINE="$PI05_HF_OFFLINE"
export TOKENIZERS_PARALLELISM=false

"$PI05_PYTHON" - "$PI05_MODEL_PATH" <<'PY'
import json
import sys
from pathlib import Path

import torch
from transformers import AutoTokenizer

model = Path(sys.argv[1]).expanduser().resolve()
required = (
    "config.json",
    "train_config.json",
    "model.safetensors",
    "policy_preprocessor.json",
    "policy_postprocessor.json",
)
missing = [name for name in required if not (model / name).is_file()]
if missing:
    raise SystemExit(f"Model is incomplete; missing: {', '.join(missing)}")

for name in ("config.json", "train_config.json"):
    data = json.loads((model / name).read_text())
    if data.get("compile_model") is not False:
        raise SystemExit(f"{name}: compile_model must be false")

processor = json.loads((model / "policy_preprocessor.json").read_text())
tokenizer_names = [
    step.get("config", {}).get("tokenizer_name")
    for step in processor.get("steps", [])
    if step.get("registry_name") == "tokenizer_processor"
]
for tokenizer_name in filter(None, tokenizer_names):
    AutoTokenizer.from_pretrained(tokenizer_name, local_files_only=True)
    print("tokenizer cache: OK", tokenizer_name)

print("model files: OK")
print("model path:", model)
print("torch:", torch.__version__)
print("torch CUDA runtime:", torch.version.cuda)
print("CUDA available:", torch.cuda.is_available())
print("visible GPUs:", torch.cuda.device_count())
if not torch.cuda.is_available():
    raise SystemExit("PyTorch cannot access CUDA")
PY

echo "PI05 server preflight passed."
