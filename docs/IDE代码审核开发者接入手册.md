# IDE 代码审核：15 分钟开发者接入手册

目标：新人按本页完成「网页配对 → VS Code Bridge → 对话选工程 → 出报告」全流程。

## 前置（约 2 分钟）

1. 本机已跑通 WorkBuddy（API + Web），仓库根 `.env` 设置：
   ```bash
   IDE_REVIEW_ENABLED=1
   ```
   改完后重启 API。
2. VS Code 安装扩展：`apps/vscode-workbuddy-bridge` 打出的 `workbuddy-bridge-0.4.x.vsix`（或团队内部分发包），要求 **≥ 0.4.4**（含工程白名单与敏感路径拒绝）。

## 步骤（约 10 分钟）

1. **登录网页** WorkBuddy，打开任意对话。
2. 侧栏点「**配对 VS Code**」，记下 **6 位配对码**（约 2 分钟有效）。
3. VS Code 命令面板执行 **`WorkBuddy: Pair`**，粘贴配对码；状态栏应显示已连接。
4. VS Code **打开要审的工程文件夹**（或确保该路径曾在「最近打开」中，以便出现在工程列表）。
5. 网页对话输入例如：「请审核当前工程安全问题」。
6. 出现工程选择卡片时，勾选目标工程并确认；之后同会话一般不再反复问范围。
7. 等待报告：按 P0 / P1 / P2 列出问题；应能看到基于本机文件内容的结论（而非服务端 `File not found`）。

## 自检失败时

| 现象 | 处理 |
|------|------|
| 提示 Bridge 离线 | 重新 Pair；确认同一登录用户；不要同时开 Python Bridge 抢会话 |
| 已连接但未开文件夹 | VS Code：文件 → 打开文件夹 |
| 工程不在允许列表 | 先在 VS Code 打开过该目录，等心跳上报后再选 |
| 审核读不到 `.env` | 预期行为：敏感文件被拒绝并记审计 |
| 开关关闭后仍想用 | `.env` 设 `IDE_REVIEW_ENABLED=1` 并重启 |

## 运维核对（约 3 分钟）

```bash
make smoke-ide-bridge-m1   # 含跨用户隔离、路径穿越/敏感拒绝、开关关闭
make smoke-embed-identity  # MES/嵌入主路径回归（可在 IDE 开关关闭时跑）
```

审计日志：`DATA_DIR/ide_bridge/audit.jsonl`（无文件正文 / token）。登录用户可调 `GET /api/ide/bridge/audit`。

演示结束建议将 `IDE_REVIEW_ENABLED=0` 并重启，避免非试点环境误开。

## 附录：公开 Git 仓库审核（独立车道）

与 VS Code Bridge **互斥**：消息含公开 `https://` 仓库地址（或「审 Git 仓库」）时，网页弹出 **Git 仓库确认卡**，即使 Bridge 在线也不走本机工程卡。

1. `.env` 保持 `IDE_REVIEW_ENABLED=1`，重启 API。
2. 对话示例：`请审核 https://github.com/org/public-repo`
3. 确认 URL（可选填分支）→ 服务端 shallow clone 并缓存 → **枚举功能源码并分批读取（每批 5）** → 全部完成后输出「🔍 代码审核报告」。
4. **一期限制**：仅公开 HTTPS；不支持 SSH、URL 内嵌 Token、私有仓。与本机 IDE 全仓审同流程，禁止只抽样几份文件结案。
5. 贴代码分析、本机 IDE 选工程流程不受影响（前端优先级：贴码围栏 → Git 卡 → IDE 卡）。

相关：Skill `git-code-review`，工具 `request_git_list_source_files` / `request_git_read_batch`（`request_git_review` 仅抽样降级），组件 `GitRepoPickCard.vue`。

## 验收对应

详见 [`IDE代码审核MCP对接方案.md`](./IDE代码审核MCP对接方案.md) §13；功能清单 F-CODE-06 / TC-CODE-04。
