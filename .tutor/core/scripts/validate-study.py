#!/usr/bin/env python3
"""Compatibility entrypoint for tutor validation.

By default this runs both:
- validate-core.py: generic tutor-project invariants.
- validate-instance.py: current study-instance legacy safeguards.
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


def find_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / ".tutor").is_dir() and (parent / "state").is_dir():
            return parent
    return Path.cwd()


ROOT = find_root(Path(__file__).resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate tutor project consistency.")
    parser.add_argument(
        "--today",
        default=dt.date.today().isoformat(),
        help="Date used for due checks, YYYY-MM-DD. Defaults to today.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--core-only",
        action="store_true",
        help="Run only generic tutor-project validation.",
    )
    mode.add_argument(
        "--instance-only",
        action="store_true",
        help="Run only current study-instance validation.",
    )
    parser.add_argument(
        "--example",
        help="Validate another tutor project root with core checks only.",
    )
    return parser.parse_args()


def run_validator(
    script: Path,
    today: str,
    root: str | None = None,
    example: str | None = None,
) -> int:
    command = [sys.executable, str(script), "--today", today]
    if root is not None:
        command.extend(["--root", root])
    if example is not None:
        command.extend(["--example", example])
    result = subprocess.run(command, cwd=ROOT)
    return result.returncode


def main() -> int:
    args = parse_args()
    try:
        dt.date.fromisoformat(args.today)
    except ValueError:
        print(f"invalid --today date: {args.today}", file=sys.stderr)
        return 2

    scripts = Path(__file__).resolve().parent
    if args.example:
        example_path = Path(args.example)
        if example_path.is_dir():
            return run_validator(scripts / "validate-core.py", args.today, root=args.example)
        return run_validator(scripts / "validate-core.py", args.today, example=args.example)
    if args.core_only:
        return run_validator(scripts / "validate-core.py", args.today)
    if args.instance_only:
        return run_validator(scripts / "validate-instance.py", args.today)

    core_status = run_validator(scripts / "validate-core.py", args.today)
    instance_status = run_validator(scripts / "validate-instance.py", args.today)
    if core_status == 0 and instance_status == 0:
        print("VALIDATION OK")
        return 0
    print("VALIDATION FAILED")
    return core_status or instance_status


if __name__ == "__main__":
    raise SystemExit(main())
