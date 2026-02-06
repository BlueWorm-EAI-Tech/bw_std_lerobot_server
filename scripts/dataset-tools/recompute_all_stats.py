#!/usr/bin/env python3
"""
Recompute ALL statistics (episode-level and dataset-level) after modifying action values.
This is necessary because lerobot stores stats at both episode and dataset levels.
"""

import sys
sys.path.insert(0, '/home/lcjs-szw/repos/lerobot/src')

import json
import numpy as np
import pandas as pd
from pathlib import Path
from lerobot.datasets.compute_stats import compute_episode_stats, aggregate_stats

def recompute_all_stats(dataset_path):
    """Recompute episode-level and dataset-level statistics"""
    
    dataset_path = Path(dataset_path)
    print("="*100)
    print("RECOMPUTING ALL STATISTICS (Episode-level + Dataset-level)")
    print("="*100)
    print(f"\nDataset: {dataset_path}")
    
    # Load info
    info_path = dataset_path / "meta" / "info.json"
    with open(info_path, 'r') as f:
        info = json.load(f)
    
    features = info['features']
    total_episodes = info['total_episodes']
    
    print(f"Total episodes: {total_episodes}")
    print(f"Total frames: {info['total_frames']}")
    
    # Load data parquet file
    data_dir = dataset_path / "data"
    data_parquet_files = sorted(data_dir.rglob("*.parquet"))
    
    print(f"\nFound {len(data_parquet_files)} data parquet files")
    
    # Load all data
    print("Loading all data...")
    all_data_df = pd.concat([pd.read_parquet(f) for f in data_parquet_files], ignore_index=True)
    print(f"Loaded {len(all_data_df)} frames")
    
    # Recompute episode-level stats
    print("\n" + "="*100)
    print("STEP 1: Recomputing episode-level statistics")
    print("="*100)
    
    all_episode_stats = []
    
    for ep_idx in range(total_episodes):
        print(f"Processing episode {ep_idx}/{total_episodes}...", end='\r')
        
        # Get frames for this episode
        ep_df = all_data_df[all_data_df['episode_index'] == ep_idx]
        
        # Prepare episode data
        episode_data = {}
        
        for key in features.keys():
            if features[key]["dtype"] == "string":
                continue
            
            if features[key]["dtype"] in ["image", "video"]:
                # Skip images/videos - they're expensive and likely unchanged
                continue
            else:
                # Stack numerical data
                if key in ep_df.columns:
                    data_list = ep_df[key].tolist()
                    episode_data[key] = np.stack(data_list)
        
        # Compute stats for this episode
        ep_stats = compute_episode_stats(episode_data, features)
        all_episode_stats.append(ep_stats)
    
    print(f"\nProcessed all {total_episodes} episodes")
    
    # Update episode metadata parquet files
    print("\n" + "="*100)
    print("STEP 2: Updating episode metadata parquet files")
    print("="*100)
    
    episodes_dir = dataset_path / "meta" / "episodes"
    episode_parquet_files = sorted(episodes_dir.rglob("*.parquet"))
    
    print(f"Found {len(episode_parquet_files)} episode metadata files")
    
    for ep_pq_file in episode_parquet_files:
        print(f"Updating {ep_pq_file.name}...")
        
        # Load episode metadata
        ep_meta_df = pd.read_parquet(ep_pq_file)
        
        # Update stats for each episode in this file
        for idx, row in ep_meta_df.iterrows():
            ep_idx = row['episode_index']
            ep_stats = all_episode_stats[ep_idx]
            
            # Update stats columns
            for feature_key, feature_stats in ep_stats.items():
                for stat_key, stat_value in feature_stats.items():
                    col_name = f"stats/{feature_key}/{stat_key}"
                    if col_name in ep_meta_df.columns:
                        # Convert numpy array to list for storage
                        if isinstance(stat_value, np.ndarray):
                            ep_meta_df.at[idx, col_name] = stat_value.tolist()
                        else:
                            ep_meta_df.at[idx, col_name] = stat_value
        
        # Save updated episode metadata
        ep_meta_df.to_parquet(ep_pq_file, index=False)
        print(f"  Updated {ep_pq_file}")
    
    # Aggregate dataset-level stats
    print("\n" + "="*100)
    print("STEP 3: Aggregating dataset-level statistics")
    print("="*100)
    
    aggregated_stats = aggregate_stats(all_episode_stats)
    
    # Convert to serializable format
    def convert_to_serializable(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        return obj
    
    stats_serializable = convert_to_serializable(aggregated_stats)
    
    # Backup and save dataset-level stats
    stats_path = dataset_path / "meta" / "stats.json"
    backup_path = dataset_path / "meta" / "stats_backup.json"
    
    print(f"\nBacking up old stats to: {backup_path}")
    with open(stats_path, 'r') as f:
        old_stats = json.load(f)
    with open(backup_path, 'w') as f:
        json.dump(old_stats, f, indent=4)
    
    print(f"Writing new stats to: {stats_path}")
    with open(stats_path, 'w') as f:
        json.dump(stats_serializable, f, indent=4)
    
    # Display results
    print("\n" + "="*100)
    print("STATISTICS RECOMPUTED SUCCESSFULLY!")
    print("="*100)
    
    if 'action' in stats_serializable:
        print("\nUpdated ACTION statistics (dataset-level):")
        action_stats = stats_serializable['action']
        joint_names = features['action']['names']
        
        print(f"\n{'Joint':<5} {'Name':<40} {'Min':<12} {'Max':<12} {'Mean':<12} {'Std':<12}")
        print("-"*100)
        
        for i, name in enumerate(joint_names):
            min_val = action_stats['min'][i]
            max_val = action_stats['max'][i]
            mean_val = action_stats['mean'][i]
            std_val = action_stats['std'][i]
            
            flag = ""
            if i == 1:
                flag = " <- LEFT SHOULDER ROLL"
            elif i == 9:
                flag = " <- RIGHT SHOULDER ROLL"
            
            print(f"{i:<5} {name:<40} {min_val:<12.6f} {max_val:<12.6f} {mean_val:<12.6f} {std_val:<12.6f}{flag}")
    
    print("\n" + "="*100)
    print("✅ All statistics updated successfully!")
    print("✅ You can now train your model with the corrected dataset.")
    print("="*100)

if __name__ == "__main__":
    dataset_path = "/home/lcjs-szw/datasets/pick_place_cube_copy/pick_place_cube"
    recompute_all_stats(dataset_path)
