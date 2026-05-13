# Mantis 迁移 Robot-Folding 落地清单

## 1. 文档目标

本文档用于回答一个非常具体的问题：

**Hugging Face 的 `robot-folding` 这套方案，能不能迁移到 Mantis 上实现叠衣服任务？**

结论先写在前面：

- **不能原样照搬 OpenArm 方案**
- **可以迁移它的方法论和训练/部署链路，做成 Mantis 版 folding pipeline**

本文档同时基于一个新的重要前提：

**Mantis 机器人本体的数采修复即将完成。**

因此本方案不再以“修旧数据”为中心，而是以“下一轮采到正确数据后，如何把 folding 方案落地”为中心。

---

## 2. 总体判断

### 2.1 哪些地方不能直接复用

`robot-folding` 公开内容对应的是一套完整的 **双臂 OpenArm 折衣系统**，不是单一模型文件。它依赖：

- `bi_openarm` 机器人形态
- 对应的遥操作硬件
- OpenArm 版数据采集与命令链路
- 该平台定义下的状态/动作语义

这些部分都不是当前 Mantis 可以直接继承的。

### 2.2 哪些地方可以迁移

对 Mantis 来说，真正有价值的是下面这些“平台无关的核心思路”：

- 叠衣服任务拆成一整条 pipeline，而不是只依赖一次 BC 训练
- 使用 **relative actions**
- 使用 **Pi0.5 / SmolVLA** 这类 action-chunking policy
- 使用 **RTC** 改善大模型实时执行平滑性
- 使用 **SARM + RA-BC** 对长时序任务做进度建模和样本重加权
- 使用 **HIL / DAgger** 做在线纠偏

当前仓库里，这些算法层能力大部分已经具备：

- `docs/source/rtc.mdx`
- `docs/source/sarm.mdx`
- `examples/rtc/eval_with_real_robot.py`
- `src/lerobot/utils/rabc.py`

因此，**Mantis 版 folding 的关键工作不在“算法从零实现”，而在“机器人侧语义对齐 + 任务级适配 + 新数据采集”**。

---

## 3. 和当前 Mantis 的匹配度

### 3.1 已具备的基础

当前 Mantis 已经具备以下基础条件：

- 双臂 16 维状态/动作空间
- 3 路视觉输入
- 已打通 `ACT / Pi0.5 / SmolVLA` 的训练与服务器侧推理链路
- 已在 `lerobot` 中存在 Mantis robot 实现
- 已经识别出历史数据的关键问题，并形成了修复方案

这意味着，Mantis 已经不是“从 0 到 1”，而是“从已有训练推理系统扩展到更长时序、更难的布料任务”。

### 3.2 当前最大的非算法风险

当前最大的风险不是模型结构，而是 **机器人本体的状态/动作语义正确性**。

根据已有排查，Mantis 历史叠衣服数据暴露过两个典型问题：

- shoulder 通道互换
- elbow 通道长期为 0

如果这些问题带入折衣服任务，长时序动作会比 pick-and-place 更明显地被放大。  
所以，`robot-folding` 能否在 Mantis 上落地，第一前提不是“先训一个更大的模型”，而是：

**保证下一批 Mantis folding 数据在机器人本体侧就是名字对齐、字段完整、语义稳定的。**

相关前置文档：

- `docs/mantis/MANTIS_DATA_COLLECTION_FIX_PLAN.md`

---

## 4. 迁移时哪些模块能直接复用

下面按模块给出复用判断。

| 模块 | 在 robot-folding 中的作用 | Mantis 侧可复用性 | 结论 |
|------|---------------------------|-------------------|------|
| 双臂基础训练框架 | policy 训练与推理主干 | 高 | 直接复用 |
| Pi0.5 / SmolVLA | 主策略模型 | 高 | 直接复用 |
| RTC | 推理实时平滑执行 | 高 | 直接复用 |
| SARM | 长时序任务进度建模 | 高 | 直接复用 |
| RA-BC | 按进度权重训练样本 | 高 | 直接复用 |
| HIL / DAgger 流程 | 在线纠偏迭代 | 中 | 流程可复用，机器人接口需改 |
| relative actions 思路 | 改善布料任务泛化 | 中高 | 需要按 Mantis 动作语义重做 |
| OpenArm 遥操作方案 | 采集高质量示教 | 低 | 不能直接复用 |
| OpenArm 机器人配置 | 状态/动作语义基准 | 低 | 不能直接复用 |
| OpenArm 数据集 | 直接训练 Mantis | 低 | 不建议直接混训 |

---

## 5. 迁移时必须重写或重新定义的部分

### 5.1 机器人侧状态/动作定义

这是第一优先级，必须基于 Mantis 自己的 canonical joint 定义重建：

- `observation.state`
- `action`
- 各维度对应的 joint name
- gripper 开合语义
- 左右手腕相机命名与顺序

如果这里仍然存在“按数组下标解释”或“缺字段补 0”，后续一切训练优化都没有意义。

### 5.2 relative action 的数学定义

`robot-folding` 的一个关键点是使用 relative actions，但这不是一句开关配置就结束的事情。  
在 Mantis 上，需要重新明确：

- 相对谁定义：相对当前观测，还是相对上一控制步
- 对哪些维度做 relative：全部关节，还是只对 arm 关节，不对 gripper 做 relative
- 训练标签如何从绝对动作转换得到
- 推理时如何从相对动作积分回实际可执行命令
- 安全边界如何加上 joint clamp / rate limit

这一步必须和机器人本体控制约束一起设计，不能只看训练侧。

### 5.3 遥操作与高质量数据策略

`robot-folding` 的成功很大程度上来自更高质量、更一致的示教和后续 HIL/DAgger。  
在 Mantis 上，需要重新定义：

- 谁来做示教
- 示教输入设备是什么
- 折衣服 task instruction 如何规范化
- 成功/失败 episode 如何标记
- 是否做高质量子集筛选

### 5.4 任务拆解与评价标准

Mantis 版 folding 不能直接照搬“最终是否折好”这一单一指标，需要先定义中间可验证目标，例如：

- 接近衣服边缘
- 两手抓住目标点
- 将衣服抬离桌面
- 第一折完成
- 第二折完成
- 最终形状稳定

这些阶段定义会直接影响：

- SARM 标注
- 失败回放分析
- DAgger 纠偏策略
- 训练数据筛选

---

## 6. 建议的落地路径

建议按 5 个阶段推进，而不是一上来就追求完整折衣成功。

### 阶段 0：数采修复完成后的准入检查

在开始任何 folding 数据采集前，必须先通过一轮新的准入验证。

**准入条件：**

- 所有 joint 都按名字对齐
- 缺失 joint 直接 fail fast
- elbow 在单关节测试中真实变化
- shoulder roll / yaw 不再互换
- 录到数据集里的 `state/action` 与机器人实发命令一致
- 左右腕相机与环境相机命名稳定

通过标准：

- 10 秒单关节 smoke test 全通过
- 录制 1 个短 episode 后，离线回放检查各维度曲线无异常
- 不需要再在推理服务器里用临时 swap 兜底

### 阶段 1：先做短视界布料原语

先不要直接训练“完整折衣服”，而是先建立几个短时序 cloth primitive：

- 左手接近衣角
- 右手接近衣角
- 双手抓取
- 抬起并拉平
- 单次对折

这一阶段的目标不是追求最终成功率，而是验证：

- 新数据语义是否稳定
- relative action 是否比 absolute action 更稳
- Pi0.5 / SmolVLA 在 Mantis 上哪个更适合作为 folding baseline

### 阶段 2：建立 folding baseline

当短原语稳定后，再进入完整任务 baseline：

- 任务统一命名，例如 `fold the tshirt`
- 固定衣服类别、摆放区域、背景和初始姿态范围
- 使用同一批 camera layout 和 joint schema
- 先训一个 **不带 SARM/RA-BC 的 baseline policy**

建议首个 baseline 同时保留两条线：

- `absolute action baseline`
- `relative action baseline`

这样能快速判断 relative formulation 在 Mantis 上是否同样带来明显收益。

### 阶段 3：加入 SARM + RA-BC

当 baseline 能学到“接近抓衣服”的趋势后，再加奖励建模：

- 先定义 4 到 6 个稀疏阶段
- 训练 SARM progress model
- 对训练样本预计算 progress
- 用 RA-BC 重新训练 policy

这一阶段最适合解决的问题是：

- 长 episode 中前半段有意义、后半段退化
- 演示质量不一致
- policy 会学到停顿、犹豫、左右晃动这类低质量片段

### 阶段 4：加入 HIL / DAgger

如果 baseline + RA-BC 后，策略已经出现“能接近成功但经常在局部失败”的情况，就该进入 HIL/DAgger。

这时建议只采 **策略容易失败的狭窄分布**，例如：

- 已抓住但提拉方向不对
- 一侧抓住另一侧漏抓
- 第一折完成后第二折失败

这类数据对长时序布料任务通常比继续盲目堆完整演示更有效。

### 阶段 5：用 RTC 做部署稳定化

如果最终选择 Pi0.5 或 SmolVLA 作为 folding 主策略，部署时建议尽早接入 RTC，而不是等末期再补。

原因很简单：

- 叠衣服动作连续性强
- chunk 之间的突变会直接表现为拉扯方向突变
- 布料任务对暂停、犹豫、回摆比刚体抓取更敏感

RTC 解决的是 **推理延迟和 chunk 衔接问题**，这对 folding 很关键。

---

## 7. 推荐的最小可行版本

如果目标是尽快验证“这条路是否适合 Mantis”，建议先做一个最小可行版本，而不是一开始就全量接入所有模块。

### MVP 配置

- 机器人：Mantis
- 相机：`env + left_wrist + right_wrist`
- policy：`pi05` 和 `smolvla` 二选一或并行对比
- 数据：只采单一衣物类别，例如 T 恤
- 动作定义：同时保留 absolute / relative 两种训练标签
- 训练：先不接 SARM / RA-BC
- 推理：尽早接 RTC

### MVP 成功标准

只要满足以下任意一个，就说明这条路线值得继续投资源：

- 策略稳定学到双手接近并尝试抓衣服
- 相对动作版本明显比绝对动作版本更稳定
- 失败主要来自视觉/任务难度，而不是 joint 语义错误

如果连这一步都达不到，应优先回头检查：

- 新数采链路是否仍存在字段错误
- 相机视角是否不足
- task instruction 是否不稳定
- 是否把多个难度差异很大的初始状态混在一起训练

---

## 8. 实施顺序建议

建议按下面顺序安排工作：

1. 完成机器人本体数采修复并通过 smoke test
2. 去掉所有临时 joint swap 兜底逻辑，确认链路本身正确
3. 设计 Mantis 版 folding 的 canonical dataset schema
4. 先采 20 到 50 条短原语数据做 sanity check
5. 做 absolute vs relative 小实验
6. 选出更稳的 formulation 后再扩完整 folding 数据
7. 训练 baseline policy
8. 失败分析后再决定是否接 SARM / RA-BC
9. 策略接近可用后，再进入 HIL / DAgger 迭代
10. 用 RTC 做最终部署稳定化

---

## 9. 当前最重要的工程判断

在你们当前阶段，最重要的不是继续研究旧的异常数据，而是：

**把“下一批数据一定正确”这件事做成系统能力。**

如果这一点成立，那么 `robot-folding` 对 Mantis 的意义会非常大，因为你们已经具备：

- 本地 `lerobot` 训练能力
- 服务器侧推理能力
- Mantis 机器人适配
- 双臂视觉输入

届时真正缺的，不是算法名字，而是：

- 稳定正确的数据
- 合理的 relative action 设计
- 渐进式任务拆解
- 面向失败分布的迭代采集

---

## 10. 下一步建议

等 Mantis 机器人本体数采修复完成后，建议立刻做下面三件事：

1. 录制一份 **folding preflight 数据集**
2. 基于这份数据集验证 `absolute / relative` 两套标签转换是否正确
3. 选一个最小 cloth primitive 做第一轮训练与部署验证

如果这三步顺利，就可以正式进入 Mantis 版 `robot-folding` 的工程落地阶段。
