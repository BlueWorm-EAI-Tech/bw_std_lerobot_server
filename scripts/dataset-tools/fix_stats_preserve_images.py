#!/usr/bin/env python3
"""
Fix stats.json by restoring image stats from backup and keeping the updated action/state stats.
"""

import json
from pathlib import Path

dataset_path = Path("/home/lcjs-szw/datasets/pick_place_cube_copy/pick_place_cube")

print("="*100)
print("FIXING STATS.JSON - PRESERVING IMAGE STATS")
print("="*100)

# Load current stats (has updated action/state stats)
stats_path = dataset_path / "meta" / "stats.json"
with open(stats_path, 'r') as f:
    current_stats = json.load(f)

print(f"\nCurrent stats keys: {list(current_stats.keys())}")

# Load backup stats (has image stats)
backup_path = dataset_path / "meta" / "stats_backup.json"
with open(backup_path, 'r') as f:
    backup_stats = json.load(f)

print(f"Backup stats keys: {list(backup_stats.keys())}")

# Merge: keep updated numerical stats, restore image stats from backup
merged_stats = {}

# First, copy all from backup
for key in backup_stats.keys():
    merged_stats[key] = backup_stats[key]

# Then, overwrite with updated numerical stats from current
for key in current_stats.keys():
    merged_stats[key] = current_stats[key]
    print(f"  Updated: {key}")

print(f"\nMerged stats keys: {list(merged_stats.keys())}")

# Verify we have the image stats
image_keys = [k for k in merged_stats.keys() if 'observation.images' in k]
print(f"\nImage stats present: {image_keys}")

# Save merged stats
print(f"\nSaving merged stats to: {stats_path}")
with open(stats_path, 'w') as f:
    json.dump(merged_stats, f, indent=4)

print("\n" + "="*100)
print("✅ Stats fixed! Image stats restored, action/state stats updated.")
print("="*100)
