#!/usr/bin/env python3
"""
Inspect the action values for shoulder roll joints to check if they're constant.
"""

import sys
sys.path.insert(0, '/home/lcjs-szw/repos/lerobot/src')

import numpy as np
import pandas as pd
from pathlib import Path
import json
from collections import Counter

def load_dataset_info(dataset_path):
    """Load dataset info.json"""
    info_path = Path(dataset_path) / "meta" / "info.json"
    with open(info_path, 'r') as f:
        return json.load(f)

def load_all_data(dataset_path):
    """Load all data chunks from the dataset"""
    data_path = Path(dataset_path) / "data"
    all_states = []
    all_actions = []
    all_episodes = []
    
    parquet_files = sorted(data_path.rglob("*.parquet"))
    
    for parquet_file in parquet_files:
        df = pd.read_parquet(parquet_file)
        
        if 'observation.state' in df.columns and 'action' in df.columns:
            states = np.stack(df['observation.state'].values)
            actions = np.stack(df['action'].values)
        else:
            state_cols = sorted([col for col in df.columns if col.startswith('observation.state')])
            action_cols = sorted([col for col in df.columns if col.startswith('action')])
            
            if state_cols and action_cols:
                states = df[state_cols].values
                actions = df[action_cols].values
            else:
                continue
        
        episodes = df['episode_index'].values
        
        all_states.append(states)
        all_actions.append(actions)
        all_episodes.append(episodes)
    
    all_states = np.vstack(all_states)
    all_actions = np.vstack(all_actions)
    all_episodes = np.concatenate(all_episodes)
    
    return all_states, all_actions, all_episodes

def inspect_shoulder_roll_joints(dataset_path):
    """Inspect shoulder roll joint actions"""
    
    info = load_dataset_info(dataset_path)
    joint_names = info['features']['action']['names']
    
    # Find shoulder roll joint indices
    left_shoulder_roll_idx = None
    right_shoulder_roll_idx = None
    
    for i, name in enumerate(joint_names):
        if 'left_shoulder_roll' in name:
            left_shoulder_roll_idx = i
        elif 'right_shoulder_roll' in name:
            right_shoulder_roll_idx = i
    
    print("="*100)
    print("SHOULDER ROLL JOINT ACTION INSPECTION")
    print("="*100)
    print(f"\nDataset: {dataset_path}")
    print(f"Total episodes: {info['total_episodes']}")
    print(f"Total frames: {info['total_frames']}")
    
    print(f"\nTarget joints:")
    print(f"  Left shoulder roll:  Joint {left_shoulder_roll_idx} - {joint_names[left_shoulder_roll_idx]}")
    print(f"  Right shoulder roll: Joint {right_shoulder_roll_idx} - {joint_names[right_shoulder_roll_idx]}")
    
    # Load data
    print("\nLoading dataset...")
    states, actions, episodes = load_all_data(dataset_path)
    print(f"Loaded {len(states)} frames")
    
    # Analyze left shoulder roll
    print("\n" + "="*100)
    print("LEFT SHOULDER ROLL JOINT (Joint 1)")
    print("="*100)
    
    left_actions = actions[:, left_shoulder_roll_idx]
    left_states = states[:, left_shoulder_roll_idx]
    
    print(f"\nACTION values:")
    print(f"  Min:     {np.min(left_actions):.6f}")
    print(f"  Max:     {np.max(left_actions):.6f}")
    print(f"  Mean:    {np.mean(left_actions):.6f}")
    print(f"  Std:     {np.std(left_actions):.6f}")
    print(f"  Median:  {np.median(left_actions):.6f}")
    
    # Check if constant
    unique_actions = np.unique(left_actions)
    print(f"\n  Number of unique action values: {len(unique_actions)}")
    
    if len(unique_actions) <= 10:
        print(f"  Unique values: {unique_actions}")
    else:
        print(f"  First 10 unique values: {unique_actions[:10]}")
        print(f"  Last 10 unique values: {unique_actions[-10:]}")
    
    # Check how many are zero or near-zero
    zero_count = np.sum(np.abs(left_actions) < 1e-6)
    near_zero_count = np.sum(np.abs(left_actions) < 0.001)
    
    print(f"\n  Frames with action == 0 (±1e-6): {zero_count} ({100*zero_count/len(left_actions):.2f}%)")
    print(f"  Frames with action ≈ 0 (±0.001): {near_zero_count} ({100*near_zero_count/len(left_actions):.2f}%)")
    
    # Check most common values
    print(f"\n  Top 10 most common action values:")
    value_counts = Counter(left_actions.round(6))
    for value, count in value_counts.most_common(10):
        print(f"    {value:>10.6f}: {count:>8} frames ({100*count/len(left_actions):>6.2f}%)")
    
    print(f"\nSTATE values (for comparison):")
    print(f"  Min:     {np.min(left_states):.6f}")
    print(f"  Max:     {np.max(left_states):.6f}")
    print(f"  Mean:    {np.mean(left_states):.6f}")
    print(f"  Std:     {np.std(left_states):.6f}")
    print(f"  Median:  {np.median(left_states):.6f}")
    
    # Analyze right shoulder roll
    print("\n" + "="*100)
    print("RIGHT SHOULDER ROLL JOINT (Joint 9)")
    print("="*100)
    
    right_actions = actions[:, right_shoulder_roll_idx]
    right_states = states[:, right_shoulder_roll_idx]
    
    print(f"\nACTION values:")
    print(f"  Min:     {np.min(right_actions):.6f}")
    print(f"  Max:     {np.max(right_actions):.6f}")
    print(f"  Mean:    {np.mean(right_actions):.6f}")
    print(f"  Std:     {np.std(right_actions):.6f}")
    print(f"  Median:  {np.median(right_actions):.6f}")
    
    # Check if constant
    unique_actions = np.unique(right_actions)
    print(f"\n  Number of unique action values: {len(unique_actions)}")
    
    if len(unique_actions) <= 10:
        print(f"  Unique values: {unique_actions}")
    else:
        print(f"  First 10 unique values: {unique_actions[:10]}")
        print(f"  Last 10 unique values: {unique_actions[-10:]}")
    
    # Check how many are zero or near-zero
    zero_count = np.sum(np.abs(right_actions) < 1e-6)
    near_zero_count = np.sum(np.abs(right_actions) < 0.001)
    
    print(f"\n  Frames with action == 0 (±1e-6): {zero_count} ({100*zero_count/len(right_actions):.2f}%)")
    print(f"  Frames with action ≈ 0 (±0.001): {near_zero_count} ({100*near_zero_count/len(right_actions):.2f}%)")
    
    # Check most common values
    print(f"\n  Top 10 most common action values:")
    value_counts = Counter(right_actions.round(6))
    for value, count in value_counts.most_common(10):
        print(f"    {value:>10.6f}: {count:>8} frames ({100*count/len(right_actions):>6.2f}%)")
    
    print(f"\nSTATE values (for comparison):")
    print(f"  Min:     {np.min(right_states):.6f}")
    print(f"  Max:     {np.max(right_states):.6f}")
    print(f"  Mean:    {np.mean(right_states):.6f}")
    print(f"  Std:     {np.std(right_states):.6f}")
    print(f"  Median:  {np.median(right_states):.6f}")
    
    # Episode-wise analysis
    print("\n" + "="*100)
    print("EPISODE-WISE ANALYSIS")
    print("="*100)
    
    unique_episodes = np.unique(episodes)
    
    print(f"\nAnalyzing action values across {len(unique_episodes)} episodes...")
    
    left_constant_episodes = 0
    right_constant_episodes = 0
    
    print(f"\n{'Episode':<10} {'Left Action':<25} {'Right Action':<25}")
    print(f"{'':10} {'(unique values)':<25} {'(unique values)':<25}")
    print("-"*60)
    
    for ep_idx in unique_episodes[:20]:  # Show first 20 episodes
        ep_mask = episodes == ep_idx
        
        left_ep_actions = left_actions[ep_mask]
        right_ep_actions = right_actions[ep_mask]
        
        left_unique = len(np.unique(left_ep_actions))
        right_unique = len(np.unique(right_ep_actions))
        
        left_val = np.unique(left_ep_actions)[0] if left_unique == 1 else None
        right_val = np.unique(right_ep_actions)[0] if right_unique == 1 else None
        
        if left_unique == 1:
            left_constant_episodes += 1
            left_str = f"CONSTANT: {left_val:.6f}"
        else:
            left_str = f"{left_unique} values"
        
        if right_unique == 1:
            right_constant_episodes += 1
            right_str = f"CONSTANT: {right_val:.6f}"
        else:
            right_str = f"{right_unique} values"
        
        print(f"{ep_idx:<10} {left_str:<25} {right_str:<25}")
    
    if len(unique_episodes) > 20:
        print(f"... ({len(unique_episodes) - 20} more episodes)")
    
    print(f"\nSummary:")
    print(f"  Episodes with constant left shoulder roll action:  {left_constant_episodes}/{len(unique_episodes)} ({100*left_constant_episodes/len(unique_episodes):.1f}%)")
    print(f"  Episodes with constant right shoulder roll action: {right_constant_episodes}/{len(unique_episodes)} ({100*right_constant_episodes/len(unique_episodes):.1f}%)")
    
    print("\n" + "="*100)
    print("CONCLUSION")
    print("="*100)
    
    # Determine if actions are constant
    left_is_constant = len(np.unique(left_actions)) == 1
    right_is_constant = len(np.unique(right_actions)) == 1
    
    left_mostly_zero = zero_count > 0.9 * len(left_actions)
    right_zero_count = np.sum(np.abs(right_actions) < 1e-6)
    right_mostly_zero = right_zero_count > 0.9 * len(right_actions)
    
    if left_is_constant:
        print(f"\n🔴 LEFT shoulder roll action is CONSTANT at {np.unique(left_actions)[0]:.6f}")
    elif left_mostly_zero:
        print(f"\n🔴 LEFT shoulder roll action is MOSTLY ZERO ({100*zero_count/len(left_actions):.1f}% of frames)")
    else:
        print(f"\n✅ LEFT shoulder roll action is VARIABLE (range: [{np.min(left_actions):.6f}, {np.max(left_actions):.6f}])")
    
    if right_is_constant:
        print(f"🔴 RIGHT shoulder roll action is CONSTANT at {np.unique(right_actions)[0]:.6f}")
    elif right_mostly_zero:
        print(f"🔴 RIGHT shoulder roll action is MOSTLY ZERO ({100*right_zero_count/len(right_actions):.1f}% of frames)")
    else:
        print(f"✅ RIGHT shoulder roll action is VARIABLE (range: [{np.min(right_actions):.6f}, {np.max(right_actions):.6f}])")
    
    print("\n" + "="*100)

if __name__ == "__main__":
    dataset_path = "/home/lcjs-szw/datasets/pick_place_cube"
    inspect_shoulder_roll_joints(dataset_path)
