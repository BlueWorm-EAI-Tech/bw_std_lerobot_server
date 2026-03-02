#!/usr/bin/env python
"""
简单的PI05模型测试，验证基础功能
"""

import torch
import sys
from pathlib import Path

# 添加lerobot路径
sys.path.insert(0, '/home/lcjs-szw/repos/lerobot')

def test_pi05_basic():
    """测试PI05基础功能"""
    
    print("🔍 测试PI05基础功能")
    print("=" * 50)
    
    try:
        # 导入必要的模块
        from lerobot.policies.pi05.configuration_pi05 import PI05Config
        from lerobot.policies.pi05.modeling_pi05 import PI05Pytorch
        
        print("✅ 成功导入PI05模块")
        
        # 创建配置
        config = PI05Config(
            paligemma_variant="gemma_2b",
            action_expert_variant="gemma_300m",
            dtype="float32",
            chunk_size=100,
            n_action_steps=100,
            max_state_dim=16,
            max_action_dim=16,
            num_inference_steps=10
        )
        
        print("✅ 成功创建PI05配置")
        print(f"  - Paligemma变体: {config.paligemma_variant}")
        print(f"  - Action Expert变体: {config.action_expert_variant}")
        print(f"  - Chunk Size: {config.chunk_size}")
        print(f"  - Action Steps: {config.n_action_steps}")
        print(f"  - State Dim: {config.max_state_dim}")
        print(f"  - Action Dim: {config.max_action_dim}")
        
        # 尝试创建模型（这可能会失败，但我们想知道在哪一步失败）
        print("🔄 尝试创建PI05模型...")
        model = PI05Pytorch(config)
        print("✅ 成功创建PI05模型")
        
        # 测试基本推理
        print("🔄 测试基本推理...")
        
        # 创建模拟输入
        batch_size = 1
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # 图像输入 (模拟3个摄像头)
        images = [
            torch.randn(batch_size, 3, 224, 224).to(device),  # env_cam
            torch.randn(batch_size, 3, 224, 224).to(device),  # left_wrist_cam
            torch.randn(batch_size, 3, 224, 224).to(device)   # right_wrist_cam
        ]
        img_masks = [
            torch.ones(batch_size, dtype=torch.bool).to(device),
            torch.ones(batch_size, dtype=torch.bool).to(device),
            torch.ones(batch_size, dtype=torch.bool).to(device)
        ]
        
        # 语言输入
        tokens = torch.randint(0, 1000, (batch_size, config.tokenizer_max_length)).to(device)
        masks = torch.ones(batch_size, config.tokenizer_max_length, dtype=torch.bool).to(device)
        
        # 动作输入
        actions = torch.randn(batch_size, config.chunk_size, config.max_action_dim).to(device)
        
        print(f"  - 图像形状: {[img.shape for img in images]}")
        print(f"  - Token形状: {tokens.shape}")
        print(f"  - Action形状: {actions.shape}")
        
        # 测试前向传播
        model = model.to(device)
        model.train()
        
        loss = model.forward(images, img_masks, tokens, masks, actions)
        print(f"✅ 前向传播成功，损失值: {loss.mean().item():.6f}")
        
        # 测试推理模式
        model.eval()
        with torch.no_grad():
            sampled_actions = model.sample_actions(images, img_masks, tokens, masks)
            print(f"✅ 推理成功，动作形状: {sampled_actions.shape}")
            print(f"  - 动作范围: [{sampled_actions.min():.4f}, {sampled_actions.max():.4f}]")
            print(f"  - 动作均值: {sampled_actions.mean():.4f}")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pi05_basic()
    if success:
        print("\n🎉 PI05基础功能测试通过！")
    else:
        print("\n💥 PI05基础功能测试失败！")