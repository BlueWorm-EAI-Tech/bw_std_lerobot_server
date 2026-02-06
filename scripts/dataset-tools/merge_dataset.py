from pathlib import Path
from lerobot.datasets.lerobot_dataset import LeRobotDataset
from lerobot.datasets.dataset_tools import merge_datasets

# Base directories containing datasets
base_dirs = [
    "/home/lcjs-szw/datasets/2026_01_20_pm/"
]

# Discover all datasets
datasets = []
dataset_paths = []

for base_dir in base_dirs:
    base_path = Path(base_dir)
    if not base_path.exists():
        print(f"Warning: {base_dir} does not exist, skipping...")
        continue
    
    # Find subfolders starting with date patterns
    if "2026_01_20" in base_dir:
        date_pattern = "20260120*"
        bag_pattern = "bw_bag_20260120_*"
    elif "2026_01_16" in base_dir:
        date_pattern = "20260116*"
        bag_pattern = "bw_bag_20260116_*"
    else:
        continue
    
    # Iterate through date folders
    for date_folder in base_path.glob(date_pattern):
        if not date_folder.is_dir():
            continue
        
        # Find all bag folders within each date folder
        for bag_folder in date_folder.glob(bag_pattern):
            if not bag_folder.is_dir():
                continue
            
            dataset_paths.append(bag_folder)
            print(f"Found dataset: {bag_folder}")

# Load all datasets
print(f"\nLoading {len(dataset_paths)} datasets...")
for dataset_path in dataset_paths:
    try:
        ds = LeRobotDataset(repo_id=dataset_path.name, root=str(dataset_path))
        datasets.append(ds)
        print(f"✓ Loaded {dataset_path.name}")
    except Exception as e:
        print(f"✗ Failed to load {dataset_path.name}: {e}")

if not datasets:
    print("No datasets found to merge!")
    exit(1)

# Merge all datasets
print(f"\nMerging {len(datasets)} datasets...")
output_dir = "/home/lcjs-szw/datasets/pick_place_cube_0120"
merged = merge_datasets(
    datasets=datasets,
    output_repo_id="pick_place_cube",
    output_dir=output_dir
)

print(f"\n✓ Done! Merged {len(datasets)} datasets into {output_dir}")
print(f"  Total episodes: {merged.meta.total_episodes}")
print(f"  Total frames: {merged.meta.total_frames}")
