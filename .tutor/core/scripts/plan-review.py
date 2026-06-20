#!/usr/bin/env python3
"""Print an interleaved review plan from the generated due queue.

This script is read-only. Run refresh-status.py first so state/due.md reflects
the current day.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path


def find_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / ".tutor").is_dir() and (parent / "state").is_dir():
            return parent
    return Path.cwd()


ROOT = find_root(Path(__file__).resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Plan today's due concept review order.")
    parser.add_argument(
        "--today",
        default=dt.date.today().isoformat(),
        help="Date used for overdue scoring, YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--cards",
        action="store_true",
        help="Include recall prompt, challenge prompt, and pass criteria for each concept.",
    )
    return parser.parse_args()


def split_markdown_row(line: str) -> list[str]:
    if not line.startswith("|"):
        return []
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in line.strip()[1:]:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    return cells


def due_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in (ROOT / "state/due.md").read_text(encoding="utf-8").splitlines():
        cells = split_markdown_row(line)
        if len(cells) < 5:
            continue
        concept_id, topic, due, q, checkpoint = cells[:5]
        if concept_id == "concept_id" or set(concept_id) == {"-"}:
            continue
        if re.fullmatch(r"[a-z0-9-]+", concept_id):
            rows.append(
                {
                    "concept_id": concept_id,
                    "topic": topic,
                    "due": due,
                    "q": q,
                    "checkpoint": checkpoint,
                }
            )
    return rows


def mistake_counts() -> dict[str, int]:
    text = (ROOT / "state/mistakes.md").read_text(encoding="utf-8")
    counts: dict[str, int] = {}
    for match in re.finditer(r"\]\s+([a-z0-9-]+)(?:[：(])", text):
        concept_id = match.group(1)
        counts[concept_id] = counts.get(concept_id, 0) + 1
    return counts


def load_project_config() -> dict:
    path = ROOT / ".tutor/config/project.yml"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def review_cards() -> dict[str, dict[str, str]]:
    config = load_project_config()
    path_text = config.get("paths", {}).get("review_cards", ".tutor/data/review-cards.json")
    path = ROOT / path_text
    data = json.loads(path.read_text(encoding="utf-8"))
    cards = data.get("cards", {})
    if not isinstance(cards, dict):
        return {}
    return {
        concept_id: card
        for concept_id, card in cards.items()
        if isinstance(concept_id, str) and isinstance(card, dict)
    }


def score(row: dict[str, str], today: dt.date, mistakes: dict[str, int]) -> int:
    due = dt.date.fromisoformat(row["due"])
    overdue_days = max((today - due).days, 0)
    try:
        q = int(row["q"])
    except ValueError:
        q = 0
    starred = 1 if row["checkpoint"].startswith("★") else 0
    return overdue_days * 10 + (5 - q) * 4 + mistakes.get(row["concept_id"], 0) * 6 + starred * 3


def interleave(rows: list[dict[str, str]], today: dt.date) -> list[dict[str, str]]:
    mistakes = mistake_counts()
    remaining = sorted(
        rows,
        key=lambda row: (
            -score(row, today, mistakes),
            row["due"],
            row["topic"],
            row["concept_id"],
        ),
    )
    ordered: list[dict[str, str]] = []
    last_topic = ""
    while remaining:
        index = 0
        for candidate_index, row in enumerate(remaining):
            if row["topic"] != last_topic:
                index = candidate_index
                break
        row = remaining.pop(index)
        ordered.append(row)
        last_topic = row["topic"]
    return ordered


def main() -> int:
    args = parse_args()
    today = dt.date.fromisoformat(args.today)
    rows = due_rows()
    due_text = (ROOT / "state/due.md").read_text(encoding="utf-8")
    if today.isoformat() not in due_text:
        print(f"WARNING: state/due.md is not refreshed for {today.isoformat()}. Run refresh-status.py first.")

    ordered = interleave(rows, today)
    print(f"# Review Plan ({today.isoformat()})")
    print()
    if not ordered:
        print("No due concepts.")
        return 0
    mistakes = mistake_counts()
    cards = review_cards() if args.cards else {}
    for number, row in enumerate(ordered, 1):
        due = dt.date.fromisoformat(row["due"])
        overdue_days = max((today - due).days, 0)
        q = row["q"] if row["q"] else "?"
        miss = mistakes.get(row["concept_id"], 0)
        print(
            f"{number}. {row['concept_id']} "
            f"[{row['topic']}; overdue={overdue_days}d; last_q={q}; mistakes={miss}]"
        )
        print(f"   checkpoint: {row['checkpoint']}")
        if args.cards:
            card = cards.get(row["concept_id"], {})
            print(f"   recall: {card.get('recall', '[missing recall prompt]')}")
            print(f"   challenge: {card.get('challenge', '[missing challenge prompt]')}")
            print(f"   pass: {card.get('pass', '[missing pass criteria]')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
