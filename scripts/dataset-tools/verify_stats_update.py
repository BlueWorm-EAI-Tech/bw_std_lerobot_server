#!/usr/bin/env python3
"""
Verify that statistics were correctly updated after modification.
"""

import sys
sys.path.insert(0, '/home/lcjs-szw/repos/lerobot/src')

import json
import numpy as np
import pandas as pd
from pathlib import Path

def verify_stats(dataset_path):
    """Verify stats are correct"""
    
    dataset_path = Path(dataset_path)
    print("="*100)
    print("VERIFYING STATISTICS UPDATE")
    print("="*100)
    
    # Load stats.json
    stats_path = dataset_path / "meta" / "stats.json"
    with open(stats_path, 'r') as f:
        stats = json.load(f)
    
    # Load actual data
    data_dir = dataset_path / "data"
    data_parquet_files = sorted(data_dir.rglob("*.parquet"))
    
    print(f"\nLoading data from {len(data_parquet_files)} files...")
    all_data_df = pd.concat([pd.read_parquet(f) for f in data_parquet_files], ignore_index=True)
    
    # Extract actions
    all_actions = np.stack(all_data_df['action'].values)
    
    print(f"Loaded {len(all_actions)} action frames")
    
    # Compute actual stats
    actual_stats = {
        'min': np.min(all_actions, axis=0),
        'max': np.max(all_actions, axis=0),
        'mean': np.mean(all_actions, axis=0),
        'std': np.std(all_actions, axis=0),
    }
    
    # Compare with stored stats
    stored_stats = {
        'min': np.array(stats['action']['min']),
        'max': np.array(stats['action']['max']),
        'mean': np.array(stats['action']['mean']),
        'std': np.array(stats['action']['std']),
    }
    
    print("\n" + "="*100)
    print("COMPARISON: Stored Stats vs Actual Data")
    print("="*100)
    
    all_match = True
    tolerance = 1e-3  # 0.001 is reasonable tolerance for aggregated stats
    
    for stat_name in ['min', 'max', 'mean', 'std']:
        diff = np.abs(stored_stats[stat_name] - actual_stats[stat_name])
        max_diff = np.max(diff)
        
        if max_diff > tolerance:
            print(f"\n❌ {stat_name.upper()}: MISMATCH (max diff: {max_diff:.6e})")
            all_match = False
        else:
            print(f"\n✅ {stat_name.upper()}: MATCH (max diff: {max_diff:.6e})")
    
    # Check shoulder roll joints specifically
    print("\n" + "="*100)
    print("SHOULDER ROLL JOINTS VERIFICATION")
    print("="*100)
    
    joint_names = ["left_shoulder_roll_joint.pos", "right_shoulder_roll_joint.pos"]
    joint_indices = [1, 9]
    
    for name, idx in zip(joint_names, joint_indices):
        print(f"\n{name} (Joint {idx}):")
        print(f"  Stored stats:")
        print(f"    min:  {stored_stats['min'][idx]:.6f}")
        print(f"    max:  {stored_stats['max'][idx]:.6f}")
        print(f"    mean: {stored_stats['mean'][idx]:.6f}")
        print(f"    std:  {stored_stats['std'][idx]:.6f}")
        
        print(f"  Actual data:")
        print(f"    min:  {actual_stats['min'][idx]:.6f}")
        print(f"    max:  {actual_stats['max'][idx]:.6f}")
        print(f"    mean: {actual_stats['mean'][idx]:.6f}")
        print(f"    std:  {actual_stats['std'][idx]:.6f}")
        
        # Check if std is non-zero (critical for training)
        if stored_stats['std'][idx] > 0:
            print(f"  ✅ Std is non-zero - normalization will work correctly")
        else:
            print(f"  ❌ Std is zero - normalization will FAIL during training!")
            all_match = False
    
    # Final verdict
    print("\n" + "="*100)
    if all_match:
        print("✅ ALL STATISTICS ARE CORRECT!")
        print("✅ Dataset is ready for training")
    else:
        print("❌ STATISTICS MISMATCH DETECTED!")
        print("❌ Please rerun recompute_all_stats.py")
    print("="*100)
    
    return all_match

if __name__ == "__main__":
    dataset_path = "/home/lcjs-szw/datasets/pick_place_cube_copy/pick_place_cube"
    verify_stats(dataset_path)
