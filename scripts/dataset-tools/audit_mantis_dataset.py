#!/usr/bin/env python3
"""
Audit a Mantis LeRobot dataset for format, stats, and joint-quality issues.

Examples:
    python scripts/dataset-tools/audit_mantis_dataset.py \
        /home/lcjs-szw/Documents/data20260415/mantis_data_0415_raw_merged

    python scripts/dataset-tools/audit_mantis_dataset.py \
        /home/lcjs-szw/Documents/data20260415/mantis_data_0415_raw_merged \
        /home/lcjs-szw/Documents/data20260415/mantis_data_0415_action_fixed_merged
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_FOCUS_PATTERNS = [
    "elbow",
    "shoulder_roll",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_paths", nargs="+", help="Paths to LeRobot dataset roots")
    parser.add_argument(
        "--focus",
        nargs="*",
        default=None,
        help="Joint names or substrings to highlight. Defaults to elbow and shoulder_roll joints.",
    )
    parser.add_argument(
        "--std-threshold",
        type=float,
        default=1e-4,
        help="Flag joints whose std is below this threshold",
    )
    parser.add_argument(
        "--zero-threshold",
        type=float,
        default=95.0,
        help="Flag joints whose zero percentage exceeds this threshold",
    )
    parser.add_argument(
        "--stats-tol",
        type=float,
        default=1e-3,
        help="Tolerance when comparing computed mean/std against meta/stats.json",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of suspicious joints to print at most",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_array_columns(df: pd.DataFrame, prefix: str) -> np.ndarray:
    if prefix in df.columns:
        return np.stack(df[prefix].values)

    split_cols = sorted(col for col in df.columns if col.startswith(prefix))
    if not split_cols:
        raise KeyError(f"Could not find {prefix!r} in columns")
    return df[split_cols].values


def load_dataset_arrays(root: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    parquet_files = sorted((root / "data").rglob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(f"No parquet files found under {root / 'data'}")

    states = []
    actions = []
    episodes = []

    for parquet_file in parquet_files:
        df = pd.read_parquet(parquet_file)
        states.append(load_array_columns(df, "observation.state"))
        actions.append(load_array_columns(df, "action"))
        episodes.append(df["episode_index"].to_numpy())

    return np.vstack(states), np.vstack(actions), np.concatenate(episodes)


def normalize_focus_patterns(raw_patterns: list[str] | None) -> list[str]:
    if raw_patterns:
        return [pattern.strip() for pattern in raw_patterns if pattern.strip()]
    return DEFAULT_FOCUS_PATTERNS


def task_summary(root: Path) -> str:
    tasks_parquet = root / "meta" / "tasks.parquet"
    if not tasks_parquet.exists():
        return "missing"

    try:
        tasks_df = pd.read_parquet(tasks_parquet)
    except Exception as exc:  # pragma: no cover - defensive reporting
        return f"unreadable ({exc})"

    if "task" in tasks_df.columns:
        unique_tasks = tasks_df["task"].nunique()
        return f"{unique_tasks} rows={len(tasks_df)}"
    return f"rows={len(tasks_df)} no_task_column"


def find_focus_indices(joint_names: list[str], patterns: list[str]) -> list[int]:
    selected = []
    for idx, joint_name in enumerate(joint_names):
        lowered = joint_name.lower()
        if any(pattern.lower() in lowered for pattern in patterns):
            selected.append(idx)
    return selected


def format_joint_stats(
    joint_name: str,
    joint_idx: int,
    state_values: np.ndarray,
    action_values: np.ndarray,
    stored_mean: float | None,
    stored_std: float | None,
) -> str:
    gap = action_values - state_values
    lines = [
        f"[{joint_name}] idx={joint_idx}",
        (
            "  STATE  "
            f"min={state_values.min(): .6f} max={state_values.max(): .6f} "
            f"mean={state_values.mean(): .6f} std={state_values.std(): .6f} "
            f"zero%={(np.abs(state_values) < 1e-6).mean() * 100:6.2f}"
        ),
        (
            "  ACTION "
            f"min={action_values.min(): .6f} max={action_values.max(): .6f} "
            f"mean={action_values.mean(): .6f} std={action_values.std(): .6f} "
            f"zero%={(np.abs(action_values) < 1e-6).mean() * 100:6.2f}"
        ),
        (
            "  GAP    "
            f"mean={gap.mean(): .6f} std={gap.std(): .6f} "
            f"abs_mean={np.abs(gap).mean(): .6f}"
        ),
    ]
    if stored_mean is not None and stored_std is not None:
        lines.append(f"  META   stats.mean={stored_mean: .6f} stats.std={stored_std: .6f}")
    return "\n".join(lines)


def audit_dataset(
    root: Path,
    focus_patterns: list[str],
    std_threshold: float,
    zero_threshold: float,
    stats_tol: float,
    top: int,
) -> int:
    print("\n" + "=" * 120)
    print(f"DATASET: {root}")

    issues = 0
    required_files = [
        root / "meta" / "info.json",
        root / "meta" / "stats.json",
        root / "data",
    ]
    missing = [path for path in required_files if not path.exists()]
    if missing:
        for path in missing:
            print(f"Missing required path: {path}")
        return len(missing)

    info = load_json(root / "meta" / "info.json")
    stats = load_json(root / "meta" / "stats.json")

    state_names = info["features"]["observation.state"]["names"]
    action_names = info["features"]["action"]["names"]
    if state_names != action_names:
        issues += 1
        print("State/action feature names do not match exactly")

    states, actions, episode_indices = load_dataset_arrays(root)
    unique_episodes = np.unique(episode_indices)

    print(
        "Summary: "
        f"episodes={info.get('total_episodes')} "
        f"frames={info.get('total_frames')} "
        f"fps={info.get('fps')} "
        f"codebase={info.get('codebase_version')} "
        f"tasks={task_summary(root)}"
    )
    print(
        "Loaded: "
        f"state_shape={states.shape} "
        f"action_shape={actions.shape} "
        f"unique_episodes={len(unique_episodes)} "
        f"nan_state={bool(np.isnan(states).any())} "
        f"nan_action={bool(np.isnan(actions).any())}"
    )

    if states.shape != actions.shape:
        issues += 1
        print("State/action shapes do not match")

    if states.shape[1] != len(action_names):
        issues += 1
        print(
            f"Loaded action dimension {actions.shape[1]} does not match metadata "
            f"{len(action_names)}"
        )

    focus_indices = find_focus_indices(action_names, focus_patterns)
    if focus_indices:
        print("\nFocus joints:")
        for idx in focus_indices:
            stored_mean = stats.get("action", {}).get("mean", [None] * len(action_names))[idx]
            stored_std = stats.get("action", {}).get("std", [None] * len(action_names))[idx]
            print(
                format_joint_stats(
                    action_names[idx],
                    idx,
                    states[:, idx],
                    actions[:, idx],
                    stored_mean,
                    stored_std,
                )
            )
    else:
        print("\nFocus joints: none matched")

    suspicious = []
    for idx, joint_name in enumerate(action_names):
        state_values = states[:, idx]
        action_values = actions[:, idx]
        action_std = float(action_values.std())
        action_zero_pct = float((np.abs(action_values) < 1e-6).mean() * 100)
        state_std = float(state_values.std())
        state_zero_pct = float((np.abs(state_values) < 1e-6).mean() * 100)
        stored_mean = stats.get("action", {}).get("mean", [None] * len(action_names))[idx]
        stored_std = stats.get("action", {}).get("std", [None] * len(action_names))[idx]

        reasons = []
        if state_std < std_threshold:
            reasons.append(f"state_std={state_std:.8f}")
        if action_std < std_threshold:
            reasons.append(f"action_std={action_std:.8f}")
        if state_zero_pct > zero_threshold:
            reasons.append(f"state_zero%={state_zero_pct:.2f}")
        if action_zero_pct > zero_threshold:
            reasons.append(f"action_zero%={action_zero_pct:.2f}")
        if stored_mean is not None and abs(float(stored_mean) - float(action_values.mean())) > stats_tol:
            reasons.append(
                f"stats.mean_mismatch={abs(float(stored_mean) - float(action_values.mean())):.6f}"
            )
        if stored_std is not None and abs(float(stored_std) - action_std) > stats_tol:
            reasons.append(f"stats.std_mismatch={abs(float(stored_std) - action_std):.6f}")

        if reasons:
            suspicious.append((idx, joint_name, reasons))

    print("\nSuspicious joints:")
    if suspicious:
        issues += len(suspicious)
        for idx, joint_name, reasons in suspicious[:top]:
            print(f"  {idx:2d} {joint_name}: " + ", ".join(reasons))
        if len(suspicious) > top:
            print(f"  ... and {len(suspicious) - top} more")
    else:
        print("  none")

    print(f"\nAudit issues found: {issues}")
    return issues


def main() -> int:
    args = parse_args()
    focus_patterns = normalize_focus_patterns(args.focus)

    total_issues = 0
    for dataset_path in args.dataset_paths:
        total_issues += audit_dataset(
            root=Path(dataset_path),
            focus_patterns=focus_patterns,
            std_threshold=args.std_threshold,
            zero_threshold=args.zero_threshold,
            stats_tol=args.stats_tol,
            top=args.top,
        )

    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
