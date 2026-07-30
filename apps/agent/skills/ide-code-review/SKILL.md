---
name: ide-code-review
description: >-
  用户在 WorkBuddy 对话中要求审核/审查/代码评审本机 VS Code 或 Bridge 工程时启用。
  本 Skill 只负责经 Bridge/Git 拉取 findings 与 file_contents；
  深度评审口径强制套用 Skill「code-review」（Viprasol + workbuddy-gate-90），勿自造检查清单。
  勿与 MES 查导写、API 健康分析混用。
---

# 本机 IDE 代码审核（Bridge 适配器）

> **分工**：本文件 = 取码与降级；**专业评审** = `code-review`（Viprasol + `workbuddy-gate-90`）。

## 禁止追问（最重要）

用户已选定工程（`page_context.ide_workspace_root`）或消息为「审核代码 / 审查代码」时：

- **禁止**再问审哪个工程 / 全仓还是目录 / 关注点
- **立刻** `request_ide_review` → 补拉依赖与配置 → 按 `code-review` + gate-90 出报告

## 流程

1. **立刻** `request_ide_review`（尊重 `ide_workspace_root`）
2. 按 gate-90「必扫面」检查：`file_contents` 是否含依赖清单与运行配置；缺失则 `request_ide_read_files` 补拉（如 `pom.xml`、`package.json`、`requirements.txt`、`application.yml`、`application.properties`、`appsettings.json`、`go.mod`、`*.csproj` 等实际存在者）
3. Bridge **离线** → `request_git_review`
4. 读 `/skills/code-review/SKILL.md` → `references/viprasol-skill.md` → `references/workbuddy-gate-90.md`
5. 按下方报告壳输出（P0/P1 条数自洽；每条含修复代码 + **验证**）

## 语言（强制）

- 用户可见内容**全部中文**：报告正文、过渡句、旁白、步骤说明
- **禁止**英文旁白，例如：`Now I have all files…`、`Let me compile the report`、`Looking at…`
- 改用中文，例如：「源码已齐，开始汇总审核报告。」
- 例外：代码块、文件路径、CVE/CWE 编号、shell 命令、库名可保留原文

## 硬约束（取码层）

- 禁止服务端 `read_file` / `grep` / `glob` 读本机绝对路径
- 禁止让用户贴代码；禁止因诊断为空宣称「无问题」
- `selected-not-open` ≠ 离线

## 公司报告壳

```markdown
## 🔍 代码审核报告

**工作区**: …
**审核范围**: 已审文件列表；**未覆盖**（依赖/配置/测试等）须明示
**审核引擎**: IDE Bridge (vX.Y.Z) + code-review (Viprasol) + gate-90
**审核结论**: Approve / Approve with comments / Request changes
**审核重点**: …

### 📊 问题总览
| 严重度 | 数量 | 说明 |
| P0 / P1 / P2 | n | 数量=正文条数 |

### 🔴 P0 — 必须立即修复
每条：文件:行号、触发条件、片段、**可粘贴修复**、**验证（复现+通过标准）**

### 🟠 P1 — 高风险，应尽快修复
同上

### 🟡 P2 — 建议改进
表格；Nit 不阻塞

### ✅ 质量较好的部分

### 🎯 优先修复建议
立即 / 本周 / 本迭代

### 🔎 验证清单（可选总表）
| ID | 复现要点 | 修复后通过标准 |
```
