# 自定义脚本

## websocket-act/
WebSocket ACT 推理系统，包含 server、client、部署脚本和配置。

| 文件 | 说明 |
|------|------|
| `websocket_act_server.py` | ACT 模型 WebSocket 推理服务 |
| `ros2_websocket_act_client.py` | ROS2 机器人客户端 |
| `websocket_act_client_example.py` | 测试用示例客户端 |
| `start_websocket_server.sh` | 服务启动脚本 |
| `deploy_ros2_client.sh` | 部署到机器人 PC 的脚本 |
| `test_websocket_server.py` | 服务端测试 |
| `websocket_server_config.yaml` | 服务端配置 |
| `ros2_client_config.yaml` | 客户端配置 |
| `requirements_websocket.txt` | 依赖列表 |

## dataset-tools/
数据集调试、修复和分析工具。

| 文件 | 说明 |
|------|------|
| `merge_dataset.py` | 合并多个数据集 |
| `recompute_stats.py` | 重算数据集统计量 |
| `recompute_stats_fast.py` | 快速重算统计量 |
| `recompute_all_stats.py` | 批量重算所有统计量 |
| `fix_stats_preserve_images.py` | 修复统计量（保留图片） |
| `analyze_dataset_gaps.py` | 分析 action/state 差距 |
| `audit_mantis_dataset.py` | 检查 Mantis 数据格式、统计量和异常关节 |
| `detailed_gap_analysis.py` | 详细差距分析 |
| `inspect_shoulder_roll_actions.py` | 检查 shoulder roll 关节数据 |
| `verify_stats_update.py` | 验证统计量更新 |
| `test_normalization_theory.py` | 归一化理论测试 |

## commands_memo.txt
常用命令备忘（训练、推理、数据集可视化等）。
