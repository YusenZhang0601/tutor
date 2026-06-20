---
name: schedule-review
description: 用 SM-2 算法根据质量分更新概念的复习间隔与到期日,并刷新 mastery.json。每次测验/复习后调用。
allowed-tools: [Read, Write, Edit, Bash]
---

# schedule-review — SM-2 间隔重复排程

目标：根据质量分 q（0–5）更新每个概念的 `ef/interval/reps/due`，对抗遗忘。纯文本逻辑，零依赖。

`reviews.jsonl` 是**尝试日志**，会记录 formative 测验、即时纠错和重测；同一概念同一天可以有多条。SM-2 的 `reps` 表示**间隔成功复习次数**，不能把同日即时重测当成新的间隔复习。若同一会话内先错后纠正，记录尝试，但排程 frontmatter 应以导师接受的最终状态为准；同日多次成功最多只贡献 1 次 `reps`。

## SM-2 算法（参数读 `.tutor/core/settings.yml`）
对一个概念，给定本次质量分 `q`：

```
若 q < 3（失败/遗忘）:
    reps     = 0
    interval = lapse.reset_interval        # 默认 1 天
    ef       = max(min_ef, ef - lapse.ef_penalty)
    status   = lapsed
若 q >= 3 且这是新的间隔复习日（last_review != today）:
    reps += 1
    若 reps == 1: interval = sm2.first_interval   # 1 天
    elif reps == 2: interval = sm2.second_interval # 6 天
    else: interval = round(interval * ef)
    # 更新 ef（SM-2 标准公式）
    ef = ef + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    ef = max(min_ef, ef)
若 q >= 3 但 last_review == today（同日即时纠错/重测）:
    追加 reviews.jsonl 尝试记录
    不增加 reps, 不把 interval 当作新的间隔向前滚
    可按导师判断更新 mastery/note，但不得冒充间隔成功

due = today + interval 天
last_review = today
```

## 步骤
1. 对每个刚测的概念，先判定是新的间隔复习日还是同日即时纠错，再按上式算出新的 `ef/interval/reps/due/last_review`。
2. **写回**该概念笔记的 frontmatter（用 Edit 精确替换这几行）。
3. 向 `state/reviews.jsonl` **追加**一行：`{"concept_id": "...", "q": <0-5>, "ts": "<ISO日期>"}`。
4. 更新 `state/mastery.json`：
   - 重算该概念的 `status` 与 `mastery`。
   - **掌握门禁**：仅当 `reps >= mastery.min_successful_reps` 且 `interval >= mastery.min_interval_days` 且本次 `q >= mastery.promote_quality` → `status: mastered`。
   - 刷新 `summary` 计数。
5. 日期计算可用 `Bash`（`date -v+<n>d +%F`）确保准确，不要心算。
6. 完成学习/复习/测验收尾时，按 `.tutor/docs/session-close-checklist.md` 核对 `reviews.jsonl`、frontmatter、`state/mastery.json`、`state/mistakes.md`、派生索引和 STATUS。

## 原则
- frontmatter 是 SM-2 状态的真相源；mastery.json 是聚合视图。两者保持一致。
- `reps` 只数跨日的成功复习日期；`reviews.jsonl` 可以有更多尝试行。
- 失败要真的惩罚 ef 并重置 interval——否则遗忘会被掩盖。
