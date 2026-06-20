#!/usr/bin/env python3
"""Generate a concept prerequisite graph from note frontmatter."""

from __future__ import annotations

import argparse
import json
import re
from collections import deque
from pathlib import Path


def find_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / ".tutor").is_dir() and (parent / "state").is_dir():
            return parent
    return Path.cwd()


ROOT = find_root(Path(__file__).resolve())


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


def subject_config(config: dict, subject_id: str | None) -> dict:
    subjects = config.get("subjects", {})
    if isinstance(subjects, dict) and isinstance(subject_id, str):
        subject = subjects.get(subject_id, {})
        if isinstance(subject, dict):
            return subject
    return {}


def subject_path(config: dict, subject_id: str | None) -> Path | None:
    path_text = subject_config(config, subject_id).get("path")
    if isinstance(path_text, str):
        return ROOT / path_text
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate concept dependency graph.")
    parser.add_argument(
        "--subject",
        help="Subject id to render. Defaults to status.current_subject in project.yml.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write graph to the subject concept-graph.md instead of printing.",
    )
    return parser.parse_args()


def parse_inline_list(value: str | None) -> list[str]:
    if value is None:
        return []
    stripped = value.strip()
    if not stripped.startswith("[") or not stripped.endswith("]"):
        return []
    body = stripped[1:-1].strip()
    if not body:
        return []
    return [item.strip().strip('"').strip("'") for item in body.split(",") if item.strip()]


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        raise ValueError(f"missing frontmatter: {path.relative_to(ROOT)}")
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    data["_path"] = str(path.relative_to(ROOT))
    return data


def concept_notes(base_path: Path | None = None) -> dict[str, dict[str, str]]:
    notes: dict[str, dict[str, str]] = {}
    search_root = base_path if base_path is not None else ROOT / "subjects"
    for path in sorted(search_root.glob("topics/*/*.md")):
        if path.name == "INDEX.md":
            continue
        data = parse_frontmatter(path)
        concept_id = data.get("id")
        if not concept_id:
            continue
        notes[concept_id] = data
    return notes


def topic_label(config: dict, subject_id: str | None, topic: str) -> str:
    labels = subject_config(config, subject_id).get("graph_topic_labels", {})
    if not labels:
        labels = subject_config(config, subject_id).get("topic_labels", {})
    return labels.get(topic, topic) if isinstance(labels, dict) else topic


def node_name(index: int) -> str:
    return f"C{index:02d}"


def mermaid(config: dict, subject_id: str | None, notes: dict[str, dict[str, str]]) -> str:
    ids = sorted(notes)
    node_by_id = {concept_id: node_name(index) for index, concept_id in enumerate(ids)}
    lines = ["```mermaid", "graph TD"]
    for concept_id in ids:
        note = notes[concept_id]
        label = (
            f"{concept_id}<br/>{topic_label(config, subject_id, note.get('topic', ''))}"
            f"<br/>{note.get('status', '?')} {float(note.get('mastery', 0)):.2f}"
        )
        lines.append(f'  {node_by_id[concept_id]}["{label}"]')
    for concept_id in ids:
        for prereq in parse_inline_list(notes[concept_id].get("prerequisites")):
            if prereq in node_by_id:
                lines.append(f"  {node_by_id[prereq]} --> {node_by_id[concept_id]}")
    for gate_index, gate in enumerate(subject_config(config, subject_id).get("next_gates", [])):
        title = gate.get("title", f"next gate {gate_index + 1}")
        node = f"NEXT{gate_index}" if gate_index else "NEXT"
        lines.append(f'  {node}["{title}<br/>next learning gate"]')
        for prereq in gate.get("prerequisites", []):
            if prereq in node_by_id:
                lines.append(f"  {node_by_id[prereq]} --> {node}")
    lines.append("```")
    return "\n".join(lines)


def topological_layers(notes: dict[str, dict[str, str]]) -> list[list[str]]:
    ids = set(notes)
    incoming = {
        concept_id: {
            prereq for prereq in parse_inline_list(notes[concept_id].get("prerequisites")) if prereq in ids
        }
        for concept_id in ids
    }
    outgoing: dict[str, set[str]] = {concept_id: set() for concept_id in ids}
    for concept_id, prereqs in incoming.items():
        for prereq in prereqs:
            outgoing[prereq].add(concept_id)

    ready = deque(sorted(concept_id for concept_id, prereqs in incoming.items() if not prereqs))
    layers: list[list[str]] = []
    seen: set[str] = set()
    while ready:
        layer = list(ready)
        ready.clear()
        layers.append(layer)
        for concept_id in layer:
            seen.add(concept_id)
            for child in sorted(outgoing[concept_id]):
                incoming[child].discard(concept_id)
                if not incoming[child] and child not in seen and child not in ready:
                    ready.append(child)
    remaining = sorted(ids - seen)
    if remaining:
        layers.append(remaining)
    return layers


def due_summary(notes: dict[str, dict[str, str]]) -> str:
    due = sorted(
        (note for note in notes.values() if note.get("due") and note.get("due") != "null"),
        key=lambda note: (note.get("due", ""), note.get("topic", ""), note.get("id", "")),
    )
    by_status: dict[str, int] = {}
    for note in notes.values():
        status = note.get("status", "unknown")
        by_status[status] = by_status.get(status, 0) + 1
    status_text = "，".join(f"{key}: {value}" for key, value in sorted(by_status.items()))
    return f"当前共有 {len(notes)} 个概念；状态分布：{status_text}。其中 {len(due)} 个有复习日期，见 `state/due.md`。"


def render(config: dict, subject_id: str | None) -> str:
    subject = subject_config(config, subject_id)
    notes = concept_notes(subject_path(config, subject_id))
    title = subject.get("graph_title", "概念依赖图")
    gate_descriptions = [
        gate.get("description")
        for gate in subject.get("next_gates", [])
        if isinstance(gate, dict) and gate.get("description")
    ]
    lines = [
        f"# {title}",
        "",
        "> 生成产物，勿手工编辑。来源：概念笔记 frontmatter 的 `prerequisites`。",
        "> 重新生成：`python3 .tutor/core/scripts/concept-graph.py --write`。",
        "",
        "## 当前门禁",
        due_summary(notes),
        "",
        *gate_descriptions,
        "",
        "## Mermaid",
        mermaid(config, subject_id, notes),
        "",
        "## 拓扑层级",
    ]
    for index, layer in enumerate(topological_layers(notes)):
        lines.append(f"- L{index}: " + " · ".join(layer))
    lines.append("")
    lines.append("## 直接前置表")
    for concept_id in sorted(notes):
        prereqs = parse_inline_list(notes[concept_id].get("prerequisites"))
        prereq_text = ", ".join(prereqs) if prereqs else "无"
        lines.append(f"- `{concept_id}` ← {prereq_text}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    config = load_project_config()
    subject_id = args.subject or current_subject_id(config)
    output = render(config, subject_id)
    if args.write:
        output_path = subject_path(config, subject_id)
        if output_path is None:
            raise ValueError("cannot determine subject path for concept graph output")
        (output_path / "concept-graph.md").write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
