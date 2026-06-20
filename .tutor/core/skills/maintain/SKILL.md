---
name: maintain
description: 审计并维护私人导师项目本身，发现状态漂移、协议矛盾、索引过期、复习排程语义错误和可升级机会。当学习者要求维护、优化、检查这个学习空间时调用。
allowed-tools: [Read, Edit, Bash]
---

# maintain — 导师项目自检与升级

目标：把当前 tutor 项目当成一个可持续运行的教学系统来维护，而不是只修单张笔记。维护时仍服从学习模式：保护学习者画像、概念状态、间隔重复记录和多 agent 交接面。

## 步骤
1. **刷新当天派生状态**：运行 `python3 .tutor/core/scripts/refresh-status.py --today <YYYY-MM-DD>`，让 `state/due.md`、双入口 STATUS、根索引和主题门禁先回到今天。
2. **完整校验**：运行 `python3 .tutor/core/scripts/validate-study.py --today <YYYY-MM-DD>`；失败时先修验证失败项。
3. **复习计划冒烟测试**：运行 `python3 .tutor/core/scripts/plan-review.py --today <YYYY-MM-DD> --cards`，确认 due 队列能生成可读的交错复习顺序与题卡。
4. **依赖图冒烟测试**：运行 `python3 .tutor/core/scripts/concept-graph.py`，确认概念前置图能从 frontmatter 生成。
5. **教学效果评估**：运行 `python3 .tutor/core/scripts/evaluate-learning.py --today <YYYY-MM-DD>`，读取 due pass rate、average q、误解复发和高摩擦概念；只作为维护证据，不直接改学习状态。
6. **自我进化 dry-run**：运行 `python3 .tutor/core/scripts/evolve-tutor.py --today <YYYY-MM-DD> --dry-run`，审查候选 observation/reflection；没有重复证据或用户确认，不晋升规则。
7. **协议/技能审计**：检查 `.tutor/core/protocol.md`、`.tutor/core/settings.yml`、`.tutor/core/skills/*/SKILL.md` 是否互相矛盾，尤其是：
   - 本会话放行门禁 vs 长期 `mastered` 门禁。
   - `reviews.jsonl` 尝试日志 vs frontmatter 的 SM-2 真相源。
   - 同日即时重测不能冒充新的间隔复习。
   - `.tutor/docs/session-close-checklist.md` 是否仍覆盖 attempts、frontmatter、mastery、mistakes、索引、STATUS 和校验命令。
8. **状态/索引审计**：核对 `AGENTS.md`、`CLAUDE.md`、`INDEX.md`、`subjects/**/INDEX.md`、`state/mastery.json`、`state/due.md`、`state/mistakes.md` 是否同源派生、无 stale 占位；若教学需要外部项目事实，先按 `.tutor/config/external-evidence.md` live verify。
9. **内容精度审计**：抽查近期学过的概念卡，优先找“好记但过度绝对”的物理/数值表述；发现后补到 `.tutor/config/lints.yml`，再由 `validate-study.py` 执行内容 lint。
10. **升级机会沉淀**：把不适合当场落地的大项写入 `.tutor/docs/upgrade-opportunities.md`，按优先级说明收益、风险和触发条件。
11. **收尾验证**：再次运行 refresh + validate，并用 `rg` 扫描 stale/待办/旧误导短语；最后说明已修项与剩余机会。

## 原则
- 不随意改 `reviews.jsonl` 或概念 frontmatter；只有证据明确显示状态不一致时才修。
- 自动化优先：能用校验脚本守住的规则，不只写在人类说明里。
- `.tutor/evolution/` 只记录导师系统经验；不要把它混入学习者 mastery。
- 维护文档要服务接力：下一位 Claude/Codex 应能按文件直接继续。
