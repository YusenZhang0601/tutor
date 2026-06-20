#!/usr/bin/env python3
"""Run an optional instance-specific validator declared in project.yml."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def find_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / ".tutor").is_dir() and (parent / "state").is_dir():
            return parent
    return Path.cwd()


ROOT = find_root(Path(__file__).resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run optional instance-specific tutor validation.")
    parser.add_argument(
        "--today",
        default=dt.date.today().isoformat(),
        help="Date used for due checks, YYYY-MM-DD. Defaults to today.",
    )
    return parser.parse_args()


def load_project_config() -> dict[str, Any]:
    path = ROOT / ".tutor/config/project.yml"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def main() -> int:
    args = parse_args()
    try:
        dt.date.fromisoformat(args.today)
    except ValueError:
        print(f"invalid --today date: {args.today}", file=sys.stderr)
        return 2
    config = load_project_config()
    validator = config.get("paths", {}).get("instance_validator")
    if not isinstance(validator, str) or not validator:
        print("INSTANCE VALIDATION SKIPPED")
        print("- no paths.instance_validator configured")
        return 0
    path = ROOT / validator
    if not path.is_file():
        print("INSTANCE VALIDATION FAILED")
        print(f"- missing configured instance validator: {validator}")
        return 1
    result = subprocess.run(
        [sys.executable, str(path), "--today", args.today],
        cwd=ROOT,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
