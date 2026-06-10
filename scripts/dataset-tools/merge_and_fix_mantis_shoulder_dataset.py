#!/usr/bin/env python3

import argparse
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_REPAIR_SPEC = "1=2,2=-1,9=-10,10=9"
DATA_PATH_TEMPLATE = "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"
VIDEO_PATH_TEMPLATE = "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4"
EPISODES_PATH_TEMPLATE = "meta/episodes/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet"


def parse_repair_spec(text: str) -> list[tuple[int, int, int]]:
    mappings: list[tuple[int, int, int]] = []
    for item in text.split(","):
        dst_str, src_expr = item.split("=")
        dst_idx = int(dst_str)
        src_expr = src_expr.strip()
        scale = -1 if src_expr.startswith("-") else 1
        src_idx = int(src_expr[1:] if src_expr.startswith("-") else src_expr)
        mappings.append((dst_idx, scale, src_idx))
    return mappings


def discover_episode_datasets(root: Path) -> list[Path]:
    datasets = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "meta" / "info.json").exists() and (child / "data").is_dir():
            datasets.append(child)
    if not datasets:
        raise FileNotFoundError(f"No episode datasets found under {root}")
    return datasets


def read_info(dataset_path: Path) -> dict:
    return json.loads((dataset_path / "meta" / "info.json").read_text())


def validate_feature_layout(dataset_paths: list[Path]) -> dict:
    reference = None
    for path in dataset_paths:
        info = read_info(path)
        features = info["features"]
        layout = {
            "robot_type": info["robot_type"],
            "fps": info["fps"],
            "features": features,
            "action_names": tuple(features["action"]["names"]),
            "state_names": tuple(features["observation.state"]["names"]),
            "video_keys": tuple(k for k, v in features.items() if v["dtype"] == "video"),
        }
        if reference is None:
            reference = layout
            continue
        for key in ["robot_type", "fps", "action_names", "state_names", "video_keys"]:
            if layout[key] != reference[key]:
                raise ValueError(f"Feature layout mismatch in {path} for key '{key}'")
    assert reference is not None
    return reference


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_vector_series(series: pd.Series) -> np.ndarray:
    return np.stack(series.to_numpy()).astype(np.float64)


def repair_actions(actions: np.ndarray, mappings: list[tuple[int, int, int]]) -> np.ndarray:
    repaired = actions.copy()
    original = actions.copy()
    for dst_idx, scale, src_idx in mappings:
        repaired[:, dst_idx] = scale * original[:, src_idx]
    return repaired


def compute_vector_stats(array: np.ndarray) -> dict[str, np.ndarray]:
    return {
        "min": np.min(array, axis=0),
        "max": np.max(array, axis=0),
        "mean": np.mean(array, axis=0),
        "std": np.std(array, axis=0),
        "count": np.array([array.shape[0]], dtype=np.float64),
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


def json_stats_to_numpy(stats: dict) -> dict[str, np.ndarray]:
    return {k: np.asarray(v, dtype=np.float64) for k, v in stats.items()}


def numpy_stats_to_json(stats: dict[str, np.ndarray]) -> dict:
    return {k: np.asarray(v).tolist() for k, v in stats.items()}


def copy_video_tree(src_dataset: Path, dst_dataset: Path, video_keys: tuple[str, ...], file_index: int) -> None:
    for video_key in video_keys:
        src = src_dataset / VIDEO_PATH_TEMPLATE.format(video_key=video_key, chunk_index=0, file_index=0)
        dst = dst_dataset / VIDEO_PATH_TEMPLATE.format(video_key=video_key, chunk_index=0, file_index=file_index)
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)


def infer_task_text(dataset_path: Path) -> str:
    df = pd.read_parquet(dataset_path / "meta" / "tasks.parquet")
    if len(df.index) != 1:
        raise ValueError(f"Expected one task in {dataset_path}, found {len(df.index)}")
    return str(df.index[0])


def build_episode_row(
    source_row: pd.Series,
    numeric_stats: dict[str, dict[str, np.ndarray]],
    episode_index: int,
    file_index: int,
    dataset_from_index: int,
    dataset_to_index: int,
    task_text: str,
    video_keys: tuple[str, ...],
) -> dict:
    row = source_row.to_dict()
    row["episode_index"] = episode_index
    row["tasks"] = np.array([task_text], dtype=object)
    row["data/chunk_index"] = 0
    row["data/file_index"] = file_index
    row["dataset_from_index"] = dataset_from_index
    row["dataset_to_index"] = dataset_to_index
    row["meta/episodes/chunk_index"] = 0
    row["meta/episodes/file_index"] = 0

    for video_key in video_keys:
        row[f"videos/{video_key}/chunk_index"] = 0
        row[f"videos/{video_key}/file_index"] = file_index

    for feature_key, stats in numeric_stats.items():
        for stat_key, value in stats.items():
            row[f"stats/{feature_key}/{stat_key}"] = value

    return row


def create_merged_fixed_dataset(
    src_root: Path,
    dst_dataset: Path,
    output_repo_id: str,
    mappings: list[tuple[int, int, int]],
    task_text_override: str | None,
) -> dict:
    dataset_paths = discover_episode_datasets(src_root)
    layout = validate_feature_layout(dataset_paths)
    template_info = read_info(dataset_paths[0])
    video_keys = layout["video_keys"]

    ensure_dir(dst_dataset)
    ensure_dir(dst_dataset / "data" / "chunk-000")
    ensure_dir(dst_dataset / "meta" / "episodes" / "chunk-000")
    for video_key in video_keys:
        ensure_dir(dst_dataset / "videos" / video_key / "chunk-000")
        ensure_dir(dst_dataset / "images" / video_key)

    total_frames = 0
    episode_rows: list[dict] = []
    aggregate_stats_by_feature: dict[str, list[dict[str, np.ndarray]]] = {}

    for episode_index, dataset_path in enumerate(dataset_paths):
        task_text = task_text_override or infer_task_text(dataset_path)
        source_data = pd.read_parquet(dataset_path / DATA_PATH_TEMPLATE.format(chunk_index=0, file_index=0))
        source_episode_meta = pd.read_parquet(
            dataset_path / EPISODES_PATH_TEMPLATE.format(chunk_index=0, file_index=0)
        ).iloc[0]
        source_stats_json = json.loads((dataset_path / "meta" / "stats.json").read_text())

        num_frames = len(source_data)
        dataset_from_index = total_frames
        dataset_to_index = total_frames + num_frames

        repaired_df = source_data.copy()
        repaired_actions = repair_actions(load_vector_series(repaired_df["action"]), mappings).astype(np.float32)
        repaired_df["action"] = list(repaired_actions)
        repaired_df["episode_index"] = episode_index
        repaired_df["task_index"] = 0
        repaired_df["index"] = np.arange(dataset_from_index, dataset_to_index, dtype=np.int64)

        data_file = dst_dataset / DATA_PATH_TEMPLATE.format(chunk_index=0, file_index=episode_index)
        repaired_df.to_parquet(data_file, index=False)
        copy_video_tree(dataset_path, dst_dataset, video_keys, episode_index)

        numeric_stats = {
            "action": compute_vector_stats(repaired_actions),
            "observation.state": compute_vector_stats(load_vector_series(repaired_df["observation.state"])),
            "timestamp": compute_vector_stats(repaired_df["timestamp"].to_numpy(dtype=np.float64).reshape(-1, 1)),
            "frame_index": compute_vector_stats(repaired_df["frame_index"].to_numpy(dtype=np.float64).reshape(-1, 1)),
            "episode_index": compute_vector_stats(repaired_df["episode_index"].to_numpy(dtype=np.float64).reshape(-1, 1)),
            "index": compute_vector_stats(repaired_df["index"].to_numpy(dtype=np.float64).reshape(-1, 1)),
            "task_index": compute_vector_stats(repaired_df["task_index"].to_numpy(dtype=np.float64).reshape(-1, 1)),
        }

        episode_row = build_episode_row(
            source_row=source_episode_meta,
            numeric_stats=numeric_stats,
            episode_index=episode_index,
            file_index=episode_index,
            dataset_from_index=dataset_from_index,
            dataset_to_index=dataset_to_index,
            task_text=task_text,
            video_keys=video_keys,
        )
        episode_rows.append(episode_row)

        per_feature_stats = {k: json_stats_to_numpy(v) for k, v in source_stats_json.items()}
        per_feature_stats["action"] = numeric_stats["action"]
        per_feature_stats["observation.state"] = numeric_stats["observation.state"]
        per_feature_stats["timestamp"] = numeric_stats["timestamp"]
        per_feature_stats["frame_index"] = numeric_stats["frame_index"]
        per_feature_stats["episode_index"] = numeric_stats["episode_index"]
        per_feature_stats["index"] = numeric_stats["index"]
        per_feature_stats["task_index"] = numeric_stats["task_index"]

        for feature_key, stats in per_feature_stats.items():
            aggregate_stats_by_feature.setdefault(feature_key, []).append(stats)

        total_frames += num_frames

    episodes_df = pd.DataFrame(episode_rows)
    episodes_df.to_parquet(
        dst_dataset / EPISODES_PATH_TEMPLATE.format(chunk_index=0, file_index=0),
        index=False,
    )

    final_task_text = task_text_override or infer_task_text(dataset_paths[0])
    tasks_df = pd.DataFrame({"task_index": [0]}, index=pd.Index([final_task_text]))
    tasks_df.to_parquet(dst_dataset / "meta" / "tasks.parquet")

    aggregated_stats_json = {
        feature_key: numpy_stats_to_json(aggregate_feature_stats(stats_list))
        for feature_key, stats_list in aggregate_stats_by_feature.items()
    }
    (dst_dataset / "meta" / "stats.json").write_text(json.dumps(aggregated_stats_json, indent=4))

    data_bytes = sum(p.stat().st_size for p in (dst_dataset / "data").rglob("*.parquet"))
    video_bytes = sum(p.stat().st_size for p in (dst_dataset / "videos").rglob("*.mp4"))
    data_files_size_in_mb = math.ceil(data_bytes / (1024 * 1024)) if data_bytes else 0
    video_files_size_in_mb = math.ceil(video_bytes / (1024 * 1024)) if video_bytes else 0

    merged_info = template_info
    merged_info["repo_id"] = output_repo_id
    merged_info["total_episodes"] = len(dataset_paths)
    merged_info["total_frames"] = total_frames
    merged_info["total_tasks"] = 1
    merged_info["data_files_size_in_mb"] = data_files_size_in_mb
    merged_info["video_files_size_in_mb"] = video_files_size_in_mb
    merged_info["splits"] = {"train": f"0:{len(dataset_paths)}"}
    merged_info["data_path"] = DATA_PATH_TEMPLATE
    merged_info["video_path"] = VIDEO_PATH_TEMPLATE
    (dst_dataset / "meta" / "info.json").write_text(json.dumps(merged_info, indent=2))

    return {
        "episodes": len(dataset_paths),
        "frames": total_frames,
        "task_text": final_task_text,
        "video_keys": list(video_keys),
        "data_files_size_in_mb": data_files_size_in_mb,
        "video_files_size_in_mb": video_files_size_in_mb,
    }


def validate_alignment(dataset_path: Path) -> dict:
    frames = []
    for parquet_path in sorted((dataset_path / "data").rglob("*.parquet")):
        frames.append(pd.read_parquet(parquet_path, columns=["episode_index", "frame_index", "observation.state", "action"]))
    df = pd.concat(frames, ignore_index=True).sort_values(["episode_index", "frame_index"]).reset_index(drop=True)

    state = load_vector_series(df["observation.state"])
    action = load_vector_series(df["action"])
    episode = df["episode_index"].to_numpy()
    same_next = episode[1:] == episode[:-1]
    action_t = action[:-1][same_next]
    next_state = state[1:][same_next]

    info = read_info(dataset_path)
    action_names = info["features"]["action"]["names"]
    state_names = info["features"]["observation.state"]["names"]
    mae = np.mean(np.abs(action_t - next_state), axis=0)

    focus_dims = [1, 2, 9, 10]
    return {
        "pairs": int(len(action_t)),
        "focus": [
            {
                "dim": dim,
                "action_name": action_names[dim],
                "state_name": state_names[dim],
                "mae": float(mae[dim]),
            }
            for dim in focus_dims
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge per-episode Mantis datasets, repair shoulder action semantics, and write a training-ready LeRobot dataset."
    )
    parser.add_argument("--src_root", required=True, help="Directory containing one dataset root per episode.")
    parser.add_argument("--dst_dataset", required=True, help="Output merged dataset path.")
    parser.add_argument("--output_repo_id", default=None, help="Repo ID to store in metadata.")
    parser.add_argument("--repair_spec", default=DEFAULT_REPAIR_SPEC)
    parser.add_argument("--task_text", default=None, help="Optional replacement task text for meta/tasks.parquet.")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    src_root = Path(args.src_root)
    dst_dataset = Path(args.dst_dataset)
    output_repo_id = args.output_repo_id or dst_dataset.name
    mappings = parse_repair_spec(args.repair_spec)

    if dst_dataset.exists():
        if not args.overwrite:
            raise FileExistsError(f"Destination already exists: {dst_dataset}")
        shutil.rmtree(dst_dataset)

    summary = create_merged_fixed_dataset(
        src_root=src_root,
        dst_dataset=dst_dataset,
        output_repo_id=output_repo_id,
        mappings=mappings,
        task_text_override=args.task_text,
    )
    alignment = validate_alignment(dst_dataset)

    print(json.dumps(
        {
            "source_root": str(src_root),
            "destination": str(dst_dataset),
            "repo_id": output_repo_id,
            "repair_spec": args.repair_spec,
            **summary,
            "alignment": alignment,
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
