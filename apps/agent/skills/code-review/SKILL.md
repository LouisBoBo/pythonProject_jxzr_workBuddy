---
name: code-review
description: >-
  专业级代码评审方法论（vendor：Viprasol Tech code-review-skill，MIT）。
  正确性优先，再安全(OWASP/CWE)、性能、API、测试、可维护性；按 Critical/High/Medium/Low/Nit
  定级并给出具体修复。用于审 diff/PR/文件/工程源码。
  公司门禁叠层见 references/workbuddy-gate-90.md（依赖/配置/脱敏、严重度锋利、可修可验）。
  勿用于 MES 查导写、API 健康分析。本机 VS Code 工程审核请优先走 ide-code-review。
version: 1.1.0
vendor: Viprasol-Tech/code-review-skill
vendor_url: https://github.com/Viprasol-Tech/code-review-skill
---

# Code Review（专业方法论 · Vendor + 公司门禁）

> **来源**： [Viprasol-Tech/code-review-skill](https://github.com/Viprasol-Tech/code-review-skill)（MIT）  
> **原则**：不自造上游检查清单；完整方法论在 `references/viprasol-skill.md`。  
> **冲 90 分叠层**：`references/workbuddy-gate-90.md`（通用，非某一仓库特例）。

## 必须先做

1. **读取并严格执行** `references/viprasol-skill.md`。
2. **再读取并严格执行** `references/workbuddy-gate-90.md`（必扫面、严重度锋利、修复可粘贴、验证方法）。
3. Critical/High（及映射后的 P0/P1）必须含：触发条件、**问题代码**、**修复建议**、**修复代码**、**验证步骤**；P2 也须四段（可更短）；Nit 不得抬成阻塞项。
4. 问题总览数量必须与正文条目数一致。
5. **用户可见输出一律中文**（含过渡句）；禁止英文旁白。代码/路径/CVE/CWE/命令可保留原文。
6. 每条正文统一四段式：问题描述 → 问题代码 → 修复建议 → 修复代码（完整相对路径）。

## WorkBuddy 输出映射（公司内部中文报告）

| Viprasol | 报告 | 是否阻塞合并 |
|----------|------|--------------|
| Critical | **P0** | 是 |
| High | **P1** | 是（门禁叠层中上调为 P0 的除外，见 gate-90） |
| Medium | **P1** 或 **P2** | 按 gate-90 / 影响面 |
| Low / Nit | **P2** | 否 |

分类纪律：

- **确认缺陷**可进 P0/P1；**潜伏风险**禁止标 P0（除非 gate-90 明文上调类且当前可利用）
- 风格 / formatter 可修 → Nit/P2

## 何时不用本 Skill 单独开场

- 本机 VS Code / Bridge：先 `ide-code-review` 取码，再套用本文 + gate-90；跳过上游「先问审什么」。
- MES 查数 / 导入导出 / API 健康：用对应业务 Skill。
