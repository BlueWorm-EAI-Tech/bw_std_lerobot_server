# PI05 叠衣项目 Git 与 4x4090 迁移手册

> 当前文件位于 `/home/lcjs-szw/doc`，这个目录不属于 LeRobot Git 仓库。编辑这里的文件只会保存在本机，不会自动出现在 `git status` 中，也不会随项目上传 GitHub。需要把本文档一起上传时，请执行第 4.2 节的命令，将它复制回发布仓库的 `docs/mantis/` 后再提交。

## 1. 先理解 Git 在做什么

Git 管理的是代码历史，GitHub 是放置 Git 仓库的远程服务器。最常用的数据流是：

```text
工作区文件 -> git add -> 暂存区 -> git commit -> 本地历史 -> git push -> GitHub
GitHub -> git fetch/pull -> 本地历史和工作区
```

这里有四个容易混淆的位置：

| 位置 | 含义 | 对应命令 |
|---|---|---|
| 工作区 | 磁盘上正在编辑的文件 | 编辑器、`git diff` |
| 暂存区 | 本次准备提交的文件快照 | `git add`、`git diff --cached` |
| 本地仓库 | 已经形成的 commit 历史 | `git commit`、`git log` |
| GitHub | 远程备份和协作仓库 | `git push`、`git pull` |

`git commit` 只写入本机，不等于已经上传；只有 `git push` 成功后，GitHub 才能看到该 commit。

### 常用 Git 命令作用速查

| 命令 | 简要作用 | 影响范围 |
|---|---|---|
| `git --version` | 查看 Git 是否安装及版本号 | 只读 |
| `git config` | 查看或设置提交者姓名、邮箱等 Git 配置 | 修改配置 |
| `git init` | 把普通目录初始化为新的本地 Git 仓库 | 创建本地仓库 |
| `git clone URL` | 从 GitHub 等远程地址完整下载仓库 | 创建本地仓库和工作区 |
| `git status` | 查看当前分支、修改、暂存和未跟踪文件 | 只读 |
| `git diff` | 查看工作区尚未暂存的具体修改 | 只读 |
| `git diff --cached` | 查看已经暂存、准备进入下次 commit 的修改 | 只读 |
| `git add 文件` | 把指定文件当前内容放进暂存区 | 修改暂存区 |
| `git restore --staged 文件` | 把文件移出暂存区，但保留工作区修改 | 修改暂存区 |
| `git restore 文件` | 丢弃文件尚未提交的工作区修改 | 修改工作区，谨慎使用 |
| `git commit -m "说明"` | 把暂存区内容保存为一个本地版本 | 修改本地历史 |
| `git log` | 查看 commit 历史 | 只读 |
| `git show commit编号` | 查看某个 commit 的内容或文件统计 | 只读 |
| `git branch` | 查看分支；带名称时可创建分支 | 只读或创建本地分支 |
| `git switch 分支` | 切换到已有分支 | 切换工作区内容 |
| `git switch -c 新分支` | 创建并切换到新分支 | 创建分支并切换工作区 |
| `git worktree list` | 查看同一仓库当前有哪些独立工作区 | 只读 |
| `git remote -v` | 查看本地仓库连接的远程地址 | 只读 |
| `git remote set-url` | 修改某个 remote 对应的远程地址 | 修改本地仓库配置 |
| `git fetch` | 下载远程 commit 和分支信息，不改当前工作区 | 更新远程跟踪信息 |
| `git pull --ff-only` | 下载远程更新，并且只允许安全快进当前分支 | 更新本地分支和工作区 |
| `git push` | 把本地 commit 上传到远程仓库 | 修改 GitHub 远程分支 |
| `git merge 分支` | 把另一个分支的历史合并进当前分支 | 修改本地历史和工作区 |
| `git cherry-pick commit编号` | 只把指定 commit 应用到当前分支 | 修改本地历史和工作区 |
| `git revert commit编号` | 新建一个反向 commit，撤销已有 commit 的效果 | 修改本地历史 |
| `git tag` | 给确定的 commit 添加版本标签 | 创建本地标签 |
| `git rev-parse HEAD` | 输出当前分支的精确 commit 编号 | 只读 |
| `git ls-files` | 查看已经被 Git 跟踪的文件 | 只读 |

最常见的安全顺序是：先用 `status` 和 `diff` 查看，再用 `add` 选择文件，用 `commit` 保存本地版本，最后用 `push` 上传。`fetch` 只下载远程信息；`pull` 还会更新当前工作区，因此执行 `pull` 前先确认工作区干净。

### 1.1 本机首次配置 Git

确认 Git 已安装：

```bash
git --version
```

Git 的姓名和邮箱会记录为 commit 作者。以下命令使用文档当前填写的 `Edward2002-zjw` 和 `1580026067@qq.com`；如果实际身份不同，应替换成正确值：

```bash
git config --global user.name "Edward2002-zjw"
git config --global user.email "1580026067@qq.com"
git config --global init.defaultBranch main
```

查看配置来自哪个文件：

```bash
git config --global --list
git config --list --show-origin
```

用户名和邮箱会写进 commit 历史，不是 GitHub 登录密码。GitHub 登录由第 3 节的 SSH 密钥负责。

### 1.2 每次操作前先确认自己在哪里

发布版和开发版是两个不同工作区。先进入准备操作的目录，再确认路径和分支：

```bash
cd /home/lcjs-szw/repos/lerobot-pi05-folding-release
pwd
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch
```

预期发布分支名称是：

```text
release/pi05-folding-portable-20260811
```

如果分支名称不对，先停止，不要执行 `git add` 或 `git commit`。

`git status --short` 的常见标记：

| 标记 | 含义 |
|---|---|
| ` M file` | 已跟踪文件被修改，但尚未暂存 |
| `M  file` | 修改已经进入暂存区 |
| `?? file` | 新文件，Git 还没有跟踪 |
| ` D file` | 已跟踪文件在工作区被删除 |
| `D  file` | 删除操作已经进入暂存区 |

### 1.3 查看修改，不写入任何内容

以下命令都是只读检查，可以放心运行：

```bash
# 查看所有未暂存修改的概要
git diff --stat

# 查看所有未暂存修改的具体内容
git diff

# 只看一个文件
git diff -- src/lerobot/policies/pi05/modeling_pi05.py

# 查看新文件和修改文件状态
git status --short

# 查看最近十个本地版本
git log --oneline --decorate -10

# 查看某个 commit 修改了哪些文件
git show --stat b7a43844

# 查看当前精确 commit 编号
git rev-parse HEAD
```

### 1.4 在本地提交一次修改

假设只修改了 PI05 模型代码和对应测试，使用下面的固定流程：

```bash
cd /home/lcjs-szw/repos/lerobot-pi05-folding-release

# 第一步：查看有哪些修改
git status --short
git diff

# 第二步：只暂存本次确实要提交的文件
git add src/lerobot/policies/pi05/modeling_pi05.py
git add tests/processor/test_relative_action_processor.py

# 第三步：检查即将写进 commit 的内容
git diff --cached --name-status
git diff --cached --stat
git diff --cached

# 第四步：创建本地 commit
git commit -m "fix: correct PI05 relative action handling"

# 第五步：确认 commit 已生成
git status --short --branch
git log --oneline --decorate -5
```

commit 信息推荐使用以下前缀：

| 前缀 | 使用场景 | 示例 |
|---|---|---|
| `feat:` | 新功能 | `feat: add PI05 phase progress server` |
| `fix:` | 修复错误 | `fix: validate camera image keys` |
| `test:` | 增加或修改测试 | `test: cover relative action processor` |
| `docs:` | 只修改文档 | `docs: expand Git deployment guide` |
| `chore:` | 配置或维护工作 | `chore: ignore local server environment` |

不要在机器人项目中习惯性执行 `git add .` 或 `git add -A`。它们可能把模型、数据、日志、密钥和不相关实验一起暂存。优先逐个写出文件路径。

### 1.5 暂存错了或代码改错了

文件已经 `git add`，但还没有 commit，只取消暂存、不删除文件：

```bash
git restore --staged 文件路径
```

查看某个文件在上一次 commit 中的版本：

```bash
git show HEAD:文件路径
```

丢弃尚未提交的修改：

```bash
git restore 文件路径
```

最后一条命令会直接覆盖工作区修改，通常无法通过 Git 找回。运行前必须先执行 `git diff -- 文件路径`，确认这些内容确实不要了。

已经 commit 的错误，如果已经上传或可能被别人使用，使用反向 commit：

```bash
git revert 错误的commit编号
```

不要随意使用 `git reset --hard` 或 `git push --force`，它们可能删除本地修改或改写远程公共历史。

### 1.6 分支的本地用法

分支可以理解成一条独立开发线。本项目的可迁移叠衣 release 分支是：

```text
release/pi05-folding-portable-20260811
```

它基于已经验证动作帧处理的 commit `50fa1630`，并在后续提交中纳入了当前开发目录的实验代码，包括数据质量分层、PI05 优化/phase-progress 服务、相对动作处理、ACT loss 权重和配套测试。这些实验代码用于继续开发和复现；新机器首次部署仍默认使用 `deploy/mantis_pi05_folding/run_server.sh`，保持 `--disable_joint_order_bridge`，不要在服务端额外交换或翻转肩关节动作。

查看本地和远程分支：

```bash
git branch
git branch -a
```

创建一个新的实验分支并切换过去：

```bash
cd /home/lcjs-szw/repos/lerobot
git switch -c exp/pi05-new-test
```

切换到已有分支：

```bash
git switch exp/20260610-pi05-fold-clothes-audit
```

有未提交修改时，Git 可能拒绝切换分支。不要为了切换分支而运行 `git reset --hard`；先提交、确认是否需要暂存，或保留在原工作区。

### 1.7 本项目的 worktree 用法

本项目用 Git worktree 同时打开开发分支和发布分支：

```text
/home/lcjs-szw/repos/lerobot
  -> exp/20260610-pi05-fold-clothes-audit

/home/lcjs-szw/repos/lerobot-pi05-folding-release
  -> release/pi05-folding-portable-20260811
```

查看所有 worktree：

```bash
git -C /home/lcjs-szw/repos/lerobot worktree list
```

两个目录共享 commit 历史，但工作区文件不会自动同步。开发目录改完以后，推荐先在实验分支形成一个清晰 commit，再选择合并或挑选提交：

```bash
# 查看实验分支的提交编号
git -C /home/lcjs-szw/repos/lerobot log --oneline -5

# 进入发布工作区后，只引入某一个已经确认的 commit
cd /home/lcjs-szw/repos/lerobot-pi05-folding-release
git cherry-pick 实验commit编号
```

`cherry-pick` 会把指定 commit 应用到当前分支。出现冲突时不要盲目继续，先运行 `git status` 查看冲突文件并进行人工核对。

### 1.8 从零创建一个新的本地 Git 仓库

现有 LeRobot 项目已经是 Git 仓库，不需要执行本节。只有全新目录才使用：

```bash
mkdir -p ~/repos/git-demo
cd ~/repos/git-demo
git init -b main

echo "# git-demo" > README.md
git status
git add README.md
git diff --cached
git commit -m "docs: initialize repository"
git log --oneline
```

执行到这里，版本只存在本机。连接和上传 GitHub 见第 3、4 节。

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

### 3.1 检查是否已有 SSH 密钥

```bash
ls -la ~/.ssh
test -f ~/.ssh/id_ed25519_github && echo "GitHub private key already exists"
test -f ~/.ssh/id_ed25519_github.pub && echo "GitHub public key already exists"
```

如果两个文件已经存在，不要再次运行 `ssh-keygen` 覆盖它们。直接从“启动 ssh-agent”继续。

### 3.2 生成独立 GitHub SSH 密钥

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 -C "1580026067@qq.com" -f ~/.ssh/id_ed25519_github
```

命令会询问 passphrase。设置 passphrase 更安全；如果设置了，每次新会话可以通过 ssh-agent 缓存。

启动 ssh-agent 并加载私钥：

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519_github
ssh-add -l
```

显示公钥：

```bash
cat ~/.ssh/id_ed25519_github.pub
```

只把 `.pub` 公钥内容添加到 `GitHub -> Settings -> SSH and GPG keys`。私钥 `~/.ssh/id_ed25519_github` 绝对不能上传或发给别人。

因为密钥文件名不是默认的 `id_ed25519`，建议编辑 SSH 配置：

```bash
nano ~/.ssh/config
```

写入以下内容并保存：

```sshconfig
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/id_ed25519_github
  IdentitiesOnly yes
```

设置权限：

```bash
chmod 600 ~/.ssh/config
chmod 600 ~/.ssh/id_ed25519_github
chmod 644 ~/.ssh/id_ed25519_github.pub
```

### 3.3 在 GitHub 网页添加公钥

1. 登录正确的 GitHub 账号。
2. 打开 `Settings -> SSH and GPG keys -> New SSH key`。
3. Title 可以填写 `pi05-training-server-20260811`。
4. Key type 选择 Authentication Key。
5. Key 中只粘贴 `id_ed25519_github.pub` 的一整行内容。
6. 如果组织启用了 SSO，再执行 Configure SSO/Authorize。

测试连接：

```bash
ssh -T git@github.com
```

第一次连接会询问是否信任 GitHub 主机指纹，核对来源后输入 `yes`。成功时通常会显示 GitHub 已认证，但不提供 shell；这是正常结果。

如果失败，运行详细诊断：

```bash
ssh -vT git@github.com
```

重点确认输出中使用的是 `~/.ssh/id_ed25519_github`，以及当前 GitHub 账号对组织仓库有写权限。

### 3.4 理解和配置 remote

remote 是“本地仓库给远程 Git 地址起的名字”。当前仓库有多个 remote：

| remote | 用途 |
|---|---|
| `origin` | Hugging Face 官方 LeRobot 上游 |
| `mantis_server` | Mantis PI05 服务端私有仓库 |
| `blueworm` | 另一个 BlueWorm 代码仓库 |

查看当前 remote：

```bash
cd /home/lcjs-szw/repos/lerobot-pi05-folding-release
git remote -v
git remote get-url mantis_server
```

把 `mantis_server` 从 HTTPS 改成 SSH：

```bash
git remote set-url mantis_server \
  git@github.com:BlueWorm-EAI-Tech/lerobot_mantis_server.git
git remote -v
```

这里是修改远程地址，不会修改项目文件或 commit。不要把 Token 写进 remote URL。

## 4. 当前机器第一次上传 release 分支

### 4.1 上传前确认 GitHub 仓库和本地版本

需要先满足：

- GitHub 上已经存在 `BlueWorm-EAI-Tech/lerobot_mantis_server`。
- 当前 GitHub 账号对该仓库有 Write 权限。
- 第 3 节的 `ssh -T git@github.com` 已成功。
- 准备上传的是发布分支，不是开发分支或 `main`。

查看本机状态：

```bash
cd /home/lcjs-szw/repos/lerobot-pi05-folding-release
pwd
git branch --show-current
git status --short --branch
git log --oneline --decorate -5
git remote -v
```

当前发布分支应包含至少以下两个本地 commit：

```text
b7a43844 feat: include current PI05 experiments in release
2b1ff63b docs: add portable PI05 folding deployment
```

### 4.2 把本机这份文档加入发布仓库

本文档现在位于 `/home/lcjs-szw/doc`，不在 Git 仓库中。执行以下命令把它复制回发布仓库：

```bash
mkdir -p /home/lcjs-szw/repos/lerobot-pi05-folding-release/docs/mantis

cp /home/lcjs-szw/doc/PI05_FOLDING_GIT_AND_4090_MIGRATION_ZH.md \
  /home/lcjs-szw/repos/lerobot-pi05-folding-release/docs/mantis/

cd /home/lcjs-szw/repos/lerobot-pi05-folding-release
git status --short -- docs/mantis/PI05_FOLDING_GIT_AND_4090_MIGRATION_ZH.md
git diff -- docs/mantis/PI05_FOLDING_GIT_AND_4090_MIGRATION_ZH.md
```

确认内容正确后，只暂存和提交这份文档：

```bash
git add docs/mantis/PI05_FOLDING_GIT_AND_4090_MIGRATION_ZH.md
git diff --cached --stat
git diff --cached -- docs/mantis/PI05_FOLDING_GIT_AND_4090_MIGRATION_ZH.md
git commit -m "docs: expand local Git and GitHub workflow"
git log --oneline --decorate -5
```

不要在复制之前提交当前的删除状态，否则 Git 会记录“从发布版删除迁移文档”。

### 4.3 上传前做最后检查

```bash
cd /home/lcjs-szw/repos/lerobot-pi05-folding-release

# 分支必须正确
git branch --show-current

# 工作区应该没有不理解的修改
git status --short --branch

# 查看准备上传的最近版本
git log --oneline --decorate -10

# 检查最后一次提交包含哪些文件
git show --stat --oneline HEAD

# 检查仓库目录中是否混入大文件
find . -path ./.git -prune -o -type f -size +50M -print
```

`find` 如果显示模型、checkpoint、视频、数据集或日志，应先停止上传并检查这些文件是否被 Git 跟踪：

```bash
git ls-files --error-unmatch 大文件路径
```

如果命令输出该路径，说明大文件已被 Git 跟踪，需要先处理；仅仅补写 `.gitignore` 不会自动把它从历史中删除。

### 4.4 第一次 push 到 GitHub

确认 SSH 和检查都完成后执行：

```bash
cd /home/lcjs-szw/repos/lerobot-pi05-folding-release

git push -u mantis_server release/pi05-folding-portable-20260811
```

命令各部分含义：

| 内容 | 含义 |
|---|---|
| `git push` | 上传本地 commit |
| `-u` | 记录本地分支对应的远程上游分支 |
| `mantis_server` | 远程仓库名称 |
| `release/pi05-folding-portable-20260811` | 要上传的本地分支 |

上传完成后验证：

```bash
git status --short --branch
git branch -vv
git ls-remote --heads mantis_server \
  release/pi05-folding-portable-20260811
```

`git branch -vv` 应显示发布分支正在跟踪 `mantis_server/release/pi05-folding-portable-20260811`。`git ls-remote` 应输出远程 commit 编号和分支名称。

### 4.5 以后每天修改并上传

开始工作前，先确认工作区干净并获取远程更新：

```bash
cd /home/lcjs-szw/repos/lerobot-pi05-folding-release
git status --short --branch
git pull --ff-only
```

修改代码并完成测试后：

```bash
git status
git diff

git add 具体文件1
git add 具体文件2

git diff --cached --name-status
git diff --cached --stat
git diff --cached

git commit -m "fix: 简短、准确地说明这次改动"
git log --oneline --decorate -5
git push
```

第一次使用过 `-u` 后，后续的 `git push` 不需要再写 remote 和分支名。

查看本地尚未上传的 commit：

```bash
git log --oneline '@{u}..HEAD'
```

查看远程存在、但本地还没有的 commit：

```bash
git fetch mantis_server
git log --oneline 'HEAD..@{u}'
```

工作区干净时，用下面命令快进更新：

```bash
git pull --ff-only
```

如果提示 `Not possible to fast-forward`，说明本地和远程历史已经分叉。不要使用 force push；运行以下命令收集信息后再决定合并方案：

```bash
git status
git log --oneline --graph --decorate --all -20
```

### 4.6 全新 GitHub 仓库的首次连接方式

本项目已经有 `mantis_server`，不需要执行本节。其他全新项目在 GitHub 网页创建空仓库后，可以运行：

```bash
cd ~/repos/git-demo
git remote add origin git@github.com:你的账号或组织/git-demo.git
git remote -v
ssh -T git@github.com
git push -u origin main
```

如果 `git remote add origin` 提示 `remote origin already exists`，先查看现有地址，不要重复添加：

```bash
git remote -v
git remote get-url origin
```

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

### 12.1 `fatal: not a git repository`

当前目录不在 Git 仓库中。确认路径并进入项目：

```bash
pwd
cd /home/lcjs-szw/repos/lerobot-pi05-folding-release
git rev-parse --show-toplevel
git status
```

### 12.2 `git status` 显示 `modified` 或 `untracked`

`modified` 表示文件改过但尚未提交，先查看差异：

```bash
git diff
git diff -- 文件路径
```

`untracked` 表示新文件尚未受 Git 管理。确认它不是模型、数据、日志、虚拟环境或密钥后，再执行：

```bash
git add 文件路径
git diff --cached -- 文件路径
```

### 12.3 `nothing to commit, working tree clean`

表示当前没有尚未提交的修改。这不是错误。查看最近提交：

```bash
git log --oneline --decorate -5
```

如果刚才编辑的是 `/home/lcjs-szw/doc` 下的本文档，因为它在仓库外，所以项目 `git status` 不会显示；按第 4.2 节复制回仓库。

### 12.4 `Your branch is ahead`

本地有 commit 尚未上传。查看这些 commit：

```bash
git log --oneline '@{u}..HEAD'
git push
```

### 12.5 `Your branch is behind`

远程有新 commit。本地工作区干净时执行：

```bash
git fetch
git log --oneline 'HEAD..@{u}'
git pull --ff-only
```

### 12.6 `could not read Username for https://github.com`

remote 仍是 HTTPS，而当前终端不能交互输入凭据。切换为 SSH：

```bash
git remote -v
ssh -T git@github.com
git remote set-url mantis_server \
  git@github.com:BlueWorm-EAI-Tech/lerobot_mantis_server.git
git remote -v
```

### 12.7 `Permission denied (publickey)`

依次检查密钥、agent、SSH 配置和 GitHub 权限：

```bash
ls -l ~/.ssh/id_ed25519_github ~/.ssh/id_ed25519_github.pub
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519_github
ssh-add -l
ssh -vT git@github.com
```

仍失败时，确认公钥添加到了正确 GitHub 账号，并完成组织 SSO 授权。

### 12.8 push 被拒绝：`non-fast-forward`

远程分支包含本地没有的提交。不要 force push。先获取并查看关系：

```bash
git fetch mantis_server
git status
git log --oneline --graph --decorate --all -30
```

如果只是可以快进的远程更新：

```bash
git pull --ff-only
git push
```

如果 `pull --ff-only` 仍失败，说明历史已经分叉，需要人工决定 merge 或 rebase；初次使用时不要自行改写历史。

### 12.9 `large files detected`

大文件已经进入 commit。不要继续 push，先检查：

```bash
git status
git show --stat --oneline HEAD
find . -path ./.git -prune -o -type f -size +50M -print
```

不能只补一个 `.gitignore`，因为已经进入 commit 的文件仍在 Git 历史中。模型和数据应转移到 Hugging Face、NAS、对象存储或使用 `rsync`。

### 12.10 出现合并冲突

先查看冲突文件，不要继续 push：

```bash
git status
git diff --name-only --diff-filter=U
```

冲突文件中通常会出现 `<<<<<<<`、`=======`、`>>>>>>>` 标记。人工确认正确内容并删除标记，完成测试后再逐个暂存。若无法判断，应保留现场并请项目维护者一起处理，不要执行 `git reset --hard`。
