# Requirements: WebSocket ACT Inference System

## 1. Overview

Create a complete WebSocket-based inference system for trained ACT (Action Chunking Transformer) models, enabling real-time robot control through a client-server architecture.

## 2. User Stories

### 2.1 As a robotics researcher, I want to deploy trained ACT models as a WebSocket server
- So that I can serve inference requests from multiple clients
- So that I can maintain persistent connections with low latency
- So that I can process observations and return action chunks in real-time

### 2.2 As a robot operator, I want a ROS2 client that connects to the ACT server
- So that I can read observations from my robot's sensors
- So that I can send observations to the server for inference
- So that I can receive action chunks and execute them on my robot
- So that I can apply action smoothing and limiting for safe robot control

### 2.3 As a deployment engineer, I want automated deployment tools
- So that I can easily deploy the client to robot PCs
- So that I can configure the system for different network topologies
- So that I can troubleshoot common deployment issues

## 3. Acceptance Criteria

### 3.1 WebSocket Server Requirements

**3.1.1 Server Initialization**
- Server MUST load ACT model from specified checkpoint path
- Server MUST bind to configurable host and port (default: 0.0.0.0:8000)
- Server MUST support CPU and GPU inference
- Server MUST log initialization status and model configuration

**3.1.2 Model Configuration**
- Server MUST extract and validate model features (state, images, actions)
- Server MUST support multiple camera inputs with different resolutions
- Server MUST handle state vectors of configurable dimensions
- Server MUST report chunk size and action steps from model config

**3.1.3 WebSocket Communication**
- Server MUST accept WebSocket connections on specified port
- Server MUST handle JSON-formatted observation messages
- Server MUST support message sizes up to 10MB for high-resolution images
- Server MUST maintain persistent connections with clients
- Server MUST handle client disconnections gracefully

**3.1.4 Observation Processing**
- Server MUST accept observations with state vector and base64-encoded images
- Server MUST validate observation format and dimensions
- Server MUST decode base64 images and convert to tensors
- Server MUST apply preprocessing pipeline to observations
- Server MUST normalize inputs according to model requirements

**3.1.5 Inference Execution**
- Server MUST run ACT inference using `predict_action_chunk()` method
- Server MUST return action chunks of size specified by model config
- Server MUST apply postprocessing to denormalize actions
- Server MUST handle inference errors and return error messages

**3.1.6 Response Format**
- Server MUST return JSON response with action chunk array
- Server MUST include timing metrics (preprocessing, inference, postprocessing, total)
- Server MUST include chunk size and metadata in response
- Server MUST return error responses with descriptive messages

**3.1.7 Performance**
- Server MUST process observations and return actions within 100ms (target)
- Server MUST support concurrent connections from multiple clients
- Server MUST log performance metrics for monitoring

### 3.2 ROS2 Client Requirements

**3.2.1 Connection Management**
- Client MUST connect to WebSocket server at configurable URL
- Client MUST implement automatic reconnection with exponential backoff
- Client MUST handle connection failures gracefully
- Client MUST log connection status changes

**3.2.2 Robot Interface**
- Client MUST read observations from robot using BWRobot interface
- Client MUST read joint states (positions) from robot
- Client MUST capture images from multiple cameras
- Client MUST send actions to robot for execution

**3.2.3 Observation Encoding**
- Client MUST encode robot state as float array
- Client MUST encode camera images as base64 strings
- Client MUST construct JSON observation message matching server format
- Client MUST handle image encoding errors

**3.2.4 Action Chunking**
- Client MUST receive action chunks (100 actions) from server
- Client MUST store action chunks in local queue
- Client MUST pop one action per control cycle
- Client MUST request new chunk when queue is depleted

**3.2.5 Action Smoothing**
- Client MUST apply action smoothing: `smoothed = state + alpha * (action - state)`
- Client MUST support configurable smoothing factor (default: alpha=0.5)
- Client MUST smooth actions before execution

**3.2.6 Action Limiting**
- Client MUST limit maximum action change per step
- Client MUST support configurable max change (default: 0.3 radians)
- Client MUST clip action deltas to prevent sudden movements

**3.2.7 Control Loop**
- Client MUST run control loop at configurable frequency (default: 10Hz)
- Client MUST maintain consistent timing between control cycles
- Client MUST handle control loop errors without crashing

**3.2.8 Configuration**
- Client MUST support command-line arguments for all parameters
- Client MUST support YAML configuration file
- Client MUST allow runtime parameter adjustment

### 3.3 Deployment Requirements

**3.3.1 Deployment Script**
- Script MUST copy client files to robot PC via SCP
- Script MUST install Python dependencies on robot PC
- Script MUST set correct file permissions
- Script MUST test connection to server after deployment

**3.3.2 Documentation**
- Documentation MUST cover all deployment scenarios (same PC, separate PCs, cloud)
- Documentation MUST include systemd service configuration
- Documentation MUST provide troubleshooting guide
- Documentation MUST include quick start guide

**3.3.3 Configuration Management**
- System MUST provide example configuration files
- System MUST validate configuration on startup
- System MUST provide clear error messages for invalid configuration

### 3.4 Testing Requirements

**3.4.1 Server Testing**
- Test suite MUST verify server initialization
- Test suite MUST verify connection handling
- Test suite MUST verify observation processing
- Test suite MUST verify inference execution
- Test suite MUST verify error handling

**3.4.2 Client Testing**
- Test suite MUST verify connection management
- Test suite MUST verify action chunking
- Test suite MUST verify action smoothing
- Test suite MUST verify action limiting

**3.4.3 Integration Testing**
- Test suite MUST verify end-to-end communication
- Test suite MUST verify performance under load
- Test suite MUST verify error recovery

## 4. Technical Constraints

### 4.1 Model Compatibility
- System MUST work with ACT models trained using LeRobot framework
- System MUST support models with multiple camera inputs
- System MUST support variable state and action dimensions

### 4.2 Network Requirements
- System MUST work over local network (LAN)
- System MUST work over internet with proper port forwarding
- System MUST handle network latency up to 100ms

### 4.3 Performance Requirements
- Server MUST support at least 10 requests per second
- Client MUST maintain 10Hz control loop with <5% jitter
- End-to-end latency MUST be under 200ms (target: 100ms)

### 4.4 Compatibility
- Server MUST run on Python 3.10+
- Client MUST run on Python 3.10+
- System MUST work on Linux (Ubuntu 20.04+)
- System MUST support both CPU and GPU inference

## 5. Non-Functional Requirements

### 5.1 Reliability
- System MUST recover from temporary network failures
- System MUST handle invalid inputs without crashing
- System MUST log all errors for debugging

### 5.2 Maintainability
- Code MUST follow Python best practices (PEP 8)
- Code MUST include docstrings for all public functions
- Code MUST include type hints where appropriate

### 5.3 Usability
- System MUST provide clear startup messages
- System MUST provide helpful error messages
- System MUST include comprehensive documentation

### 5.4 Security
- System MUST validate all input data
- System MUST handle malformed messages safely
- System MUST log security-relevant events

## 6. Out of Scope

The following are explicitly out of scope for this implementation:

- Authentication and authorization
- Encryption (TLS/SSL)
- Multi-model serving
- Model hot-reloading
- Distributed inference
- Video streaming
- Data recording/logging
- Web-based UI
- REST API endpoints

## 7. Success Metrics

### 7.1 Functional Success
- Server successfully loads and serves ACT model
- Client successfully controls robot using server inference
- System handles 100+ consecutive control cycles without errors

### 7.2 Performance Success
- Average inference latency < 100ms
- Control loop maintains 10Hz ± 0.5Hz
- Network efficiency: < 1 request per second (via action chunking)

### 7.3 Deployment Success
- Deployment script successfully deploys to robot PC
- System runs for 1+ hour without manual intervention
- Documentation enables new users to deploy in < 30 minutes

## 8. Dependencies

### 8.1 External Dependencies
- LeRobot framework (for ACT model loading)
- websockets library (for WebSocket protocol)
- PyTorch (for model inference)
- NumPy (for array operations)
- PIL/OpenCV (for image processing)

### 8.2 Robot Dependencies
- BWRobot interface (for robot control)
- ROS2 (optional, for robot communication)
- Robot-specific drivers and libraries

## 9. References

- ACT Paper: "Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware"
- LeRobot Framework: https://github.com/huggingface/lerobot
- WebSocket Protocol: RFC 6455
- Reference HTTP client: `/home/lcjs/lerobot_act/client/act_client.py`
- Reference HTTP server: `/home/lcjs/lerobot_act/server/serve_act_simple.py`

## 10. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-17 | Kiro | Initial requirements document |
