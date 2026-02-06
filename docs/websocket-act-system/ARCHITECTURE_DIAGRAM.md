# WebSocket ACT Server - Architecture Diagrams

Visual representations of the WebSocket ACT server architecture and data flow.

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Applications                          │
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   Python     │  │  JavaScript  │  │    Robot     │              │
│  │   Client     │  │  Web Client  │  │  Controller  │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                  │                  │                       │
└─────────┼──────────────────┼──────────────────┼───────────────────────┘
          │                  │                  │
          │    WebSocket (JSON over TCP)        │
          │    Port 8000                        │
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼───────────────────────┐
│                    WebSocket ACT Server                                │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  Connection Handler                           │   │
│  │  - Accept WebSocket connections                              │   │
│  │  - Parse JSON requests                                       │   │
│  │  - Route to inference pipeline                               │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                           │
│  ┌────────────────────────▼─────────────────────────────────────┐   │
│  │              Observation Parser                               │   │
│  │  - Decode base64 images                                      │   │
│  │  - Convert JSON to tensors                                   │   │
│  │  - Validate input shapes                                     │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                           │
│  ┌────────────────────────▼─────────────────────────────────────┐   │
│  │              Preprocessor Pipeline                            │   │
│  │  - Normalize observations                                    │   │
│  │  - Batch data                                                │   │
│  │  - Move to device (GPU/CPU)                                  │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                           │
│  ┌────────────────────────▼─────────────────────────────────────┐   │
│  │                  ACT Model                                    │   │
│  │  ┌────────────────────────────────────────────────────────┐ │   │
│  │  │  Vision Backbone (ResNet)                              │ │   │
│  │  │  - Extract image features                              │ │   │
│  │  └────────────────────────────────────────────────────────┘ │   │
│  │  ┌────────────────────────────────────────────────────────┐ │   │
│  │  │  Transformer Encoder                                   │ │   │
│  │  │  - Process observations                                │ │   │
│  │  └────────────────────────────────────────────────────────┘ │   │
│  │  ┌────────────────────────────────────────────────────────┐ │   │
│  │  │  Transformer Decoder                                   │ │   │
│  │  │  - Generate action sequence                            │ │   │
│  │  └────────────────────────────────────────────────────────┘ │   │
│  │  ┌────────────────────────────────────────────────────────┐ │   │
│  │  │  Action Head                                           │ │   │
│  │  │  - Output action chunk                                 │ │   │
│  │  └────────────────────────────────────────────────────────┘ │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                           │
│  ┌────────────────────────▼─────────────────────────────────────┐   │
│  │              Postprocessor Pipeline                           │   │
│  │  - Unnormalize actions                                       │   │
│  │  - Move to CPU                                               │   │
│  │  - Convert to list                                           │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                           │
│  ┌────────────────────────▼─────────────────────────────────────┐   │
│  │              Response Builder                                 │   │
│  │  - Format action chunk                                       │   │
│  │  - Add timing metrics                                        │   │
│  │  - Encode as JSON                                            │   │
│  └────────────────────────┬─────────────────────────────────────┘   │
│                           │                                           │
└───────────────────────────┼───────────────────────────────────────────┘
                           │
                           ▼
                    JSON Response
```

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Input Data                                   │
└─────────────────────────────────────────────────────────────────────┘

    Robot State          Camera Images         Environment State
    [14 floats]          [640x480x3 RGB]       [optional]
         │                     │                      │
         │                     │                      │
         ▼                     ▼                      ▼
    ┌────────────────────────────────────────────────────┐
    │              JSON Encoding                         │
    │  - State: [0.1, 0.2, ...]                         │
    │  - Images: base64_encode(PNG)                     │
    │  - Env: [0.5, 0.6, ...]                          │
    └────────────────────┬───────────────────────────────┘
                        │
                        ▼
    ┌────────────────────────────────────────────────────┐
    │         WebSocket Message (JSON)                   │
    │  {                                                 │
    │    "observation": {                                │
    │      "observation.state": [...],                   │
    │      "observation.images.front": "base64...",      │
    │      "observation.environment_state": [...]        │
    │    },                                              │
    │    "timestep": 0                                   │
    │  }                                                 │
    └────────────────────┬───────────────────────────────┘
                        │
                        ▼
    ┌────────────────────────────────────────────────────┐
    │              Server Processing                     │
    │                                                    │
    │  1. Parse JSON                                     │
    │     └─> Extract fields                             │
    │                                                    │
    │  2. Decode Images                                  │
    │     └─> base64 → PIL → numpy → tensor             │
    │                                                    │
    │  3. Preprocess                                     │
    │     └─> Normalize, batch, to device                │
    │                                                    │
    │  4. Inference                                      │
    │     └─> ACT model forward pass                     │
    │                                                    │
    │  5. Postprocess                                    │
    │     └─> Unnormalize, to CPU, to list               │
    │                                                    │
    └────────────────────┬───────────────────────────────┘
                        │
                        ▼
    ┌────────────────────────────────────────────────────┐
    │         WebSocket Response (JSON)                  │
    │  {                                                 │
    │    "action_chunk": [                               │
    │      [0.1, 0.2, ...],  // Action at t+0            │
    │      [0.15, 0.25, ...], // Action at t+1           │
    │      ...                                           │
    │    ],                                              │
    │    "timestep": 0,                                  │
    │    "inference_time_ms": 33.5,                      │
    │    "chunk_size": 100,                              │
    │    "action_dim": 14                                │
    │  }                                                 │
    └────────────────────┬───────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         Output Data                                  │
│                                                                      │
│  Action Chunk: 100 actions × 14 dimensions                          │
│  - Each action controls robot joints                                │
│  - Client executes actions sequentially                             │
└─────────────────────────────────────────────────────────────────────┘
```

## Timing Diagram

```
Client                                    Server
  │                                         │
  │ t=0ms: Connect                          │
  │────────────────────────────────────────>│
  │                                         │
  │ t=5ms: Send Observation (JSON)          │
  │────────────────────────────────────────>│
  │                                         │ t=7ms: Receive
  │                                         │ t=8ms: Parse JSON (1ms)
  │                                         │ t=11ms: Decode Images (3ms)
  │                                         │ t=19ms: Preprocess (8ms)
  │                                         │ t=44ms: Inference (25ms)
  │                                         │ t=49ms: Postprocess (5ms)
  │                                         │ t=51ms: Encode JSON (2ms)
  │ t=53ms: Receive Response                │
  │<────────────────────────────────────────│
  │                                         │
  │ Total Round Trip: 48ms                  │
  │ Server Processing: 44ms                 │
  │ Network Latency: 4ms                    │
  │                                         │
```

## Component Interaction

```
┌─────────────────────────────────────────────────────────────────────┐
│                    WebSocket Server Components                       │
│                                                                      │
│  ┌────────────────┐                                                 │
│  │  Main Server   │                                                 │
│  │  - asyncio     │                                                 │
│  │  - websockets  │                                                 │
│  └───────┬────────┘                                                 │
│          │                                                           │
│          │ creates                                                   │
│          ▼                                                           │
│  ┌────────────────┐         ┌──────────────────┐                   │
│  │ Connection     │◄────────│  Client Socket   │                   │
│  │ Handler        │         └──────────────────┘                   │
│  └───────┬────────┘                                                 │
│          │                                                           │
│          │ uses                                                      │
│          ▼                                                           │
│  ┌────────────────┐         ┌──────────────────┐                   │
│  │ Observation    │◄────────│  Image Decoder   │                   │
│  │ Parser         │         └──────────────────┘                   │
│  └───────┬────────┘                                                 │
│          │                                                           │
│          │ feeds                                                     │
│          ▼                                                           │
│  ┌────────────────┐         ┌──────────────────┐                   │
│  │ Preprocessor   │◄────────│  Normalizer      │                   │
│  │ Pipeline       │         └──────────────────┘                   │
│  └───────┬────────┘                                                 │
│          │                                                           │
│          │ inputs to                                                 │
│          ▼                                                           │
│  ┌────────────────┐         ┌──────────────────┐                   │
│  │  ACT Policy    │◄────────│  Pretrained      │                   │
│  │                │         │  Weights         │                   │
│  └───────┬────────┘         └──────────────────┘                   │
│          │                                                           │
│          │ outputs to                                                │
│          ▼                                                           │
│  ┌────────────────┐         ┌──────────────────┐                   │
│  │ Postprocessor  │◄────────│  Unnormalizer    │                   │
│  │ Pipeline       │         └──────────────────┘                   │
│  └───────┬────────┘                                                 │
│          │                                                           │
│          │ formats                                                   │
│          ▼                                                           │
│  ┌────────────────┐                                                 │
│  │ Response       │                                                 │
│  │ Builder        │                                                 │
│  └───────┬────────┘                                                 │
│          │                                                           │
└──────────┼──────────────────────────────────────────────────────────┘
           │
           ▼
    JSON Response
```

## State Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Server State Machine                            │
└─────────────────────────────────────────────────────────────────────┘

    ┌──────────┐
    │  START   │
    └────┬─────┘
         │
         │ Load model
         ▼
    ┌──────────┐
    │  READY   │◄──────────────────────┐
    └────┬─────┘                       │
         │                             │
         │ Client connects             │
         ▼                             │
    ┌──────────┐                       │
    │ CONNECTED│                       │
    └────┬─────┘                       │
         │                             │
         │ Receive message             │
         ▼                             │
    ┌──────────┐                       │
    │ PARSING  │                       │
    └────┬─────┘                       │
         │                             │
         │ Parse success               │
         ▼                             │
    ┌──────────┐                       │
    │PROCESSING│                       │
    └────┬─────┘                       │
         │                             │
         │ Inference complete          │
         ▼                             │
    ┌──────────┐                       │
    │ SENDING  │                       │
    └────┬─────┘                       │
         │                             │
         │ Response sent               │
         └─────────────────────────────┘
         
    Error handling:
    Any state ──[error]──> Send error response ──> CONNECTED
```

## Deployment Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Production Setup                             │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────┐         ┌──────────────────┐
│   Web Browser    │         │  Python Client   │
│   (JavaScript)   │         │   (Robot)        │
└────────┬─────────┘         └────────┬─────────┘
         │                            │
         │ wss://                     │ ws://
         │ (SSL/TLS)                  │ (Local)
         │                            │
         ▼                            ▼
┌─────────────────────────────────────────────────┐
│              Load Balancer                       │
│              (nginx/HAProxy)                     │
└────────┬────────────────────────┬────────────────┘
         │                        │
         ▼                        ▼
┌──────────────────┐    ┌──────────────────┐
│  WS Server #1    │    │  WS Server #2    │
│  Port 8000       │    │  Port 8001       │
│  GPU 0           │    │  GPU 1           │
└────────┬─────────┘    └────────┬─────────┘
         │                        │
         └────────────┬───────────┘
                     │
                     ▼
         ┌──────────────────────┐
         │   Shared Storage     │
         │   (Model Files)      │
         └──────────────────────┘
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Error Handling                                  │
└─────────────────────────────────────────────────────────────────────┘

Request Received
      │
      ▼
┌──────────────┐
│ Parse JSON   │──[Invalid JSON]──> Return error: "Invalid JSON"
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Validate     │──[Missing field]──> Return error: "Missing field"
│ Required     │
│ Fields       │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Decode       │──[Decode fail]───> Return error: "Image decode error"
│ Images       │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Preprocess   │──[Shape error]───> Return error: "Shape mismatch"
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Inference    │──[Model error]───> Return error: "Inference failed"
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Postprocess  │──[Process error]─> Return error: "Postprocess failed"
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Send         │──[Send error]────> Log error, close connection
│ Response     │
└──────────────┘

All errors are:
1. Logged with full traceback
2. Returned as JSON: {"error": "type", "message": "details"}
3. Non-fatal (connection stays open)
```

## Scalability Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Horizontal Scaling                                │
└─────────────────────────────────────────────────────────────────────┘

                    ┌──────────────┐
                    │   Clients    │
                    │   (1000+)    │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │Load Balancer │
                    │  (Round      │
                    │   Robin)     │
                    └──────┬───────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Server #1    │  │ Server #2    │  │ Server #3    │
│ GPU 0        │  │ GPU 1        │  │ GPU 2        │
│ ~30 req/s    │  │ ~30 req/s    │  │ ~30 req/s    │
└──────────────┘  └──────────────┘  └──────────────┘

Total Capacity: ~90 requests/second
```

This architecture allows the system to scale horizontally by adding more server instances, each with its own GPU.
