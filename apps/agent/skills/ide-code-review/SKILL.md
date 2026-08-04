---
name: ide-code-review
description: >-
  审核本机工程功能源码：list → read_batch → 仅终稿进对话输出区。
  过程旁白禁止输出；配置/uni_modules 等已自动排除。
  若消息含【Git仓库已确认】/ git_repo_url，改走 git-code-review，禁止本 Skill。
---

# 本机 IDE 代码审核

## 何时禁止

- 消息含 `【Git仓库已确认】` 或 `page_context.git_repo_url` → 走 `git-code-review`
- 用户只是粘贴源码围栏问这段问题 → 走 `paste-code-analyze`

## 输出纪律（硬）

- **过程中**：只调工具，**不要**写「共 N 文件 / 第 N 批纪要」给用户（过程区由系统展示）
- **全部批次完成后**：输出区第一行必须是 `## 🔍 代码审核报告`
- **禁止**英文过渡句（Now I have… / Let me compile…）；直接从报告标题写起

## 范围

**审**：业务页面/组件/接口/store/utils 等功能源码  
**不审**：配置、锁文件、样式、文档、`uni_modules`、locale、static、测试与 mock

## 流程

1. `request_ide_list_source_files`
2. `request_ide_read_batch(0..N-1)` 连续调用（脑内记 findings，勿贴正文）
3. 终稿报告（合并各批）

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

禁止只列文件名+一句话；禁止无代码块的空话修复。P0/P1/P2 均须四段（P2 可更短但仍须贴代码）。
