#!/usr/bin/env python3

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


def compute_vector_stats(array: np.ndarray) -> dict[str, np.ndarray]:
    return {
        "min": np.min(array, axis=0),
        "max": np.max(array, axis=0),
        "mean": np.mean(array, axis=0),
        "std": np.std(array, axis=0),
        "count": np.array([array.shape[0]]),
        "q01": np.quantile(array, 0.01, axis=0),
        "q10": np.quantile(array, 0.10, axis=0),
        "q50": np.quantile(array, 0.50, axis=0),
        "q90": np.quantile(array, 0.90, axis=0),
        "q99": np.quantile(array, 0.99, axis=0),
    }


def aggregate_feature_stats(stats_list: list[dict[str, np.ndarray]]) -> dict[str, np.ndarray]:
    means = np.stack([s["mean"] for s in stats_list])
    variances = np.stack([s["std"] ** 2 for s in stats_list])
    counts = np.stack([s["count"] for s in stats_list])
    total_count = counts.sum(axis=0)

    while counts.ndim < means.ndim:
        counts = np.expand_dims(counts, axis=-1)

    total_mean = (means * counts).sum(axis=0) / total_count
    delta_means = means - total_mean
    total_variance = ((variances + delta_means**2) * counts).sum(axis=0) / total_count

    aggregated = {
        "min": np.min(np.stack([s["min"] for s in stats_list]), axis=0),
        "max": np.max(np.stack([s["max"] for s in stats_list]), axis=0),
        "mean": total_mean,
        "std": np.sqrt(total_variance),
        "count": total_count,
    }
    for q_key in ["q01", "q10", "q50", "q90", "q99"]:
        aggregated[q_key] = (np.stack([s[q_key] for s in stats_list]) * counts).sum(axis=0) / total_count
    return aggregated


def parse_swap_pairs(text: str) -> list[tuple[int, int]]:
    pairs = []
    for item in text.split(","):
        left, right = item.split(":")
        pairs.append((int(left), int(right)))
    return pairs


def copy_dataset_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        raise FileExistsError(f"Destination already exists: {dst}")
    shutil.copytree(src, dst)


def swap_action_dims_in_parquet(parquet_path: Path, swap_pairs: list[tuple[int, int]]) -> int:
    df = pd.read_parquet(parquet_path)
    if "action" not in df.columns:
        raise KeyError(f"Missing 'action' column in {parquet_path}")

    actions = np.stack(df["action"].to_list())
    for left, right in swap_pairs:
        actions[:, [left, right]] = actions[:, [right, left]]

    df["action"] = list(actions)
    df.to_parquet(parquet_path, index=False)
    return len(df)


def recompute_all_stats(dataset_path: Path) -> None:
    info = json.loads((dataset_path / "meta" / "info.json").read_text())
    features = info["features"]
    total_episodes = info["total_episodes"]

    data_parquet_files = sorted((dataset_path / "data").rglob("*.parquet"))
    all_data_df = pd.concat([pd.read_parquet(f) for f in data_parquet_files], ignore_index=True)

    numerical_keys = [
        key for key, feature in features.items() if feature["dtype"] not in ["string", "image", "video"]
    ]

    all_episode_stats = []
    for ep_idx in range(total_episodes):
        ep_df = all_data_df[all_data_df["episode_index"] == ep_idx]
        ep_stats = {}
        for key in numerical_keys:
            if key in ep_df.columns:
                ep_stats[key] = compute_vector_stats(np.stack(ep_df[key].tolist()))
        all_episode_stats.append(ep_stats)

    episodes_dir = dataset_path / "meta" / "episodes"
    episode_parquet_files = sorted(episodes_dir.rglob("*.parquet"))
    for ep_pq_file in episode_parquet_files:
        ep_meta_df = pd.read_parquet(ep_pq_file)
        for idx, row in ep_meta_df.iterrows():
            ep_idx = row["episode_index"]
            ep_stats = all_episode_stats[ep_idx]
            for feature_key, feature_stats in ep_stats.items():
                for stat_key, stat_value in feature_stats.items():
                    col_name = f"stats/{feature_key}/{stat_key}"
                    if col_name in ep_meta_df.columns:
                        ep_meta_df.at[idx, col_name] = stat_value.tolist()
        ep_meta_df.to_parquet(ep_pq_file, index=False)

    aggregated_stats = {
        key: aggregate_feature_stats([ep_stats[key] for ep_stats in all_episode_stats if key in ep_stats])
        for key in numerical_keys
    }

    def convert_to_serializable(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, dict):
            return {k: convert_to_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        return obj

    stats_path = dataset_path / "meta" / "stats.json"
    existing_stats = json.loads(stats_path.read_text())
    for key, value in aggregated_stats.items():
        existing_stats[key] = convert_to_serializable(value)

    backup_path = dataset_path / "meta" / "stats_backup.json"
    backup_path.write_text(stats_path.read_text())
    stats_path.write_text(json.dumps(existing_stats, indent=4))


def validate_alignment(dataset_path: Path, swap_pairs: list[tuple[int, int]]) -> dict:
    info = json.loads((dataset_path / "meta" / "info.json").read_text())
    action_names = info["features"]["action"]["names"]
    state_names = info["features"]["observation.state"]["names"]

    parquet_files = sorted((dataset_path / "data").glob("chunk-*/file-*.parquet"))
    frames = []
    for p in parquet_files:
        frames.append(pd.read_parquet(p, columns=["episode_index", "frame_index", "observation.state", "action"]))
    df = pd.concat(frames, ignore_index=True).sort_values(["episode_index", "frame_index"]).reset_index(drop=True)

    state = np.stack(df["observation.state"].to_list()).astype(np.float64)
    action = np.stack(df["action"].to_list()).astype(np.float64)
    episode = df["episode_index"].to_numpy()
    same_next = episode[1:] == episode[:-1]
    action_t = action[:-1][same_next]
    next_state = state[1:][same_next]

    mae = np.mean(np.abs(action_t - next_state), axis=0)
    focus = sorted({idx for pair in swap_pairs for idx in pair})
    return {
        "pairs": int(len(action_t)),
        "focus": [
            {
                "dim": i,
                "action_name": action_names[i],
                "state_name": state_names[i],
                "mae": float(mae[i]),
            }
            for i in focus
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a corrected LeRobot dataset by swapping action dimensions.")
    parser.add_argument("--src_dataset", required=True)
    parser.add_argument("--dst_dataset", required=True)
    parser.add_argument("--swap_pairs", default="1:2,9:10")
    args = parser.parse_args()

    src = Path(args.src_dataset)
    dst = Path(args.dst_dataset)
    swap_pairs = parse_swap_pairs(args.swap_pairs)

    print(f"Copying dataset: {src} -> {dst}")
    copy_dataset_tree(src, dst)

    data_files = sorted((dst / "data").rglob("*.parquet"))
    total_frames = 0
    for parquet_path in data_files:
        frames = swap_action_dims_in_parquet(parquet_path, swap_pairs)
        total_frames += frames
        print(f"Updated {parquet_path.relative_to(dst)} ({frames} frames)")

    print("Recomputing stats...")
    recompute_all_stats(dst)

    print("Validating action[t] vs state[t+1] alignment...")
    summary = validate_alignment(dst, swap_pairs)
    print(json.dumps({
        "dataset": str(dst),
        "swap_pairs": swap_pairs,
        "parquet_files": len(data_files),
        "total_frames": total_frames,
        "alignment": summary,
    }, indent=2))


if __name__ == "__main__":
    main()
