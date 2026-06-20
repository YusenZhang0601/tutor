---
name: evolve
description: 对导师系统自身做复盘，把用户纠正、导师失误、误解复发和验证结果整理成 observation、reflection、experiment 或 promoted rule 候选；默认不修改 core protocol。
allowed-tools: [Read, Edit, Bash]
---

# evolve — 导师自我进化

目标：让导师从使用证据中变强，同时避免一次性直觉污染长期规则。`state/` 记录学习者状态；`.tutor/evolution/` 记录导师系统经验，两者不能混用。

## 步骤
1. 先运行 `python3 .tutor/core/scripts/evolve-tutor.py --today <YYYY-MM-DD> --dry-run`。
2. 阅读 dry-run reflection，确认候选观察是否有证据支撑。
3. 单次现象只写入 `.tutor/evolution/observations.jsonl`。
4. 同类问题重复出现，或用户明确指出，才生成 `.tutor/evolution/reflections/<date>-*.md`。
5. reflection 能形成可测试假设时，才写入 `.tutor/evolution/experiments/`。
6. experiment 有指标改善或用户确认后，才能写入 `.tutor/evolution/promoted/`。
7. promoted rule 必须包含 source evidence、scope、rollback condition。

## 禁止事项
- 不因一次会话直接改 `.tutor/core/protocol.md` 或 `.tutor/core/skills/*/SKILL.md`。
- 不把学科内容写入 `.tutor/evolution/`。
- 不把导师策略观察写入 `state/mastery.json`、`state/reviews.jsonl` 或概念 frontmatter。
