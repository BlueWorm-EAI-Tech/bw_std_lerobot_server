#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="${PI05_VENV_DIR:-$REPO_ROOT/.venv-pi05}"
UV_BIN="${PI05_UV_BIN:-}"

if [ -z "$UV_BIN" ]; then
  if command -v uv >/dev/null 2>&1; then
    UV_BIN="$(command -v uv)"
  elif [ -x "${HOME}/.local/bin/uv" ]; then
    UV_BIN="${HOME}/.local/bin/uv"
  else
    if ! command -v curl >/dev/null 2>&1; then
      echo "uv and curl were not found. Install either uv or curl first."
      exit 1
    fi
    echo "uv was not found; installing it with the official Astral installer."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    UV_BIN="${HOME}/.local/bin/uv"
  fi
fi

if [ ! -x "$UV_BIN" ]; then
  echo "uv executable does not exist: $UV_BIN"
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "Warning: ffmpeg is not installed. It is required for dataset/video workflows."
fi

echo "Using $($UV_BIN --version)"
echo "Synchronizing the locked PI05 environment at: $VENV_DIR"
UV_PROJECT_ENVIRONMENT="$VENV_DIR" \
  "$UV_BIN" sync \
    --project "$SCRIPT_DIR" \
    --locked \
    --no-dev

PYTHON="$VENV_DIR/bin/python"
"$UV_BIN" pip check --python "$PYTHON"
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

if torch.__version__.split("+")[0] != "2.7.1":
    raise SystemExit(f"Unexpected torch version: {torch.__version__}")
if not torch.cuda.is_available():
    raise SystemExit(
        "CUDA is not available. Install a driver compatible with the locked CUDA 12.8 runtime."
    )
PY

echo "PI05 server environment is ready: $VENV_DIR"
