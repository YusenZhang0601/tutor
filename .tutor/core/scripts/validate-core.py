#!/usr/bin/env python3
"""Validate generic tutor project invariants without subject-specific rules."""

from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any


def find_root(start: Path) -> Path:
    for parent in [start, *start.parents]:
        if (parent / ".tutor").is_dir() and (parent / "state").is_dir():
            return parent
    return Path.cwd()


ROOT = find_root(Path(__file__).resolve())
STATUS_RE = re.compile(
    r"<!-- TUTOR-STATUS:START -->\n(.*?)\n<!-- TUTOR-STATUS:END -->",
    re.S,
)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate generic tutor project consistency.")
    parser.add_argument(
        "--today",
        default=dt.date.today().isoformat(),
        help="Date used for due checks, YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--root",
        help="Tutor project root. Defaults to auto-detecting the current repository root.",
    )
    parser.add_argument(
        "--example",
        help="Validate a subject example config file instead of a full tutor root.",
    )
    return parser.parse_args()


def fail(errors: list[str], msg: str) -> None:
    errors.append(msg)


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(errors, f"missing file: {rel(path)}")
    except UnicodeDecodeError as exc:
        fail(errors, f"cannot decode utf-8: {rel(path)} ({exc})")
    return ""


def load_project_config(errors: list[str]) -> dict[str, Any]:
    for candidate in [ROOT / ".tutor/config/project.yml", ROOT / ".tutor/project.yml"]:
        if candidate.is_file():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                fail(errors, f"invalid project config json: {rel(candidate)} ({exc})")
                return {}
            if not isinstance(data, dict):
                fail(errors, f"project config must be an object: {rel(candidate)}")
                return {}
            return data
    fail(errors, "missing project config: .tutor/config/project.yml")
    return {}


def parse_example_config(path: Path, errors: list[str]) -> dict[str, Any]:
    text = read_text(path, errors)
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = parse_simple_yaml(text, path, errors)
    if not isinstance(data, dict):
        fail(errors, f"example config must be an object: {rel(path)}")
        return {}
    return data


def parse_simple_yaml(text: str, path: Path, errors: list[str]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("  - "):
            if current_key is None:
                fail(errors, f"example list item outside list at {rel(path)}:{line_number}")
                continue
            values = data.setdefault(current_key, [])
            if not isinstance(values, list):
                fail(errors, f"example mixed scalar/list field at {rel(path)}:{line_number}")
                continue
            values.append(line.strip()[2:].strip().strip('"').strip("'"))
            continue
        if line.startswith(" "):
            fail(errors, f"unsupported example indentation at {rel(path)}:{line_number}")
            continue
        if ":" not in line:
            fail(errors, f"bad example config line at {rel(path)}:{line_number}: {raw}")
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            data[key] = value.strip('"').strip("'")
            current_key = None
        else:
            data[key] = []
            current_key = key
    return data


def validate_example_subject(errors: list[str], path: Path) -> None:
    data = parse_example_config(path, errors)
    required = {
        "id",
        "title",
        "domain_type",
        "goal_depth",
        "output_mode",
        "practice_types",
        "mastery_evidence",
    }
    missing = sorted(required - set(data))
    if missing:
        fail(errors, f"example subject missing fields {missing}: {rel(path)}")
    for key in ["id", "title", "domain_type", "goal_depth", "mastery_evidence"]:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(errors, f"example subject {key} must be a non-empty string: {rel(path)}")
    if isinstance(data.get("id"), str) and not re.fullmatch(r"[a-z0-9-]+", data["id"]):
        fail(errors, f"example subject id must be kebab-case: {data['id']}")
    for key in ["output_mode", "practice_types"]:
        value = data.get(key)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
            fail(errors, f"example subject {key} must be a non-empty list of strings: {rel(path)}")


def configured_path(config: dict[str, Any], key: str, default: str) -> Path:
    value = config.get("paths", {}).get(key, default)
    return ROOT / value if isinstance(value, str) else ROOT / default


def entry_files(config: dict[str, Any]) -> list[str]:
    configured = config.get("project", {}).get("entry_files", ["AGENTS.md", "CLAUDE.md"])
    return [item for item in configured if isinstance(item, str)] or ["AGENTS.md", "CLAUDE.md"]


def scripts_dir(config: dict[str, Any]) -> Path:
    return configured_path(config, "scripts", ".tutor/core/scripts")


def subjects_dir(config: dict[str, Any]) -> Path:
    return configured_path(config, "subjects", "subjects")


def parse_scalar(value: str) -> Any:
    stripped = value.strip()
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    try:
        if "." in stripped:
            return float(stripped)
        return int(stripped)
    except ValueError:
        return stripped


def parse_settings(errors: list[str], config: dict[str, Any]) -> dict[str, Any]:
    path = configured_path(config, "settings", ".tutor/core/settings.yml")
    settings: dict[str, Any] = {}
    section: str | None = None
    for line_number, raw in enumerate(read_text(path, errors).splitlines(), 1):
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" "):
            if ":" not in line:
                fail(errors, f"bad settings line {line_number}: {raw}")
                continue
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value:
                settings[key] = parse_scalar(value)
                section = None
            else:
                settings[key] = {}
                section = key
            continue
        if section is None:
            fail(errors, f"settings value outside section at line {line_number}: {raw}")
            continue
        if ":" not in line:
            fail(errors, f"bad settings line {line_number}: {raw}")
            continue
        key, value = line.strip().split(":", 1)
        section_value = settings.setdefault(section, {})
        if isinstance(section_value, dict):
            section_value[key.strip()] = parse_scalar(value.strip())
    return settings


def parse_frontmatter(path: Path, errors: list[str]) -> dict[str, str] | None:
    text = read_text(path, errors)
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        fail(errors, f"missing frontmatter: {rel(path)}")
        return None
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in line:
            fail(errors, f"bad frontmatter line in {rel(path)}: {line}")
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    return data


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


def same_value(frontmatter_value: str | None, state_value: Any, key: str) -> bool:
    if frontmatter_value is None:
        return state_value is None
    if key == "mastery":
        try:
            return abs(float(frontmatter_value) - float(state_value)) < 1e-9
        except (TypeError, ValueError):
            return False
    if key == "reps":
        try:
            return int(frontmatter_value) == int(state_value)
        except (TypeError, ValueError):
            return False
    return str(frontmatter_value) == str(state_value)


def concept_note_paths(config: dict[str, Any]) -> list[Path]:
    base = subjects_dir(config)
    paths = []
    for path in base.glob("*/topics/*/*.md"):
        if path.name != "INDEX.md":
            paths.append(path)
    return sorted(paths)


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


def require_float(errors: list[str], section: dict[str, Any], section_name: str, key: str) -> float | None:
    try:
        return float(section[key])
    except KeyError:
        return None
    except (TypeError, ValueError):
        fail(errors, f"settings {section_name}.{key} must be numeric")
        return None


def require_int(errors: list[str], section: dict[str, Any], section_name: str, key: str) -> int | None:
    try:
        return int(section[key])
    except KeyError:
        return None
    except (TypeError, ValueError):
        fail(errors, f"settings {section_name}.{key} must be an integer")
        return None


def validate_project_config(errors: list[str], config: dict[str, Any]) -> None:
    project = config.get("project")
    if not isinstance(project, dict):
        fail(errors, "project config missing object field: project")
    elif not isinstance(project.get("name"), str) or not project.get("name"):
        fail(errors, "project config project.name must be a non-empty string")
    paths = config.get("paths")
    if not isinstance(paths, dict):
        fail(errors, "project config missing object field: paths")
    elif "review_cards" not in paths:
        fail(errors, "project config paths.review_cards is required")
    if not entry_files(config):
        fail(errors, "project config project.entry_files must contain at least one file")


def validate_required_files(errors: list[str], config: dict[str, Any]) -> None:
    required = [
        *entry_files(config),
        "INDEX.md",
        ".gitignore",
        ".tutor/config/project.yml",
        str(configured_path(config, "protocol", ".tutor/core/protocol.md").relative_to(ROOT)),
        str(configured_path(config, "settings", ".tutor/core/settings.yml").relative_to(ROOT)),
        str(configured_path(config, "learner_profile", ".tutor/config/learner-profile.md").relative_to(ROOT)),
        str(configured_path(config, "review_cards", ".tutor/data/review-cards.json").relative_to(ROOT)),
        str(configured_path(config, "lints", ".tutor/config/lints.yml").relative_to(ROOT)),
        "state/mastery.json",
        "state/due.md",
        "state/mistakes.md",
        "state/reviews.jsonl",
        "subjects/INDEX.md",
    ]
    script_names = [
        "validate-study.py",
        "validate-core.py",
        "validate-instance.py",
        "refresh-status.py",
        "plan-review.py",
        "concept-graph.py",
        "evaluate-learning.py",
        "evolve-tutor.py",
    ]
    for script_name in script_names:
        required.append(str((scripts_dir(config) / script_name).relative_to(ROOT)))
    for item in required:
        if not (ROOT / item).is_file():
            fail(errors, f"missing required file: {item}")


def validate_python_scripts(errors: list[str]) -> None:
    for path in sorted((ROOT / ".tutor").rglob("*.py")):
        text = read_text(path, errors)
        if not text:
            continue
        try:
            ast.parse(text, filename=rel(path))
        except SyntaxError as exc:
            fail(errors, f"python syntax error in {rel(path)}: {exc}")


def validate_skill_docs(errors: list[str]) -> None:
    config_errors: list[str] = []
    config = load_project_config(config_errors)
    errors.extend(config_errors)
    skills_dir = configured_path(config, "skills", ".tutor/core/skills")
    if not skills_dir.is_dir():
        fail(errors, f"missing skills directory: {rel(skills_dir)}")
        return
    for path in sorted(skills_dir.glob("*/SKILL.md")):
        text = read_text(path, errors)
        match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not match:
            fail(errors, f"missing skill frontmatter: {rel(path)}")
            continue
        frontmatter = match.group(1)
        skill_name = path.parent.name
        if f"name: {skill_name}" not in frontmatter:
            fail(errors, f"skill name mismatch in {rel(path)}")
        for field in ["description:", "allowed-tools:"]:
            if field not in frontmatter:
                fail(errors, f"skill missing {field.rstrip(':')}: {rel(path)}")


def validate_settings(errors: list[str], settings: dict[str, Any]) -> None:
    if settings.get("scheduler") != "sm2":
        fail(errors, f"unsupported scheduler: {settings.get('scheduler')}")
    required = {
        "mastery": ["min_successful_reps", "min_interval_days", "promote_quality"],
        "sm2": ["initial_ef", "min_ef", "first_interval", "second_interval"],
        "review": ["target_retention", "max_new_per_session", "interleave"],
        "lapse": ["reset_interval", "ef_penalty"],
    }
    for section, keys in required.items():
        value = settings.get(section)
        if not isinstance(value, dict):
            fail(errors, f"settings missing section: {section}")
            continue
        for key in keys:
            if key not in value:
                fail(errors, f"settings missing key: {section}.{key}")
    sm2 = settings.get("sm2", {}) if isinstance(settings.get("sm2"), dict) else {}
    mastery = settings.get("mastery", {}) if isinstance(settings.get("mastery"), dict) else {}
    review = settings.get("review", {}) if isinstance(settings.get("review"), dict) else {}
    lapse = settings.get("lapse", {}) if isinstance(settings.get("lapse"), dict) else {}
    min_ef = require_float(errors, sm2, "sm2", "min_ef")
    initial_ef = require_float(errors, sm2, "sm2", "initial_ef")
    if min_ef is not None and min_ef <= 0:
        fail(errors, "settings sm2.min_ef must be positive")
    if initial_ef is not None and min_ef is not None and initial_ef < min_ef:
        fail(errors, "settings sm2.initial_ef must be >= sm2.min_ef")
    for key in ["first_interval", "second_interval"]:
        interval = require_int(errors, sm2, "sm2", key)
        if interval is not None and interval <= 0:
            fail(errors, f"settings sm2.{key} must be positive")
    promote_quality = require_int(errors, mastery, "mastery", "promote_quality")
    if promote_quality is not None and not 0 <= promote_quality <= 5:
        fail(errors, "settings mastery.promote_quality must be in 0..5")
    for key in ["min_successful_reps", "min_interval_days"]:
        value = require_int(errors, mastery, "mastery", key)
        if value is not None and value <= 0:
            fail(errors, f"settings mastery.{key} must be positive")
    retention = require_float(errors, review, "review", "target_retention")
    if retention is not None and not 0 < retention < 1:
        fail(errors, "settings review.target_retention must be between 0 and 1")
    max_new = require_int(errors, review, "review", "max_new_per_session")
    if max_new is not None and max_new <= 0:
        fail(errors, "settings review.max_new_per_session must be positive")
    if "interleave" in review and not isinstance(review["interleave"], bool):
        fail(errors, "settings review.interleave must be true or false")
    reset_interval = require_int(errors, lapse, "lapse", "reset_interval")
    if reset_interval is not None and reset_interval <= 0:
        fail(errors, "settings lapse.reset_interval must be positive")
    ef_penalty = require_float(errors, lapse, "lapse", "ef_penalty")
    if ef_penalty is not None and ef_penalty < 0:
        fail(errors, "settings lapse.ef_penalty must be non-negative")


def validate_status_blocks(errors: list[str], config: dict[str, Any], today: dt.date) -> int | None:
    statuses: dict[str, str] = {}
    due_today: int | None = None
    for name in entry_files(config):
        text = read_text(ROOT / name, errors)
        match = STATUS_RE.search(text)
        if not match:
            fail(errors, f"missing TUTOR-STATUS block: {name}")
            continue
        status = match.group(1)
        statuses[name] = status
        due_match = re.search(r"^due_today:\s*(\d+)\b", status, re.M)
        if not due_match:
            fail(errors, f"missing numeric due_today in status: {name}")
        else:
            value = int(due_match.group(1))
            if due_today is None:
                due_today = value
            elif due_today != value:
                fail(errors, "entry files have different due_today values")
        if today.isoformat() not in status:
            fail(errors, f"TUTOR-STATUS is not refreshed for {today.isoformat()}: {name}")
    if len(set(statuses.values())) > 1:
        fail(errors, "TUTOR-STATUS blocks differ across entry files")
    return due_today


def validate_mastery_and_frontmatter(
    errors: list[str],
    config: dict[str, Any],
) -> tuple[dict[str, tuple[Path, dict[str, str]]], dict[str, Any]]:
    mastery_path = ROOT / "state/mastery.json"
    try:
        mastery_data = json.loads(read_text(mastery_path, errors))
    except json.JSONDecodeError as exc:
        fail(errors, f"invalid json: state/mastery.json ({exc})")
        return {}, {}
    concepts = mastery_data.get("concepts")
    if not isinstance(concepts, dict):
        fail(errors, "state/mastery.json missing object field: concepts")
        return {}, {}
    frontmatter_by_id: dict[str, tuple[Path, dict[str, str]]] = {}
    required_fm = {
        "id",
        "subject",
        "topic",
        "prerequisites",
        "status",
        "mastery",
        "ef",
        "interval",
        "reps",
        "last_review",
        "due",
    }
    allowed_status = {"new", "learning", "mastered", "lapsed"}
    for path in concept_note_paths(config):
        data = parse_frontmatter(path, errors)
        if data is None:
            continue
        missing = sorted(required_fm - set(data))
        if missing:
            fail(errors, f"frontmatter missing {missing}: {rel(path)}")
        concept_id = data.get("id")
        if not concept_id:
            continue
        if concept_id in frontmatter_by_id:
            fail(errors, f"duplicate concept id {concept_id}: {rel(path)}")
        frontmatter_by_id[concept_id] = (path, data)
        if data.get("status") not in allowed_status:
            fail(errors, f"bad status for {concept_id}: {data.get('status')}")
        for numeric_key in ["mastery", "ef", "interval", "reps"]:
            try:
                float(data[numeric_key])
            except (KeyError, ValueError):
                fail(errors, f"bad numeric frontmatter {numeric_key}: {rel(path)}")
        for date_key in ["last_review", "due"]:
            value = data.get(date_key)
            if value and value != "null":
                try:
                    dt.date.fromisoformat(value)
                except ValueError:
                    fail(errors, f"bad date frontmatter {date_key}: {rel(path)}")
    for concept_id in sorted(set(frontmatter_by_id) - set(concepts)):
        fail(errors, f"concept note missing from mastery.json: {concept_id}")
    for concept_id in sorted(set(concepts) - set(frontmatter_by_id)):
        fail(errors, f"mastery.json concept missing note: {concept_id}")
    compare_map = {
        "status": "status",
        "mastery": "mastery",
        "reps": "reps",
        "last_review": "last_seen",
        "due": "due",
    }
    for concept_id in sorted(set(frontmatter_by_id) & set(concepts)):
        path, frontmatter = frontmatter_by_id[concept_id]
        state = concepts[concept_id]
        if not isinstance(state, dict):
            fail(errors, f"mastery concept is not object: {concept_id}")
            continue
        for fm_key, state_key in compare_map.items():
            if not same_value(frontmatter.get(fm_key), state.get(state_key), fm_key):
                fail(
                    errors,
                    "frontmatter/mastery mismatch "
                    f"{concept_id} {fm_key}: {rel(path)}={frontmatter.get(fm_key)} "
                    f"state.{state_key}={state.get(state_key)}",
                )
    for concept_id, (_path, frontmatter) in sorted(frontmatter_by_id.items()):
        prerequisites = parse_inline_list(frontmatter.get("prerequisites"))
        if frontmatter.get("prerequisites") not in {None, "[]"} and not prerequisites:
            fail(errors, f"cannot parse prerequisites for {concept_id}")
        for prereq in prerequisites:
            if prereq == concept_id:
                fail(errors, f"concept depends on itself: {concept_id}")
            if prereq not in frontmatter_by_id:
                fail(errors, f"unknown prerequisite for {concept_id}: {prereq}")
    summary = mastery_data.get("summary")
    if not isinstance(summary, dict):
        fail(errors, "state/mastery.json missing object field: summary")
    else:
        total = len(concepts)
        mastered = sum(1 for state in concepts.values() if isinstance(state, dict) and state.get("status") == "mastered")
        if summary.get("total") != total:
            fail(errors, f"summary.total mismatch: {summary.get('total')} != {total}")
        if summary.get("mastered") != mastered:
            fail(errors, f"summary.mastered mismatch: {summary.get('mastered')} != {mastered}")
    return frontmatter_by_id, concepts


def validate_reviews(errors: list[str], concepts: dict[str, Any]) -> tuple[dict[str, int], dict[str, set[str]]]:
    latest_q: dict[str, int] = {}
    successful_dates: dict[str, set[str]] = {}
    for line_number, line in enumerate(read_text(ROOT / "state/reviews.jsonl", errors).splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(errors, f"invalid jsonl at state/reviews.jsonl:{line_number} ({exc})")
            continue
        concept_id = row.get("concept_id")
        if concept_id not in concepts:
            fail(errors, f"review references unknown concept at line {line_number}: {concept_id}")
        parsed_q: int | None = None
        if "q" not in row:
            fail(errors, f"review missing q at line {line_number}")
        else:
            try:
                parsed_q = int(row["q"])
                if not 0 <= parsed_q <= 5:
                    raise ValueError
                if isinstance(concept_id, str):
                    latest_q[concept_id] = parsed_q
            except (TypeError, ValueError):
                fail(errors, f"review q out of range at line {line_number}: {row.get('q')}")
        try:
            parsed_ts = dt.date.fromisoformat(str(row.get("ts"))).isoformat()
        except ValueError:
            fail(errors, f"review ts is not YYYY-MM-DD at line {line_number}: {row.get('ts')}")
            parsed_ts = None
        if isinstance(concept_id, str) and parsed_q is not None and parsed_q >= 3 and parsed_ts:
            successful_dates.setdefault(concept_id, set()).add(parsed_ts)
    return latest_q, successful_dates


def validate_schedule_fields(
    errors: list[str],
    frontmatter_by_id: dict[str, tuple[Path, dict[str, str]]],
    settings: dict[str, Any],
    latest_q: dict[str, int],
) -> None:
    sm2 = settings.get("sm2", {}) if isinstance(settings.get("sm2"), dict) else {}
    mastery_settings = settings.get("mastery", {}) if isinstance(settings.get("mastery"), dict) else {}
    min_ef = float(sm2.get("min_ef", 1.3))
    min_reps = int(mastery_settings.get("min_successful_reps", 3))
    min_interval = int(mastery_settings.get("min_interval_days", 21))
    promote_quality = int(mastery_settings.get("promote_quality", 4))
    for concept_id, (_path, frontmatter) in sorted(frontmatter_by_id.items()):
        try:
            mastery = float(frontmatter["mastery"])
            ef = float(frontmatter["ef"])
            interval = int(frontmatter["interval"])
            reps = int(frontmatter["reps"])
        except (KeyError, ValueError):
            continue
        if not 0 <= mastery <= 1:
            fail(errors, f"mastery out of range for {concept_id}: {frontmatter.get('mastery')}")
        if ef < min_ef:
            fail(errors, f"ef below min_ef for {concept_id}: {ef} < {min_ef}")
        if interval < 0:
            fail(errors, f"negative interval for {concept_id}: {interval}")
        if reps < 0:
            fail(errors, f"negative reps for {concept_id}: {reps}")
        last_review = frontmatter.get("last_review")
        due = frontmatter.get("due")
        if last_review and last_review != "null" and due and due != "null":
            expected_due = (dt.date.fromisoformat(last_review) + dt.timedelta(days=interval)).isoformat()
            if due != expected_due:
                fail(errors, f"due arithmetic mismatch for {concept_id}: {due} != {expected_due}")
        if frontmatter.get("status") == "new" and (reps != 0 or last_review != "null" or due != "null"):
            fail(errors, f"new concept has review state: {concept_id}")
        if frontmatter.get("status") == "lapsed" and reps != 0:
            fail(errors, f"lapsed concept should have reps=0: {concept_id}")
        if frontmatter.get("status") == "mastered":
            if reps < min_reps or interval < min_interval:
                fail(errors, f"mastered concept fails gate: {concept_id}")
            if concept_id in latest_q and latest_q[concept_id] < promote_quality:
                fail(errors, f"mastered concept latest q below gate: {concept_id}")


def validate_reps_against_review_dates(
    errors: list[str],
    frontmatter_by_id: dict[str, tuple[Path, dict[str, str]]],
    successful_dates: dict[str, set[str]],
) -> None:
    for concept_id, (_path, frontmatter) in sorted(frontmatter_by_id.items()):
        try:
            reps = int(frontmatter["reps"])
        except (KeyError, ValueError):
            continue
        unique_success_days = successful_dates.get(concept_id, set())
        if reps > len(unique_success_days):
            fail(errors, f"reps exceeds unique successful review dates for {concept_id}: {reps} > {len(unique_success_days)}")
        last_review = frontmatter.get("last_review")
        if reps > 0 and last_review not in unique_success_days:
            fail(errors, f"last_review is not a logged successful review date for {concept_id}: {last_review}")


def validate_mistakes(errors: list[str], concepts: dict[str, Any]) -> None:
    for line_number, line in enumerate(read_text(ROOT / "state/mistakes.md", errors).splitlines(), 1):
        match = re.match(r"^-\s+\[(\d{4}-\d{2}-\d{2})\]\s+([a-z0-9-]+)(?:\([^)]*\))?[：:]", line)
        if not match:
            continue
        date_text, concept_id = match.groups()
        try:
            dt.date.fromisoformat(date_text)
        except ValueError:
            fail(errors, f"mistake date is not YYYY-MM-DD at line {line_number}: {date_text}")
        if concept_id not in concepts:
            fail(errors, f"mistake references unknown concept at line {line_number}: {concept_id}")


def validate_review_cards(errors: list[str], config: dict[str, Any], concepts: dict[str, Any]) -> None:
    path = configured_path(config, "review_cards", ".tutor/data/review-cards.json")
    try:
        data = json.loads(read_text(path, errors))
    except json.JSONDecodeError as exc:
        fail(errors, f"invalid json: {rel(path)} ({exc})")
        return
    cards = data.get("cards")
    if not isinstance(cards, dict):
        fail(errors, f"{rel(path)} missing object field: cards")
        return
    concept_ids = set(concepts)
    card_ids = set(cards)
    for concept_id in sorted(concept_ids - card_ids):
        fail(errors, f"review card missing for concept: {concept_id}")
    for concept_id in sorted(card_ids - concept_ids):
        fail(errors, f"review card references unknown concept: {concept_id}")
    required_fields = {"recall", "challenge", "pass"}
    for concept_id, card in sorted(cards.items()):
        if not isinstance(card, dict):
            fail(errors, f"review card is not object: {concept_id}")
            continue
        missing = sorted(required_fields - set(card))
        if missing:
            fail(errors, f"review card missing {missing}: {concept_id}")
        for field in required_fields & set(card):
            value = card[field]
            if not isinstance(value, str) or len(value.strip()) < 8:
                fail(errors, f"review card {field} too short: {concept_id}")


def validate_due_counts(
    errors: list[str],
    frontmatter_by_id: dict[str, tuple[Path, dict[str, str]]],
    today: dt.date,
    status_due_count: int | None,
    latest_q: dict[str, int],
) -> None:
    due_ids = []
    for concept_id, (_path, frontmatter) in frontmatter_by_id.items():
        due = frontmatter.get("due")
        if not due or due == "null":
            continue
        try:
            if dt.date.fromisoformat(due) <= today:
                due_ids.append(concept_id)
        except ValueError:
            continue
    due_count = len(due_ids)
    if status_due_count is not None and status_due_count != due_count:
        fail(errors, f"STATUS due_today mismatch for {today}: {status_due_count} != {due_count}")
    due_text = read_text(ROOT / "state/due.md", errors)
    if today.isoformat() not in due_text:
        fail(errors, f"state/due.md is not refreshed for {today.isoformat()}")
    due_match = re.search(r"共\s*(\d+)\s*个概念已到期", due_text)
    if due_match and int(due_match.group(1)) != due_count:
        fail(errors, f"state/due.md due count mismatch: {due_match.group(1)} != {due_count}")
    elif not due_match:
        fail(errors, "state/due.md missing '共 N 个概念已到期' summary")
    due_rows: dict[str, dict[str, str]] = {}
    for line in due_text.splitlines():
        cells = split_markdown_row(line)
        if len(cells) >= 5:
            concept_id, _topic, due, q, _checkpoint = cells[:5]
            if concept_id in {"concept_id", "-----------"}:
                continue
            if re.fullmatch(r"[a-z0-9-]+", concept_id):
                due_rows[concept_id] = {"due": due, "q": q}
    if due_count > 0 and due_rows:
        for concept_id in sorted(set(due_ids) - set(due_rows)):
            fail(errors, f"due concept missing from state/due.md table: {concept_id}")
        for concept_id in sorted(set(due_rows) - set(due_ids)):
            fail(errors, f"state/due.md table includes non-due concept: {concept_id}")
        for concept_id in sorted(set(due_ids) & set(due_rows)):
            expected_due = frontmatter_by_id[concept_id][1].get("due")
            if due_rows[concept_id]["due"] != expected_due:
                fail(errors, f"state/due.md due mismatch for {concept_id}: {due_rows[concept_id]['due']} != {expected_due}")
            if concept_id in latest_q:
                try:
                    actual_q = int(due_rows[concept_id]["q"])
                except ValueError:
                    fail(errors, f"state/due.md q is not numeric for {concept_id}: {due_rows[concept_id]['q']}")
                    continue
                if actual_q != latest_q[concept_id]:
                    fail(errors, f"state/due.md q mismatch for {concept_id}: {actual_q} != {latest_q[concept_id]}")


def validate_indexes(errors: list[str], config: dict[str, Any], frontmatter_by_id: dict[str, tuple[Path, dict[str, str]]]) -> None:
    base = subjects_dir(config)
    for directory in sorted(path for path in base.rglob("*") if path.is_dir()):
        if not (directory / "INDEX.md").is_file():
            fail(errors, f"subject directory missing INDEX.md: {rel(directory)}")
    concepts_by_topic: dict[Path, dict[str, dict[str, str]]] = {}
    paths_by_topic: dict[Path, dict[str, Path]] = {}
    for concept_id, (path, frontmatter) in frontmatter_by_id.items():
        topic_dir = path.parent
        concepts_by_topic.setdefault(topic_dir, {})[concept_id] = frontmatter
        paths_by_topic.setdefault(topic_dir, {})[concept_id] = path
    for topic_dir, topic_concepts in sorted(concepts_by_topic.items()):
        index_path = topic_dir / "INDEX.md"
        text = read_text(index_path, errors)
        rows: dict[str, dict[str, str]] = {}
        for line in text.splitlines():
            cells = split_markdown_row(line)
            if len(cells) < 4:
                continue
            concept_id, _summary, status_text, link = cells[:4]
            if concept_id in {"id", "----"}:
                continue
            if concept_id in topic_concepts or re.fullmatch(r"[a-z0-9-]+", concept_id):
                rows[concept_id] = {"status": status_text, "link": link}
        for concept_id in sorted(set(topic_concepts) - set(rows)):
            fail(errors, f"topic INDEX missing concept row: {rel(index_path)} -> {concept_id}")
        for concept_id in sorted(set(rows) - set(topic_concepts)):
            fail(errors, f"topic INDEX has extra concept row: {rel(index_path)} -> {concept_id}")
        for concept_id in sorted(set(topic_concepts) & set(rows)):
            frontmatter = topic_concepts[concept_id]
            expected_status = f"{frontmatter['status']} ({float(frontmatter['mastery']):.2f})"
            if rows[concept_id]["status"] != expected_status:
                fail(errors, f"topic INDEX status mismatch for {concept_id}: {rows[concept_id]['status']} != {expected_status}")
            note_name = paths_by_topic[topic_dir][concept_id].name
            expected_link = f"[{note_name}]({note_name})"
            if rows[concept_id]["link"] != expected_link:
                fail(errors, f"topic INDEX link mismatch for {concept_id}: {rows[concept_id]['link']} != {expected_link}")


def validate_markdown_links(errors: list[str], config: dict[str, Any]) -> None:
    concept_ids = set()
    for path in concept_note_paths(config):
        data = parse_frontmatter(path, errors)
        if data and data.get("id"):
            concept_ids.add(data["id"])
    for path in sorted(ROOT.rglob("*.md")):
        if ".git" in path.parts or ".omc" in path.parts:
            continue
        text = read_text(path, errors)
        for _label, target in MD_LINK_RE.findall(text):
            if "://" in target or target.startswith("#") or target.startswith("mailto:"):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            if not (path.parent / target_path).resolve().exists():
                fail(errors, f"broken markdown link: {rel(path)} -> {target}")
        if "subjects" in path.parts:
            for target in WIKI_LINK_RE.findall(text):
                concept_id = target.split("|", 1)[0].split("#", 1)[0].strip()
                if concept_id and concept_id not in concept_ids:
                    fail(errors, f"broken concept wiki link: {rel(path)} -> [[{target}]]")


def unquote_lint_value(value: str, item: str, line_number: int, errors: list[str]) -> str:
    stripped = value.strip()
    if not stripped:
        fail(errors, f"empty lints.yml value at line {line_number}: {item}")
        return ""
    if stripped[0] in {"'", '"'}:
        quote = stripped[0]
        if len(stripped) < 2 or stripped[-1] != quote:
            fail(errors, f"unterminated quoted lints.yml value at line {line_number}: {item}")
            return stripped[1:]
        return stripped[1:-1]
    return stripped


def load_lint_config(errors: list[str], config: dict[str, Any]) -> tuple[list[Path], list[dict[str, str]]]:
    path = configured_path(config, "lints", ".tutor/config/lints.yml")
    roots: list[Path] = []
    rules: list[dict[str, str]] = []
    section: str | None = None
    current_rule: dict[str, str] | None = None
    for line_number, raw in enumerate(read_text(path, errors).splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not raw.startswith(" "):
            if stripped == "roots:":
                section = "roots"
                current_rule = None
                continue
            if stripped == "rules:":
                section = "rules"
                current_rule = None
                continue
            fail(errors, f"unknown top-level lints.yml line {line_number}: {raw}")
            continue
        if section == "roots":
            if not stripped.startswith("- "):
                fail(errors, f"bad lints.yml root line {line_number}: {raw}")
                continue
            root_name = unquote_lint_value(stripped[2:], "root", line_number, errors)
            if root_name:
                roots.append(ROOT / root_name)
            continue
        if section == "rules":
            if stripped.startswith("- "):
                body = stripped[2:]
                if ":" not in body:
                    fail(errors, f"bad lints.yml rule line {line_number}: {raw}")
                    current_rule = None
                    continue
                key, value = body.split(":", 1)
                current_rule = {key.strip(): unquote_lint_value(value, key.strip(), line_number, errors)}
                rules.append(current_rule)
                continue
            if current_rule is None:
                fail(errors, f"lints.yml rule field without rule at line {line_number}: {raw}")
                continue
            if ":" not in stripped:
                fail(errors, f"bad lints.yml rule field line {line_number}: {raw}")
                continue
            key, value = stripped.split(":", 1)
            current_rule[key.strip()] = unquote_lint_value(value, key.strip(), line_number, errors)
            continue
        fail(errors, f"lints.yml value outside section at line {line_number}: {raw}")
    return roots, rules


def validate_content_lints(errors: list[str], config: dict[str, Any]) -> None:
    roots, rules = load_lint_config(errors, config)
    if not roots:
        fail(errors, "lints.yml must define at least one root")
    if not rules:
        fail(errors, "lints.yml must define at least one rule")
    compiled: list[tuple[re.Pattern[str], str, str]] = []
    seen_ids: set[str] = set()
    for root in roots:
        try:
            relative = root.resolve().relative_to(ROOT.resolve())
        except ValueError:
            fail(errors, f"lints.yml root escapes workspace: {root}")
            continue
        if str(relative) in {"", "."}:
            fail(errors, "lints.yml root must not scan the whole workspace")
        if not root.exists():
            fail(errors, f"lints.yml root does not exist: {rel(root)}")
    for index, rule in enumerate(rules, 1):
        missing = sorted({"id", "pattern", "message"} - set(rule))
        if missing:
            fail(errors, f"lints.yml rule {index} missing fields: {missing}")
            continue
        rule_id = rule["id"]
        if not re.fullmatch(r"[a-z0-9-]+", rule_id):
            fail(errors, f"lints.yml rule id must be kebab-case: {rule_id}")
        if rule_id in seen_ids:
            fail(errors, f"duplicate lints.yml rule id: {rule_id}")
        seen_ids.add(rule_id)
        try:
            pattern = re.compile(rule["pattern"])
        except re.error as exc:
            fail(errors, f"bad lints.yml regex for {rule_id}: {exc}")
            continue
        if len(rule["message"].strip()) < 20:
            fail(errors, f"lints.yml rule message too short: {rule_id}")
        compiled.append((pattern, rule_id, rule["message"]))
    for path in sorted(path for root in roots for path in root.rglob("*.md")):
        text = read_text(path, errors)
        for pattern, rule_id, message in compiled:
            if pattern.search(text):
                fail(errors, f"content lint {rule_id} failed in {rel(path)}: {message}")


def validate_housekeeping(errors: list[str]) -> None:
    for path in sorted(ROOT.rglob(".DS_Store")):
        fail(errors, f"remove Finder metadata: {rel(path)}")
    for path in sorted(ROOT.rglob("__pycache__")):
        fail(errors, f"remove Python cache directory: {rel(path)}")
    for path in sorted(ROOT.rglob("*.pyc")):
        fail(errors, f"remove Python bytecode cache: {rel(path)}")
    gitignore = read_text(ROOT / ".gitignore", errors)
    if ".DS_Store" not in gitignore:
        fail(errors, ".gitignore does not ignore .DS_Store")
    if ".omc/" not in gitignore:
        fail(errors, ".gitignore does not ignore .omc/")
    if "__pycache__/" not in gitignore or "*.pyc" not in gitignore:
        fail(errors, ".gitignore does not ignore Python caches")


def main() -> int:
    global ROOT
    args = parse_args()
    if args.root:
        ROOT = Path(args.root).resolve()
    if args.example:
        errors: list[str] = []
        example_path = (ROOT / args.example).resolve()
        validate_example_subject(errors, example_path)
        if errors:
            print("CORE EXAMPLE VALIDATION FAILED")
            for error in errors:
                print(f"- {error}")
            return 1
        print("CORE EXAMPLE VALIDATION OK")
        print(f"- example: {rel(example_path)}")
        return 0
    try:
        today = dt.date.fromisoformat(args.today)
    except ValueError:
        print(f"invalid --today date: {args.today}", file=sys.stderr)
        return 2
    errors: list[str] = []
    config = load_project_config(errors)
    validate_project_config(errors, config)
    validate_required_files(errors, config)
    validate_python_scripts(errors)
    validate_skill_docs(errors)
    settings = parse_settings(errors, config)
    validate_settings(errors, settings)
    status_due_count = validate_status_blocks(errors, config, today)
    frontmatter_by_id, concepts = validate_mastery_and_frontmatter(errors, config)
    latest_q, successful_dates = validate_reviews(errors, concepts)
    validate_reps_against_review_dates(errors, frontmatter_by_id, successful_dates)
    validate_mistakes(errors, concepts)
    validate_review_cards(errors, config, concepts)
    validate_schedule_fields(errors, frontmatter_by_id, settings, latest_q)
    validate_due_counts(errors, frontmatter_by_id, today, status_due_count, latest_q)
    validate_indexes(errors, config, frontmatter_by_id)
    validate_markdown_links(errors, config)
    validate_content_lints(errors, config)
    validate_housekeeping(errors)
    if errors:
        print("CORE VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("CORE VALIDATION OK")
    print(f"- date: {today.isoformat()}")
    print(f"- concepts: {len(frontmatter_by_id)}")
    print(f"- due: {status_due_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
