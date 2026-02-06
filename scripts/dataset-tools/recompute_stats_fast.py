#!/usr/bin/env python3
"""
Fast recomputation of statistics for modified action values.
Directly processes parquet files without filtering.
"""

import sys
sys.path.insert(0, '/home/lcjs-szw/repos/lerobot/src')

import json
import numpy as np
import pandas as pd
from pathlib import Path

def recompute_action_stats_fast(dataset_path):
    """Quickly recompute action statistics from parquet files"""
    
    dataset_path = Path(dataset_path)
    print(f"Recomputing action statistics for: {dataset_path}")
    
    # Load info to get feature names
    info_path = dataset_path / "meta" / "info.json"
    with open(info_path, 'r') as f:
        info = json.load(f)
    
    action_names = info['features']['action']['names']
    num_joints = len(action_names)
    
    print(f"Number of action joints: {num_joints}")
    print(f"Total frames: {info['total_frames']}")
    
    # Find all parquet data files
    data_dir = dataset_path / "data"
    parquet_files = sorted(data_dir.rglob("*.parquet"))
    
    print(f"Found {len(parquet_files)} parquet files")
    
    # Collect all actions
    print("\nLoading action data from parquet files...")
    all_actions = []
    
    for pf in parquet_files:
        df = pd.read_parquet(pf)
        
        # Actions are stored as arrays in the 'action' column
        if 'action' in df.columns:
            actions = np.stack(df['action'].values)
            all_actions.append(actions)
    
    # Stack all actions
    all_actions = np.vstack(all_actions)
    print(f"Loaded {len(all_actions)} action frames")
    
    # Compute statistics
    print("\nComputing statistics...")
    
    action_stats = {
        'min': np.min(all_actions, axis=0).tolist(),
        'max': np.max(all_actions, axis=0).tolist(),
        'mean': np.mean(all_actions, axis=0).tolist(),
        'std': np.std(all_actions, axis=0).tolist(),
        'count': [len(all_actions)]
    }
    
    # Compute quantiles
    quantiles = [0.01, 0.10, 0.50, 0.90, 0.99]
    for q in quantiles:
        q_key = f"q{int(q * 100):02d}"
        action_stats[q_key] = np.quantile(all_actions, q, axis=0).tolist()
    
    # Load existing stats
    stats_path = dataset_path / "meta" / "stats.json"
    print(f"\nLoading existing stats from: {stats_path}")
    with open(stats_path, 'r') as f:
        stats = json.load(f)
    
    # Backup
    backup_path = dataset_path / "meta" / "stats_backup.json"
    print(f"Backing up old stats to: {backup_path}")
    with open(backup_path, 'w') as f:
        json.dump(stats, f, indent=4)
    
    # Update action stats
    stats['action'] = action_stats
    
    # Also update observation.state stats if needed
    print("\nRecomputing observation.state statistics...")
    all_states = []
    
    for pf in parquet_files:
        df = pd.read_parquet(pf)
        
        if 'observation.state' in df.columns:
            states = np.stack(df['observation.state'].values)
            all_states.append(states)
    
    all_states = np.vstack(all_states)
    
    state_stats = {
        'min': np.min(all_states, axis=0).tolist(),
        'max': np.max(all_states, axis=0).tolist(),
        'mean': np.mean(all_states, axis=0).tolist(),
        'std': np.std(all_states, axis=0).tolist(),
        'count': [len(all_states)]
    }
    
    for q in quantiles:
        q_key = f"q{int(q * 100):02d}"
        state_stats[q_key] = np.quantile(all_states, q, axis=0).tolist()
    
    stats['observation.state'] = state_stats
    
    # Save updated stats
    print(f"\nWriting updated stats to: {stats_path}")
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=4)
    
    print("\n" + "="*100)
    print("Statistics recomputed successfully!")
    print("="*100)
    
    # Display updated stats for shoulder roll joints
    print("\nUpdated statistics for shoulder roll joints:")
    print("\nLEFT SHOULDER ROLL (Joint 1):")
    print(f"  Action  - min: {action_stats['min'][1]:.6f}, max: {action_stats['max'][1]:.6f}, mean: {action_stats['mean'][1]:.6f}, std: {action_stats['std'][1]:.6f}")
    print(f"  State   - min: {state_stats['min'][1]:.6f}, max: {state_stats['max'][1]:.6f}, mean: {state_stats['mean'][1]:.6f}, std: {state_stats['std'][1]:.6f}")
    
    print("\nRIGHT SHOULDER ROLL (Joint 9):")
    print(f"  Action  - min: {action_stats['min'][9]:.6f}, max: {action_stats['max'][9]:.6f}, mean: {action_stats['mean'][9]:.6f}, std: {action_stats['std'][9]:.6f}")
    print(f"  State   - min: {state_stats['min'][9]:.6f}, max: {state_stats['max'][9]:.6f}, mean: {state_stats['mean'][9]:.6f}, std: {state_stats['std'][9]:.6f}")
    
    print("\n" + "="*100)
    print("IMPORTANT: The stats have been updated. You can now train your model.")
    print("="*100)

if __name__ == "__main__":
    dataset_path = "/home/lcjs-szw/datasets/pick_place_cube_copy/pick_place_cube"
    recompute_action_stats_fast(dataset_path)
