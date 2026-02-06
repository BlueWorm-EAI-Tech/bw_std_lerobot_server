#!/usr/bin/env python3
"""
Recompute statistics for a modified lerobot dataset.
This is necessary after manually editing action values in parquet files.
"""

import sys
sys.path.insert(0, '/home/lcjs-szw/repos/lerobot/src')

import json
import numpy as np
from pathlib import Path
from lerobot.datasets.compute_stats import compute_episode_stats, aggregate_stats
from lerobot.datasets.lerobot_dataset import LeRobotDataset

def recompute_dataset_stats(dataset_path):
    """Recompute all statistics for a dataset"""
    
    dataset_path = Path(dataset_path)
    print(f"Recomputing statistics for: {dataset_path}")
    
    # Load the dataset
    print("Loading dataset...")
    dataset = LeRobotDataset(str(dataset_path))
    
    print(f"Dataset loaded: {len(dataset)} frames, {dataset.num_episodes} episodes")
    
    # Get features info
    features = dataset.features
    
    # Compute stats for each episode
    print("\nComputing statistics per episode...")
    all_episode_stats = []
    
    for ep_idx in range(dataset.num_episodes):
        print(f"  Processing episode {ep_idx}/{dataset.num_episodes}...", end='\r')
        
        # Get all frames for this episode
        episode_data = {}
        
        # Filter frames for this episode
        ep_frames = dataset.hf_dataset.filter(lambda x: x["episode_index"] == ep_idx)
        
        # Collect data for each feature
        for key in features.keys():
            if features[key]["dtype"] == "string":
                continue
            
            if features[key]["dtype"] in ["image", "video"]:
                # For images/videos, we need the file paths
                # Skip for now as they're expensive to recompute and likely unchanged
                continue
            else:
                # For numerical data, stack all values
                data_list = []
                for frame in ep_frames:
                    data_list.append(frame[key])
                episode_data[key] = np.stack(data_list)
        
        # Compute stats for this episode
        ep_stats = compute_episode_stats(episode_data, features)
        all_episode_stats.append(ep_stats)
    
    print(f"\n  Processed all {dataset.num_episodes} episodes")
    
    # Aggregate stats across all episodes
    print("\nAggregating statistics across all episodes...")
    aggregated_stats = aggregate_stats(all_episode_stats)
    
    # Convert numpy arrays to lists for JSON serialization
    def convert_to_serializable(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        return obj
    
    stats_serializable = convert_to_serializable(aggregated_stats)
    
    # Load existing stats to preserve image stats
    stats_path = dataset_path / "meta" / "stats.json"
    print(f"\nLoading existing stats from: {stats_path}")
    with open(stats_path, 'r') as f:
        existing_stats = json.load(f)
    
    # Merge: keep image stats from existing, update numerical stats
    print("Merging statistics...")
    for key in stats_serializable.keys():
        if key in existing_stats:
            existing_stats[key] = stats_serializable[key]
    
    # Backup old stats
    backup_path = dataset_path / "meta" / "stats_backup.json"
    print(f"Backing up old stats to: {backup_path}")
    with open(backup_path, 'w') as f:
        json.dump(existing_stats, f, indent=4)
    
    # Save new stats
    print(f"Writing new stats to: {stats_path}")
    with open(stats_path, 'w') as f:
        json.dump(existing_stats, f, indent=4)
    
    print("\n" + "="*80)
    print("Statistics recomputed successfully!")
    print("="*80)
    
    # Show the updated action stats
    if 'action' in existing_stats:
        print("\nUpdated ACTION statistics:")
        action_stats = existing_stats['action']
        joint_names = features['action']['names']
        
        print(f"\n{'Joint':<5} {'Name':<40} {'Min':<12} {'Max':<12} {'Mean':<12} {'Std':<12}")
        print("-"*100)
        
        for i, name in enumerate(joint_names):
            min_val = action_stats['min'][i]
            max_val = action_stats['max'][i]
            mean_val = action_stats['mean'][i]
            std_val = action_stats['std'][i]
            
            print(f"{i:<5} {name:<40} {min_val:<12.6f} {max_val:<12.6f} {mean_val:<12.6f} {std_val:<12.6f}")

if __name__ == "__main__":
    dataset_path = "/home/lcjs-szw/datasets/pick_place_cube_copy/pick_place_cube"
    recompute_dataset_stats(dataset_path)
