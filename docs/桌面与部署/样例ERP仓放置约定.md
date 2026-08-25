# 样例 ERP 仓放置约定（P1-10）

> 日期：2026-08-21  
> 背景：仓库根曾误放 `pythonProject_zr_aicoding/`（内含嵌套 `.git`），与 monorepo 并列污染工作区。

## 约定

| 项 | 要求 |
|----|------|
| **禁止** | 在 `simplified-workbuddy/` 根下 clone / 解压 `pythonProject_zr_aicoding` |
| **应放** | 本机独立目录，例如 `~/Desktop/pythonProject_zr_aicoding` 或任意 monorepo **外**路径 |
| **GitHub 白名单** | 写码 Cloud 仍用 `LouisBoBo/pythonProject_zr_aicoding`（远程仓名，≠ 本地嵌套目录） |
| **忽略** | 根 `.gitignore` 已忽略 `pythonProject_zr_aicoding/`，防再次误提交 |

## 本机写码联调

确认卡选「本地目录」时指向上述**独立路径**，不要指向 WorkBuddy 仓库内子目录。

相关：[`cursor_dev与local_dev对照接手指南.md`](../写码与审码/cursor_dev与local_dev对照接手指南.md)、[`本机目录写码与沙箱隔离方案.md`](../写码与审码/本机目录写码与沙箱隔离方案.md)。
