# Tutor Template

This is a generic mastery-learning tutor project. It contains no personal study content.

## Start
1. Open this folder with any agent.
2. Read `AGENTS.md` or `CLAUDE.md`.
3. Run `/onboard` to fill `.tutor/config/learner-profile.md`.
4. Run `/plan <subject>` to create the first subject under `subjects/`.

## Validate
```bash
python3 .tutor/core/scripts/validate-study.py --today 2026-06-20 --core-only
python3 .tutor/core/scripts/refresh-status.py --today 2026-06-20
python3 .tutor/core/scripts/plan-review.py --today 2026-06-20 --cards
python3 .tutor/core/scripts/evaluate-learning.py --today 2026-06-20
```
