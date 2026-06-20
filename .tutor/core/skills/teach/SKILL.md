---
name: teach
description: 讲解一个新概念,从第一性原理出发、有脚手架、难度贴边。当学习循环进入"教新内容"时调用。
allowed-tools: [Read, Write, Edit]
---

# teach — 只教缺口

目标：把单个概念讲到学习者能自己复述。先回忆再揭示，不直接灌答案。

## 前提
- 该概念的前置已经通过**本会话放行门禁**：到期复习/主动回忆达到 `q >= promote_quality`，费曼复述能讲清；若未通过，先回去补前置。
- `mastered` 是长期稳固状态，不是当天能否继续学习的唯一条件；不要因为前置尚未 `mastered` 就把学习路径永久卡死。
- 已通过 diagnose 知道学习者在此概念上的具体缺口。

## 步骤
1. **激活已知**：先问学习者对这个概念已有什么直觉/猜测，从他的话接上去。
2. **第一性原理讲解**：从为什么需要它、它解决什么问题讲起，再到形式定义。多用类比和最小例子。难度贴边。
3. **脚手架**：复杂概念拆成小台阶，每讲一步停下来用一个小问题确认跟上了。
4. **创建/更新概念笔记** `subjects/NN-<学科>/topics/MM-<主题>/<概念>.md`：
   - 顶部 frontmatter（见下方模板）
   - 正文：精炼的知识要点（这是知识库，可以厚），学习者自己的话/类比也记进去
   - 在所在 `topics/MM-<主题>/INDEX.md` 加链接
   - 在 `.tutor/data/review-cards.json` 为该 `concept_id` 增加 `recall` / `challenge` / `pass` 三段题卡
5. 教完不直接判定掌握——交给 `quiz` 做 formative 测验。

## 概念笔记 frontmatter 模板
```yaml
---
id: <学科缩写>-<概念slug>
subject: <学科>
topic: <主题>
prerequisites: [<前置concept_id>, ...]
status: learning        # new|learning|mastered|lapsed
mastery: 0.3            # 导师判断式估计 0–1
# --- SM-2 间隔重复状态 ---
ef: 2.5
interval: 0
reps: 0
last_review: null
due: null
---
```

## 原则
- 告诉学习者"觉得费劲"是真学习的信号，别追求顺滑的"懂了"错觉。
- grounding 取自笔记已有内容,保持一致,不自相矛盾。
