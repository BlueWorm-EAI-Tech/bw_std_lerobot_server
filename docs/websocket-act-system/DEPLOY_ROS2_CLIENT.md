# Deploying ROS2 Client to Robot PC

Guide for copying and setting up the ROS2 WebSocket ACT client on your Robot PC.

## Quick Deploy (Recommended)

### Option 1: Using the Deploy Script

```bash
# On your development PC, run:
./deploy_ros2_client.sh robot@192.168.1.100 /home/robot/act_client

# This will:
# 1. Copy all necessary files
# 2. Install dependencies
# 3. Set up the client
```

### Option 2: Manual Copy with SCP

```bash
# Copy files to robot PC
scp ros2_websocket_act_client.py robot@192.168.1.100:~/act_client/
scp ros2_client_config.yaml robot@192.168.1.100:~/act_client/
scp README_ROS2_CLIENT.md robot@192.168.1.100:~/act_client/
scp QUICKSTART_ROS2_CLIENT.md robot@192.168.1.100:~/act_client/

# SSH to robot PC
ssh robot@192.168.1.100

# Install dependencies
pip install websockets pillow numpy

# Make executable
chmod +x ~/act_client/ros2_websocket_act_client.py

# Test
cd ~/act_client
python ros2_websocket_act_client.py --help
```

### Option 3: Using rsync (Best for Updates)

```bash
# Sync entire directory
rsync -avz --progress \
    ros2_websocket_act_client.py \
    ros2_client_config.yaml \
    README_ROS2_CLIENT.md \
    QUICKSTART_ROS2_CLIENT.md \
    robot@192.168.1.100:~/act_client/

# SSH and setup
ssh robot@192.168.1.100
cd ~/act_client
pip install websockets pillow numpy
chmod +x ros2_websocket_act_client.py
```

## Files to Copy

### Essential Files (Required)
```
ros2_websocket_act_client.py    # Main client script
```

### Configuration Files (Recommended)
```
ros2_client_config.yaml          # Configuration template
```

### Documentation Files (Optional)
```
README_ROS2_CLIENT.md            # Complete documentation
QUICKSTART_ROS2_CLIENT.md        # Quick start guide
```

## Step-by-Step Deployment

### Step 1: Prepare Files on Development PC

```bash
# Create a deployment package
mkdir -p ros2_client_deploy
cp ros2_websocket_act_client.py ros2_client_deploy/
cp ros2_client_config.yaml ros2_client_deploy/
cp README_ROS2_CLIENT.md ros2_client_deploy/
cp QUICKSTART_ROS2_CLIENT.md ros2_client_deploy/

# Create requirements file
cat > ros2_client_deploy/requirements.txt << EOF
websockets>=12.0
pillow>=9.5.0
numpy>=1.24.0
EOF
```

### Step 2: Copy to Robot PC

```bash
# Using SCP
scp -r ros2_client_deploy robot@ROBOT_IP:~/act_client

# Or using rsync (better for updates)
rsync -avz --progress ros2_client_deploy/ robot@ROBOT_IP:~/act_client/
```

### Step 3: Setup on Robot PC

```bash
# SSH to robot
ssh robot@ROBOT_IP

# Navigate to directory
cd ~/act_client

# Install dependencies
pip install -r requirements.txt

# Or install manually
pip install websockets pillow numpy

# Make executable
chmod +x ros2_websocket_act_client.py

# Test installation
python ros2_websocket_act_client.py --help
```

### Step 4: Configure

```bash
# Edit configuration (optional)
nano ros2_client_config.yaml

# Update server URL to point to your server PC
# Change: url: "ws://localhost:8000"
# To:     url: "ws://SERVER_IP:8000"
```

### Step 5: Test Connection

```bash
# Test connection to server
python ros2_websocket_act_client.py \
    --server ws://SERVER_IP:8000 \
    --robot-id bw_robot \
    --fps 10.0
```

## Network Setup

### Same Machine (Development)
```bash
# Server and client on same PC
python ros2_websocket_act_client.py --server ws://localhost:8000
```

### Different Machines (Production)
```bash
# Server on PC A (192.168.1.100)
# Client on Robot PC B (192.168.1.101)

# On Robot PC:
python ros2_websocket_act_client.py --server ws://192.168.1.100:8000
```

### Firewall Configuration

```bash
# On server PC, allow port 8000
sudo ufw allow 8000/tcp

# Or for specific IP
sudo ufw allow from 192.168.1.101 to any port 8000
```

## Deployment Scenarios

### Scenario 1: Development (Same PC)

```
┌─────────────────────────────────┐
│      Development PC              │
│                                  │
│  ┌──────────┐  ┌──────────┐    │
│  │  Server  │  │  Client  │    │
│  │  :8000   │  │          │    │
│  └────┬─────┘  └────┬─────┘    │
│       │             │            │
│       └─────────────┘            │
│       localhost:8000             │
└─────────────────────────────────┘
```

**Setup:**
```bash
# Terminal 1: Server
./start_websocket_server.sh

# Terminal 2: Client
python ros2_websocket_act_client.py --server ws://localhost:8000
```

### Scenario 2: Production (Separate PCs)

```
┌──────────────────┐         ┌──────────────────┐
│   Server PC      │         │    Robot PC      │
│   192.168.1.100  │         │   192.168.1.101  │
│                  │         │                  │
│  ┌──────────┐   │         │  ┌──────────┐   │
│  │  Server  │   │         │  │  Client  │   │
│  │  :8000   │   │         │  │  +Robot  │   │
│  └────┬─────┘   │         │  └────┬─────┘   │
│       │         │         │       │          │
└───────┼─────────┘         └───────┼──────────┘
        │                           │
        └───────────────────────────┘
           Network: 192.168.1.0/24
```

**Setup:**
```bash
# On Server PC (192.168.1.100):
./start_websocket_server.sh

# On Robot PC (192.168.1.101):
python ros2_websocket_act_client.py --server ws://192.168.1.100:8000
```

### Scenario 3: Cloud Server

```
┌──────────────────┐         ┌──────────────────┐
│   Cloud Server   │         │    Robot PC      │
│   (Internet)     │         │   (Local)        │
│                  │         │                  │
│  ┌──────────┐   │         │  ┌──────────┐   │
│  │  Server  │   │         │  │  Client  │   │
│  │  :8000   │   │         │  │  +Robot  │   │
│  └────┬─────┘   │         │  └────┬─────┘   │
│       │         │         │       │          │
└───────┼─────────┘         └───────┼──────────┘
        │                           │
        └───────────────────────────┘
              Internet/VPN
```

**Setup:**
```bash
# On Cloud Server:
./start_websocket_server.sh --host 0.0.0.0 --port 8000

# On Robot PC:
python ros2_websocket_act_client.py --server ws://cloud.example.com:8000
```

## Troubleshooting

### Issue: Permission Denied

```bash
# Fix permissions
chmod +x ros2_websocket_act_client.py
```

### Issue: Module Not Found

```bash
# Install dependencies
pip install websockets pillow numpy

# Or with specific versions
pip install websockets==12.0 pillow==9.5.0 numpy==1.24.0
```

### Issue: Connection Refused

```bash
# Check server is running
ping SERVER_IP
telnet SERVER_IP 8000

# Check firewall
sudo ufw status
sudo ufw allow 8000/tcp
```

### Issue: Import Error (lerobot_robot_bw)

```bash
# Make sure robot library is installed
pip install -e /path/to/robot/library

# Or add to Python path
export PYTHONPATH=/path/to/robot/library:$PYTHONPATH
```

## Automated Deployment

### Using Ansible (Advanced)

```yaml
# deploy_client.yml
---
- hosts: robot_pc
  tasks:
    - name: Create directory
      file:
        path: ~/act_client
        state: directory
    
    - name: Copy client files
      copy:
        src: "{{ item }}"
        dest: ~/act_client/
      with_items:
        - ros2_websocket_act_client.py
        - ros2_client_config.yaml
    
    - name: Install dependencies
      pip:
        name:
          - websockets
          - pillow
          - numpy
    
    - name: Make executable
      file:
        path: ~/act_client/ros2_websocket_act_client.py
        mode: '0755'
```

Run with:
```bash
ansible-playbook -i robot_pc, deploy_client.yml
```

## Updates and Maintenance

### Updating the Client

```bash
# On development PC, after making changes:
rsync -avz --progress \
    ros2_websocket_act_client.py \
    robot@ROBOT_IP:~/act_client/

# On robot PC:
# No need to reinstall dependencies
# Just restart the client
```

### Version Control

```bash
# Add version to client
echo "VERSION = '1.0.0'" >> ros2_websocket_act_client.py

# Check version on robot
ssh robot@ROBOT_IP "cd ~/act_client && python -c 'import ros2_websocket_act_client; print(ros2_websocket_act_client.VERSION)'"
```

## Production Checklist

Before deploying to production:

- [ ] Test on development PC first
- [ ] Copy all required files
- [ ] Install dependencies
- [ ] Configure server URL
- [ ] Test network connectivity
- [ ] Configure firewall
- [ ] Test with robot
- [ ] Set up automatic startup (systemd)
- [ ] Configure logging
- [ ] Set up monitoring

## Automatic Startup (systemd)

Create a systemd service for automatic startup:

```bash
# On robot PC, create service file
sudo nano /etc/systemd/system/act-client.service
```

```ini
[Unit]
Description=ACT WebSocket Client
After=network.target

[Service]
Type=simple
User=robot
WorkingDirectory=/home/robot/act_client
ExecStart=/usr/bin/python3 /home/robot/act_client/ros2_websocket_act_client.py --server ws://192.168.1.100:8000 --robot-id bw_robot
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable act-client
sudo systemctl start act-client

# Check status
sudo systemctl status act-client

# View logs
sudo journalctl -u act-client -f
```

## Summary

**Quick Deploy:**
```bash
# 1. Copy files
scp ros2_websocket_act_client.py robot@ROBOT_IP:~/

# 2. SSH and setup
ssh robot@ROBOT_IP
pip install websockets pillow numpy
chmod +x ros2_websocket_act_client.py

# 3. Run
python ros2_websocket_act_client.py --server ws://SERVER_IP:8000
```

**That's it! Your client is deployed and ready to use! 🚀**
