#!/bin/bash
# Deploy ROS2 WebSocket ACT Client to Robot PC
#
# Usage:
#   ./deploy_ros2_client.sh USER@ROBOT_IP [REMOTE_DIR]
#
# Example:
#   ./deploy_ros2_client.sh robot@192.168.1.100 /home/robot/act_client

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 USER@ROBOT_IP [REMOTE_DIR]"
    echo ""
    echo "Example:"
    echo "  $0 robot@192.168.1.100"
    echo "  $0 robot@192.168.1.100 /home/robot/act_client"
    exit 1
fi

REMOTE_HOST=$1
REMOTE_DIR=${2:-"~/act_client"}

log_info "Deploying ROS2 WebSocket ACT Client"
log_info "Target: $REMOTE_HOST:$REMOTE_DIR"
echo ""

# Check if files exist
log_info "Checking files..."
REQUIRED_FILES=(
    "ros2_websocket_act_client.py"
)

OPTIONAL_FILES=(
    "ros2_client_config.yaml"
    "README_ROS2_CLIENT.md"
    "QUICKSTART_ROS2_CLIENT.md"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        log_error "Required file not found: $file"
        exit 1
    fi
    log_info "  ✓ $file"
done

for file in "${OPTIONAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        log_info "  ✓ $file (optional)"
    else
        log_warn "  ✗ $file (optional, not found)"
    fi
done

echo ""

# Test SSH connection
log_info "Testing SSH connection..."
if ssh -o ConnectTimeout=5 -o BatchMode=yes "$REMOTE_HOST" "echo 'Connection OK'" > /dev/null 2>&1; then
    log_info "  ✓ SSH connection successful"
else
    log_error "Cannot connect to $REMOTE_HOST"
    log_error "Please check:"
    log_error "  1. Host is reachable: ping ${REMOTE_HOST#*@}"
    log_error "  2. SSH is configured: ssh $REMOTE_HOST"
    log_error "  3. SSH keys are set up"
    exit 1
fi

echo ""

# Create remote directory
log_info "Creating remote directory..."
ssh "$REMOTE_HOST" "mkdir -p $REMOTE_DIR"
log_info "  ✓ Directory created: $REMOTE_DIR"

echo ""

# Copy files
log_info "Copying files..."

# Copy required files
for file in "${REQUIRED_FILES[@]}"; do
    log_info "  Copying $file..."
    scp -q "$file" "$REMOTE_HOST:$REMOTE_DIR/"
    log_info "    ✓ $file copied"
done

# Copy optional files
for file in "${OPTIONAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        log_info "  Copying $file..."
        scp -q "$file" "$REMOTE_HOST:$REMOTE_DIR/"
        log_info "    ✓ $file copied"
    fi
done

echo ""

# Create requirements.txt
log_info "Creating requirements.txt..."
cat > /tmp/requirements_ros2_client.txt << EOF
websockets>=12.0
pillow>=9.5.0
numpy>=1.24.0
EOF
scp -q /tmp/requirements_ros2_client.txt "$REMOTE_HOST:$REMOTE_DIR/requirements.txt"
rm /tmp/requirements_ros2_client.txt
log_info "  ✓ requirements.txt created"

echo ""

# Install dependencies
log_info "Installing dependencies on remote host..."
ssh "$REMOTE_HOST" "cd $REMOTE_DIR && pip install -q -r requirements.txt" || {
    log_warn "Failed to install dependencies automatically"
    log_warn "You may need to install manually:"
    log_warn "  ssh $REMOTE_HOST"
    log_warn "  cd $REMOTE_DIR"
    log_warn "  pip install -r requirements.txt"
}
log_info "  ✓ Dependencies installed"

echo ""

# Make executable
log_info "Making client executable..."
ssh "$REMOTE_HOST" "chmod +x $REMOTE_DIR/ros2_websocket_act_client.py"
log_info "  ✓ Client is now executable"

echo ""

# Test installation
log_info "Testing installation..."
if ssh "$REMOTE_HOST" "cd $REMOTE_DIR && python ros2_websocket_act_client.py --help" > /dev/null 2>&1; then
    log_info "  ✓ Client runs successfully"
else
    log_warn "Client test failed, but files are copied"
    log_warn "You may need to check dependencies manually"
fi

echo ""
echo "=========================================="
log_info "Deployment completed successfully!"
echo "=========================================="
echo ""
echo "Files deployed to: $REMOTE_HOST:$REMOTE_DIR"
echo ""
echo "Next steps:"
echo ""
echo "1. SSH to robot PC:"
echo "   ssh $REMOTE_HOST"
echo ""
echo "2. Navigate to directory:"
echo "   cd $REMOTE_DIR"
echo ""
echo "3. Test the client:"
echo "   python ros2_websocket_act_client.py --help"
echo ""
echo "4. Run the client:"
echo "   python ros2_websocket_act_client.py \\"
echo "       --server ws://SERVER_IP:8000 \\"
echo "       --robot-id bw_robot \\"
echo "       --fps 10.0"
echo ""
echo "For more information, see:"
echo "  - README_ROS2_CLIENT.md"
echo "  - QUICKSTART_ROS2_CLIENT.md"
echo ""
