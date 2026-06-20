---
name: evaluate
description: 阶段性评估学习效果，读取 mastery、reviews、mistakes 与复习负荷，输出 retention、低 q、误解复发和下一步干预建议；不教授新内容、不修改学习状态。
allowed-tools: [Read, Bash]
---

# evaluate — 学习效果评估

目标：判断导师和学习者当前配合是否有效，而不是推进新课。评估只读，不直接修改 `state/`、概念 frontmatter、protocol 或技能。

## 步骤
1. 运行 `python3 .tutor/core/scripts/evaluate-learning.py --today <YYYY-MM-DD>`。
2. 阅读输出中的 review_count、due_pass_rate、average_q、recurring_misconceptions、concepts_with_high_friction。
3. 如果 high friction 或 recurring misconceptions 不为空，下一次教学优先换问法、换例子或回到更小前置概念。
4. 如果 due_now 大于 0，先清复习门禁，再推进新内容。
5. 需要长期改进时，只把观察写入 `.tutor/evolution/observations.jsonl` 或交给 `evolve`；不要在 evaluate 中晋升规则。

## 输出口径
- 先说证据窗口和样本量，样本不足时明确说明。
- 建议必须落到下一次教学动作，例如复习、重测、反例题、迁移题或降低粒度。
- 不把一次低分泛化成学习者能力结论。
