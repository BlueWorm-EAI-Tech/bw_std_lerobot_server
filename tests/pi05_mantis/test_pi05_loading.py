#!/usr/bin/env python
"""测试PI05模型加载和基本功能"""

import torch
import sys
from pathlib import Path

# 添加lerobot路径
sys.path.insert(0, '/home/lcjs-szw/repos/lerobot')

def test_pi05_loading():
    """测试PI05模型加载"""
    
    print("🔍 测试PI05模型加载")
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
        print(f"配置详情:")
        print(f"  - paligemma_variant: {config.paligemma_variant}")
        print(f"  - action_expert_variant: {config.action_expert_variant}")
        print(f"  - chunk_size: {config.chunk_size}")
        print(f"  - n_action_steps: {config.n_action_steps}")
        print(f"  - max_state_dim: {config.max_state_dim}")
        print(f"  - max_action_dim: {config.max_action_dim}")
        
        # 尝试创建模型实例
        print("\n🔄 尝试创建PI05模型实例...")
        model = PI05Pytorch(config)
        print("✅ 成功创建PI05模型实例")
        
        # 检查模型结构
        print(f"\n📊 模型结构信息:")
        print(f"  - 模型类型: {type(model)}")
        print(f"  - 设备: {next(model.parameters()).device}")
        
        # 测试前向传播
        print("\n🧪 测试前向传播...")
        batch_size = 2
        seq_len = 100
        
        # 创建模拟输入（符合PI05的要求）
        # 根据代码分析，images应该是列表格式，每个元素是[batch_size, 3, 224, 224]
        seq_len = 10  # 序列长度
        images = [torch.randn(batch_size, 3, 224, 224) for _ in range(seq_len)]
        img_masks = [torch.ones(batch_size, dtype=torch.bool) for _ in range(seq_len)]  # 每个时间步的掩码
        tokens = torch.randint(0, 1000, (batch_size, 50))  # token序列
        masks = torch.ones(batch_size, 50, dtype=torch.bool)  # token掩码
        actions = torch.randn(batch_size, 100, 16)  # 动作序列
        
        print("  输入形状:")
        print(f"    images: 列表，长度{len(images)}，每个元素形状{images[0].shape}")
        print(f"    img_masks: 列表，长度{len(img_masks)}，每个元素形状{img_masks[0].shape}")
        print(f"    tokens: {tokens.shape}")
        print(f"    masks: {masks.shape}")
        print(f"    actions: {actions.shape}")
        
        # 先测试embed_prefix方法来理解维度
        print("\n🔍 测试embed_prefix方法...")
        try:
            with torch.no_grad():
                prefix_embs, prefix_pad_masks, prefix_att_masks = model.embed_prefix(images, img_masks, tokens, masks)
            print("✅ embed_prefix成功")
            print(f"  prefix_embs形状: {prefix_embs.shape}")
            print(f"  prefix_pad_masks形状: {prefix_pad_masks.shape}")
            print(f"  prefix_att_masks形状: {prefix_att_masks.shape}")
        except Exception as e:
            print(f"❌ embed_prefix失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
            
        # 执行完整的前向传播
        print("\n🧪 测试完整前向传播...")
        with torch.no_grad():
            output = model.forward(images, img_masks, tokens, masks, actions)
            
        print("✅ 前向传播成功")
        print(f"  输出类型: {type(output)}")
        
        if hasattr(output, 'action'):
            print(f"  动作输出形状: {output.action.shape}")
        elif isinstance(output, dict) and 'action' in output:
            print(f"  动作输出形状: {output['action'].shape}")
        else:
            print(f"  输出内容: {output}")
            
        print("\n🎉 PI05模型基础功能测试通过!")
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pi05_loading()
    sys.exit(0 if success else 1)