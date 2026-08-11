#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import av
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

REQUIRED_FILES = (
    "meta/info.json",
    "meta/stats.json",
    "meta/tasks.parquet",
    "data/chunk-000/file-000.parquet",
    "meta/episodes/chunk-000/file-000.parquet",
    "videos/observation.images.env_cam/chunk-000/file-000.mp4",
    "videos/observation.images.left_wrist_cam/chunk-000/file-000.mp4",
    "videos/observation.images.right_wrist_cam/chunk-000/file-000.mp4",
)

CAMERA_FILES = {
    "env": "videos/observation.images.env_cam/chunk-000/file-000.mp4",
    "left": "videos/observation.images.left_wrist_cam/chunk-000/file-000.mp4",
    "right": "videos/observation.images.right_wrist_cam/chunk-000/file-000.mp4",
}

NON_GRIP_DIMS = [i for i in range(16) if i not in (7, 15)]
SHOULDER_DIMS = [1, 2, 9, 10]
TIER_ORDER = ["core_high", "good", "usable_with_risk", "borderline", "reject"]


@dataclass
class EpisodeMetrics:
    source: str
    root_label: str
    raw_path: str
    valid: bool
    missing_files: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    tier: str = "reject"
    quality_score: float = 0.0
    duration_s: float = math.nan
    frames: int = 0
    estimated_fps: float = math.nan
    first_left_close_s: float = math.nan
    first_right_close_s: float = math.nan
    first_both_close_s: float = math.nan
    first_both_close_frame: int = -1
    close_sync_frames: int = -1
    mean_delta: float = math.nan
    jerk: float = math.nan
    max_jump: float = math.nan
    tracking_mae: float = math.nan
    repaired_tracking_mae: float = math.nan
    shoulder_mae: float = math.nan
    after_motion: float = math.nan
    post_grasp_duration_s: float = math.nan
    grip_switches: int = 0
    both_closed_ratio: float = math.nan
    non_monotonic_timestamps: int = 0
    non_uniform_frame_gaps: int = 0
    reject_reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)


def finite_values(rows: list[EpisodeMetrics], attr: str) -> np.ndarray:
    values: list[float] = []
    for row in rows:
        value = getattr(row, attr)
        if value is not None and np.isfinite(value):
            values.append(float(value))
    return np.asarray(values, dtype=np.float64)


def quantiles(rows: list[EpisodeMetrics], attr: str) -> dict[str, float]:
    values = finite_values(rows, attr)
    if values.size == 0:
        return {}
    qs = [0.0, 0.05, 0.1, 0.2, 0.25, 0.35, 0.5, 0.7, 0.75, 0.85, 0.9, 0.95, 0.98, 1.0]
    return {f"{q:.2f}": float(np.quantile(values, q)) for q in qs}


def q(stats: dict[str, dict[str, float]], attr: str, quantile: str, default: float) -> float:
    return float(stats.get(attr, {}).get(quantile, default))


def clipped(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return float(max(lo, min(hi, value)))


def triangular_score(value: float, good_lo: float, good_hi: float, bad_lo: float, bad_hi: float) -> float:
    if not np.isfinite(value):
        return 0.0
    if good_lo <= value <= good_hi:
        return 1.0
    if value < good_lo:
        if good_lo <= bad_lo:
            return 0.0
        return clipped((value - bad_lo) / (good_lo - bad_lo))
    if bad_hi <= good_hi:
        return 0.0
    return clipped((bad_hi - value) / (bad_hi - good_hi))


def low_score(value: float, good: float, bad: float) -> float:
    if not np.isfinite(value):
        return 0.0
    if bad <= good:
        return 1.0 if value <= good else 0.0
    if value <= good:
        return 1.0
    if value >= bad:
        return 0.0
    return clipped(1.0 - ((value - good) / (bad - good)))


def high_enough_score(value: float, bad_low: float, good_low: float, good_high: float, bad_high: float) -> float:
    if not np.isfinite(value):
        return 0.0
    if good_low <= value <= good_high:
        return 1.0
    if value < good_low:
        if good_low <= bad_low:
            return 0.0
        return clipped((value - bad_low) / (good_low - bad_low))
    if bad_high <= good_high:
        return 0.75
    return 0.75 + 0.25 * clipped((bad_high - value) / (bad_high - good_high))


def repaired_actions(action: np.ndarray) -> np.ndarray:
    repaired = action.copy()
    repaired[:, 1] = action[:, 2]
    repaired[:, 2] = -action[:, 1]
    repaired[:, 9] = -action[:, 10]
    repaired[:, 10] = action[:, 9]
    return repaired


def read_array_column(df: pd.DataFrame, name: str) -> np.ndarray:
    return np.asarray(df[name].tolist(), dtype=np.float32)


def scan_episode(path: Path, root_label: str) -> EpisodeMetrics:
    missing = [rel for rel in REQUIRED_FILES if not (path / rel).is_file()]
    empty_videos = [
        rel
        for rel in CAMERA_FILES.values()
        if (path / rel).is_file() and (path / rel).stat().st_size == 0
    ]
    if empty_videos:
        missing.extend([f"{rel}:empty" for rel in empty_videos])
    if missing:
        return EpisodeMetrics(
            source=path.name,
            root_label=root_label,
            raw_path=str(path),
            valid=False,
            missing_files=missing,
            reject_reasons=["incomplete_episode"],
        )

    result = EpisodeMetrics(source=path.name, root_label=root_label, raw_path=str(path), valid=True)
    try:
        df = pd.read_parquet(path / "data/chunk-000/file-000.parquet")
        action = read_array_column(df, "action")
        state = read_array_column(df, "observation.state")
        timestamps = np.asarray(df["timestamp"].to_numpy(), dtype=np.float64)
        frame_index = np.asarray(df["frame_index"].to_numpy(), dtype=np.int64)
    except Exception as exc:  # noqa: BLE001
        result.valid = False
        result.reject_reasons = ["read_error"]
        result.notes = [f"{type(exc).__name__}: {exc}"]
        return result

    if action.ndim != 2 or state.ndim != 2 or action.shape[0] < 3 or state.shape[0] != action.shape[0]:
        result.valid = False
        result.reject_reasons = ["bad_action_state_shape"]
        result.notes = [f"action_shape={action.shape}", f"state_shape={state.shape}"]
        return result
    if action.shape[1] < 16 or state.shape[1] < 16:
        result.valid = False
        result.reject_reasons = ["bad_action_state_width"]
        result.notes = [f"action_shape={action.shape}", f"state_shape={state.shape}"]
        return result

    result.frames = int(action.shape[0])
    result.duration_s = float(timestamps[-1] - timestamps[0]) if timestamps.size > 1 else 0.0
    dt = np.diff(timestamps)
    positive_dt = dt[dt > 0]
    result.estimated_fps = float(1.0 / np.median(positive_dt)) if positive_dt.size else math.nan
    result.non_monotonic_timestamps = int(np.count_nonzero(dt <= 0))
    frame_gaps = np.diff(frame_index)
    if frame_gaps.size:
        result.non_uniform_frame_gaps = int(np.count_nonzero(frame_gaps != frame_gaps[0]))

    grip_left = action[:, 7] > 0.5
    grip_right = action[:, 15] > 0.5
    both_closed = grip_left & grip_right
    left_idx = int(np.argmax(grip_left)) if np.any(grip_left) else -1
    right_idx = int(np.argmax(grip_right)) if np.any(grip_right) else -1
    both_idx = int(np.argmax(both_closed)) if np.any(both_closed) else -1
    result.first_both_close_frame = both_idx
    if left_idx >= 0:
        result.first_left_close_s = float(timestamps[left_idx])
    if right_idx >= 0:
        result.first_right_close_s = float(timestamps[right_idx])
    if both_idx >= 0:
        result.first_both_close_s = float(timestamps[both_idx])
        result.post_grasp_duration_s = float(timestamps[-1] - timestamps[both_idx])
    if left_idx >= 0 and right_idx >= 0:
        result.close_sync_frames = abs(left_idx - right_idx)
    result.grip_switches = int(np.count_nonzero(np.diff(grip_left.astype(np.int8)))) + int(
        np.count_nonzero(np.diff(grip_right.astype(np.int8)))
    )
    result.both_closed_ratio = float(np.mean(both_closed))

    fixed = repaired_actions(action)
    action_diff = np.diff(fixed[:, NON_GRIP_DIMS], axis=0)
    result.mean_delta = float(np.mean(np.abs(action_diff)))
    result.max_jump = float(np.max(np.abs(action_diff)))
    if action.shape[0] > 2:
        result.jerk = float(np.mean(np.abs(np.diff(action_diff, axis=0))))
    if action.shape[0] > 1:
        result.tracking_mae = float(np.mean(np.abs(action[:-1, NON_GRIP_DIMS] - state[1:, NON_GRIP_DIMS])))
        result.repaired_tracking_mae = float(np.mean(np.abs(fixed[:-1, NON_GRIP_DIMS] - state[1:, NON_GRIP_DIMS])))
        result.shoulder_mae = float(np.mean(np.abs(fixed[:-1, SHOULDER_DIMS] - state[1:, SHOULDER_DIMS])))
    if both_idx >= 0 and both_idx < fixed.shape[0] - 1:
        result.after_motion = float(np.sum(np.abs(np.diff(fixed[both_idx:, NON_GRIP_DIMS], axis=0))))
    else:
        result.after_motion = 0.0

    return result


def score_and_tier(rows: list[EpisodeMetrics]) -> dict[str, dict[str, float]]:
    valid_rows = [row for row in rows if row.valid]
    stats = {
        attr: quantiles(valid_rows, attr)
        for attr in (
            "duration_s",
            "first_both_close_s",
            "close_sync_frames",
            "mean_delta",
            "jerk",
            "max_jump",
            "tracking_mae",
            "repaired_tracking_mae",
            "shoulder_mae",
            "after_motion",
            "grip_switches",
        )
    }

    after_q05 = q(stats, "after_motion", "0.05", 0.0)
    after_q20 = q(stats, "after_motion", "0.20", 10.0)
    after_q25 = q(stats, "after_motion", "0.25", 12.0)
    after_q35 = q(stats, "after_motion", "0.35", 15.0)
    after_q90 = q(stats, "after_motion", "0.90", 40.0)
    after_q98 = q(stats, "after_motion", "0.98", 55.0)
    max_jump_q95 = q(stats, "max_jump", "0.95", 0.2)
    max_jump_q98 = q(stats, "max_jump", "0.98", 0.35)
    shoulder_q70 = q(stats, "shoulder_mae", "0.70", 0.003)
    shoulder_q85 = q(stats, "shoulder_mae", "0.85", 0.005)
    shoulder_q95 = q(stats, "shoulder_mae", "0.95", 0.008)
    tracking_q20 = q(stats, "repaired_tracking_mae", "0.20", 0.12)
    tracking_q90 = q(stats, "repaired_tracking_mae", "0.90", 0.30)
    mean_delta_q20 = q(stats, "mean_delta", "0.20", 0.0015)
    mean_delta_q90 = q(stats, "mean_delta", "0.90", 0.004)
    jerk_q20 = q(stats, "jerk", "0.20", 0.0008)
    jerk_q90 = q(stats, "jerk", "0.90", 0.002)

    for row in rows:
        if not row.valid:
            row.tier = "reject"
            row.quality_score = 0.0
            continue

        severe: list[str] = []
        risk: list[str] = []
        if row.non_monotonic_timestamps > 0:
            severe.append("non_monotonic_timestamps")
        if not np.isfinite(row.first_both_close_s):
            severe.append("no_both_gripper_close")
        elif row.first_both_close_s < 3.0:
            severe.append("first_grasp_too_early")
        elif row.first_both_close_s > 14.0:
            severe.append("first_grasp_too_late")
        elif not (5.5 <= row.first_both_close_s <= 10.0):
            risk.append("first_grasp_off_nominal")

        if row.close_sync_frames < 0:
            severe.append("missing_gripper_sync")
        elif row.close_sync_frames > 12:
            severe.append("gripper_async_severe")
        elif row.close_sync_frames > 3:
            risk.append("gripper_async")

        if row.duration_s < 18.0:
            severe.append("duration_too_short")
        elif row.duration_s > 90.0:
            severe.append("duration_too_long")
        elif row.duration_s < 25.0 or row.duration_s > 65.0:
            risk.append("duration_off_nominal")

        if row.grip_switches < 4:
            severe.append("too_few_grip_switches")
        elif row.grip_switches > 32:
            severe.append("too_many_grip_switches")
        elif row.grip_switches < 12 or row.grip_switches > 24:
            risk.append("grip_switch_count_unusual")

        if np.isfinite(row.after_motion):
            if row.after_motion <= max(after_q05, 6.0):
                severe.append("very_low_post_grasp_motion")
            elif row.after_motion < max(after_q20, 10.0):
                risk.append("low_post_grasp_motion")
        else:
            severe.append("missing_post_grasp_motion")

        if np.isfinite(row.max_jump):
            if row.max_jump > max_jump_q98:
                severe.append("large_action_jump")
            elif row.max_jump > max_jump_q95:
                risk.append("action_jump_high")

        if np.isfinite(row.shoulder_mae):
            if row.shoulder_mae > shoulder_q95:
                severe.append("shoulder_tracking_error_high")
            elif row.shoulder_mae > shoulder_q85:
                risk.append("shoulder_tracking_error")

        first_score = triangular_score(row.first_both_close_s, 6.0, 9.0, 3.0, 14.0)
        duration_score = triangular_score(row.duration_s, 30.0, 55.0, 18.0, 90.0)
        sync_score = low_score(float(row.close_sync_frames), 1.0, 8.0)
        smooth_score = 0.55 * low_score(row.mean_delta, mean_delta_q20, mean_delta_q90) + 0.45 * low_score(
            row.jerk, jerk_q20, jerk_q90
        )
        tracking_score = low_score(row.repaired_tracking_mae, tracking_q20, tracking_q90)
        shoulder_score = low_score(row.shoulder_mae, shoulder_q70, shoulder_q95)
        motion_score = high_enough_score(row.after_motion, after_q05, after_q35, after_q90, after_q98)
        grip_score = triangular_score(float(row.grip_switches), 16.0, 22.0, 4.0, 32.0)
        jump_score = low_score(row.max_jump, max_jump_q95 * 0.65, max_jump_q98)

        score = (
            0.22 * first_score
            + 0.12 * sync_score
            + 0.12 * smooth_score
            + 0.10 * tracking_score
            + 0.13 * shoulder_score
            + 0.13 * motion_score
            + 0.08 * duration_score
            + 0.06 * grip_score
            + 0.04 * jump_score
        )
        if severe:
            score *= 0.35
        elif risk:
            score *= max(0.72, 1.0 - 0.07 * len(risk))
        row.quality_score = float(score)
        row.reject_reasons = severe
        row.risk_flags = risk

        if severe:
            row.tier = "reject"
        elif (
            score >= 0.82
            and not risk
            and 5.5 <= row.first_both_close_s <= 9.5
            and row.close_sync_frames <= 2
            and row.after_motion >= after_q25
            and row.shoulder_mae <= shoulder_q70
        ):
            row.tier = "core_high"
        elif score >= 0.72 and len(risk) <= 1 and row.close_sync_frames <= 4:
            row.tier = "good"
        elif score >= 0.55:
            row.tier = "usable_with_risk"
        else:
            row.tier = "borderline"

    return stats


def csv_value(value: Any) -> Any:
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    if isinstance(value, float) and not np.isfinite(value):
        return ""
    return value


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row.get(column, "")) for column in columns})


def sorted_rows(rows: list[EpisodeMetrics]) -> list[EpisodeMetrics]:
    tier_rank = {tier: i for i, tier in enumerate(TIER_ORDER)}
    return sorted(
        rows,
        key=lambda row: (
            tier_rank.get(row.tier, 99),
            -row.quality_score,
            row.root_label,
            row.source,
        ),
    )


def row_to_dict(row: EpisodeMetrics) -> dict[str, Any]:
    data = asdict(row)
    return data


def write_reports(rows: list[EpisodeMetrics], stats: dict[str, dict[str, float]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ranked = sorted_rows([row for row in rows if row.valid])
    ranked_dicts: list[dict[str, Any]] = []
    for rank, row in enumerate(ranked, start=1):
        data = row_to_dict(row)
        data["rank"] = rank
        ranked_dicts.append(data)

    invalid = [row_to_dict(row) for row in rows if not row.valid]
    ranked_columns = [
        "rank",
        "tier",
        "root_label",
        "source",
        "quality_score",
        "duration_s",
        "frames",
        "estimated_fps",
        "first_both_close_s",
        "first_left_close_s",
        "first_right_close_s",
        "first_both_close_frame",
        "close_sync_frames",
        "mean_delta",
        "jerk",
        "max_jump",
        "tracking_mae",
        "repaired_tracking_mae",
        "shoulder_mae",
        "after_motion",
        "post_grasp_duration_s",
        "grip_switches",
        "both_closed_ratio",
        "risk_flags",
        "reject_reasons",
        "raw_path",
    ]
    write_csv(output_dir / "ranked_episodes.csv", ranked_dicts, ranked_columns)
    write_csv(
        output_dir / "invalid_episodes.csv",
        invalid,
        ["root_label", "source", "valid", "missing_files", "reject_reasons", "notes", "raw_path"],
    )

    tier_summary: list[dict[str, Any]] = []
    for tier in TIER_ORDER:
        tier_rows = [row for row in rows if row.tier == tier]
        by_root = Counter(row.root_label for row in tier_rows)
        tier_summary.append(
            {
                "tier": tier,
                "episodes": len(tier_rows),
                "by_root": dict(sorted(by_root.items())),
                "score_min": float(min((row.quality_score for row in tier_rows), default=0.0)),
                "score_max": float(max((row.quality_score for row in tier_rows), default=0.0)),
                "score_mean": float(np.mean([row.quality_score for row in tier_rows])) if tier_rows else 0.0,
            }
        )
    write_csv(
        output_dir / "tier_summary.csv",
        tier_summary,
        ["tier", "episodes", "by_root", "score_min", "score_max", "score_mean"],
    )

    tier_dir = output_dir / "sources_by_tier"
    tier_dir.mkdir(exist_ok=True)
    tier_ordered_all = sorted_rows(rows)
    for tier in TIER_ORDER:
        with (tier_dir / f"{tier}_sources.txt").open("w") as fh:
            for row in tier_ordered_all:
                if row.tier == tier:
                    fh.write(f"{row.raw_path}\n")
        with (tier_dir / f"{tier}_names.txt").open("w") as fh:
            for row in tier_ordered_all:
                if row.tier == tier:
                    fh.write(f"{row.source}\n")

    candidates = build_candidates(ranked)
    with (output_dir / "candidate_mixes.json").open("w") as fh:
        json.dump(candidates, fh, indent=2, ensure_ascii=False)

    failure_modes = Counter()
    for row in rows:
        for reason in row.reject_reasons:
            failure_modes[reason] += 1
        for flag in row.risk_flags:
            failure_modes[flag] += 1

    summary = {
        "raw_roots": sorted({row.root_label for row in rows}),
        "total_episode_folders": len(rows),
        "valid_episodes": sum(row.valid for row in rows),
        "invalid_episodes": sum(not row.valid for row in rows),
        "tiers": tier_summary,
        "failure_modes": dict(failure_modes.most_common()),
        "metric_quantiles": stats,
        "candidates": candidates,
    }
    with (output_dir / "summary.json").open("w") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    write_markdown_summary(output_dir / "summary.md", summary)


def build_candidates(ranked: list[EpisodeMetrics]) -> list[dict[str, Any]]:
    candidates_spec = [
        (
            "core_high_only",
            {"core_high"},
            "Highest-consistency set; best for first-grasp debugging or a conservative continuation run.",
        ),
        (
            "core_high_plus_good",
            {"core_high", "good"},
            "Default clean training candidate; keeps quality high without forcing a fixed TopN cutoff.",
        ),
        (
            "core_good_plus_usable_review",
            {"core_high", "good", "usable_with_risk"},
            "Broader coverage; use after visual review of the usable_with_risk tier.",
        ),
        (
            "borderline_review_pool",
            {"borderline"},
            "Do not train by default; review only if a missing maneuver is visible here.",
        ),
    ]
    candidates: list[dict[str, Any]] = []
    for name, tiers, description in candidates_spec:
        rows = [row for row in ranked if row.tier in tiers]
        by_root = Counter(row.root_label for row in rows)
        by_tier = Counter(row.tier for row in rows)
        candidates.append(
            {
                "name": name,
                "description": description,
                "tiers": sorted(tiers, key=lambda tier: TIER_ORDER.index(tier)),
                "episodes": len(rows),
                "by_root": dict(sorted(by_root.items())),
                "by_tier": dict(sorted(by_tier.items(), key=lambda item: TIER_ORDER.index(item[0]))),
                "sources": [row.raw_path for row in rows],
            }
        )

    for root_label in sorted({row.root_label for row in ranked}):
        rows = [row for row in ranked if row.root_label == root_label and row.tier in {"core_high", "good"}]
        candidates.append(
            {
                "name": f"{root_label}_core_good_focus",
                "description": f"Clean per-day subset for isolating {root_label} collection behavior.",
                "tiers": ["core_high", "good"],
                "episodes": len(rows),
                "by_root": {root_label: len(rows)},
                "by_tier": dict(Counter(row.tier for row in rows)),
                "sources": [row.raw_path for row in rows],
            }
        )
    return candidates


def write_markdown_summary(path: Path, summary: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append("# Mantis Quality Layer Report")
    lines.append("")
    lines.append(f"- Total episode folders: {summary['total_episode_folders']}")
    lines.append(f"- Valid episodes: {summary['valid_episodes']}")
    lines.append(f"- Invalid/partial episodes: {summary['invalid_episodes']}")
    lines.append("")
    lines.append("## Tier Distribution")
    lines.append("")
    lines.append("| tier | episodes | by_root | score_mean | score_range |")
    lines.append("|---|---:|---|---:|---|")
    for item in summary["tiers"]:
        lines.append(
            "| {tier} | {episodes} | {by_root} | {score_mean:.3f} | {score_min:.3f}-{score_max:.3f} |".format(
                **item
            )
        )
    lines.append("")
    lines.append("## Main Flags")
    lines.append("")
    if summary["failure_modes"]:
        for name, count in summary["failure_modes"].items():
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none")
    lines.append("")
    lines.append("## Candidate Mixes")
    lines.append("")
    for candidate in summary["candidates"]:
        lines.append(
            f"- {candidate['name']}: {candidate['episodes']} episodes, "
            f"tiers={candidate['tiers']}, by_root={candidate['by_root']}"
        )
        lines.append(f"  {candidate['description']}")
    lines.append("")
    lines.append("No training dataset was exported by this report. Confirm one candidate/tier policy before export.")
    path.write_text("\n".join(lines) + "\n")


def frame_at(video_path: Path, timestamp_s: float, thumb_width: int) -> Image.Image:
    timestamp_s = max(0.0, float(timestamp_s))
    try:
        with av.open(str(video_path)) as container:
            stream = container.streams.video[0]
            if stream.duration is not None and stream.time_base is not None:
                seek_ts = int(timestamp_s / float(stream.time_base))
                container.seek(seek_ts, stream=stream, any_frame=False, backward=True)
            frame_img: Image.Image | None = None
            for frame in container.decode(stream):
                frame_time = float(frame.time or 0.0)
                frame_img = frame.to_image()
                if frame_time >= timestamp_s:
                    break
            if frame_img is None:
                raise RuntimeError("no frame decoded")
    except Exception:  # noqa: BLE001
        frame_img = Image.new("RGB", (thumb_width, int(thumb_width * 0.75)), (30, 30, 30))
        draw = ImageDraw.Draw(frame_img)
        draw.text((8, 8), "frame error", fill=(240, 240, 240))
        return frame_img

    w, h = frame_img.size
    new_h = max(1, int(round(h * (thumb_width / w))))
    return frame_img.resize((thumb_width, new_h), Image.Resampling.LANCZOS).convert("RGB")


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: tuple[int, int, int]) -> None:
    try:
        font = ImageFont.load_default()
    except Exception:  # noqa: BLE001
        font = None
    draw.text(xy, text, fill=fill, font=font)


def make_contact_sheet(rows: list[EpisodeMetrics], output_path: Path, title: str, max_rows: int) -> None:
    rows = rows[:max_rows]
    if not rows:
        return
    thumb_w = 150
    label_w = 310
    pad = 8
    header_h = 46
    row_h = 128
    columns = [
        ("env start", "env", "start"),
        ("env grasp", "env", "grasp"),
        ("env mid", "env", "mid"),
        ("env final", "env", "final"),
        ("left grasp", "left", "grasp"),
        ("right grasp", "right", "grasp"),
    ]
    width = label_w + len(columns) * (thumb_w + pad) + pad
    height = header_h + len(rows) * row_h + pad
    sheet = Image.new("RGB", (width, height), (246, 246, 244))
    draw = ImageDraw.Draw(sheet)
    draw_text(draw, (pad, 8), title, (20, 20, 20))
    for i, (label, _, _) in enumerate(columns):
        draw_text(draw, (label_w + i * (thumb_w + pad), 28), label, (45, 45, 45))

    for row_idx, row in enumerate(rows):
        y = header_h + row_idx * row_h
        draw.rectangle((0, y, width, y + row_h - 1), fill=(255, 255, 255) if row_idx % 2 == 0 else (238, 240, 239))
        label = (
            f"{row.source}\n{row.root_label} | {row.tier} | score {row.quality_score:.3f}\n"
            f"grasp {row.first_both_close_s:.1f}s sync {row.close_sync_frames} "
            f"motion {row.after_motion:.1f}\n{';'.join(row.risk_flags or row.reject_reasons)[:58]}"
        )
        draw_text(draw, (pad, y + 10), label, (25, 25, 25))
        times = {
            "start": 0.5,
            "grasp": row.first_both_close_s if np.isfinite(row.first_both_close_s) else max(0.5, row.duration_s * 0.25),
            "mid": max(0.5, row.duration_s * 0.55),
            "final": max(0.5, row.duration_s - 0.5),
        }
        for col_idx, (_, camera, time_key) in enumerate(columns):
            video_path = Path(row.raw_path) / CAMERA_FILES[camera]
            frame = frame_at(video_path, times[time_key], thumb_w)
            max_h = row_h - 22
            if frame.height > max_h:
                new_w = max(1, int(round(frame.width * (max_h / frame.height))))
                frame = frame.resize((new_w, max_h), Image.Resampling.LANCZOS)
            x = label_w + col_idx * (thumb_w + pad)
            sheet.paste(frame, (x, y + 10))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path, quality=90)


def write_contact_sheets(rows: list[EpisodeMetrics], output_dir: Path, max_rows: int) -> None:
    ranked = sorted_rows([row for row in rows if row.valid])
    contact_dir = output_dir / "contact_sheets"
    for tier in TIER_ORDER:
        tier_rows = [row for row in ranked if row.tier == tier]
        make_contact_sheet(tier_rows, contact_dir / f"{tier}_threecam.jpg", f"{tier} representative episodes", max_rows)
    overview_rows: list[EpisodeMetrics] = []
    for tier in TIER_ORDER:
        overview_rows.extend([row for row in ranked if row.tier == tier][: max(2, max_rows // 3)])
    make_contact_sheet(overview_rows, contact_dir / "tier_overview_threecam.jpg", "tier overview", max_rows * 2)


def collect_episode_dirs(raw_roots: list[Path]) -> list[tuple[Path, str]]:
    episodes: list[tuple[Path, str]] = []
    for root in raw_roots:
        root = root.expanduser().resolve()
        root_label = root.name
        if not root.is_dir():
            raise FileNotFoundError(root)
        for child in sorted(root.iterdir()):
            if child.is_dir():
                episodes.append((child, root_label))
    return episodes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rank Mantis raw episodes into quality tiers.")
    parser.add_argument("--raw-root", action="append", required=True, help="Raw root containing per-episode folders.")
    parser.add_argument("--output-dir", required=True, help="Directory for ranked CSV, tier summaries, and contact sheets.")
    parser.add_argument("--skip-contact-sheets", action="store_true")
    parser.add_argument("--contact-sheet-rows", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw_roots = [Path(item) for item in args.raw_root]
    output_dir = Path(args.output_dir)
    episode_dirs = collect_episode_dirs(raw_roots)
    rows = [scan_episode(path, root_label) for path, root_label in episode_dirs]
    stats = score_and_tier(rows)
    write_reports(rows, stats, output_dir)
    if not args.skip_contact_sheets:
        write_contact_sheets(rows, output_dir, max_rows=max(1, args.contact_sheet_rows))
    tier_counts = Counter(row.tier for row in rows)
    print(f"episodes={len(rows)} valid={sum(row.valid for row in rows)} invalid={sum(not row.valid for row in rows)}")
    print("tiers=" + ", ".join(f"{tier}:{tier_counts.get(tier, 0)}" for tier in TIER_ORDER))
    print(f"output_dir={output_dir}")


if __name__ == "__main__":
    main()
