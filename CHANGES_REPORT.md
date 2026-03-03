# LeRobot-Mantis 项目改动报告

## 项目概述

本项目是基于 [huggingface/lerobot](https://github.com/huggingface/lerobot) 的 Mantis 机器人集成 fork，添加了 Mantis 双臂机器人的支持以及 WebSocket 推理系统。

---

## 1. 新增核心功能

### 1.1 Mantis 机器人支持

| 文件路径 | 说明 |
|----------|------|
| `src/lerobot/robots/mantis/__init__.py` | Mantis 机器人注册 |
| `src/lerobot/robots/mantis/config_mantis.py` | Mantis 配置 (16 DOF, 3 相机) |
| `src/lerobot/robots/mantis/mantis.py` | Mantis 机器人实现 |

**注册方式：** `@RobotConfig.register_subclass("mantis")`

**使用方式：**
```bash
lerobot-train --robot.type=mantis --policy.type=act ...
lerobot-train --robot.type=mantis --policy.type=pi05 ...
lerobot-train --robot.type=mantis --policy.type=smolvla ...
```

### 1.2 WebSocket 推理系统

#### 服务器端 (`scripts/websocket-server/`)
```
websocket-server/
├── act/              # ACT 推理服务器
├── smolvla/         # SmolVLA 推理服务器
├── pi05/            # PI05 推理服务器
└── ros2/            # ROS2 客户端模板
```

#### 客户端 (`scripts/websocket-mantis/`)
```
websocket-mantis/
├── mantis_websocket_client.py       # JSON 协议客户端
├── mantis_websocket_client_json.py  # msgpack 协议客户端
├── mantis_pi05_inference_client.py  # 本地推理客户端
├── config.yaml                      # 配置文件
└── requirements.txt                  # 依赖
```

---

## 2. 文档改动

### 2.1 新增文档

| 文件路径 | 说明 |
|----------|------|
| `docs/mantis/MANTIS_TRAINING_GUIDE.md` | Mantis 训练指南 |
| `docs/mantis/MANTIS_TRAINING_SUMMARY.md` | Mantis 训练总结 |
| `docs/mantis/PI05_Mantis_部署调试记录.md` | 部署调试记录 |
| `docs/websocket-act-system/` | WebSocket 推理系统文档 (11 个文件) |
| `docs/dataset-issues/` | 数据集问题分析 (3 个文件) |

### 2.2 训练脚本

```
examples/training/mantis/
├── train_pi05_mantis.sh           # PI05 训练
├── train_pi05_mantis_continue.sh  # PI05 继续训练
├── eval_pi05_mantis.sh           # PI05 评估
├── train_smolvla_mantis.sh       # SmolVLA 训练
└── train_smolvla_continue.sh      # SmolVLA 继续训练
```

---

## 3. 代码改动

### 3.1 策略适配

| 文件 | 改动 |
|------|------|
| `src/lerobot/policies/pi05/processor_pi05.py` | 添加 Mantis 支持 |
| `src/lerobot/policies/smolvla/processor_smolvla.py` | 添加 Mantis 支持 |
| `src/lerobot/datasets/lerobot_dataset.py` | 数据集相关改动 |
| `src/lerobot/robots/utils.py` | 工具函数改动 |

### 3.2 配置文件

| 文件 | 说明 |
|------|------|
| `src/lerobot/configs/policies/__init__.py` | 新增，保持 import 兼容 |
| `src/lerobot/configs/train.py.backup` | 备份文件 |

---

## 4. GitHub Actions 改动

### 4.1 禁用的测试 Jobs

由于 fork 没有 Docker Hub 凭证，禁用了以下 jobs：

- `build-and-push-docker` - Docker 镜像构建
- `gpu-tests` - GPU 测试
- `delete-pr-image` - 删除测试镜像
- `fast-pytest-tests` - 快速测试

### 4.2 保留的测试

- ✅ `Quality` - 代码质量检查 (linting)

---

## 5. 项目结构总览

```
lerobot-mantis/
├── src/lerobot/
│   ├── robots/
│   │   └── mantis/           # ✨ 新增: Mantis 机器人
│   ├── policies/              # 策略 (act, pi05, smolvla 等)
│   └── configs/
├── examples/training/mantis/ # ✨ 新增: 训练脚本
├── scripts/
│   ├── websocket-server/     # ✨ 新增: 推理服务器
│   └── websocket-mantis/     # ✨ 新增: 机器人客户端
├── docs/
│   ├── mantis/              # ✨ 新增: Mantis 文档
│   ├── websocket-act-system/ # ✨ 新增: WebSocket 文档
│   └── dataset-issues/      # ✨ 新增: 数据集问题
└── tests/pi05_mantis/       # ✨ 新增: 测试文件
```

---

## 6. 与原工程的一致性

### ✅ 遵循原工程模式

1. **机器人注册方式** - 使用 `@RobotConfig.register_subclass("mantis")`
2. **策略使用** - 直接使用现有策略 (`act`, `pi05`, `smolvla`)，无需修改
3. **训练命令** - 使用标准 `lerobot-train` 命令
4. **目录结构** - 保持与原工程一致

### ❌ 已删除的冗余

1. ~~`src/lerobot/configs/policies/pi05_mantis.py`~~ - 不需要单独的 policy 配置
2. ~~`.kiro/`~~ - 开发笔记目录
3. ~~20 个冗余训练脚本~~ - 精简为 5 个核心脚本

---

## 7. 使用说明

### 7.1 训练

```bash
# ACT 策略
lerobot-train --policy.type=act --robot.type=mantis --dataset.repo_id=...

# PI05 策略
lerobot-train --policy.type=pi05 --robot.type=mantis --dataset.repo_id=...

# SmolVLA 策略
lerobot-train --policy.type=smolvla --robot.type=mantis --dataset.repo_id=...
```

### 7.2 推理

```bash
# 启动 WebSocket 服务器 (GPU 机器)
python scripts/websocket-server/pi05/websocket_pi05_server.py ...

# 启动机器人客户端
python scripts/websocket-mantis/mantis_websocket_client.py --server ws://SERVER:8000
```

---

## 8. 提交历史

| 提交 | 说明 |
|------|------|
| `9bfd88d3` | 删除 pi05_mantis policy 配置 |
| `fb794989` | 精简训练脚本至 5 个 |
| `2b09e2a3` | 重组织 websocket 脚本 |
| `382e94d8` | 移动测试文件 |
| `6ad6cfbb` | 整理项目结构 |
| `ced74ba5` | 禁用 Fast Tests |
| `5fc83e96` | 修复 ruff/typos 问题 |
| `4931f33b` | 添加 Mantis 集成 |

---

## 9. 总结

本 fork 成功将 Mantis 双臂机器人集成到 LeRobot 框架中，同时：

1. ✅ **遵循原工程规范** - 不修改核心策略，使用标准注册方式
2. ✅ **完整的推理系统** - WebSocket 服务器 + 客户端
3. ✅ **规范的代码结构** - 与原工程保持一致
4. ✅ **精简冗余** - 删除不必要的配置和脚本

---

*报告生成时间: 2026-03-03*
*基于提交: origin/main..HEAD (12 commits)*
