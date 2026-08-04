---
name: git-code-review
description: >-
  审核公开 HTTPS Git 仓库全仓功能源码：list → read_batch → 仅终稿进对话输出区。
  与本机 IDE Bridge 审核、粘贴代码分析互斥；禁止只用抽样工具结案。
---

# 公开 Git 仓库代码审核（全仓分批）

## 何时使用

- 消息含 `【Git仓库已确认】`，或 `page_context.git_repo_url` 已给出公开 HTTPS 地址
- 用户明确要求审核远程 Git / GitHub / GitLab / Gitee 仓库（公开仓）

## 何时禁止

- 用户只是粘贴了源码块问这段有什么问题 → 走 `paste-code-analyze`
- 用户已确认本机工程（`【本机工程已确认】` / `ide_workspace_root`）→ 走 `ide-code-review` / `request_ide_*`
- **禁止**对本车道调用 `request_ide_review` / `request_ide_list_source_files` / `request_ide_read_batch` / `request_ide_read_files`
- **禁止**只用 `request_git_review` 审 5～30 个文件就输出终稿（那是抽样降级，不是全仓）

## 输出纪律（硬）

- **过程中**：只调工具，不要写「正在 clone / 共 N 文件 / 第 N 批纪要」给用户（过程区由系统展示）
- **全部批次完成后**：输出区第一行必须是 `## 🔍 代码审核报告`
- **禁止**英文过渡句；直接从报告标题写起
- **禁止**只审 1～2 批就结案

## 范围

**审**：业务页面/组件/接口/store/utils 等功能源码（list 工具已自动排除非核心）  
**不审**：配置、锁文件、样式、文档、依赖目录等

## 流程（与本机 IDE 全仓审对齐）

1. `request_git_list_source_files`（从消息标记或 page_context 取 url/ref；服务端 shallow clone 并缓存）
2. 记下返回的 `total` / `batch_count`
3. `request_git_read_batch(batch_index=0..N-1)` 连续调用：每批静默记下 P0/P1/P2，立刻下一批
4. 当 `done_after=true`：合并各批，输出终稿报告

## 每条问题四段式（硬，缺一不可）

```
#### Px-n: 简短标题
- **文件**：`完整相对路径`
- **问题描述**：错在哪 / 为何危险 / 触发条件
- **问题代码**：
```语言
（file_contents 中的原文片段）
```
- **修复建议**：怎么改、如何验证
- **修复代码**：
```语言
（可粘贴替换的修复示例）
```
```

禁止只列文件名+一句话；禁止无代码块的空话修复。

## 终稿模板

```
## 🔍 代码审核报告
仓库 / 审核范围(N 文件 M 批) / 引擎 / 结论
### 📊 问题总览（条数与正文一致）
### 🔴 P0 / 🟠 P1 / 🟡 P2
（每条按四段式展开）
### 🎯 优先修复建议
```

若工具返回错误（私有仓、SSH、clone 失败）：用中文说明原因与一期限制（仅公开 HTTPS），不要伪造 findings。
