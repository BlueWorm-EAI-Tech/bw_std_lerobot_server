# Mantis PI05 叠衣项目：新 4x4090 电脑部署命令

本文档只包含迁移到新 GPU 服务器时需要执行的命令。代码由 GitHub 管理，Python 环境由 uv 和 `uv.lock` 管理，模型权重单独传输。

## 0. 机器角色

- **旧电脑**：当前保存训练 checkpoint 的电脑，例如 `/data/runtime_red_rel30_from_folding_latest_30k_bs10_foreground/checkpoints/060000/pretrained_model`。
- **新电脑**：准备部署的 4x4090 GPU 服务器。
- 命令中的 `新电脑用户名`、`新电脑IP` 必须替换成真实值。
- GitHub 仓库不包含训练数据和约 7 GB 的模型权重。

## 1. 新电脑：检查基础条件

先确认 NVIDIA 驱动可以识别四张显卡：

```bash
nvidia-smi
```

Ubuntu/Debian 安装基础工具：

```bash
sudo apt update
sudo apt install -y git git-lfs curl ffmpeg rsync ca-certificates
git lfs install
```

如果 `nvidia-smi` 失败，先安装或升级 NVIDIA 驱动，再继续下面的步骤。项目使用锁定的 PyTorch 2.7.1 和 CUDA 12.8 wheel。

## 2. 新电脑：克隆指定发布分支

下面使用 GitHub SSH 地址。新电脑的 GitHub SSH 密钥必须已经配置，并且账号对私有仓库有读取权限。

```bash
ssh -T git@github.com

mkdir -p ~/repos
cd ~/repos

GIT_LFS_SKIP_SMUDGE=1 git clone \
  --branch release/pi05-folding-portable-20260811 \
  --single-branch \
  git@github.com:BlueWorm-EAI-Tech/lerobot_mantis_server.git \
  lerobot

cd ~/repos/lerobot
git status --short --branch
git rev-parse HEAD
```

分支必须显示：

```text
release/pi05-folding-portable-20260811
```

## 3. 新电脑：uv 一键安装环境

只执行以下脚本。它会在缺少 uv 时自动安装 uv，自动准备 Python 3.10.19，并严格按照 `uv.lock` 创建 `~/repos/lerobot/.venv-pi05`：

```bash
cd ~/repos/lerobot
bash deploy/mantis_pi05_folding/install_server.sh
```

安装完成后复核关键版本：

```bash
cd ~/repos/lerobot
.venv-pi05/bin/python - <<'PY'
import torch
import transformers
import websockets

print("torch:", torch.__version__)
print("torch CUDA:", torch.version.cuda)
print("CUDA available:", torch.cuda.is_available())
print("visible GPUs:", torch.cuda.device_count())
print("transformers:", transformers.__version__)
print("websockets:", websockets.__version__)
PY
```

预期关键结果：

```text
torch: 2.7.1+cu128
torch CUDA: 12.8
CUDA available: True
visible GPUs: 4
transformers: 4.53.2
websockets: 15.0.1
```

## 4. 旧电脑：把当前 060000 模型传到新电脑

以下命令在**旧电脑**执行。先在新电脑创建目标目录：

```bash
ssh 新电脑用户名@新电脑IP 'mkdir -p /data/models/pi05-folding/pretrained_model'
```

使用可续传的 `rsync` 传输当前 `060000` checkpoint：

```bash
rsync -avP \
  /data/runtime_red_rel30_from_folding_latest_30k_bs10_foreground/checkpoints/060000/pretrained_model/ \
  新电脑用户名@新电脑IP:/data/models/pi05-folding/pretrained_model/
```

记录旧电脑模型校验值：

```bash
sha256sum \
  /data/runtime_red_rel30_from_folding_latest_30k_bs10_foreground/checkpoints/060000/pretrained_model/model.safetensors
```

## 5. 新电脑：校验模型并准备 serving 目录

以下命令重新回到**新电脑**执行：

```bash
sha256sum /data/models/pi05-folding/pretrained_model/model.safetensors
```

输出必须与旧电脑一致。然后生成关闭 `torch.compile` 的 serving 目录：

```bash
cd ~/repos/lerobot
.venv-pi05/bin/python \
  deploy/mantis_pi05_folding/prepare_model.py \
  /data/models/pi05-folding/pretrained_model \
  /data/models/pi05-folding/pretrained_model_serve_nocompile
```

PI05 还需要 PaliGemma tokenizer。新电脑第一次联网部署时执行：

```bash
cd ~/repos/lerobot
.venv-pi05/bin/hf auth login
.venv-pi05/bin/hf download google/paligemma-3b-pt-224 \
  --include 'config.json' \
  --include 'tokenizer*' \
  --include 'added_tokens.json' \
  --include 'special_tokens_map.json'
```

如果 Hugging Face 提示没有权限，需要先在网页接受该模型许可。

## 6. 新电脑：生成服务配置

```bash
cd ~/repos/lerobot
cp deploy/mantis_pi05_folding/server.env.example \
  deploy/mantis_pi05_folding/server.env

sed -i \
  's|^PI05_MODEL_PATH=.*|PI05_MODEL_PATH=/data/models/pi05-folding/pretrained_model_serve_nocompile|' \
  deploy/mantis_pi05_folding/server.env
```

确认配置：

```bash
sed -n '1,120p' ~/repos/lerobot/deploy/mantis_pi05_folding/server.env
```

默认配置使用物理 GPU 0、监听 `0.0.0.0:8005`，RTC 默认关闭。

## 7. 新电脑：预检并启动 PI05 WebSocket server

预检：

```bash
cd ~/repos/lerobot
bash deploy/mantis_pi05_folding/preflight_server.sh
```

预检通过后，在前台启动：

```bash
cd ~/repos/lerobot
bash deploy/mantis_pi05_folding/run_server.sh
```

新开一个终端检查监听端口和 GPU：

```bash
ss -ltnp | grep ':8005'
nvidia-smi
```

启动脚本固定包含 `--disable_joint_order_bridge`。服务端保持模型动作帧，不要额外增加 shoulder roll/yaw 交换或符号翻转。

## 8. 新电脑：后续更新代码和环境

```bash
cd ~/repos/lerobot
git status --short
git pull --ff-only
bash deploy/mantis_pi05_folding/install_server.sh
```

`git pull --ff-only` 更新代码和锁文件；再次运行安装脚本会把 `.venv-pi05` 精确同步到新版 `uv.lock`。模型目录和本机 `server.env` 不会被 Git 覆盖。

## 9. 最短命令清单

基础软件和模型已经准备好时，新电脑只需：

```bash
mkdir -p ~/repos
cd ~/repos
GIT_LFS_SKIP_SMUDGE=1 git clone \
  --branch release/pi05-folding-portable-20260811 \
  --single-branch \
  git@github.com:BlueWorm-EAI-Tech/lerobot_mantis_server.git \
  lerobot

cd ~/repos/lerobot
bash deploy/mantis_pi05_folding/install_server.sh
cp deploy/mantis_pi05_folding/server.env.example \
  deploy/mantis_pi05_folding/server.env
sed -i \
  's|^PI05_MODEL_PATH=.*|PI05_MODEL_PATH=/data/models/pi05-folding/pretrained_model_serve_nocompile|' \
  deploy/mantis_pi05_folding/server.env
bash deploy/mantis_pi05_folding/preflight_server.sh
bash deploy/mantis_pi05_folding/run_server.sh
```

不要把 `server.env`、模型权重、Hugging Face Token 或 GitHub 私钥提交到 GitHub。
