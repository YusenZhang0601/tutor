# Tutor

A file-based AI tutor template for mastery learning, active recall, and spaced repetition.

`tutor` is designed for people who want an AI agent to behave less like a generic chatbot and more like a disciplined learning coach. It gives the agent a stable project structure, a session protocol, review state, validation scripts, and explicit rules for recall-before-reveal tutoring.

This repository is a clean template. It contains no personal study history, no private notes, and no real learner progress.

## What It Does

- Guides AI-assisted study sessions with a mastery-learning protocol.
- Uses active recall, Feynman-style explanation, prerequisite gates, and spaced review.
- Tracks concept state in plain files under `state/` and `subjects/`.
- Keeps review scheduling deterministic with SM-2-style settings.
- Provides validation scripts so the learning space stays coherent over time.
- Works as a template for Claude Code, Codex, or another agent that can read project instructions.

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/YusenZhang0601/tutor.git
   cd tutor
   ```

2. **Initialize your AI Agent:**
   Open this folder in your AI workspace (such as Claude Code, Cursor, Copilot, etc.). 
   To activate the tutor system, **send this initial message to your agent**:
   > Please read AGENTS.md (or CLAUDE.md if using Claude Code) to initialize the Tutor learning mode.

3. **Start your first session:**
   Type the following commands to your agent to begin:
   ```text
   /onboard
   /plan <subject>
   /learn
   ```

## Validate The Template

Use the current date for `<YYYY-MM-DD>`. 

```bash
# On macOS/Linux:
python3 .tutor/core/scripts/refresh-status.py --today <YYYY-MM-DD>
python3 .tutor/core/scripts/validate-study.py --today <YYYY-MM-DD> --core-only
python3 .tutor/core/scripts/plan-review.py --today <YYYY-MM-DD> --cards

# On Windows (if python3 is not mapped):
python .tutor/core/scripts/refresh-status.py --today <YYYY-MM-DD>
python .tutor/core/scripts/validate-study.py --today <YYYY-MM-DD> --core-only
python .tutor/core/scripts/plan-review.py --today <YYYY-MM-DD> --cards
```

A clean template should report:

- `concepts: 0`
- `due: 0`
- `No due concepts.`

## Folder Layout

```text
.
├── AGENTS.md                  # Agent entrypoint and cold-start status
├── CLAUDE.md                  # Claude Code mirror of the same instructions
├── .tutor/
│   ├── config/                # Instance config and learner profile template
│   ├── core/                  # Protocol, settings, scripts, and skills
│   ├── data/                  # Review cards
│   ├── docs/                  # Maintenance and session checklists
│   └── evolution/             # Tutor-system observations and experiments
├── examples/                  # Example subject configurations
├── state/                     # Mastery, reviews, due queue, and mistakes
└── subjects/                  # Learning content, empty by default
```

## Privacy Boundary

This repository is meant to be copied before use. Personal learning data should live in your own instance, not in the public template.

Before publishing a fork or derivative, check that it does not contain:

- learner profile details
- real review logs
- private notes or external evidence
- local machine paths
- credentials or API tokens

## Design Notes

The template favors plain text over databases so an agent can inspect, update, and validate the learning state directly. The important boundary is that durable learning state lives in `state/` and `subjects/`, while reusable method and tooling live in `.tutor/core/`.

The tutor protocol is intentionally strict:

- recall before reveal
- do not move past weak prerequisites
- schedule due concepts before new material
- distinguish a session pass from long-term mastery
- validate generated status before closing a session

## Author

Created by TonyRainforest.

Contact: zhangyswx@163.com

GitHub: https://github.com/YusenZhang0601

## License

MIT License. See `LICENSE`.
