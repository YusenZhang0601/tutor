# Tutor Template

A generic mastery-learning tutor project template. This contains no personal study content and is ready for anyone to use.

## Quick Start

1. **Clone or copy** this folder to start your own learning project
2. Open it with Claude Code or any AI agent
3. Read `AGENTS.md` or `CLAUDE.md` for full instructions
4. Run `/onboard` to fill your learner profile
5. Run `/plan <subject>` to create your first subject

## What's Inside

- **`.tutor/`** — Core tutor system (protocol, scripts, skills)
- **`subjects/`** — Your learning content goes here (empty by default)
- **`state/`** — Mastery tracking and review schedule
- **`examples/`** — Sample subjects to copy from (optional)

## Validate Setup

```bash
# Check core integrity (should pass on clean template)
python3 .tutor/core/scripts/validate-study.py --today 2026-06-20 --core-only

# Refresh status files
python3 .tutor/core/scripts/refresh-status.py --today 2026-06-20

# Plan review cards
python3 .tutor/core/scripts/plan-review.py --today 2026-06-20 --cards

# Evaluate learning (after you have concepts)
python3 .tutor/core/scripts/evaluate-learning.py --today 2026-06-20
```

## Features

- **Bloom 2-Sigma Method**: Mastery learning + one-on-one tutoring
- **Spaced Repetition**: SM-2 algorithm with configurable parameters
- **Active Recall**: Blank recall, Feynman technique, counterexamples
- **Progress Tracking**: Automatic mastery state and review scheduling
- **Content Linting**: Prevent common misconceptions in notes
- **Evolution Layer**: Experiment tracking for tutor improvements

## Documentation

- **Protocol**: `.tutor/core/protocol.md` — Core learning method
- **Session Checklist**: `.tutor/docs/session-close-checklist.md`
- **Skills**: `.tutor/core/skills/*/SKILL.md` — Available commands

## License

This template is provided as-is for educational use. Customize freely.
