#!/usr/bin/env python3
"""Draft tutor self-evolution reflections without changing teaching rules."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any


def find_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / ".tutor").is_dir() and (parent / "state").is_dir():
            return parent
    return Path.cwd()


ROOT = find_root(Path(__file__).resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draft tutor evolution reflections.")
    parser.add_argument("--today", default=dt.date.today().isoformat(), help="Reflection date, YYYY-MM-DD.")
    parser.add_argument("--window-days", type=int, default=30, help="Evidence window size in days.")
    parser.add_argument("--dry-run", action="store_true", help="Print the reflection without writing files.")
    return parser.parse_args()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def concepts() -> dict[str, dict[str, Any]]:
    data = load_json(ROOT / "state/mastery.json", {})
    raw = data.get("concepts", {}) if isinstance(data, dict) else {}
    return {key: value for key, value in raw.items() if isinstance(value, dict)}


def reviews(window_start: dt.date, today: dt.date) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = ROOT / "state/reviews.jsonl"
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            row_date = dt.date.fromisoformat(str(row.get("ts")))
        except (json.JSONDecodeError, ValueError):
            continue
        if window_start <= row_date <= today:
            rows.append(row)
    return rows


def mistakes() -> dict[str, int]:
    counts: dict[str, int] = {}
    path = ROOT / "state/mistakes.md"
    if not path.exists():
        return counts
    for match in re.finditer(r"\]\s+([a-z0-9-]+)(?:[：(])", path.read_text(encoding="utf-8")):
        concept_id = match.group(1)
        counts[concept_id] = counts.get(concept_id, 0) + 1
    return counts


def observations() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    path = ROOT / ".tutor/evolution/observations.jsonl"
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def due_overdue(today: dt.date, states: dict[str, dict[str, Any]]) -> int:
    count = 0
    for state in states.values():
        due = state.get("due")
        if not due:
            continue
        try:
            if dt.date.fromisoformat(str(due)) < today:
                count += 1
        except ValueError:
            continue
    return count


def draft_reflection(today: dt.date, window_days: int) -> str:
    window_start = today - dt.timedelta(days=max(window_days - 1, 0))
    states = concepts()
    review_rows = reviews(window_start, today)
    q_values = []
    low_q: dict[str, int] = {}
    for row in review_rows:
        try:
            q = int(row.get("q"))
        except (TypeError, ValueError):
            continue
        q_values.append(q)
        concept_id = row.get("concept_id")
        if isinstance(concept_id, str) and q <= 3:
            low_q[concept_id] = low_q.get(concept_id, 0) + 1
    avg_q = sum(q_values) / len(q_values) if q_values else None
    mistake_counts = mistakes()
    recurring = sorted(((cid, count) for cid, count in mistake_counts.items() if count >= 2), key=lambda item: (-item[1], item[0]))
    observation_rows = observations()
    overdue = due_overdue(today, states)

    candidates = []
    if recurring:
        candidates.append("同类误解出现复发迹象；下一轮应把这些概念改成反例优先或边界条件优先的问法。")
    if low_q:
        candidates.append("窗口内存在低 q 概念；应检查题目是否贴边、提示是否过早揭示。")
    if overdue:
        candidates.append("到期复习积压；应在新课前坚持 mastery gate，避免用进度感替代巩固。")
    if not observation_rows:
        candidates.append("observations.jsonl 仍为空；后续会话中，用户纠正和导师失误应先进入 observations，而非直接改规则。")
    if not candidates:
        candidates.append("暂无足够证据晋升规则；保持现有教学协议，只继续收集观察。")

    lines = [
        f"# Tutor Evolution Reflection - {today.isoformat()}",
        "",
        "## Evidence Window",
        f"- window: {window_start.isoformat()}..{today.isoformat()}",
        f"- review_count: {len(review_rows)}",
        f"- average_q: {avg_q:.2f}" if avg_q is not None else "- average_q: n/a",
        f"- overdue_due_count: {overdue}",
        f"- observation_count: {len(observation_rows)}",
        "",
        "## Candidate Observations",
        *[f"- {item}" for item in candidates],
        "",
        "## Evidence Pointers",
        "- state/reviews.jsonl",
        "- state/mistakes.md",
        "- state/mastery.json",
        "- .tutor/evolution/observations.jsonl",
        "",
        "## Promotion Gate",
        "- Do not edit protocol or skills from this reflection alone.",
        "- Promote only after repeated evidence or explicit user confirmation.",
        "- Any promoted rule must include scope, source evidence, and rollback condition.",
    ]
    if recurring:
        lines.extend(["", "## Recurring Misconceptions"])
        lines.extend(f"- {concept_id}: {count}" for concept_id, count in recurring[:8])
    if low_q:
        lines.extend(["", "## Low-Q Concepts"])
        lines.extend(f"- {concept_id}: {count}" for concept_id, count in sorted(low_q.items(), key=lambda item: (-item[1], item[0]))[:8])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    today = dt.date.fromisoformat(args.today)
    text = draft_reflection(today, args.window_days)
    if args.dry_run:
        print(text, end="")
        print("\nDRY RUN: no files changed.")
        return 0
    output_dir = ROOT / ".tutor/evolution/reflections"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{today.isoformat()}-learning-system-reflection.md"
    output.write_text(text, encoding="utf-8")
    print(f"wrote {output.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
