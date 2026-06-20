#!/usr/bin/env python3
"""Refresh generated study status files.

This updates only generated handoff surfaces:
- state/due.md
- the TUTOR-STATUS blocks in AGENTS.md and CLAUDE.md
- the current subject concept graph declared in .tutor/config/project.yml

It does not change concept mastery, SM-2 fields, reviews, or knowledge notes.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path


def find_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / ".tutor").is_dir() and (parent / "state").is_dir():
            return parent
    return Path.cwd()


ROOT = find_root(Path(__file__).resolve())
SCRIPT_DIR = Path(__file__).resolve().parent
STATUS_RE = re.compile(
    r"(<!-- TUTOR-STATUS:START -->\n)(.*?)(\n<!-- TUTOR-STATUS:END -->)",
    re.S,
)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh due.md and TUTOR-STATUS blocks.")
    parser.add_argument(
        "--today",
        default=dt.date.today().isoformat(),
        help="Date used for due generation, YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip running validate-study.py after writing files.",
    )
    return parser.parse_args()


def load_project_config() -> dict:
    path = ROOT / ".tutor/config/project.yml"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def current_subject_id(config: dict) -> str | None:
    status = config.get("status", {})
    subject_id = status.get("current_subject")
    if isinstance(subject_id, str) and subject_id:
        return subject_id
    subjects = config.get("subjects", {})
    if isinstance(subjects, dict) and len(subjects) == 1:
        return next(iter(subjects))
    return None


def current_subject_config(config: dict) -> dict:
    subject_id = current_subject_id(config)
    subjects = config.get("subjects", {})
    if isinstance(subjects, dict) and isinstance(subject_id, str):
        subject = subjects.get(subject_id, {})
        if isinstance(subject, dict):
            return subject
    return {}


def configured_entry_files(config: dict) -> list[str]:
    entry_files = config.get("project", {}).get("entry_files", ["AGENTS.md", "CLAUDE.md"])
    return [item for item in entry_files if isinstance(item, str)]


def review_groups(config: dict) -> list[dict]:
    groups = config.get("review", {}).get("groups", [])
    return [group for group in groups if isinstance(group, dict)]


def review_cards(config: dict) -> dict[str, dict[str, str]]:
    path_text = config.get("paths", {}).get("review_cards", ".tutor/data/review-cards.json")
    path = ROOT / path_text
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    cards = data.get("cards", {})
    if not isinstance(cards, dict):
        return {}
    return {concept_id: card for concept_id, card in cards.items() if isinstance(card, dict)}


def topic_labels(config: dict) -> dict[str, str]:
    labels = current_subject_config(config).get("topic_labels", {})
    return labels if isinstance(labels, dict) else {}


def topic_gate_suffixes(config: dict) -> dict[str, str]:
    suffixes = current_subject_config(config).get("topic_gate_suffixes", {})
    return suffixes if isinstance(suffixes, dict) else {}


def checkpoint_for(cards: dict[str, dict[str, str]], concept_id: str) -> str:
    value = cards.get(concept_id, {}).get("checkpoint", "")
    return value if isinstance(value, str) else ""


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        raise ValueError(f"missing frontmatter: {path.relative_to(ROOT)}")
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line and not line.strip().startswith("#"):
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip()
    return data


def concept_notes() -> list[dict[str, str]]:
    notes = []
    for path in sorted((ROOT / "subjects").glob("*/topics/*/*.md")):
        if path.name == "INDEX.md":
            continue
        data = parse_frontmatter(path)
        data["_path"] = str(path.relative_to(ROOT))
        notes.append(data)
    return notes


def latest_q_by_concept() -> dict[str, int]:
    latest: dict[str, int] = {}
    path = ROOT / "state/reviews.jsonl"
    if not path.exists():
        return latest
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        latest[row["concept_id"]] = int(row["q"])
    return latest


def mistake_counts() -> dict[str, int]:
    path = ROOT / "state/mistakes.md"
    if not path.exists():
        return {}
    counts: dict[str, int] = {}
    for match in re.finditer(r"\]\s+([a-z0-9-]+)(?:[：(])", path.read_text(encoding="utf-8")):
        concept_id = match.group(1)
        counts[concept_id] = counts.get(concept_id, 0) + 1
    return counts


def mastery_summary() -> dict[str, int]:
    data = json.loads((ROOT / "state/mastery.json").read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    return {
        "total": int(summary.get("total", 0)),
        "mastered": int(summary.get("mastered", 0)),
        "learning": int(summary.get("learning", 0)),
        "lapsed": int(summary.get("lapsed", 0)),
    }


def last_session_date(notes: list[dict[str, str]]) -> str:
    dates = sorted(
        note["last_review"]
        for note in notes
        if note.get("last_review") and note.get("last_review") != "null"
    )
    return dates[-1] if dates else "unknown"


def due_notes(today: dt.date) -> list[dict[str, str]]:
    notes = []
    for note in concept_notes():
        due = note.get("due")
        if due and due != "null" and dt.date.fromisoformat(due) <= today:
            notes.append(note)
    return sorted(notes, key=lambda note: (note["due"], note["topic"], note["id"]))


def due_days_phrase(start: str, today: dt.date) -> str:
    days = (today - dt.date.fromisoformat(start)).days
    if days == 0:
        return "今日到期"
    if days < 0:
        return f"{abs(days)} 天后到期"
    return f"逾期 {days} 天"


def group_due_start(notes: list[dict[str, str]], fallback: str) -> str:
    dates = sorted(note["due"] for note in notes if note.get("due") and note.get("due") != "null")
    return dates[0] if dates else fallback


def group_status_phrase(count: int, start: str, today: dt.date) -> str:
    if count == 0:
        return "0项到期"
    return f"{count}项自{start}{due_days_phrase(start, today)}"


def topic_gate_line(
    config: dict,
    topic: str,
    total_count: int,
    due_for_topic: list[dict[str, str]],
) -> str:
    suffix = topic_gate_suffixes(config).get(topic, "")
    due_count = len(due_for_topic)
    if due_count == 0:
        return f"当前无到期概念。{suffix}".strip()
    first_due = group_due_start(due_for_topic, "unknown")
    if due_count == total_count:
        return f"{due_count} 个概念均已到期（{first_due} 起）。{suffix}".strip()
    return f"{due_count}/{total_count} 个概念已到期（最早 {first_due}）。{suffix}".strip()


def table_for(
    config: dict,
    cards: dict[str, dict[str, str]],
    notes: list[dict[str, str]],
    latest_q: dict[str, int],
) -> str:
    lines = [
        "| concept_id | 主题 | due | 上次q | 核验点 |",
        "|-----------|------|-----|-----|--------|",
    ]
    for note in notes:
        concept_id = note["id"]
        topic = topic_labels(config).get(note["topic"], note["topic"])
        q = latest_q.get(concept_id, "")
        check = checkpoint_for(cards, concept_id)
        lines.append(f"| {concept_id} | {topic} | {note['due']} | {q} | {check} |")
    return "\n".join(lines)


def priority_score(
    cards: dict[str, dict[str, str]],
    note: dict[str, str],
    today: dt.date,
    latest_q: dict[str, int],
    mistakes: dict[str, int],
) -> int:
    due = dt.date.fromisoformat(note["due"])
    overdue_days = max((today - due).days, 0)
    q = latest_q.get(note["id"], 0)
    starred = 1 if checkpoint_for(cards, note["id"]).startswith("★") else 0
    return overdue_days * 10 + (5 - q) * 4 + mistakes.get(note["id"], 0) * 6 + starred * 3


def interleaved_priority(
    cards: dict[str, dict[str, str]],
    notes: list[dict[str, str]],
    today: dt.date,
    latest_q: dict[str, int],
    mistakes: dict[str, int],
) -> list[dict[str, str]]:
    remaining = sorted(
        notes,
        key=lambda note: (
            -priority_score(cards, note, today, latest_q, mistakes),
            note["due"],
            note["topic"],
            note["id"],
        ),
    )
    ordered: list[dict[str, str]] = []
    last_topic = ""
    while remaining:
        index = 0
        for candidate_index, note in enumerate(remaining):
            if note["topic"] != last_topic:
                index = candidate_index
                break
        note = remaining.pop(index)
        ordered.append(note)
        last_topic = note["topic"]
    return ordered


def priority_reason(
    cards: dict[str, dict[str, str]],
    note: dict[str, str],
    today: dt.date,
    latest_q: dict[str, int],
    mistakes: dict[str, int],
) -> str:
    overdue_days = max((today - dt.date.fromisoformat(note["due"])).days, 0)
    q = latest_q.get(note["id"], "?")
    mistake_count = mistakes.get(note["id"], 0)
    starred = "；★重点" if checkpoint_for(cards, note["id"]).startswith("★") else ""
    return f"逾期{overdue_days}天；上次q={q}；弱项{mistake_count}次{starred}"


def priority_table(
    config: dict,
    cards: dict[str, dict[str, str]],
    today: dt.date,
    due: list[dict[str, str]],
    latest_q: dict[str, int],
) -> str:
    mistakes = mistake_counts()
    ordered = interleaved_priority(cards, due, today, latest_q, mistakes)
    if not ordered:
        return "今日无到期概念。"

    lines = [
        "| # | concept_id | 主题 | 排序信号 |",
        "|---|------------|------|----------|",
    ]
    for number, note in enumerate(ordered, 1):
        topic = topic_labels(config).get(note["topic"], note["topic"])
        lines.append(
            f"| {number} | {note['id']} | {topic} | {priority_reason(cards, note, today, latest_q, mistakes)} |"
        )
    return "\n".join(lines)


def render_due_md(
    config: dict,
    cards: dict[str, dict[str, str]],
    today: dt.date,
    due: list[dict[str, str]],
    latest_q: dict[str, int],
) -> str:
    groups: dict[str, list[dict[str, str]]] = {}
    configured_groups = review_groups(config)
    for group in configured_groups:
        group_name = group.get("name", "")
        ids = set(group.get("concept_ids", []))
        groups[group_name] = [note for note in due if note["id"] in ids]

    review_config = config.get("review", {})
    due_next = review_config.get(
        "due_summary_next",
        "下次学习先做空白回忆与交错测验，再决定是否进入下一项学习任务。",
    )
    signal_label = review_config.get(
        "priority_signal_label",
        "逾期天数、上次 q、弱项次数、★ 核验点",
    )
    group_sections = []
    for group in configured_groups:
        group_name = group.get("name", "")
        group_notes = groups.get(group_name, [])
        fallback_due = group.get("fallback_due", today.isoformat())
        group_due = group_due_start(group_notes, fallback_due)
        description = str(group.get("description", "")).format(count=len(group_notes))
        group_sections.append(
            "\n".join(
                [
                    f"## {group_name} {len(group_notes)} 概念（{group_due} 起到期，{due_days_phrase(group_due, today)}）",
                    description,
                    "",
                    table_for(config, cards, group_notes, latest_q),
                ]
            )
        )
    footer = "\n".join(f"> {note}" for note in review_config.get("footer_notes", []))
    if footer:
        footer = "\n\n" + footer
    group_body = "\n\n".join(group_sections)

    return f"""# 今日复习队列（due.md）

> 每次会话开头重新生成：扫描所有概念笔记 frontmatter，列出 `due` ≤ 今天的概念。生成产物，勿手工编辑。
> 上次生成：{today.isoformat()}（维护刷新；按概念笔记 frontmatter 重算）

截至 {today.isoformat()}，共 {len(due)} 个概念已到期；{due_next}

## 建议交错顺序
> 生成提示，不替代导师判断。排序信号：{signal_label}；输出时尽量避免连续同主题。

{priority_table(config, cards, today, due, latest_q)}

{group_body}{footer}
"""


def status_note(summary: dict[str, int]) -> str:
    if summary["total"] == 0:
        return "暂无概念"
    parts = []
    if summary["learning"]:
        parts.append(f"{summary['learning']} learning")
    if summary["lapsed"]:
        parts.append(f"{summary['lapsed']} lapsed")
    if summary["mastered"] == summary["total"]:
        return "均 mastered"
    if summary["learning"] == summary["total"]:
        return "均 learning，待间隔复习巩固"
    return "，".join(parts) if parts else "状态待核验"


def render_status(
    config: dict,
    today: dt.date,
    due: list[dict[str, str]],
    summary: dict[str, int],
    last_session: str,
) -> str:
    groups = review_groups(config)
    due_detail_parts = []
    group_count_parts = []
    for group in groups:
        ids = set(group.get("concept_ids", []))
        count = sum(1 for note in due if note["id"] in ids)
        fallback_due = group.get("fallback_due", today.isoformat())
        start = group_due_start([note for note in due if note["id"] in ids], fallback_due)
        due_detail_parts.append(group_status_phrase(count, start, today))
        group_count_parts.append(f"{count}{group.get('status_label', group.get('name', ''))}")
    due_detail = "；".join(due_detail_parts) if due_detail_parts else "无到期概念"
    group_counts = "+".join(group_count_parts) if group_count_parts else "0概念"
    status_config = config.get("status", {})
    current_subject = status_config.get("current_subject", current_subject_id(config) or "none")
    current_topic = status_config.get(
        "current_topic",
        "当前处于{due_count}项到期复习门禁",
    ).format(due_count=len(due), group_counts=group_counts)
    next_text = status_config.get(
        "next",
        "先做空白回忆+交错复习({group_counts})；通过后继续学习",
    ).format(due_count=len(due), group_counts=group_counts)
    note = status_config.get("note", "")
    return "\n".join(
        [
            f"current_subject: {current_subject}",
            f"current_topic: {current_topic}",
            f"last_session: {last_session}",
            f"due_today: {len(due)} (截至{today.isoformat()}：{due_detail})",
            f"mastered: {summary['mastered']}/{summary['total']} ({status_note(summary)})",
            f"next: {next_text}",
            f"note: {note}",
        ]
    )


def replace_status(path: Path, status: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = STATUS_RE.subn(rf"\1{status}\3", text)
    if count != 1:
        raise ValueError(f"expected exactly one TUTOR-STATUS block in {path.name}, found {count}")
    path.write_text(updated, encoding="utf-8")


def refresh_root_index(due: list[dict[str, str]]) -> None:
    path = ROOT / "INDEX.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r"学习中；\d+ 个概念待间隔复习",
        f"学习中；{len(due)} 个概念待间隔复习",
        text,
    )
    text = re.sub(
        r"先做 \d+ 项到期复习",
        f"先做 {len(due)} 项到期复习",
        text,
    )
    path.write_text(text, encoding="utf-8")


def refresh_topic_indexes(config: dict, notes: list[dict[str, str]], due: list[dict[str, str]]) -> None:
    notes_by_topic: dict[str, list[dict[str, str]]] = {}
    due_by_topic: dict[str, list[dict[str, str]]] = {}
    for note in notes:
        notes_by_topic.setdefault(note["topic"], []).append(note)
    for note in due:
        due_by_topic.setdefault(note["topic"], []).append(note)

    for topic, topic_notes in sorted(notes_by_topic.items()):
        if topic not in topic_gate_suffixes(config):
            continue
        topic_dir = Path(topic_notes[0]["_path"]).parent
        path = ROOT / topic_dir / "INDEX.md"
        text = path.read_text(encoding="utf-8")
        gate = topic_gate_line(config, topic, len(topic_notes), due_by_topic.get(topic, []))
        updated, count = re.subn(r"(## 复习门禁\n)([^\n]*)", rf"\g<1>{gate}", text)
        if count != 1:
            raise ValueError(f"expected one review gate block in {path.relative_to(ROOT)}, found {count}")
        path.write_text(updated, encoding="utf-8")


def main() -> int:
    args = parse_args()
    today = dt.date.fromisoformat(args.today)
    config = load_project_config()
    cards = review_cards(config)
    notes = concept_notes()
    due = due_notes(today)
    latest_q = latest_q_by_concept()
    summary = mastery_summary()

    (ROOT / "state/due.md").write_text(render_due_md(config, cards, today, due, latest_q), encoding="utf-8")
    status = render_status(config, today, due, summary, last_session_date(notes))
    for entry_file in configured_entry_files(config):
        replace_status(ROOT / entry_file, status)
    refresh_root_index(due)
    refresh_topic_indexes(config, notes, due)
    if current_subject_config(config).get("path"):
        graph_result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "concept-graph.py"), "--write"],
            cwd=ROOT,
            check=False,
        )
        if graph_result.returncode != 0:
            return graph_result.returncode

    print(f"refreshed state/due.md and TUTOR-STATUS for {today.isoformat()} ({len(due)} due)")
    if not args.no_validate:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "validate-study.py"), "--today", today.isoformat()],
            cwd=ROOT,
            check=False,
        )
        return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
