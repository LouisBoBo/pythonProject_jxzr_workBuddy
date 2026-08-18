---
name: skill-template
description: >-
  这是新建 Skill 的模板示例，一般不会被业务对话触发。
  仅当用户明确说「按 skill 模板新建技能」时参考本文件结构。
---

# Skill 模板（复制本目录后改名）

> 使用方法：复制整个 `skill-template/` 目录，改名为你的技能名（小写+连字符），
> 再编辑 `SKILL.md` 的 frontmatter 与正文。详见仓库文档
> `docs/Agent开发/DeepAgents-Skills使用指南.md`。

## 何时使用

- （写清楚触发场景，description 里也要写，便于 Agent 自动选择）

## 步骤

1. …
2. …

## 必须调用的工具

- `tool_a`：做什么
- `tool_b`：做什么

## 禁止事项

- …

## 自检清单

- [ ] …
