# Mantis 机器人本体数采修复方案

## 1. 文档目的

本文档的目标不是继续修补旧数据，而是保证 **Mantis 机器人本体下一次采集到的数据从源头就是正确的**。

指导方针只有一条：

**先修“按名字对齐”，再谈训练和数据后处理。**

这意味着：

- 不再依赖“关节数组默认顺序应该没变”的假设。
- 不再接受“字段缺失时静默补 0”的行为。
- 不再通过训练侧 swap、数据侧 swap 来兜底机器人本体的数采错误。

---

## 2. 当前已确认的问题

### 2.1 关节互换

在 2026-04-15 这批 Mantis 叠衣服数据中，肩部通道存在稳定互换：

- `left_shoulder_roll_joint.pos` 和 `left_shoulder_yaw_joint.pos` 互换
- `right_shoulder_roll_joint.pos` 和 `right_shoulder_yaw_joint.pos` 互换

对应到 16 维状态/动作向量，就是：

- `1 <-> 2`
- `9 <-> 10`

这不是随机噪声，更像是 **上游 joint 数组顺序变化后，下游仍按旧顺序解释**。

### 2.2 肘部为 0

在目前这三份叠衣服数据中：

- `left_elbow_joint.pos`
- `right_elbow_joint.pos`

都在 `observation.state` 和 `action` 中长期为 0。

这说明问题发生在采集链路上游，而不是训练阶段。

---

## 3. 现有代码中暴露出的高风险点

以下几个实现细节，足以解释为什么会出现“关节互换”和“肘部为 0”。

### 3.1 机器人状态读取依赖数组下标，而不是关节名字

当前机器人侧客户端从 ROS `JointState` 读状态时，直接使用：

- `msg.position[:16]`

而没有根据：

- `msg.name`

来做重排。

相关文件：

- `scripts/websocket-mantis/mantis_websocket_client.py`
- `scripts/websocket-mantis/mantis_websocket_client_json.py`

这意味着只要机器人控制代码更新后改变了 `JointState` 发布顺序，LeRobot 侧就会把“值对不上名字”的状态静默写进数据集。

### 3.2 动作发送路径存在“缺字段默认补 0”的风险

当前 Mantis 机器人类的 `send_action()` 实现会先构造一个全 0 的 16 维数组，然后只对出现过的 key 赋值：

```python
goal_positions = np.zeros(16)
for i, joint in enumerate(ALL_JOINTS):
    key = f"{joint}.pos"
    if key in action:
        goal_positions[i] = action[key]
```

如果上游 action 字典里缺了 elbow，或 elbow key 名字不匹配，那么最终发出去的 elbow 就会是 0。

相关文件：

- `src/lerobot/robots/mantis/mantis.py`

### 3.3 旧版动作命令通道是纯数组，不带名字

旧版机器人侧客户端写命令时使用的是：

- `Float64MultiArray`

这类消息只携带数组，不携带 joint name。

一旦控制端更新了数组顺序，而客户端仍按旧顺序发命令，就会把动作写错。

相关文件：

- `scripts/websocket-mantis/mantis_websocket_client.py`

---

## 4. 根因判断

### 4.1 关节互换的最可能根因

高置信判断：

**机器人本体控制代码更新后，joint 发布或消费顺序发生变化，但数采侧仍使用旧的 index-based 顺序解释 joint 数组。**

更具体地说，可能是以下任一情况：

1. `JointState.name` 顺序发生变化，但客户端只读 `position[:16]`
2. 控制端内部 joint 顺序变化，但命令侧仍用旧数组顺序
3. 状态侧和动作侧来自两条不同链路，两边对同一数组维度的语义解释不同

这类问题最典型的表征，就是：

- 不是全部乱掉
- 而是某几个通道稳定成对互换

### 4.2 肘部为 0 的最可能根因

高置信判断：

**elbow 通道在某一级链路中没有被正确填值，随后被默认值 0 贯穿了状态和动作采集。**

最可能的几种来源：

1. teleop / IK / 上层控制输出里本来就没有 elbow
2. `JointState` 发布中 elbow name 存在，但 `position` 没更新
3. 状态侧有 elbow，但 action 字典缺 elbow key，发送时被静默补 0
4. elbow 被控制端错误地视为 fixed / passive / 不可控关节

这类问题最典型的表征，就是：

- `state` 和 `action` 两边都长期为 0
- 而其他关节正常变化

---

## 5. 修复原则

机器人本体数采修复必须遵守以下原则。

### 5.1 所有关节都按名字对齐，禁止按数组下标直接解释

凡是 ROS `JointState`、控制器 joint 数组、SDK joint 数组，只要上游提供了名字，就必须：

- 先建立 `joint_name -> value` 映射
- 再按本地 `ALL_JOINTS` 进行重排

禁止使用：

- `msg.position[:16]`
- “前 16 个就是目标顺序”
- “控制器顺序应该不会变”

### 5.2 缺失字段必须 fail fast，禁止静默补 0

如果某个关节缺失、重复、NaN、长度不符，应该：

- 立刻报错
- 阻止正式采集开始

而不是：

- 自动补 0
- 忽略缺失字段继续录制

### 5.3 命令通道优先使用带名字的消息

如果控制端支持：

- `sensor_msgs/JointState`
- 或其他带 `name` 的消息

则命令发送必须带名字。

只有在控制端 **明确只能接收数组** 时，才允许发纯数组；但此时必须显式维护：

- `controller_joint_order`
- 版本号
- 对应校验脚本

### 5.4 采集前必须通过单关节 smoke test

在正式录制前，必须先做 10 秒左右的单关节测试，自动验证：

- 关节名字与数组维度映射是否正确
- elbow 是否真实变化
- shoulder roll / yaw 是否串位

不通过就禁止开始正式数采。

---

## 6. 目标架构

### 6.1 统一的 canonical joint 顺序

Mantis 数采、推理、回放、日志，一律使用同一份 canonical 顺序：

```python
[
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    "left_gripper_joint",
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
    "right_gripper_joint",
]
```

来源：

- `src/lerobot/robots/mantis/mantis.py` 中的 `ALL_JOINTS`

### 6.2 输入状态链路

目标流程：

```text
ROS / SDK JointState
    -> 读取 name + position
    -> 构建 name_to_value
    -> 校验完整性
    -> 按 ALL_JOINTS 重排
    -> 得到 canonical 16 维状态向量
    -> 写入 observation.state
```

### 6.3 输出动作链路

目标流程：

```text
模型 / teleop / IK 输出
    -> 先转成 {joint_name: value}
    -> 校验 key 完整性
    -> 若控制端支持 name: 发送带 name 的命令
    -> 若控制端只支持数组: 按 controller_joint_order 显式重排
    -> 记录“实际发送的命令”而不是隐含默认值
```

---

## 7. 必做修复项

## 7.1 修复机器人状态读取：按名字重排

### 问题

当前实现只取 `msg.position[:16]`，没有使用 `msg.name`。

### 修复要求

在 ROS `JointState` 回调里：

1. 校验 `len(msg.name) == len(msg.position)`
2. 建立 `name_to_value = dict(zip(msg.name, msg.position))`
3. 使用 `ALL_JOINTS` 逐项取值并重排
4. 如果任一 canonical joint 缺失，直接报错并打断采集
5. 如果存在重复 joint name，也直接报错

### 推荐伪代码

```python
def joint_state_to_canonical(msg, expected_joint_names):
    if len(msg.name) != len(msg.position):
        raise ValueError("JointState name/position length mismatch")

    if len(set(msg.name)) != len(msg.name):
        raise ValueError("Duplicate joint names in JointState")

    name_to_value = dict(zip(msg.name, msg.position))

    missing = [name for name in expected_joint_names if name not in name_to_value]
    if missing:
        raise ValueError(f"Missing joints in JointState: {missing}")

    return np.array([name_to_value[name] for name in expected_joint_names], dtype=np.float32)
```

### 额外要求

每次连接机器人时打印一次：

- 上游发布顺序 `msg.name`
- 本地 canonical 顺序 `ALL_JOINTS`
- 是否完全一致

如果不一致，也不应报错，只要名字齐全并且重排成功即可。

## 7.2 修复动作命令发送：禁止隐式顺序假设

### 问题

旧版命令通道是纯数组，不带名字；同时 `send_action()` 对缺失字段会静默补 0。

### 修复要求

1. 命令源统一先生成 `{joint_name: value}`
2. 发送前校验 16 个 joint key 是否齐全
3. 若控制端支持带 `name` 的消息，优先发送带 `name` 的消息
4. 若控制端必须收数组，则在配置文件中显式维护 `controller_joint_order`
5. 按 `controller_joint_order` 生成数组，禁止复用 `ALL_JOINTS` 直接裸发

### 禁止行为

- 缺失 elbow 时自动补 0
- 因为“字段不重要”而跳过某个 joint
- 因为“顺序历史上一直没变”而不做校验

## 7.3 修复 `send_action()`：缺关节直接报错

### 当前风险

当前实现先创建全 0 数组，再逐项写入存在的 key；这会把缺失关节静默变成 0。

### 修复要求

把：

```python
goal_positions = np.zeros(16)
```

这类逻辑改成 fail-fast 模式：

```python
missing = [f"{joint}.pos" for joint in ALL_JOINTS if f"{joint}.pos" not in action]
if missing:
    raise ValueError(f"Missing action keys: {missing}")
```

随后再组装数组。

## 7.4 明确 elbow 的上游来源

机器人本体侧必须查清 elbow 在哪一级第一次变成 0。

建议沿以下链路逐级打印：

1. teleop 原始输出
2. IK / 中间控制输出
3. 发送给机器人前的 action dict
4. 机器人控制端实际接收到的命令
5. `/joint_states` 中的 elbow 反馈

如果某一级开始 elbow 就是 0，该级就是首要修复点。

## 7.5 增加“数采前预飞检查”

正式数采前必须执行一段短测试，建议命名为：

- `mantis_data_collection_preflight`

至少包含以下检查：

1. `JointState.name` 是否覆盖全部 `ALL_JOINTS`
2. 是否有重复 joint name
3. elbow state 在手动摆动时标准差是否大于阈值
4. elbow action 在 teleop/命令测试时标准差是否大于阈值
5. shoulder_roll 和 shoulder_yaw 的单关节测试是否出现串位
6. 当前控制端 joint 顺序是否被记录到日志

任一失败，禁止开始正式采集。

---

## 8. 单关节 smoke test 方案

正式采集前，按以下顺序逐个关节做手动测试：

1. 左肩 roll
2. 左肩 yaw
3. 左肘
4. 右肩 roll
5. 右肩 yaw
6. 右肘

每个关节测试 2 到 3 秒即可。

### 期望结果

如果只动 `left_shoulder_roll_joint`：

- `observation.state[left_shoulder_roll_joint]` 明显变化
- `action[left_shoulder_roll_joint]` 明显变化
- `left_shoulder_yaw_joint` 不应同步出现同量级变化

如果只动 `left_elbow_joint`：

- `observation.state[left_elbow_joint]` 不应恒为 0
- `action[left_elbow_joint]` 不应恒为 0

### 自动判定规则

可以用下面的简单阈值：

- 目标关节标准差 `> 0.02 rad`
- 非目标相关关节标准差 `< 0.01 rad`
- elbow 的 `max - min > 0.05 rad`

如果左肩 roll 测试时左肩 yaw 的变化幅度和目标关节接近，则高概率存在通道串位。

---

## 9. 采集过程中的在线保护

正式采集期间，不应只是盲录。建议在线增加以下保护：

### 9.1 每个 episode 开始前输出 joint 顺序摘要

记录：

- 上游状态消息 joint 顺序
- 控制器命令 joint 顺序
- 本地 canonical 顺序
- 机器人控制代码版本
- 数采客户端 git commit

### 9.2 每 N 帧计算关键关节健康指标

建议每 30 帧统计一次：

- shoulder roll / yaw 的均值和标准差
- elbow 的均值和标准差
- `action - state` 的均值和标准差

若出现以下情况，立即报警：

- elbow std 接近 0
- shoulder roll / yaw 两个关节高度同步
- 某关节 action 全 0 但 state 明显变化

### 9.3 自动中断条件

建议触发以下任一条件就停止录制当前 episode：

1. 任一 elbow 在最近 2 秒内 `std < 1e-4`
2. 任一关键 joint 出现 NaN / Inf
3. `JointState` 丢失关键 joint name
4. 实际发送动作缺少关键 key

---

## 10. 正式数采前的验收标准

机器人本体侧在恢复正式录制前，必须满足以下验收条件。

### 10.1 状态侧验收

- `JointState.name` 覆盖全部 16 个 joint
- 名字和数组映射已经通过重排逻辑固定下来
- shoulder roll / yaw 单关节测试无串位
- elbow 单关节测试不为 0

### 10.2 动作侧验收

- 发送给机器人前的 action dict 包含全部 16 个 joint
- 任何 joint 缺失时系统直接报错，不允许静默补 0
- 如果控制端使用数组命令，则其顺序已经文档化并经过单关节验证

### 10.3 数据集侧验收

先录 1 到 3 个短 episode，不要直接开整批采集。

短 episode 验收标准：

- `observation.state` 的 elbow 方差非零
- `action` 的 elbow 方差非零
- shoulder `roll/yaw` 不再出现固定 swap
- 关键关节的 `action - state` 分布在可解释范围内

只有短 episode 验收通过，才允许开始正式批量采集。

---

## 11. 推荐实施顺序

### 第一步：修状态读取

优先把所有 `JointState -> 16维向量` 的逻辑改成按名字对齐。

这是最关键的一步，因为如果状态语义就是错的，后面的采集、推理、训练都会建立在错误输入上。

### 第二步：修动作发送

把命令通道改成：

- 优先带名字发送
- 若必须数组发送，则显式维护 controller 顺序
- 缺字段直接报错

### 第三步：做单关节 preflight

在机器人本体上做 10 秒到 30 秒的单关节测试，验证：

- shoulder 没串位
- elbow 不是 0

### 第四步：录短 episode 验收

先录少量短片段，立刻跑检查脚本，不要直接录整批任务数据。

### 第五步：开始正式数采

只有 preflight 和短 episode 验收都通过，才开始正式任务采集。

---

## 12. 建议新增的本体侧脚本

建议机器人本体侧新增以下脚本。

### 12.1 `joint_state_name_alignment_check.py`

用途：

- 订阅 `JointState`
- 打印 `msg.name`
- 校验是否覆盖 `ALL_JOINTS`
- 输出重排后的 canonical 向量

### 12.2 `single_joint_smoke_test.py`

用途：

- 引导人工逐个移动指定关节
- 在线统计目标关节和相邻关节的变化幅度
- 自动判断是否存在串位或全 0

### 12.3 `mantis_data_collection_preflight.py`

用途：

- 把名字覆盖检查、elbow 检查、shoulder 串位检查合并成正式数采前的统一入口
- 不通过则返回非零退出码，阻止正式录制脚本启动

---

## 13. 不建议再做的事情

以下做法不应再作为主要方案：

1. 继续依赖训练后数据 swap 来修机器人本体数采问题
2. 在推理端继续保留临时 joint swap 作为长期方案
3. elbow 缺失时继续补 0 录制
4. 因为“模型看起来还能动”而跳过数采链路修复

这些做法最多只能作为临时排障手段，不能作为正式数采方案。

---

## 14. 最终结论

当前 Mantis 数采问题更像是两类上游接口错误：

1. **关节互换**：本质是 joint 顺序契约失效，必须改成按名字对齐
2. **肘部为 0**：本质是 elbow 通道缺失或未填值，必须改成缺字段直接报错

所以，机器人本体侧的修复重点不是“继续修旧数据”，而是：

- 用 `joint name` 固定状态语义
- 用完整 key 校验固定动作语义
- 用 preflight 和 smoke test 阻止错误数据进入数据集

如果这三点落实到位，下次采集出来的数据才有资格进入训练流程。
