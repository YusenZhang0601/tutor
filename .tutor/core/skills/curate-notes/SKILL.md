---
name: curate-notes
description: 维护目录结构与各级 INDEX.md,在新增学科/主题/概念等结构变化时调用。与每会话进度写入分离,防索引漂移。
allowed-tools: [Read, Write, Edit, Bash]
---

# curate-notes — 结构与索引维护

目标：保持目录骨架整洁、各级 `INDEX.md` 准确。**只在结构变化时跑**（新增/重命名/移动学科·主题·概念），与每会话的 STATUS/进度写入分开，避免导航文件频繁改动导致漂移。

## 何时触发
- 新开学科 → 建 `subjects/NN-<学科>/{INDEX.md, progress.md, topics/INDEX.md}`，更新 `subjects/INDEX.md`。
- 新开主题 → 建 `topics/MM-<主题>/INDEX.md`，更新 `topics/INDEX.md`。
- 新建概念笔记 → 在所属 `topics/MM-<主题>/INDEX.md` 加链接。

## 索引规则
- 每级**恰好一个** `INDEX.md`（MOC）：向下链接子项，向上链接父级 INDEX。
- 用数字前缀（`01-`,`02-`）固定排序。
- 文件夹只承载纵向骨架（学科→主题→概念，浅层）；更细的关联用**笔记内链接** `[[concept_id]]`，不要再加深文件夹。
- INDEX 只放链接与一句话摘要，不放知识正文。

## 防漂移
- 本技能只改 `INDEX.md` 等结构文件，**不碰** `state/` 与 STATUS 块。
- 每会话进度由 protocol 第 9、10 步处理；二者职责不重叠。
- 改动后用 `Bash` 快速核对：每个目录都有 INDEX.md、无悬空链接。
