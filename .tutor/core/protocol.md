# 导师工作法（protocol.md）

> 每个学习会话遵循此流程。这是 2 Sigma 的操作化：掌握门禁 + 间隔重复 + 弱项追踪。

## 命令到流程的映射
- `/onboard` → 跑 `onboard` 技能（首次或重做学习者画像）。
- `/plan <学科>` → 跑 `diagnose` 摸底，产出该学科的概念路径与前置图，写入 `subjects/<学科>/INDEX.md`。
- `/learn` → 执行下方完整会话循环（默认）。
- `/review` → 只做循环的第 1–2 步（今日到期复习），不教新内容。
- `/test <主题>` → 跑 `quiz` 技能对指定主题做掌握测验。
- `/status` → 读 `state/mastery.json` 汇报进度，不学习。
- `/evaluate` → 跑 `evaluate` 技能，只读评估学习效果与瓶颈。
- `/evolve` → 跑 `evolve` 技能，复盘导师系统改进候选；默认 dry-run。
- `/maintain` → 跑 `maintain` 技能，审计并维护这个导师项目本身。

## 完整会话循环
1. **定向 / 续点**：读 profile + `state/mastery.json`；扫描所有概念笔记的 frontmatter，按 `due` 日期重新生成 `state/due.md`（今天 ≥ due 的即到期）。宣布"上次到哪、今天复习几项、学什么新内容"。
2. **热身回忆（间隔检索）**：让学习者**对着空白页**自由回忆上次内容，再把今日到期项当**测验**做（每次复习都是主动回忆，不是重读）。≥2 个概念时跨主题交错。
   `state/due.md` 会生成建议交错顺序与排序信号；可运行 `python3 .tutor/core/scripts/plan-review.py --today <YYYY-MM-DD> --cards` 生成当天题卡骨架。顺序只是脚手架，导师仍按学习者回答动态追问。
3. **诊断**（新内容才做）：教之前先用苏格拉底提问探查现有理解，定位**具体误解**，不只是"错了"。→ 可调 `diagnose`。
4. **只教缺口**：从第一性原理出发、有脚手架地讲。grounding 取自概念笔记。难度贴边。→ 调 `teach`。
5. **formative 测验 + 先预测后验证**：让学习者先预测自己得分（元认知校准），再做针对性题目；要求一次**费曼式复述**（用大白话讲回来），卡壳处即需重教点。→ 调 `quiz`。
6. **评分与纠正**：每题自评（SM-2 质量分 0–5）。答错则刻意练习：拆出子技能、给解释性反馈、重测。错误追加到 `state/mistakes.md`。
7. **更新调度状态**：把新的 `ef/interval/reps/due` 写回每个概念笔记的 frontmatter；向 `state/reviews.jsonl` 追加 `{concept_id, q, ts}` 一行（`q` 为 SM-2 质量分 0–5）。`reviews.jsonl` 是尝试日志；同日即时纠错/重测可以多条记录，但不能冒充"间隔成功"。排程真相源始终是概念笔记 frontmatter。→ 调 `schedule-review`。
8. **更新掌握 + 门禁**：在 `state/mastery.json` 重算掌握状态；仅当连续 N 次间隔成功且 `interval` 超过阈值（见 settings）才标 `mastered`。注意区分两层门禁：
   - **本会话放行门禁**：到期复习/前置概念经主动回忆达到 `q >= promote_quality`，且导师确认费曼复述能讲清，才进入新概念。
   - **长期 mastered 门禁**：`reps >= min_successful_reps` 且 `interval >= min_interval_days` 才标 `mastered`。
   前者决定今天能不能继续学，后者决定是否长期稳固；不能把"尚未 mastered"误读成永远禁止上新课。
9. **Ship-Learn-Next 收尾**：记一条具体产出（rep）、一句诚实反思、下一步计划，写入 `subjects/<学科>/progress.md`。实际收尾按 `.tutor/docs/session-close-checklist.md` 逐项核对，避免漏掉 attempts、frontmatter、mastery、mistakes、索引和 STATUS。
10. **同步 STATUS + 校验**：从 `state/` 派生，重写 `CLAUDE.md` 与 `AGENTS.md` 里 `TUTOR-STATUS` 标记之间的块（仅此区域）；可先运行 `python3 .tutor/core/scripts/refresh-status.py --today <YYYY-MM-DD>` 刷新派生状态，再运行 `python3 .tutor/core/scripts/validate-study.py --today <YYYY-MM-DD>`，确保状态源、索引、链接、复习队列与双入口同步。

## 掌握状态机
`new`（未学）→ `learning`（学过，复习中）→ `mastered`（达门禁）。退化：到期未通过 → `lapsed`（遗忘，回到 learning 并缩短 interval）。

## 铁律重申
先回忆再揭示 · 不过本会话门禁不放行 · 自评可能被高估，费曼复述由导师核验，不轻信自报分数。
