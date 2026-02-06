#!/usr/bin/env python3
"""
Detailed gap analysis with visualization and outlier detection.
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
        frame_indices = df['frame_index'].values
        
        all_states.append(states)
        all_actions.append(actions)
        all_episodes.append(episodes)
        all_frame_indices.append(frame_indices)
    
    all_states = np.vstack(all_states)
    all_actions = np.vstack(all_actions)
    all_episodes = np.concatenate(all_episodes)
    all_frame_indices = np.concatenate(all_frame_indices)
    
    return all_states, all_actions, all_episodes, all_frame_indices

def detailed_analysis(dataset_path):
    """Perform detailed gap analysis"""
    
    info = load_dataset_info(dataset_path)
    joint_names = info['features']['observation.state']['names']
    
    print("="*100)
    print("DETAILED GAP ANALYSIS REPORT")
    print("="*100)
    print(f"\nDataset: {dataset_path}")
    print(f"Total episodes: {info['total_episodes']}")
    print(f"Total frames: {info['total_frames']}")
    
    states, actions, episodes, frame_indices = load_all_data_chunks(dataset_path)
    gaps = actions - states
    
    print("\n" + "="*100)
    print("SUMMARY TABLE")
    print("="*100)
    print(f"\n{'Joint':<5} {'Name':<40} {'Mean':<10} {'Std':<10} {'|Mean|':<10} {'Max|Gap|':<10}")
    print("-"*100)
    
    problematic = []
    
    for i, joint_name in enumerate(joint_names):
        joint_gaps = gaps[:, i]
        
        mean_gap = np.mean(joint_gaps)
        std_gap = np.std(joint_gaps)
        abs_mean_gap = np.mean(np.abs(joint_gaps))
        max_abs_gap = np.max(np.abs(joint_gaps))
        
        # Flag if concerning
        flag = ""
        if abs_mean_gap > 0.05:
            flag = "⚠️ HIGH"
            problematic.append((i, joint_name, abs_mean_gap, "High average absolute gap"))
        elif std_gap > 0.1:
            flag = "⚠️ VARY"
            problematic.append((i, joint_name, std_gap, "High variability"))
        elif max_abs_gap > 0.5:
            flag = "⚠️ SPIKE"
            problematic.append((i, joint_name, max_abs_gap, "Large spike detected"))
        
        print(f"{i:<5} {joint_name:<40} {mean_gap:<10.6f} {std_gap:<10.6f} {abs_mean_gap:<10.6f} {max_abs_gap:<10.6f} {flag}")
    
    # Detailed problematic joint analysis
    if problematic:
        print("\n" + "="*100)
        print("⚠️  PROBLEMATIC JOINTS DETECTED")
        print("="*100)
        
        for joint_idx, joint_name, value, reason in problematic:
            print(f"\n🔴 Joint {joint_idx}: {joint_name}")
            print(f"   Issue: {reason} (value: {value:.6f})")
            
            joint_gaps = gaps[:, joint_idx]
            
            # Percentile analysis
            p1 = np.percentile(joint_gaps, 1)
            p5 = np.percentile(joint_gaps, 5)
            p25 = np.percentile(joint_gaps, 25)
            p50 = np.percentile(joint_gaps, 50)
            p75 = np.percentile(joint_gaps, 75)
            p95 = np.percentile(joint_gaps, 95)
            p99 = np.percentile(joint_gaps, 99)
            
            print(f"   Percentiles:")
            print(f"     1%:  {p1:>10.6f}")
            print(f"     5%:  {p5:>10.6f}")
            print(f"     25%: {p25:>10.6f}")
            print(f"     50%: {p50:>10.6f}")
            print(f"     75%: {p75:>10.6f}")
            print(f"     95%: {p95:>10.6f}")
            print(f"     99%: {p99:>10.6f}")
            
            # Find outliers (beyond 3 std devs)
            mean = np.mean(joint_gaps)
            std = np.std(joint_gaps)
            outliers = np.abs(joint_gaps - mean) > 3 * std
            num_outliers = np.sum(outliers)
            
            if num_outliers > 0:
                print(f"   Outliers (>3σ): {num_outliers} frames ({100*num_outliers/len(joint_gaps):.2f}%)")
                
                # Show some outlier examples
                outlier_indices = np.where(outliers)[0][:5]
                print(f"   Example outlier frames:")
                for idx in outlier_indices:
                    print(f"     Frame {idx}: state={states[idx, joint_idx]:.6f}, action={actions[idx, joint_idx]:.6f}, gap={joint_gaps[idx]:.6f}")
    else:
        print("\n" + "="*100)
        print("✅ ALL JOINTS LOOK GOOD")
        print("="*100)
        print("\nNo significant issues detected. All gaps are within acceptable ranges.")
    
    # Check for systematic bias
    print("\n" + "="*100)
    print("SYSTEMATIC BIAS CHECK")
    print("="*100)
    
    print("\nJoints with consistent directional bias (|mean| > 0.01):")
    biased_joints = []
    for i, joint_name in enumerate(joint_names):
        mean_gap = np.mean(gaps[:, i])
        if abs(mean_gap) > 0.01:
            direction = "positive" if mean_gap > 0 else "negative"
            biased_joints.append((i, joint_name, mean_gap, direction))
            print(f"  Joint {i} ({joint_name}): {mean_gap:.6f} ({direction} bias)")
    
    if not biased_joints:
        print("  None detected - all joints are well-centered around zero.")
    
    # Episode consistency check
    print("\n" + "="*100)
    print("EPISODE CONSISTENCY CHECK")
    print("="*100)
    
    unique_episodes = np.unique(episodes)
    episode_stats = []
    
    for ep_idx in unique_episodes:
        ep_mask = episodes == ep_idx
        ep_gaps = gaps[ep_mask]
        
        mean_abs_gap = np.mean(np.abs(ep_gaps))
        max_abs_gap = np.max(np.abs(ep_gaps))
        
        episode_stats.append({
            'episode': ep_idx,
            'frames': np.sum(ep_mask),
            'mean_abs_gap': mean_abs_gap,
            'max_abs_gap': max_abs_gap
        })
    
    # Sort by mean_abs_gap
    episode_stats.sort(key=lambda x: x['mean_abs_gap'], reverse=True)
    
    print(f"\nTop 10 episodes with highest average absolute gap:")
    print(f"{'Episode':<10} {'Frames':<10} {'Mean |Gap|':<15} {'Max |Gap|':<15}")
    print("-"*50)
    for stat in episode_stats[:10]:
        print(f"{stat['episode']:<10} {stat['frames']:<10} {stat['mean_abs_gap']:<15.6f} {stat['max_abs_gap']:<15.6f}")
    
    print(f"\nBottom 10 episodes with lowest average absolute gap:")
    print(f"{'Episode':<10} {'Frames':<10} {'Mean |Gap|':<15} {'Max |Gap|':<15}")
    print("-"*50)
    for stat in episode_stats[-10:]:
        print(f"{stat['episode']:<10} {stat['frames']:<10} {stat['mean_abs_gap']:<15.6f} {stat['max_abs_gap']:<15.6f}")
    
    print("\n" + "="*100)
    print("ANALYSIS COMPLETE")
    print("="*100)

if __name__ == "__main__":
    dataset_path = "/home/lcjs-szw/datasets/pick_place_cube"
    detailed_analysis(dataset_path)
