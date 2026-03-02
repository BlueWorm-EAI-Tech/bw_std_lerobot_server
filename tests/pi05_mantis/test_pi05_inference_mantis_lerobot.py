#!/usr/bin/env python
"""
测试训练好的PI05模型在Mantis机器人上的推理能力
"""

import torch
import numpy as np
from pathlib import Path
import sys

# 添加lerobot路径
sys.path.insert(0, '/home/lcjs-szw/repos/lerobot')

from lerobot.common.datasets.factory import make_dataset
from lerobot.scripts.eval import rollout
from lerobot.common.policies.factory import make_policy
from lerobot.common.utils.utils import init_logging, log_output_dir

def test_pi05_inference():
    """测试PI05模型推理"""
    
    # 配置参数
    checkpoint_path = "/home/lcjs-szw/repos/lerobot/outputs/train/pi05_mantis_final_20260212_153042"  # 根据实际训练结果调整
    dataset_path = "/home/lcjs-szw/datasets/datasets/pick_place_cube_0121"
    
    print("🔍 测试PI05模型推理能力")
    print(f"_checkpoint路径: {checkpoint_path}")
    print(f"数据集路径: {dataset_path}")
    print("=" * 50)
    
    # 检查checkpoint是否存在
    if not Path(checkpoint_path).exists():
        print(f"❌ Checkpoint路径不存在: {checkpoint_path}")
        print("请先运行训练脚本生成模型")
        return False
    
    try:
        # 加载数据集获取任务信息
        dataset = make_dataset(dataset_path)
        print(f"✅ 成功加载数据集，包含 {len(dataset)} 个样本")
        
        # 获取第一个样本的任务描述
        first_item = dataset[0]
        if 'language_instruction' in first_item:
            task_description = first_item['language_instruction']
            print(f"📋 任务描述: {task_description}")
        else:
            task_description = "pick up the cube and place it"  # 默认任务
            print("📋 使用默认任务描述")
        
        # 创建策略
        policy = make_policy(
            policy_type="pi05_mantis",
            pretrained_policy_name_or_path=checkpoint_path
        )
        
        print("✅ 成功加载PI05策略")
        
        # 准备输入数据
        # 模拟观测数据结构
        batch = {
            'observation.state': first_item['observation.state'].unsqueeze(0),  # 添加batch维度
            'observation.images.env_cam': first_item['observation.images.env_cam'].unsqueeze(0),
            'observation.images.left_wrist_cam': first_item['observation.images.left_wrist_cam'].unsqueeze(0),
            'observation.images.right_wrist_cam': first_item['observation.images.right_wrist_cam'].unsqueeze(0),
            'language_instruction': [task_description]  # 添加语言指令
        }
        
        print("📦 准备输入数据完成")
        
        # 执行推理
        policy.eval()
        with torch.no_grad():
            actions = policy.select_action(batch)
        
        print("✅ 推理执行成功")
        print(f"动作形状: {actions.shape}")
        print(f"动作范围: [{actions.min():.4f}, {actions.max():.4f}]")
        print(f"动作均值: {actions.mean():.4f}")
        print(f"动作标准差: {actions.std():.4f}")
        
        # 检查动作合理性
        if torch.isnan(actions).any():
            print("❌ 动作包含NaN值")
            return False
            
        if torch.isinf(actions).any():
            print("❌ 动作包含无穷大值")
            return False
            
        # 动作应该在合理范围内 (-1, 1)
        if actions.abs().max() > 2.0:
            print("⚠️  动作值超出预期范围，可能存在数值不稳定")
        
        print("✅ 动作输出看起来合理")
        return True
        
    except Exception as e:
        print(f"❌ 推理测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pi05_inference()
    if success:
        print("\n🎉 PI05推理测试通过！")
    else:
        print("\n💥 PI05推理测试失败！")