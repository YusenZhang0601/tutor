# Session Close Checklist

Use this at the end of every learning, review, test, or maintenance session.

## 1. Attempts
- Append review attempts to `state/reviews.jsonl`.
- Use one JSON object per line with `concept_id`, `q`, and `ts`.
- Same-day immediate retests may be logged, but do not count as new spaced repetitions.

## 2. Concept State
- Update concept frontmatter for `status`, `mastery`, `ef`, `interval`, `reps`, `last_review`, and `due`.
- Recompute `state/mastery.json` from concept frontmatter.
- Do not hand-edit `state/due.md`; regenerate it.

## 3. Mistakes
- Add concrete weak points to `state/mistakes.md`.
- Convert recurring mistakes into better review cards or teaching prompts.

## 4. Cards And Indexes
- Keep `.tutor/data/review-cards.json` aligned with concept ids.
- Keep `subjects/INDEX.md` and subject/topic indexes aligned with notes.
- If prerequisites change, regenerate the concept graph for that subject.

## 5. Refresh And Validate
- Run `python3 .tutor/core/scripts/refresh-status.py --today <YYYY-MM-DD>`.
- Run `python3 .tutor/core/scripts/validate-study.py --today <YYYY-MM-DD>`.
- Run `python3 .tutor/core/scripts/plan-review.py --today <YYYY-MM-DD> --cards` after review queue changes.

## 6. Handoff
- Say what was learned, what remains weak, and where to start next.
- Leave no `.DS_Store`, `__pycache__`, or `*.pyc` files.
