# PI05 叠衣项目 Git 与 4x4090 迁移手册

## 1. 先理解 Git 在做什么

Git 管理的是代码历史，GitHub 是放置 Git 仓库的远程服务器。最常用的数据流是：

```text
工作区文件 -> git add -> 暂存区 -> git commit -> 本地历史 -> git push -> GitHub
GitHub -> git fetch/pull -> 本地历史和工作区
```

- `git status`：查看当前分支、修改和未跟踪文件，任何提交前都先运行。
- `git diff`：查看尚未暂存的改动。
- `git add path`：选择本次提交要包含的文件。不要在机器人项目里盲目使用 `git add .`。
- `git diff --cached`：检查即将提交的内容。
- `git commit -m "说明"`：在本地创建一个可追踪版本。
- `git push`：把本地 commit 上传到 GitHub。
- `git pull --ff-only`：下载远程新 commit；如果本地历史分叉则停止，避免自动产生难懂的合并。
- `git log --oneline --decorate -10`：查看最近十次提交。

分支可以理解成一条独立开发线。本项目的可迁移叠衣 release 分支是：

```text
release/pi05-folding-portable-20260811
```

它基于已经验证动作帧处理的 commit `50fa1630`，并在后续提交中纳入了当前开发目录的实验代码，包括数据质量分层、PI05 优化/phase-progress 服务、相对动作处理、ACT loss 权重和配套测试。这些实验代码用于继续开发和复现；新机器首次部署仍默认使用 `deploy/mantis_pi05_folding/run_server.sh`，保持 `--disable_joint_order_bridge`，不要在服务端额外交换或翻转肩关节动作。

## 2. 本项目必须拆开的三类资产

| 资产 | 保存位置 | 原因 |
|---|---|---|
| LeRobot/PI05 服务端代码 | GitHub `lerobot_mantis_server` | 文本代码适合 Git 审查和回滚 |
| Mantis 机器人客户端 | GitHub `lerobot_mantis_runtime` | ROS/机器人侧独立部署 |
| 模型 checkpoint | Hugging Face 私有模型仓库、对象存储或 `rsync` | 单个权重约 7.47 GB |
| LeRobot 数据集 | Hugging Face 私有 dataset、NAS 或对象存储 | 含 Parquet、视频，通常数百 MB 到数 GB |
| 日志、缓存、虚拟环境 | 只保留在运行机器或日志系统 | 不属于源码，且不可复现性很强 |

普通 GitHub Git 文件超过 100 MiB 会被拒绝。当前 PI05 `model.safetensors` 约 7.47 GB，也超过 GitHub Free/Pro 的 2 GB 单文件 LFS 上限。因此模型不要放进代码仓库。

## 3. GitHub 凭据安全

本机曾把 Personal Access Token 直接写进 remote URL。remote URL 已改回不含 Token 的 HTTPS 地址，但旧 Token 必须在 GitHub 网页中立即删除：

```text
GitHub -> Settings -> Developer settings -> Personal access tokens
```

推荐以后使用 SSH，不要再使用下面这种 URL：

```text
https://用户名:Token@github.com/组织/仓库.git
```

生成独立 GitHub SSH 密钥：

```bash
ssh-keygen -t ed25519 -C "你的GitHub邮箱" -f ~/.ssh/id_ed25519_github
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519_github
cat ~/.ssh/id_ed25519_github.pub
```

只把 `.pub` 公钥内容添加到 `GitHub -> Settings -> SSH and GPG keys`。私钥 `~/.ssh/id_ed25519_github` 绝对不能上传或发给别人。

测试并切换本项目 remote：

```bash
ssh -T git@github.com
cd /home/lcjs-szw/repos/lerobot-pi05-folding-release
git remote set-url mantis_server git@github.com:BlueWorm-EAI-Tech/lerobot_mantis_server.git
git remote -v
```

如果组织启用了 SSO，还要在 GitHub 中为这把 SSH key 执行 Configure SSO/Authorize。

## 4. 当前机器第一次上传 release 分支

先检查，再推送：

```bash
cd /home/lcjs-szw/repos/lerobot-pi05-folding-release
git status
git log --oneline --decorate -5
git remote -v
git push -u mantis_server release/pi05-folding-portable-20260811
```

`-u` 会记录本地分支对应的远程分支，以后同一分支只需 `git push`。不要对 `main` 做 force push。

日常修改使用以下固定循环：

```bash
git status
git diff
git add 具体文件1 具体文件2
git diff --cached
git commit -m "fix: 简短说明这次改动"
git push
```

如果误把文件放入暂存区但尚未 commit：

```bash
git restore --staged 路径
```

这个命令只取消暂存，不删除工作区文件。

## 5. 新 4x4090 服务器克隆代码

先安装 NVIDIA 驱动、Git、Git LFS、Python 3.10、`python3.10-venv` 和 ffmpeg。确认四张卡：

```bash
nvidia-smi
git --version
python3.10 --version
ffmpeg -version
```

克隆时跳过仓库测试用的 LFS 二进制资产，PI05 服务端不需要它们：

```bash
mkdir -p ~/repos
cd ~/repos
GIT_LFS_SKIP_SMUDGE=1 git clone \
  --branch release/pi05-folding-portable-20260811 \
  git@github.com:BlueWorm-EAI-Tech/lerobot_mantis_server.git \
  lerobot

git clone \
  --branch ipc-client-sdk-order-fix-20260611 \
  git@github.com:BlueWorm-EAI-Tech/lerobot_mantis_runtime.git
```

记录精确版本，排查问题时必须带上这两个输出：

```bash
git -C ~/repos/lerobot rev-parse HEAD
git -C ~/repos/lerobot_mantis_runtime rev-parse HEAD
```

## 6. 安装 PI05 服务端环境

```bash
cd ~/repos/lerobot
bash deploy/mantis_pi05_folding/install_server.sh
```

默认使用系统 Python 3.10 创建 `~/repos/lerobot/.venv-pi05`，并安装 PyTorch 2.7.1、CUDA 12.8 wheel、Transformers 4.53.2 和服务端依赖。如果新服务器的驱动不支持 CUDA 12.8，先升级驱动；也可通过 `PI05_TORCH_INDEX_URL` 选择 PyTorch 官方提供的其他 CUDA wheel。

## 7. 传输模型

同一内网优先使用可续传的 `rsync`：

```bash
rsync -avP /data/某个训练目录/checkpoints/020000/pretrained_model/ \
  新服务器用户@新服务器IP:/data/models/pi05-folding/pretrained_model/
```

跨网络建议使用 Hugging Face 私有 model repo。先在 Hugging Face 网页创建 Private model，然后：

```bash
hf auth login
HF_XET_HIGH_PERFORMANCE=1 hf upload \
  组织名/pi05-mantis-folding \
  /data/某个训练目录/checkpoints/020000/pretrained_model \
  .
```

新服务器下载：

```bash
hf auth login
hf download 组织名/pi05-mantis-folding \
  --local-dir /data/models/pi05-folding/pretrained_model
```

PI05 processor 还会使用 PaliGemma tokenizer。第一次联网缓存，完成后服务端才可以使用离线模式：

```bash
source ~/repos/lerobot/.venv-pi05/bin/activate
hf auth login
hf download google/paligemma-3b-pt-224 \
  --include "config.json" \
  --include "tokenizer*" \
  --include "added_tokens.json" \
  --include "special_tokens_map.json"
```

如果该 Google 模型要求许可，需要先在 Hugging Face 网页接受许可。这里缓存的 tokenizer 约几十 MB，不会再次下载完整 PaliGemma 权重。

上传前后都计算权重校验值，两边结果必须完全一致：

```bash
sha256sum /data/models/pi05-folding/pretrained_model/model.safetensors
```

准备关闭编译的 serving 目录：

```bash
cd ~/repos/lerobot
.venv-pi05/bin/python deploy/mantis_pi05_folding/prepare_model.py \
  /data/models/pi05-folding/pretrained_model \
  /data/models/pi05-folding/pretrained_model_serve_nocompile
```

## 8. 启动服务端

```bash
cd ~/repos/lerobot/deploy/mantis_pi05_folding
cp server.env.example server.env
```

编辑 `server.env` 中的 `PI05_MODEL_PATH`。同机部署客户端时服务地址使用 `ws://127.0.0.1:8005`；跨机器时使用 GPU 服务器的内网 IP，并只在受信任网络/防火墙中开放 8005。

```bash
cd ~/repos/lerobot
bash deploy/mantis_pi05_folding/preflight_server.sh
bash deploy/mantis_pi05_folding/run_server.sh
```

启动日志必须看到模型加载成功、端口 8005，并确认命令包含 `--disable_joint_order_bridge`。服务端保持模型/动作帧，不再做 shoulder roll/yaw swap 或 sign flip。

## 9. 机器人客户端首次低速运行

```bash
cd ~/repos/lerobot_mantis_runtime/scripts
LD_PRELOAD= \
ACT_JOINT_VELOCITY_LIMIT=0.04 \
bash run_act_client.sh \
  --server ws://GPU服务器IP:8005 \
  --skip-reset \
  --fps 10 \
  --timeout 180 \
  --replan-horizon 30 \
  --log-every-n-steps 1
```

第一次必须有人在急停旁观察，先空载/远离衣物验证方向，再放衣物。动作方向、相机键、关节顺序未确认前不要提高速度。稳定后可逐步尝试 `ACT_JOINT_VELOCITY_LIMIT=0.08`。默认不启用 RTC，只有客户端和服务端都明确支持且普通模式已经跑通后再测试。

## 10. 四张 4090 怎么用

单个 WebSocket PI05 服务是单进程单卡。`PI05_GPU=0` 后，进程内看到的 `cuda:0` 就是物理 GPU 0。一张 4090 足以作为首个部署目标，四卡不会自动把一次推理加速四倍。

四卡更实用的方式有两种：

1. 每张卡运行一个独立 checkpoint/端口，例如 GPU 0/8005、GPU 1/8006，用于并行 rollout 对比。
2. 使用 Accelerate 做四卡训练：

```bash
cd ~/repos/lerobot
source .venv-pi05/bin/activate
accelerate launch --multi_gpu --num_processes=4 \
  "$(which lerobot-train)" \
  其余与单卡完全相同的训练参数
```

四卡时有效 batch size 是 `单卡 batch_size x 4`。LeRobot 不会自动调整 learning rate 和 steps；第一轮不要同时改学习率、batch 和 steps，否则无法判断行为变化来自哪里。先做 20 到 100 step smoke test，确认四个进程、loss、保存 checkpoint 都正常，再正式训练。

## 11. 每次部署的验收清单

- `git status` 干净，服务端和客户端 commit 已记录。
- `nvidia-smi` 能看到 GPU，PyTorch `torch.cuda.is_available()` 为 `True`。
- 模型 SHA-256 与源机器一致，五个必要模型/processor 文件存在。
- `compile_model=false`，服务启动不在第一次请求时编译超时。
- 服务端使用 `--disable_joint_order_bridge`。
- 三路相机分别是 `env_cam`、`left_wrist_cam`、`right_wrist_cam`。
- gripper 语义是 `0=open`、`1=closed`。
- 首次 rollout 使用 `0.04`、10 fps、replan horizon 30，并具备人工急停。
- 不在服务端或客户端重复应用离线数据 repair spec `1=2,2=-1,9=-10,10=9`。

## 12. 常见 Git 问题

`git status` 显示 `modified`：文件改过但未提交，先 `git diff`。

`untracked`：新文件尚未受 Git 管理，确认不是模型、数据、日志或密钥后再 `git add`。

`Your branch is ahead`：本地有 commit 尚未 push，运行 `git push`。

`Your branch is behind`：远程有新 commit，工作区干净时运行 `git pull --ff-only`。

`Permission denied (publickey)`：SSH 公钥未添加到正确 GitHub 账号、未授权组织 SSO，或 remote 仍不是 SSH URL。

`large files detected`：大文件已经进入 commit。不要继续 push，先停止并检查 `git status`、`git log --stat -1`，再决定从未推送历史中移除，不能只补一个 `.gitignore`。
