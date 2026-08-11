#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="${PI05_VENV_DIR:-$REPO_ROOT/.venv-pi05}"
PYTHON_BIN="${PI05_BOOTSTRAP_PYTHON:-python3.10}"
TORCH_INDEX_URL="${PI05_TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.10 was not found: $PYTHON_BIN"
  echo "Install python3.10 and python3.10-venv, or set PI05_BOOTSTRAP_PYTHON."
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Warning: ffmpeg is not installed. It is required for dataset/video workflows."
fi

if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

PYTHON="$VENV_DIR/bin/python"
"$PYTHON" -m pip install --upgrade pip setuptools wheel

# Install a CUDA build supported by the repository's torch/torchvision version ranges.
"$PYTHON" -m pip install \
  --index-url "$TORCH_INDEX_URL" \
  "torch==2.7.1" \
  "torchvision==0.22.1"

# Install the project without the broad optional extras, then add the PI05 server dependencies.
"$PYTHON" -m pip install -e "$REPO_ROOT"
"$PYTHON" -m pip install \
  "transformers==4.53.2" \
  "scipy==1.14.1" \
  "websockets==15.0.1" \
  "pytest==8.4.2"

"$PYTHON" -m pip check
"$PYTHON" - <<'PY'
import torch
import transformers
import websockets

print("python environment: OK")
print("torch:", torch.__version__)
print("torch CUDA runtime:", torch.version.cuda)
print("CUDA available:", torch.cuda.is_available())
print("visible GPUs:", torch.cuda.device_count())
print("transformers:", transformers.__version__)
print("websockets:", websockets.__version__)

if not torch.cuda.is_available():
    raise SystemExit(
        "CUDA is not available. Check the NVIDIA driver and PI05_TORCH_INDEX_URL before serving."
    )
PY

echo "PI05 server environment is ready: $VENV_DIR"
