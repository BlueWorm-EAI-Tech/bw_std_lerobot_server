#!/usr/bin/env python3
"""
Test the normalization behavior with std=0 to understand why original dataset worked
but modified dataset had huge losses.
"""

import torch

def normalize_mean_std(value, mean, std, eps=1e-8):
    """Simulate the normalization from normalize_processor.py"""
    denom = std + eps
    return (value - mean) / denom

print("="*100)
print("NORMALIZATION BEHAVIOR WITH STD=0")
print("="*100)

# Original dataset scenario: actions all 0, stats mean=0 std=0
print("\n1. ORIGINAL DATASET (actions all 0, stats: mean=0, std=0):")
print("-" * 80)
action_value = 0.0
mean = 0.0
std = 0.0
normalized = normalize_mean_std(action_value, mean, std)
print(f"   Action value: {action_value}")
print(f"   Stats: mean={mean}, std={std}")
print(f"   Normalized: ({action_value} - {mean}) / ({std} + 1e-8) = {normalized}")
print(f"   ✅ Result: {normalized} (reasonable!)")

# Modified dataset scenario: actions vary, but stats still mean=0 std=0
print("\n2. MODIFIED DATASET (actions vary, but OLD stats: mean=0, std=0):")
print("-" * 80)
action_values = [0.0, 0.1, 0.5, 0.683]  # Example values from left shoulder roll
for action_value in action_values:
    normalized = normalize_mean_std(action_value, mean, std)
    print(f"   Action value: {action_value:6.3f} -> Normalized: {normalized:15.1f}")

print(f"\n   ❌ Result: HUGE values! This causes massive losses during training")

# Modified dataset with corrected stats
print("\n3. MODIFIED DATASET with CORRECTED STATS:")
print("-" * 80)
mean_corrected = 0.092430
std_corrected = 0.151826
for action_value in action_values:
    normalized = normalize_mean_std(action_value, mean_corrected, std_corrected)
    print(f"   Action value: {action_value:6.3f} -> Normalized: {normalized:8.4f}")

print(f"\n   ✅ Result: Reasonable values! Training will work normally")

# Show the loss impact
print("\n" + "="*100)
print("IMPACT ON TRAINING LOSS")
print("="*100)

print("\nSimulating MSE loss for a batch of 10 actions:")
print("-" * 80)

# Scenario 1: Original dataset (all zeros)
print("\n1. Original dataset (actions all 0):")
actions_original = torch.zeros(10, 16)  # 10 samples, 16 joints
actions_original[:, 1] = 0.0  # Left shoulder roll all 0
actions_original[:, 9] = 0.0  # Right shoulder roll all 0

# Normalize with std=0
normalized_original = (actions_original - 0.0) / (0.0 + 1e-8)
print(f"   Normalized actions (joint 1): {normalized_original[:, 1]}")
print(f"   Max normalized value: {normalized_original.abs().max().item():.2f}")

# Simulate loss (comparing to some target)
target = torch.randn(10, 16) * 0.1  # Small random targets
loss_original = torch.nn.functional.mse_loss(normalized_original, target)
print(f"   MSE Loss: {loss_original.item():.2f}")

# Scenario 2: Modified dataset with OLD stats
print("\n2. Modified dataset with OLD stats (std=0):")
actions_modified = torch.zeros(10, 16)
actions_modified[:, 1] = torch.tensor([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.683, 0.5, 0.3])  # Varying values
actions_modified[:, 9] = torch.tensor([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.83])

# Normalize with OLD stats (std=0)
normalized_modified_bad = (actions_modified - 0.0) / (0.0 + 1e-8)
print(f"   Normalized actions (joint 1): {normalized_modified_bad[:, 1]}")
print(f"   Max normalized value: {normalized_modified_bad.abs().max().item():.2e}")

loss_modified_bad = torch.nn.functional.mse_loss(normalized_modified_bad, target)
print(f"   MSE Loss: {loss_modified_bad.item():.2e} ❌ HUGE!")

# Scenario 3: Modified dataset with CORRECTED stats
print("\n3. Modified dataset with CORRECTED stats:")
mean_tensor = torch.zeros(16)
std_tensor = torch.ones(16)
mean_tensor[1] = 0.092430
std_tensor[1] = 0.151826
mean_tensor[9] = 0.068085
std_tensor[9] = 0.136527

normalized_modified_good = (actions_modified - mean_tensor) / (std_tensor + 1e-8)
print(f"   Normalized actions (joint 1): {normalized_modified_good[:, 1]}")
print(f"   Max normalized value: {normalized_modified_good.abs().max().item():.2f}")

loss_modified_good = torch.nn.functional.mse_loss(normalized_modified_good, target)
print(f"   MSE Loss: {loss_modified_good.item():.2f} ✅ Normal!")

print("\n" + "="*100)
print("CONCLUSION")
print("="*100)
print("""
The original dataset worked because:
- Actions were all 0
- With mean=0, std=0: normalized = (0 - 0) / 1e-8 = 0
- Loss stayed reasonable

The modified dataset failed because:
- Actions varied from 0 to 0.83
- With OLD stats mean=0, std=0: normalized = (0.5 - 0) / 1e-8 = 50,000,000
- Loss exploded to 20K+

After recomputing stats:
- With correct mean and std: normalized = (0.5 - 0.092) / 0.152 = 2.68
- Loss is normal and training works!
""")
