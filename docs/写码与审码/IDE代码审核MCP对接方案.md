# WorkBuddy ↔ IDE MCP 代码审核对接方案

> 状态：**产品已对齐 + M0/M1 POC 已落地（默认关闭）**  
> 目标：用户在 **WorkBuddy** 发起代码审核，审核结果回到 **WorkBuddy**；本地 IDE / 远程仓库只是代码载体。  
> 对照现状：当前仓库是 **MES 运维助手**（查 / 导 / 受控写），**尚无 MCP 客户端/服务端**；本能力属独立研发辅助线，与第二阶段「实施运维」主线可并行、不强绑。

---

## 0. 产品锁定（2026-07-29 已拍板）

| # | 锁定结论 |
|---|----------|
| 1 | **入口**：审核指令在 **WorkBuddy 网页/对话**发起，不在 IDE 里当主入口 |
| 2 | **出口**：审核报告回到 **同一条 WorkBuddy 会话** |
| 3 | **连接**：开发者用 Bridge/扩展 **一键连公司 WorkBuddy**（出站），不靠两边手写 MCP 互指 |
| 4 | **载体可替换**：一期推荐 **VS Code 扩展**（审当前打开工程）；亦可 Python Bridge / 其它 IDE / Git 仓；WorkBuddy 对上只认统一「审核任务 / finding」协议 |
| 5 | **未连接 / 未开工程**：明确提示；MES 查/导/写不受影响 |

```text
用户 ──说「审核登录模块」──▶ WorkBuddy（唯一 UX）
                                │
                                ├─▶ 载体 A：本机 VS Code（经 Bridge）
                                ├─▶ 载体 B：本机其它 IDE（经同一 Bridge 协议）
                                └─▶ 载体 C：Git 仓库（服务端拉取，无本机 IDE 也可审）
                                │
用户 ◀──审核报告（P0/P1/P2）── WorkBuddy
```

---

## 1. 需求理解（对齐一句话）

| 项 | 结论 |
|----|------|
| 触发 | **仅** WorkBuddy 对话（如「审核登录模块」） |
| 执行 | 按可用载体执行：本机 IDE MCP，或仓库只读分析（降级/无 IDE） |
| 回传 | **仅** 回同一 WorkBuddy 会话（可流式步骤 + 最终报告） |
| 载体 | VS Code（一期）/ 其它 IDE / Git 仓；IDE **不是**产品入口 |
| 范围 | **全公司内部**：多用户、可审计；不能假设 WorkBuddy 与 IDE 同进程 |

**核心约束（决定架构）：**  
WorkBuddy 是 **中心化 Web 服务**（API 8765 / Web 5180，可嵌入 ERP）。  
本机 IDE 进程在笔记本上，中心服务不能直连 → 全公司主路径是 **本机 Bridge 出站注册**。  
`npx vscode-as-mcp-server` 仅适合单机 POC，不是上线给全员的方式。

```text
❌ 不可规模化：
  WorkBuddy Server ──stdio──▶ 某台机器上的 VS Code MCP

✅ 可规模化：
  WorkBuddy Chat → Agent Tool → 按 user_id / 任务选载体
       → Bridge→本机 IDE    或    → Git 仓只读分析
       → 统一 finding 回传 WorkBuddy
```

---

## 2. 推荐总体架构

### 2.1 三层角色

```text
┌─────────────────────────────────────────────────────────────┐
│  WorkBuddy（公司内网 / 机房）                                  │
│  Web 对话 → API → Deep Agent                                 │
│    Tools: request_ide_review / get_ide_bridge_status …       │
│    Skill: ide-code-review                                    │
│    会话路由表: user_id → bridge_session（在线心跳）              │
└──────────────────────────▲──────────────────────────────────┘
                           │ 出站 WebSocket / HTTPS（本机主动连出）
┌──────────────────────────┴──────────────────────────────────┐
│  开发者本机：wb-ide-bridge（轻量常驻）                          │
│  - 用 ERP/公司 token 注册到 WorkBuddy                          │
│  - 把 MCP 调用转成对本地 MCP Server 的 tool call               │
│  - 工作区白名单、路径脱敏、超时与取消                            │
└──────────────────────────▲──────────────────────────────────┘
                           │ stdio / 本机 HTTP
┌──────────────────────────┴──────────────────────────────────┐
│  IDE MCP Server                                              │
│  优先：VS Code + vscode-as-mcp-server（或官方 MCP 扩展）       │
│  后续：JetBrains IDEA MCP 插件（同一 Bridge 协议适配）         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 一次「审核」调用时序

1. 用户登录 WorkBuddy（与现有 ERP JWT 一致）。  
2. 本机 Bridge 已用同一身份连上 WorkBuddy，心跳显示「IDE 在线」。  
3. 用户：「审核 apps/api/routes/auth.py 的登录逻辑」。  
4. Agent 加载 Skill `ide-code-review`，调用工具 `request_ide_review`。  
5. API 按 `user_id` 找到 Bridge，下发任务（scope、路径、提示词、超时）。  
6. Bridge 调用本地 MCP：`code_checker` / 读文件 / 可选 `execute_command`（lint）。  
7. Bridge 汇总结构化结果（finding 列表 + 摘要），回传 WorkBuddy。  
8. Agent 整理成中文报告写回对话；过程事件走现有 SSE（`status` / `step`）。

### 2.3 为何本机「主动连出」而不是服务端连入

| 方式 | 全公司可行性 |
|------|----------------|
| 服务端直连每人电脑 IP:port | 防火墙/NAT/笔记本休眠，运维噩梦 |
| **本机 Bridge 出站 WSS 注册** | 与常见「远程开发助手」一致，内网策略好批 |
| 纯 stdio 同机 | 仅 POC / 开发自测 |

---

## 3. 与现有 WorkBuddy 的落点（按仓库惯例）

沿用 Deep Agents 三层，**不**另起一套对话引擎：

| 层 | 新增 | 路径建议 |
|----|------|----------|
| **Tool** | `request_ide_review`、`get_ide_bridge_status`、`cancel_ide_review` | `apps/agent/tools/ide_review/` |
| **Skill** | 何时审、问哪些问题、报告格式、无 Bridge 时的降级话术 | `apps/agent/skills/ide-code-review/SKILL.md` |
| **API** | Bridge 注册 / 心跳 / 任务下发与结果回收 | `apps/api/routes/ide_bridge.py` |
| **Web（可选）** | 侧栏「IDE 连接状态」、审核报告卡片 | `apps/web/src/components/IdeBridgeStatus.vue` 等 |
| **本机组件** | `wb-ide-bridge`（独立小包，可放 `apps/ide-bridge/`） | Node 或 Python 均可；建议 Node 便于对接 VS Code 生态 |

注册工具：在 `apps/agent/agents/agent.py` 的 `TOOLS` 列表追加；改后重启 API。

鉴权：复用现有 `require_auth` + JWT `sub`；**任务只能路由到与当前会话同一 `user_id` 的 Bridge**，禁止跨用户调用他人本机。

审计：与写操作类似，记 `user_id / thread_id / workspace / paths / tool_calls / duration / outcome`（不落源码全文，默认只存路径 + finding）。

---

## 4. IDE 侧选型（公司标准）

### 4.1 第一期标准：VS Code（推荐）

| 组件 | 选择 | 理由 |
|------|------|------|
| IDE | VS Code ≥ 1.102（内置 MCP） | 配置成本低于 IDEA，社区 MCP 成熟 |
| MCP Server | **`vscode-as-mcp-server`**（或维护中的 fork `vsc-mcp-server`） | 直接提供 `code_checker`、终端、读写等 |
| 传输（本机） | Bridge ↔ MCP：优先 **stdio**；若扩展只提供本机 HTTP 则用 HTTP | Bridge 封装差异，对 WorkBuddy 透明 |
| 工作区 | 打开「要审的那个仓库」窗口；Bridge 绑定 `workspaceRoot` | 避免审错目录 |

**团队共享配置示例**（仓库可选提交，仅方便本机开发者）：

```json
{
  "servers": {
    "vscode-code-review": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "vscode-as-mcp-server"]
    }
  }
}
```

> 注意：`.vscode/mcp.json` 是 **VS Code 自己消费 MCP** 的配置；全公司主路径是 **WorkBuddy → Bridge → 该 MCP**，不是让每位同事在 Claude Desktop 里配一遍。

### 4.2 第二期：JetBrains IDEA

- 使用 JetBrains 官方/社区 MCP Server 插件，由 **同一 Bridge 协议**增加 `adapter: idea`。  
- WorkBuddy 工具接口不变，降低双 IDE 成本。  
- 第一期不做 IDEA，避免并行两套运维。

### 4.3 不推荐作为公司主路径的做法

- 仅依赖「VS Code 命令面板 MCP: Add Server」而无 Bridge（无法被中心 WorkBuddy 调用）。  
- 把完整源码仓推到服务器再审（权限、密钥、体积、与「IDE 实时诊断」目标不符）——仅作 **离线降级**（见 §6）。

---

## 5. 协议约定（WorkBuddy ↔ Bridge，最小可用）

### 5.1 Bridge 注册

- `POST /api/ide/bridge/register`（或 WSS 握手 query）  
- 字段：`user_id`（以 JWT 为准）、`machine_name`、`ide`（`vscode`|`idea`）、`workspace_root`、`bridge_version`、`capabilities[]`  
- 心跳：每 15～30s；超时未心跳 → 标记离线

### 5.2 下发审核任务

```json
{
  "task_id": "uuid",
  "thread_id": "session-xxx",
  "intent": "code_review",
  "prompt": "审核登录与嵌入 token 处理，关注泄露面",
  "targets": {
    "paths": ["apps/api/routes/auth.py", "apps/web/src/embed.js"],
    "globs": [],
    "git_base": "main"
  },
  "tools_allowed": ["code_checker", "read_file", "search", "execute_command"],
  "timeout_sec": 120
}
```

### 5.3 回传结果（结构化，便于 Agent 二次整理）

```json
{
  "task_id": "uuid",
  "status": "ok",
  "workspace_root": "/Users/x/proj",
  "findings": [
    {
      "severity": "P0",
      "path": "apps/web/src/embed.js",
      "line": 42,
      "rule": "token-in-url",
      "message": "access_token 曾写入可被 referrer 带走的 URL",
      "suggestion": "写入 sessionStorage 后立即 replaceState 去掉 query"
    }
  ],
  "file_contents": [
    { "path": "apps/web/src/embed.js", "content": "…截断后的源码…", "bytes": 1234, "truncated": false }
  ],
  "diagnostics_count": { "error": 2, "warning": 5 },
  "raw_summary": "可选：MCP 原始摘要截断",
  "hint": "请基于 findings 与 file_contents 撰写报告；勿再调用服务端 read_file。"
}
```

严重度约定与现有评审习惯对齐：`P0` / `P1` / `P2`。

**本机源码必须经 Bridge 回传**：服务端 `FilesystemBackend(virtual_mode)` 读不到用户 Desktop 路径。  
- `code_review` 默认 `include_file_contents=true`，结果带 `file_contents`。  
- 额外读文件：`intent=read_files` → 工具 `request_ide_read_files`。  
- Agent **禁止**对 `/Users/...` 等绝对路径调用服务端 `read_file` / `grep`。

### 5.4 安全底线（公司必须项）

1. **身份绑定**：Bridge 持有与聊天同一用户的 token；服务端强制 `task.user_id == bridge.user_id`。  
2. **路径白名单**：仅允许 `workspace_root` 下路径（相对路径，或位于工作区内的绝对路径经归一化）；拒绝 `..` 穿越与工作区外路径。  
3. **命令白名单**：若开放 `execute_command`，仅允许预置脚本（如 `npm run lint -- <paths>`、`ruff check`），禁止任意 shell。  
4. **密钥**：不把 `.env`、私钥、证书内容回传；Bridge 侧对敏感文件名拦截；`file_contents` 有单文件/总量截断。  
5. **审计**：谁、何时、审了哪些路径、结果条数；源码正文默认不入库（会话内工具结果可短暂存在）。  
6. **取消与超时**：用户关掉会话或超时，Bridge 中止 MCP 调用。

---

## 6. 降级与补强（保证「能用」而不只「IDE 在线才能用」）

| 场景 | 行为 |
|------|------|
| Bridge 离线 | Agent 明确告知：「未检测到你的 IDE 连接」，并给出安装/启动 Bridge 的短链；可选走 **服务端只读 Git 评审**（clone 指定分支 + 静态规则 / 内置 review 脚本） |
| MCP 工具失败 | 返回部分 diagnostics + 错误原因；不静默空成功 |
| 无明确路径 | Skill 先追问模块/路径，或根据 `page_context` / 最近 git 改动猜，**猜错要确认** |
| 超大范围 | 限制文件数/总字节；超出则要求缩小范围 |

服务端 Git 降级可作为 M2 能力，避免「同事没开 VS Code 就完全不可用」；但产品文案上仍强调 **IDE 在线 = 一等体验（含实时诊断）**。

---

## 7. 分阶段落地（可排期、可验收）

### M0 — 单机 POC（1～2 周，验证链路）

**目标：** 同一台开发机上跑通「一句话 → MCP → 报告」。

- 本机启动 `vscode-as-mcp-server`，用任意 MCP 客户端（或脚本）验证 `code_checker`。  
- 临时：`AgentRunner` 旁路直接调本机 MCP（stdio），**不**上多用户路由。  
- 验收：对仓库内 2～3 个已知文件发出审核，对话中出现带路径/行号的 finding。

### M1 — Bridge + WorkBuddy 工具（2～3 周，可演示）

- 实现 `wb-ide-bridge`（注册、心跳、任务、回传）。  
- API：`/api/ide/bridge/*`；Tool：`request_ide_review`；Skill：`ide-code-review`。  
- 前端：显示「IDE：在线 / 离线」。  
- 验收：用户 A 在线可审自己的仓；用户 B 无法打到 A 的 Bridge；过程走 SSE。

### M2 — 公司试点硬化（2～3 周）

- 命令白名单、路径策略、审计落盘、超时取消。  
- 安装包：内网 npm/二进制 + 一页《开发者接入手册》。  
- 可选：Git 降级评审。  
- 验收：试点组（5～10 人）按手册 15 分钟内接入；抽测跨用户隔离；审计可查。

### M3 — 全公司推广

- IT 发布：Bridge 自动更新、VS Code 推荐扩展列表。  
- 运营：标准话术库（「审登录」「审嵌入链路」「审写确认」）写进 Skill。  
- 可选：IDEA adapter。  
- 验收：接入文档进新员工清单；故障有「Bridge 状态 + 最近错误」排障页。

---

## 8. 技术栈选型（贴合本仓）

| 组件 | 建议 | 说明 |
|------|------|------|
| WorkBuddy Agent | 现有 Python + Deep Agents + LangChain | 新增 Tool/Skill 即可 |
| MCP 客户端（服务端侧） | **不**在 API 进程里直连每人 MCP；由 Bridge 在本机当 MCP Client | 避免把 stdio/会话态塞进多 worker API |
| Bridge | Node 18+ 或 Python 3.11+ | 若用官方 MCP SDK，Node 生态更齐；Python 与仓内运维一致亦可 |
| 传输 | 内网 `wss://workbuddy.example/api/ide/bridge/ws` | 与现有 HTTPS 终结一致 |
| 包管理 | 公司内网镜像托管 `wb-ide-bridge` | 禁止开发者随意执行不明 `npx` 到公网时，改为内网镜像 |

本仓当前 `requirements.txt` **无** MCP 依赖；M1 起若 API 需要解析 MCP 消息，再显式加入官方 SDK，且仅用于 **协议测试/可选降级**，主路径仍是 Bridge。

---

## 9. 产品交互（最小 UX）

**用户侧话术示例：**

- 「审核登录模块代码」  
- 「对照 main，审一下嵌入 identity 相关改动」  
- 「看看 auth.py 有没有 token 泄露风险」

**系统侧反馈：**

1. 步骤：连接 IDE → 拉取诊断 → 整理报告（复用 `ProcessPanel` 的 step 事件）。  
2. 报告：按 P0/P1/P2 列表；每条含路径、行号、说明、建议。  
3. 离线：一行状态 + 接入说明，不假装已审。

**非目标（本期不做）：**

- 在 WorkBuddy 里直接改 IDE 文件并写回（可读可报即可）。  
- 全自动「改代码 → 测试 → 部署」（仍属愿景线，见第二阶段产品方向）。  
- 多租户 SaaS 对外售卖。

---

## 10. 与参考方案的关系（纠偏）

参考文中「VS Code 原生 MCP + vscode-as-mcp-server」**作为本机执行层完全正确**，且适合 POC。  
但「WorkBuddy 作为外部 MCP 客户端远程 stdio/SSE 直连 VS Code」在 **中心化 Web + 全公司多机** 场景下缺一层：**身份化的 IDE Bridge（本机出站）**。  
落地时以本文 §2 / §5 为准；参考文的扩展选型与工具表（`code_checker` 等）直接复用。

---

## 11. 风险与对策

| 风险 | 对策 |
|------|------|
| 同事不装 Bridge / 不打开 VS Code | 安装极简（一键脚本）；离线降级；侧栏常显状态 |
| MCP 扩展不稳定 / 版本漂移 | 公司锁定版本；Bridge 做 capability 协商 |
| 误审生产密钥或客户数据 | 路径/文件名黑名单；审计不含文件正文 |
| Agent 乱调 `execute_command` | 白名单 + Middleware 硬拦 |
| 与 MES 运维主线抢资源 | 独立里程碑与文档；Tool 默认仅对「开发角色」或特性开关开放 |

特性开关建议：环境变量 `IDE_REVIEW_ENABLED=1`，默认关，试点项目打开。

---

## 12. 建议的立即下一步（本周可做）

1. **立项确认**：用户画像（平台研发 / 实施二次开发）与是否必须 VS Code 优先。  
2. **M0 POC**：按下方「M0 检查点」验收（先 mock，再可选 live MCP，再特性开关挂 Tool）。  
3. **冻结 Bridge 协议草稿**（§5 JSON），前后端按字段并行。  
4. **写接入手册草稿**（装 VS Code 扩展 → 跑 Bridge → WorkBuddy 显示在线 → 说一句话）。

---

## 12.1 M0 检查点（已落地，闸门式）

> 代码落点：`apps/agent/tools/ide_review/`、`scripts/smoke_ide_review_m0.py`。  
> **默认关闭**：未设 `IDE_REVIEW_ENABLED=1` 时，Agent 工具列表与改前一致。

### Checkpoint A — mock 冒烟（必做）

```bash
make smoke-ide-review-m0
```

期望：打印若干 `P0/P1/P2` finding，末行 `SMOKE_OK`。  
不启动 API、不加载 Deep Agent。

### Checkpoint B — 可选本机 MCP

```bash
IDE_REVIEW_MCP=1 make smoke-ide-review-m0
```

- mock 仍必过。  
- live 失败默认 `SKIP`（不拖垮日常冒烟）；若要强制失败：`IDE_REVIEW_MCP_REQUIRE=1`。  
- 命令默认：`npx -y vscode-as-mcp-server`（可用 `IDE_REVIEW_MCP_COMMAND` / `IDE_REVIEW_MCP_ARGS` 覆盖）。

### Checkpoint C — Agent Tool（默认关）

1. **关闭时**：不设或 `IDE_REVIEW_ENABLED=0`，重启 API 后行为与现网一致；可跑 `make smoke-embed-identity` 等回归。  
2. **打开时**（仅本机 `.env`）：`IDE_REVIEW_ENABLED=1`，重启 API；对话可调用 `request_ide_review`。  
3. **M1 起**：工具优先走本机 Bridge；离线明确提示。M0 的 `IDE_REVIEW_MCP` 直连仅作实验，演示请用 Bridge。

---

## 12.2 M1 演示步骤（Bridge 最小闭环，已落地）

> 代码：`apps/agent/tools/ide_review/bridge_store.py`、`apps/api/routes/ide_bridge.py`、`apps/ide-bridge/run.py`、侧栏状态。  
> 载体一期 = **本机工作区 + 规则审核**（不依赖 VS Code MCP / npx）。

### 冒烟（无 LLM）

```bash
make smoke-ide-bridge-m1
```

期望：`SMOKE_OK`。

### 手工看效果

1. 仓库根 `.env` 增加：`IDE_REVIEW_ENABLED=1`，然后：

```bash
./scripts/stop.sh && ./scripts/dev.sh
```

2. **连接 VS Code（推荐）**  
   - 安装扩展 **v0.3.0**：见 [`apps/vscode-workbuddy-bridge/README.md`](../../apps/vscode-workbuddy-bridge/README.md)（覆盖重装）  
   - **主审**：MCP `vscode-as-mcp-server` → `code_checker`（先保证本机 `npx -y vscode-as-mcp-server` 能跑）  
   - 在 VS Code **打开要审核的项目文件夹** → `WorkBuddy: Connect`  
   - 网页侧栏：「在线」/「未开工程」  
   - 空 finding 时报告会带 hint，**不得当成「代码无缺陷」**；Agent 应基于回传的 `file_contents` 写报告

3. 对话：「审核登录模块」→ 审的是 **VS Code 当前工程**。  
   - 未连接 → 提示去 Connect  
   - 已连接未开文件夹 → 提示打开项目  
   - **不应再出现** 服务端 `read_file` → `File not found`（本机绝对路径）

4. （备选）仍可用 Python Bridge：`apps/ide-bridge/run.py --workspace …`（与扩展不要同时抢同一用户）

5. 演示结束：`.env` 改回 `IDE_REVIEW_ENABLED=0` 并重启。

---

## 13. 验收清单（试点通过即视为「可内部推广」）

运维/安全门槛（企业级）：

- [x] **跨用户隔离**：异用户 `put_result` / `wait_result` 拒绝并写审计（`make smoke-ide-bridge-m1` → `cross_user_isolation`）
- [x] **路径穿越 + 敏感文件**：`../`、工作区外路径、`.env`/密钥类拒绝并审计（同冒烟 → `path_traversal_and_sensitive_denied`）；扩展仅允许「当前/最近工程」作为 `workspace_root`
- [x] **15 分钟手册**：[`IDE代码审核开发者接入手册.md`](IDE代码审核开发者接入手册.md)
- [x] **开关关闭**：`IDE_REVIEW_ENABLED=0` 时 `feature_enabled=false`，Bridge API 返回 404；MES/嵌入主路径用 `make smoke-embed-identity` 回归

功能体验（试点）：

- [ ] 同一用户：对话触发 → 本机 VS Code 文件进入报告  
- [ ] Bridge 离线时有明确提示（可选 `request_git_review` 降级）  
- [ ] 工程选择卡片确认后同会话不再反复追问范围  

---

## 附录 A：Skill 大纲（实现时填写）

```markdown
---
name: ide-code-review
description: 当用户要求审核/审查/code review 本地或指定模块代码时使用；需 IDE Bridge 在线。
---
# 流程
1. get_ide_bridge_status；离线则说明并停止或走降级
2. 确认 paths / 模块；过大则收窄
3. request_ide_review(...)
4. 按 P0/P1/P2 输出；未覆盖项写「未检查」
```

## 附录 B：与现有文档索引

- 能力分层与非目标：[`第二阶段产品方向.md`](../产品规划/第二阶段产品方向.md)  
- Tools / Skills 扩展方式：[`DeepAgents-Skills使用指南.md`](../Agent开发/DeepAgents-Skills使用指南.md)  
- 身份与嵌入：[`平台嵌入说明.md`](../MES业务/平台嵌入说明.md)  
- 现有「Cursor 评审提示词」可迁移为 Skill 内标准 `prompt` 模板：[`阶段收口评审与验收清单.md`](../产品规划/阶段收口评审与验收清单.md)
