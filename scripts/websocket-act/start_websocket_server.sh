#!/bin/bash
# Convenience script to start the WebSocket ACT server

# Default configuration
PORT=8000
HOST="0.0.0.0"
# MODEL_PATH="/home/lcjs-szw/repos/lerobot/outputs/train/act_your_dataset_20260117/checkpoints/last/pretrained_model"
# MODEL_PATH="/home/lcjs-szw/repos/lerobot/outputs/train/act_20260118_fixed_shoulder_roll_join/checkpoints/last/pretrained_model"
MODEL_PATH="/home/lcjs-szw/outputs/train/act_20260121/checkpoints/060000/pretrained_model"
DEVICE="cpu"
LOG_LEVEL="INFO"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --model_path)
            MODEL_PATH="$2"
            shift 2
            ;;
        --device)
            DEVICE="$2"
            shift 2
            ;;
        --log_level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --port PORT           Port to bind server (default: 8000)"
            echo "  --host HOST           Host address (default: 0.0.0.0)"
            echo "  --model_path PATH     Path to pretrained model"
            echo "  --device DEVICE       Device for inference (cpu/cuda/mps, default: cpu)"
            echo "  --log_level LEVEL     Log level (DEBUG/INFO/WARNING/ERROR, default: INFO)"
            echo "  --help                Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Check if model path exists
if [ ! -d "$MODEL_PATH" ]; then
    echo "Error: Model path does not exist: $MODEL_PATH"
    exit 1
fi

# Check if required files exist
if [ ! -f "$MODEL_PATH/config.json" ]; then
    echo "Error: config.json not found in model path"
    exit 1
fi

if [ ! -f "$MODEL_PATH/model.safetensors" ]; then
    echo "Error: model.safetensors not found in model path"
    exit 1
fi

# Print configuration
echo "=========================================="
echo "Starting ACT WebSocket Server"
echo "=========================================="
echo "Port:        $PORT"
echo "Host:        $HOST"
echo "Model Path:  $MODEL_PATH"
echo "Device:      $DEVICE"
echo "Log Level:   $LOG_LEVEL"
echo "=========================================="
echo ""

# Start the server
python websocket_act_server.py \
    --port "$PORT" \
    --host "$HOST" \
    --model_path "$MODEL_PATH" \
    --device "$DEVICE" \
    --log_level "$LOG_LEVEL"
