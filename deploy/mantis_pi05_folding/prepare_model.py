#!/usr/bin/env python3
"""Create a PI05 serving directory with torch.compile disabled."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

CONFIG_FILES = ("config.json", "train_config.json")
REQUIRED_FILES = (
    "model.safetensors",
    "policy_preprocessor.json",
    "policy_postprocessor.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Source pretrained_model directory")
    parser.add_argument("destination", type=Path, help="Destination serving directory")
    return parser.parse_args()


def update_config(source: Path, destination: Path) -> None:
    data = json.loads(source.read_text())
    data["compile_model"] = False
    data["compile_mode"] = "default"
    destination.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    source = args.source.expanduser().resolve()
    destination = args.destination.expanduser().resolve()

    if source == destination:
        raise SystemExit("Source and destination must be different directories")
    if not source.is_dir():
        raise SystemExit(f"Source model directory does not exist: {source}")

    missing = [name for name in (*CONFIG_FILES, *REQUIRED_FILES) if not (source / name).is_file()]
    if missing:
        raise SystemExit(f"Source model is incomplete; missing: {', '.join(missing)}")

    destination.mkdir(parents=True, exist_ok=True)
    for name in CONFIG_FILES:
        update_config(source / name, destination / name)

    for item in source.iterdir():
        if not item.is_file() or item.name in CONFIG_FILES:
            continue
        link = destination / item.name
        if link.is_symlink() or link.exists():
            if link.is_dir() and not link.is_symlink():
                raise SystemExit(f"Refusing to replace directory: {link}")
            link.unlink()
        relative_target = os.path.relpath(item, start=destination)
        link.symlink_to(relative_target)

    print(f"Prepared no-compile model: {destination}")
    print(f"Source model remains at: {source}")


if __name__ == "__main__":
    main()
