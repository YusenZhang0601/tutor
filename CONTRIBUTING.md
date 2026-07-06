# Contributing

Thanks for taking a look at `tutor`.

This project is a template for AI-assisted mastery learning. Contributions should keep the template clean, reusable, and free of personal learner data.

## Good Contributions

- Clearer documentation for the tutor workflow.
- Bug fixes for validation or scheduling scripts.
- Small improvements to the learning protocol.
- Better example subject configurations.
- Tests or checks that protect template hygiene.

## Please Avoid

- Adding personal study notes or real learner progress.
- Adding project-specific research material to the generic template.
- Committing local artifacts such as `.DS_Store`, `.omc/`, `__pycache__/`, or `*.pyc`.
- Introducing dependencies unless they materially simplify the core workflow.

## Local Checks

Use the current date for `--today`.

```bash
python3 .tutor/core/scripts/refresh-status.py --today <YYYY-MM-DD>
python3 .tutor/core/scripts/validate-study.py --today <YYYY-MM-DD> --core-only
python3 .tutor/core/scripts/plan-review.py --today <YYYY-MM-DD> --cards
```

Before opening a pull request, also run a quick privacy check for credentials, local paths, and personal learning content.
