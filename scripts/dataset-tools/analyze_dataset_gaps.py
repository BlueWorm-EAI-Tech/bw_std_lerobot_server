#!/usr/bin/env python3
"""
Analyze the gap between observation.state and action for each joint in a lerobot dataset.
"""

import sys
sys.path.insert(0, '/home/lcjs-szw/repos/lerobot/src')

import numpy as np
import pandas as pd
from pathlib import Path
import json

def load_dataset_info(dataset_path):
    """Load dataset info.json"""
    info_path = Path(dataset_path) / "meta" / "info.json"
    with open(info_path, 'r') as f:
        return json.load(f)

def load_all_data_chunks(dataset_path):
    """Load all data chunks from the dataset"""
    data_path = Path(dataset_path) / "data"
    all_states = []
    all_actions = []
    all_episodes = []
    all_frame_indices = []
    
    # Find all parquet files
    parquet_files = sorted(data_path.rglob("*.parquet"))
    
    print(f"Found {len(parquet_files)} parquet files")
    
    for parquet_file in parquet_files:
        df = pd.read_parquet(parquet_file)
        
        # Debug: print columns
        print(f"\nColumns in {parquet_file.name}:")
        print(df.columns.tolist()[:10], "...")
        
        # Extract state and action - they might be stored as arrays in single columns
        if 'observation.state' in df.columns and 'action' in df.columns:
            # Data stored as arrays in single columns
            states = np.stack(df['observation.state'].values)
            actions = np.stack(df['action'].values)
        else:
            # Data stored as separate columns
            state_cols = sorted([col for col in df.columns if col.startswith('observation.state')])
            action_cols = sorted([col for col in df.columns if col.startswith('action')])
            
            if state_cols and action_cols:
                states = df[state_cols].values
                actions = df[action_cols].values
            else:
                print(f"Warning: Could not find state/action columns in {parquet_file}")
                continue
        
        episodes = df['episode_index'].values
        frame_indices = df['frame_index'].values
        
        all_states.append(states)
        all_actions.append(actions)
        all_episodes.append(episodes)
        all_frame_indices.append(frame_indices)
    
    # Concatenate all chunks
    all_states = np.vstack(all_states)
    all_actions = np.vstack(all_actions)
    all_episodes = np.concatenate(all_episodes)
    all_frame_indices = np.concatenate(all_frame_indices)
    
    return all_states, all_actions, all_episodes, all_frame_indices

def analyze_gaps(dataset_path):
    """Analyze gaps between state and action for each joint"""
    
    # Load dataset info
    info = load_dataset_info(dataset_path)
    
    # Get joint names
    joint_names = info['features']['observation.state']['names']
    print(f"\nDataset: {dataset_path}")
    print(f"Total episodes: {info['total_episodes']}")
    print(f"Total frames: {info['total_frames']}")
    print(f"Number of joints: {len(joint_names)}")
    print(f"\nJoint names:")
    for i, name in enumerate(joint_names):
        print(f"  {i}: {name}")
    
    # Load all data
    print("\nLoading dataset...")
    states, actions, episodes, frame_indices = load_all_data_chunks(dataset_path)
    
    print(f"Loaded {len(states)} frames")
    
    # Calculate gaps for each joint
    gaps = actions - states
    
    print("\n" + "="*80)
    print("GAP ANALYSIS: action - observation.state")
    print("="*80)
    
    # Statistics for each joint
    results = []
    for i, joint_name in enumerate(joint_names):
        joint_gaps = gaps[:, i]
        
        mean_gap = np.mean(joint_gaps)
        std_gap = np.std(joint_gaps)
        min_gap = np.min(joint_gaps)
        max_gap = np.max(joint_gaps)
        median_gap = np.median(joint_gaps)
        abs_mean_gap = np.mean(np.abs(joint_gaps))
        
        results.append({
            'joint_index': i,
            'joint_name': joint_name,
            'mean': mean_gap,
            'std': std_gap,
            'min': min_gap,
            'max': max_gap,
            'median': median_gap,
            'abs_mean': abs_mean_gap
        })
        
        print(f"\nJoint {i}: {joint_name}")
        print(f"  Mean gap:        {mean_gap:>10.6f}")
        print(f"  Std dev:         {std_gap:>10.6f}")
        print(f"  Min gap:         {min_gap:>10.6f}")
        print(f"  Max gap:         {max_gap:>10.6f}")
        print(f"  Median gap:      {median_gap:>10.6f}")
        print(f"  Abs mean gap:    {abs_mean_gap:>10.6f}")
    
    # Identify problematic joints
    print("\n" + "="*80)
    print("PROBLEMATIC JOINTS DETECTION")
    print("="*80)
    
    # Define thresholds for problematic joints
    HIGH_ABS_MEAN_THRESHOLD = 0.1  # High average absolute gap
    HIGH_STD_THRESHOLD = 0.2       # High variability
    HIGH_MAX_THRESHOLD = 1.0       # Very large maximum gap
    
    problematic_joints = []
    
    for result in results:
        issues = []
        
        if result['abs_mean'] > HIGH_ABS_MEAN_THRESHOLD:
            issues.append(f"High avg absolute gap: {result['abs_mean']:.6f}")
        
        if result['std'] > HIGH_STD_THRESHOLD:
            issues.append(f"High std dev: {result['std']:.6f}")
        
        if abs(result['max']) > HIGH_MAX_THRESHOLD or abs(result['min']) > HIGH_MAX_THRESHOLD:
            issues.append(f"Large max/min gap: [{result['min']:.6f}, {result['max']:.6f}]")
        
        if issues:
            problematic_joints.append({
                'joint_index': result['joint_index'],
                'joint_name': result['joint_name'],
                'issues': issues
            })
    
    if problematic_joints:
        print(f"\nFound {len(problematic_joints)} problematic joint(s):\n")
        for pj in problematic_joints:
            print(f"⚠️  Joint {pj['joint_index']}: {pj['joint_name']}")
            for issue in pj['issues']:
                print(f"    - {issue}")
            print()
    else:
        print("\n✓ No problematic joints detected. All gaps are within acceptable ranges.")
    
    # Additional analysis: check if gaps are consistent across episodes
    print("\n" + "="*80)
    print("EPISODE-WISE ANALYSIS")
    print("="*80)
    
    unique_episodes = np.unique(episodes)
    print(f"\nAnalyzing {len(unique_episodes)} episodes...")
    
    # Sample a few episodes for detailed analysis
    sample_episodes = unique_episodes[:min(5, len(unique_episodes))]
    
    for ep_idx in sample_episodes:
        ep_mask = episodes == ep_idx
        ep_gaps = gaps[ep_mask]
        
        print(f"\nEpisode {ep_idx}: {np.sum(ep_mask)} frames")
        print(f"  Overall mean abs gap: {np.mean(np.abs(ep_gaps)):.6f}")
        print(f"  Overall std: {np.std(ep_gaps):.6f}")
    
    return results, problematic_joints

if __name__ == "__main__":
    dataset_path = "/home/lcjs-szw/datasets/pick_place_cube"
    results, problematic_joints = analyze_gaps(dataset_path)
