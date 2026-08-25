# Mantis 模型与任务

本页汇总 BlueWorm 已经开展的 π0.5、ACT 和 SmolVLA 工作，帮助新成员直接找到训练脚本、推理服务和任务说明。公司模型 checkpoint 尚未统一上传，因此页面只提供已经存在的代码入口，不设置无效下载链接。

## 模型总览

| 模型    | 任务                                 | 训练入口                                                       | 推理入口                                                       | 当前情况                                       |
| ------- | ------------------------------------ | -------------------------------------------------------------- | -------------------------------------------------------------- | ---------------------------------------------- |
| π0.5    | 衣物折叠                             | `examples/training/mantis/train_pi05_mantis.sh`                | `scripts/websocket-server/pi05/websocket_pi05_server.py`       | 主要训练和服务代码已有；公司 checkpoint 待上传 |
| ACT     | 抓取平放的东方树叶饮料容器并直立放置 | `docs/mantis/MANTIS_TRAINING_GUIDE.md` 与 LeRobot ACT 训练入口 | `scripts/websocket-server/act/websocket_act_server.py`         | 任务已开展；模型和完整验收资料待整理           |
| ACT     | 根据语言指令识别、选择并抓取饮料     | 沿用 ACT 训练链路                                              | ACT WebSocket 服务                                             | 正在开发，不填写未经确认的成功率               |
| SmolVLA | 方块抓取—放置                        | `examples/training/mantis/train_smolvla_mantis.sh`             | `scripts/websocket-server/smolvla/websocket_smolvla_server.py` | 训练和服务代码已有；统一机器人端接入不完整     |

## 推荐阅读顺序

1. 阅读 [Mantis 数据采集与训练指南](MANTIS_TRAINING_GUIDE.md)。
2. 按任务选择 π0.5、ACT 或 SmolVLA 的训练脚本，检查脚本中的数据、基础模型和输出目录。
3. 训练前确认数据包含环境、左腕和右腕三路图像，状态、动作和任务文本与模型配置一致。
4. 训练完成后记录使用的 checkpoint、配置和数据批次，再启动对应 WebSocket 服务。
5. 机器人端使用 [VLA_lerobot_mantis_runtime](https://github.com/BlueWorm-EAI-Tech/VLA_lerobot_mantis_runtime) 完成相机检查、连接和安全限制。

## 训练代码在哪里

```text
examples/training/mantis/
├── train_pi05_mantis.sh
├── train_pi05_mantis_continue.sh
├── train_smolvla_mantis.sh
├── train_smolvla_continue.sh
└── eval_pi05_mantis.sh
```

ACT 使用仓库中的 LeRobot ACT policy 和训练入口。现有训练总结与历史问题记录位于：

- `docs/mantis/MANTIS_TRAINING_GUIDE.md`
- `docs/mantis/MANTIS_TRAINING_SUMMARY.md`
- `docs/mantis/MANTIS_DATA_COLLECTION_FIX_PLAN.md`
- `docs/dataset-issues/`

这些历史文件用于追溯已经开展的工作；新的训练记录应写清楚当前数据集和配置，不要直接复制旧路径或旧结论。

## 推理服务在哪里

```text
scripts/websocket-server/
├── pi05/      π0.5 服务与启动脚本
├── act/       ACT 服务与示例客户端
├── smolvla/   SmolVLA 服务与示例客户端
└── ros2/      ROS 2 客户端资料
```

服务启动后至少检查：模型能否加载、计算设备是否正确、三路图像键是否一致、状态和动作维度是否正确、任务文本是否传入。第一次连接机器人时，应先在无物体接触条件下限制动作时间和范围。

## 当前可以说明的结果

- π0.5、ACT 和 SmolVLA 均已有 Mantis 相关训练或推理代码入口。
- π0.5 是第一版衣物折叠主要案例。
- ACT 已开展饮料容器直立放置任务，并正在开展语言指令饮料识别与抓取任务。
- SmolVLA 已有方块抓取—放置的训练和服务代码，但统一机器人端接入仍不完整。

## 当前不能写成已经完成的内容

- 公司微调 checkpoint 尚未统一上传。
- 没有统一测试记录的任务不提供成功率。
- 服务端能够启动不等于机器人已经完成闭环任务。
- 示例客户端能够收发数据不等于真机安全和任务效果已经验收。

完整教培说明见 [BlueWorm Mantis 具身智能使用手册](https://github.com/BlueWorm-EAI-Tech/BlueWorm-Docs/tree/main/docs/embodied)。

维护组：具身组<br>
负责人：[@ACESUSUSU](https://github.com/ACESUSUSU)<br>
最近更新：2026-08-24
