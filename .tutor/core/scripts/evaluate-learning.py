#!/usr/bin/env python3
"""Generate a read-only learning effectiveness report."""

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
    parser = argparse.ArgumentParser(description="Evaluate learning effectiveness without changing state.")
    parser.add_argument("--today", default=dt.date.today().isoformat(), help="Report date, YYYY-MM-DD.")
    parser.add_argument("--window-days", type=int, default=30, help="Review window size in days.")
    parser.add_argument("--subject", help="Optional subject id filter.")
    return parser.parse_args()


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def project_config() -> dict[str, Any]:
    path = ROOT / ".tutor/config/project.yml"
    if path.exists():
        data = load_json(path, {})
        return data if isinstance(data, dict) else {}
    return {}


def mastery_concepts() -> dict[str, dict[str, Any]]:
    data = load_json(ROOT / "state/mastery.json", {})
    concepts = data.get("concepts", {}) if isinstance(data, dict) else {}
    return {key: value for key, value in concepts.items() if isinstance(value, dict)}


def review_rows(window_start: dt.date, today: dt.date, subject: str | None, concepts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
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
        concept_id = row.get("concept_id")
        if subject and concepts.get(concept_id, {}).get("subject") != subject:
            continue
        if window_start <= row_date <= today:
            rows.append(row)
    return rows


def mistake_counts(subject: str | None, concepts: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    path = ROOT / "state/mistakes.md"
    if not path.exists():
        return counts
    for match in re.finditer(r"\]\s+([a-z0-9-]+)(?:[：(])", path.read_text(encoding="utf-8")):
        concept_id = match.group(1)
        if subject and concepts.get(concept_id, {}).get("subject") != subject:
            continue
        counts[concept_id] = counts.get(concept_id, 0) + 1
    return counts


def latest_q(rows: list[dict[str, Any]]) -> dict[str, int]:
    latest: dict[str, int] = {}
    for row in rows:
        concept_id = row.get("concept_id")
        try:
            q = int(row.get("q"))
        except (TypeError, ValueError):
            continue
        if isinstance(concept_id, str):
            latest[concept_id] = q
    return latest


def due_count(today: dt.date, subject: str | None, concepts: dict[str, dict[str, Any]]) -> int:
    count = 0
    for state in concepts.values():
        if subject and state.get("subject") != subject:
            continue
        due = state.get("due")
        if not due:
            continue
        try:
            if dt.date.fromisoformat(str(due)) <= today:
                count += 1
        except ValueError:
            continue
    return count


def concept_label(concept_id: str, concepts: dict[str, dict[str, Any]]) -> str:
    topic = concepts.get(concept_id, {}).get("topic")
    return f"{concept_id} ({topic})" if topic else concept_id


def report(today: dt.date, window_days: int, subject: str | None) -> str:
    config = project_config()
    concepts = mastery_concepts()
    if subject is None:
        configured_subject = config.get("status", {}).get("current_subject")
        subject = configured_subject if isinstance(configured_subject, str) else None
    window_start = today - dt.timedelta(days=max(window_days - 1, 0))
    rows = review_rows(window_start, today, subject, concepts)
    q_values = [int(row["q"]) for row in rows if str(row.get("q", "")).isdigit()]
    pass_count = sum(1 for q in q_values if q >= 3)
    avg_q = sum(q_values) / len(q_values) if q_values else None
    pass_rate = pass_count / len(q_values) if q_values else None
    mistakes = mistake_counts(subject, concepts)
    latest = latest_q(rows)
    active_subjects = sorted(
        {
            str(state.get("subject"))
            for state in concepts.values()
            if state.get("subject") and (subject is None or state.get("subject") == subject)
        }
    )
    lapse_count = sum(
        1
        for state in concepts.values()
        if state.get("status") == "lapsed" and (subject is None or state.get("subject") == subject)
    )
    recurring = sorted(((cid, count) for cid, count in mistakes.items() if count >= 2), key=lambda item: (-item[1], item[0]))
    low_q_counts: dict[str, int] = {}
    for row in rows:
        concept_id = row.get("concept_id")
        try:
            q = int(row.get("q"))
        except (TypeError, ValueError):
            continue
        if isinstance(concept_id, str) and q <= 3:
            low_q_counts[concept_id] = low_q_counts.get(concept_id, 0) + 1
    friction_scores = {
        concept_id: low_q_counts.get(concept_id, 0) * 2 + mistakes.get(concept_id, 0)
        for concept_id in set(low_q_counts) | set(mistakes)
    }
    high_friction = sorted(
        ((cid, score) for cid, score in friction_scores.items() if score >= 2),
        key=lambda item: (-item[1], item[0]),
    )
    ready = sorted(
        cid
        for cid, state in concepts.items()
        if (subject is None or state.get("subject") == subject)
        and latest.get(cid, -1) >= 4
        and float(state.get("mastery", 0) or 0) >= 0.75
        and mistakes.get(cid, 0) == 0
    )
    due_now = due_count(today, subject, concepts)
    if high_friction:
        next_intervention = "优先换讲法处理高摩擦概念，再做间隔复习。"
    elif due_now:
        next_intervention = "先清到期复习门禁，再推进新内容。"
    elif ready:
        next_intervention = "安排迁移题或反例题，验证能否进入更高阶任务。"
    else:
        next_intervention = "学习数据不足，下一次会话先补一次诊断或 formative quiz。"

    lines = [
        "Learning Evaluation",
        f"- window: {window_start.isoformat()}..{today.isoformat()}",
        f"- active_subjects: {', '.join(active_subjects) if active_subjects else 'none'}",
        f"- review_count: {len(rows)}",
        f"- due_now: {due_now}",
        f"- due_pass_rate: {pass_rate:.2%}" if pass_rate is not None else "- due_pass_rate: n/a",
        f"- average_q: {avg_q:.2f}" if avg_q is not None else "- average_q: n/a",
        f"- lapse_count: {lapse_count}",
        "- recurring_misconceptions: "
        + (", ".join(f"{concept_label(cid, concepts)} x{count}" for cid, count in recurring[:5]) if recurring else "none"),
        "- concepts_with_high_friction: "
        + (", ".join(f"{concept_label(cid, concepts)} score={score}" for cid, score in high_friction[:5]) if high_friction else "none"),
        "- concepts_ready_for_transfer: "
        + (", ".join(concept_label(cid, concepts) for cid in ready[:8]) if ready else "none"),
        f"- next_intervention: {next_intervention}",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    today = dt.date.fromisoformat(args.today)
    print(report(today, args.window_days, args.subject))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
