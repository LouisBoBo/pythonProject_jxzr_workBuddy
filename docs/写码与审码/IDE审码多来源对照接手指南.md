# IDE 审码多来源对照与接手指南（P1-05）

> 日期：2026-08-21  
> 目的：审码有多条取数/执行路径，**有意并存**；本文写清边界，避免改 Bridge 却动到 Git，或把 mock 当成生产审码引擎。  
> 上手流程：[`IDE代码审核开发者接入手册.md`](IDE代码审核开发者接入手册.md)  
> 架构长文：[`IDE代码审核MCP对接方案.md`](IDE代码审核MCP对接方案.md)

---

## 1. 先分清两层

| 层 | 回答的问题 | 典型组件 |
|----|------------|----------|
| **取数通道** | 文件从哪来？ | VS Code Bridge / Python Bridge / 公开 Git clone / 用户贴码 |
| **审码引擎** | 拿到文件后谁出 finding？ | Agent 读内容写报告（主路径）；可选本机 `mock` / `mcp`（Bridge 侧诊断） |

主产品路径：**网页对话 + Agent 工具读文件 → 模型写「🔍 代码审核报告」**。  
`mock` / `mcp` 是 Bridge 任务里的 **本机诊断/冒烟**，不是「全公司默认审码大脑」。

---

## 2. 取数通道（用户可见）

| 通道 | 何时 | 代码落点 | 前端 |
|------|------|----------|------|
| **本机 IDE（Bridge）** | 用户要审「当前 VS Code 工程」 | `apps/agent/tools/ide_review/` + `routes/ide_bridge.py` | 工程选择卡；侧栏「配对 VS Code」 |
| **公开 Git** | 消息含 `https://` 仓或「审 Git 仓库」 | 同包 `git_review.py` + `request_git_*` | `GitRepoPickCard.vue` |
| **贴码** | 消息带代码围栏 | 贴码车道 / 无 Bridge | 不走工程卡 |

**互斥优先级（前端）**：贴码围栏 → Git 确认卡 → IDE 工程卡。  
车道：`workbuddy_lane=code_review`（与 `code_dev` 互斥）。

开关：`IDE_REVIEW_ENABLED=1` 才挂 IDE 工具；Git 工具策略见 `tool.py` / `create_agent`（一般默认可挂，仍受车道约束）。

---

## 3. 双 Bridge（本机出站）

| | **VS Code 扩展（推荐）** | **Python Bridge（兼容/无 IDE）** |
|--|--------------------------|----------------------------------|
| 包 | `apps/vscode-workbuddy-bridge`（≥0.4.4） | `apps/ide-bridge/run.py` |
| 配对 | 网页 6 位码 → `WorkBuddy: Pair` | CLI：`--api` + JWT `--token` + `--workspace` |
| 能力 | 工程白名单、敏感路径拒绝、心跳上报最近工程 | 扫盘取任务 + 读工作区回传 |
| 同用户 | **不要与 Python Bridge 同时抢同一会话** | 仅当无 VS Code 或排障时用 |

API 共用：`/api/ide/bridge/*`（注册 / 心跳 / 任务 / 结果 / 审计）。  
审计：`DATA_DIR/ide_bridge/audit.jsonl`（无文件正文、无 token）。

**短期不合并**两个 Bridge 实现；收敛只立专项（协议字段对齐后再抽共享客户端）。

---

## 4. 审码引擎（Bridge 任务内）

`apps/agent/tools/ide_review/review.py`：

| provider | 环境 | 用途 |
|----------|------|------|
| **`mock`**（默认） | 未设 `IDE_REVIEW_MCP` | 冒烟 / 无 MCP 时本地假 findings |
| **`mcp`** | `IDE_REVIEW_MCP=1` | 调本机 `vscode-as-mcp-server`（`IDE_REVIEW_MCP_COMMAND/ARGS`） |

Agent 主路径读文件后**不依赖**上述 provider 才能出报告；改 mock/mcp **不要**当成改「对话审码话术」。

---

## 5. 工具与 Skill 对照

| 场景 | Skill | 工具序列 |
|------|-------|----------|
| 本机全仓 | `ide-code-review` | `request_ide_list_source_files` → `request_ide_read_batch`… |
| 公开 Git 全仓 | `git-code-review` | `request_git_list_source_files` → `request_git_read_batch`… |
| 抽样/离线目录 | （降级） | `request_git_review(local_path=…)` 或抽样版 `request_ide_review` |

禁止混用：Git 全仓流程里不要 `request_ide_*`；写码车道禁止审码工具。

### 5.1 与「提交批审」的关系（路由隔离）

| | 全量审码车道 | 提交批审（commit_batch） |
|--|--------------|---------------------------|
| 路由 | `workbuddy_lane=code_review` → Deep Agents | 前端 `looksLikeLocalCommitBatch` → **local-dev API**（不进 Agent） |
| Skill | `ide-code-review` / `git-code-review` + `code-review` | **不加载 Skill**；可共用 **规则引擎**（`run_git_or_local_review` / `enrich.py`） |
| 范围 | 全仓 list → read_batch | 本批文件（同步池 ∩ Git 待提交） |

详见 [`写码后审码门禁与自动提交P1方案.md`](写码后审码门禁与自动提交P1方案.md) §2.5。

---

## 6. 改动检查清单（必过）

1. ☐ 本次动的是 **通道**（Bridge/Git/贴码）还是 **引擎**（mock/mcp）？  
2. ☐ 改 Bridge 协议字段？VS Code 扩展 **与** `ide-bridge/run.py` **与** `bridge_store` 是否同改？  
3. ☐ 改工程卡 / Git 卡？前端优先级与 `chatIntent` / lane 是否仍互斥？  
4. ☐ 敏感路径 / 白名单 / 跨用户隔离：跑 `make smoke-ide-bridge-m1`  
5. ☐ 未误开：演示后建议 `IDE_REVIEW_ENABLED=0`；MCP live 仅显式 `IDE_REVIEW_MCP=1`  
6. ☐ 是否动了 `workbuddy_lane`？勿让审码抢走写码确认卡  
7. ☐ 提交批审（commit_batch）是否误走 Deep Agents / 全仓 list？应走 local-dev API 独立链路

---

## 7. 推荐阅读顺序

1. 本文 §1～§3  
2. [`IDE代码审核开发者接入手册.md`](IDE代码审核开发者接入手册.md)（15 分钟路径）  
3. [`IDE代码审核MCP对接方案.md`](IDE代码审核MCP对接方案.md) §架构与验收  
4. 代码：`routes/ide_bridge.py` → `bridge_store.py` → `tool.py`
