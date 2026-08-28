# WorkBuddy × DeepSeek Harness：架构实现可行性再评估

> 状态：**探讨稿**（未改变 2026-08-24 选型结论） · 日期：2026-08-28
> 目的：基于对 WorkBuddy 全仓（agent/api/web/automations/local_dev/cursor_dev/desktop/docs）与 DeepSeek Harness rc.8（Studio rc.14）源码的新一轮通读，重新评估「用 DeepSeek Harness 架构实现 WorkBuddy」的可行性，并校验既有结论的论据是否仍成立。
> 关联：[`DeepAgents与DeepSeek-Harness技术选型分析.md`](DeepAgents与DeepSeek-Harness技术选型分析.md)（2026-08-24 锁定：选项 A）、[`选型落地P0清单.md`](选型落地P0清单.md)、[`AGENT-API-可行性技术报告.md`](AGENT-API-可行性技术报告.md)（WorkBuddy agent/api 深读证据）、[`dsh-architecture-report.zh.md`](dsh-architecture-report.zh.md)（DSH rc.8 架构深读证据）

---

## 0. 结论先行

- **一句话**：技术上「用 DeepSeek Harness 架构实现 WorkBuddy」是**能跑通**的（有官方 Python SDK、按会话组装的 preset、审批 seam、事件溯源会话等足够的基础设施），但它是**换内核 + 重写产品协议**级别的工程，不是换壳升级；对当前产品形态 ROI 为负，**不建议推翻选项 A**。
- **三句话论证**：
  1. WorkBuddy 的价值在 **领域工具（~50 个 Python 工具）+ 企业策略（HITL/守卫/审计/资料包）+ 产品协议（SSE status/step/chart/confirm 卡）**——这三样 DSH 都不自带，全要重写；DSH 自带的强项（文件/Shell/子代理/压缩/写码预设）与 WorkBuddy 主环价值**错位**。
  2. 本轮新事实（对比 2026-08-24）：DSH 已发布**官方 Python SDK（`deepseek-harness-sdk`，内嵌 JSON-RPC 运行时二进制，目标机无需 Node）**、`interaction/user-approval` 一次性审批 seam（与 WorkBuddy 写确认 HITL 同构）、`preset` 按会话组装机制（天然支持车道/多资料包）。这些**改善了「DSH 作写码执行器」的可行性**，但**不改变**「DSH 作主对话内核」的代价结构。
  3. WorkBuddy 现有并发/流式/审计/HA 约束（进程内单路流、flock、会话 JWT）是**产品问题**，与 harness 无关；换 DSH 不解决，反而要重新实现一遍。

---

## 1. 前提：WorkBuddy 是什么（最小画像，均来自本仓实读）

| 维度 | 事实 |
|------|------|
| 产品 | 挂在已有 MES 上的「实施/运维微助手」：A 懂平台 / B 查数分析 / C 运维值班 / D 确认后写码（`docs/总览/MES懂行助手四块能力方案.md`） |
| 主环 | DeepAgents 0.7.7（LangGraph 图）`create_deep_agent`（`apps/agent/agents/agent.py:277-288`）+ ~50 个 Python 工具 + 16 个 SKILL.md 技能 + 自定义 Middleware |
| 铁律 | 聊天理解走主环；真改文件/库/发版走旁路（local_dev / cursor_dev）；**人点确认卡 → API 直执**，模型确认后不得二次执行（`.cursor/rules/agent-harness-deep-agents.mdc`、`docs/功能实现/00-总览与架构分流.md`） |
| 车道 | `code_dev / code_review / paste_code` 三条互斥车道，显式 `page_context.workbuddy_lane` 优先（`apps/api/workbuddy_lanes.py`） |
| 会话 | LangGraph `AsyncSqliteSaver` checkpoint + 每轮以 UI 历史（`conversations.db`）回填 + 40 条窗口裁剪（`apps/agent/checkpoint_store.py`） |
| HITL | `WriteConfirmMiddleware` 挂起写工具 → SSE `confirm` 事件 → `/writes/actions/:id/confirm` API 直调（`apps/agent/middleware/write_confirm.py`、`apps/api/routes/writes.py`） |
| 流式 | SSE 事件 `status/step/token/confirm/done/error` + chart/dashboard 卡；防代理攒包 padding（`apps/api/routes/chat.py`、`sse_flush.py`） |
| 并发 | 进程内单路流（0.15s 短等后 `stream_busy` 快速失败）；跨进程 flock 文件锁 HA（`stream_concurrency.py`、`ha/fs_lock.py`） |
| 旁路写码 | local_dev=沙箱受限拷贝 + Cursor SDK Local Agent + 四道闸门（相对 import/数据链路/审码/提交）；cursor_dev=Cursor Cloud 直写 GitHub 工作分支 |
| 自动化 | 自研 RRULE + 30s asyncio tick + 企微群机器人 Webhook（`apps/automations/`） |
| 交付 | Web（Vue3+ElementPlus+ECharts）+ 桌面（Electron 壳 spawn 沙箱+API，同源托管 web dist）+ Docker compose |

依赖锁（`requirements.lock.txt`）：deepagents 0.7.7、langgraph 1.2.11、langchain-core 1.6.0、langchain-openai 1.6.0、openai 3.3.1、fastapi 0.141.1、cursor-sdk 1.0.28。

---

## 2. DeepSeek Harness 是什么（对照画像，均来自 rc.8/Studio rc.14 源码实读）

| 维度 | 事实 |
|------|------|
| 定位 | DeepSeek AI 官方的可拼装 coding-agent 运行时：一切皆 Cordis 插件（服务发现、typed events、可逆插件效果） |
| 版本 | Harness `0.1.0-rc.8`（package.json 实值）；README 自称 Studio `0.1.0-rc.14`（整合 rc.8 核心 + Web + Electron 桌面 + 插件中心/Preset 广场/皮肤），MIT；**桌面层由第三方「赋范」团队维护，非 DeepSeek 官方发布渠道** |
| 组装模型 | host 组合（registries/沙箱/审批/持久化/模型路由）+ **按会话挂载的 agent preset**（`apps/cli/config/agent-presets/{standard,minimal,code,cordis}`，每目录一份 `agent.cordis.yml`，`isolate` realm 隔离） |
| 交付形态 | CLI `dsh` / Web 工作区（`dsh web` → 127.0.0.1:3080）/ Electron 桌面（host-supervisor 管理 `dsh web --no-open`）/ **Python SDK**（`deepseek-harness-sdk`，PyPI 分发包，驱动 JSON-RPC stdio 子进程运行时 `dsh-jsonrpc-agent`，随包内置单文件可执行程序，**目标机无需 Node**） |
| 核心机制 | `dsh-agent-loop`（唯一具体循环实现，create/resume 事务、turn 事件）；session 事件溯源（JSONL 默认，SQLite 可选分片）+ 语义 checkpoint 策略 + 自动压缩（compaction，阈值触发摘要）+ 工具结果 spill/pruner；`ctx.skills` 注册表（filesystem 发现、目录/loader 工具、渐进披露）；`ctx.approval` 一次性审批 seam（allowed-once，`approval/asked`+`approval/decided` 审计）；guard（重复工具提醒 + 工具截止时间）；sandbox（bwrap/Landlock/Seatbelt/ACL，逐会话策略）；subagent/jobs/workflow/goal/plan/todo/schedule/mcp-client/extensions(运行时自修改插件)/hooks(Claude Code/Codex 线协议) |
| 模型 | `dsh-llm-deepseek`（DEEPSEEK_API_KEY/BASE_URL）+ `dsh-llm-pi-ai`（providers 字典，多供应商）+ retry + token-meter |
| 无人值守示例 | `examples/jsonrpc-agent`（SDK 内置组合）：bash(前台)+read/write/edit+subagent(进程内)+todo_write，JSONL+压缩；`minimal.cordis.yml` 只有持久 bash + str_replace_editor，danger-full-access 边界（只能对可丢弃 checkout 运行） |
| 已知边界 | 官方 README 能力表多项标「🗓️ 规划中」（独立 MCP/Skills/工具管理、自定义多 Agent、任务规划/后台/会话恢复、项目规则/Hooks/长期记忆、Git/Worktree/审码、浏览器与桌面自动化、手机远程/消息通道）；`docs/` 目录不在本 checkout 内 |

---

## 3. 逐能力块可行性映射

评价：**低/中/高** 表示迁移代价；「DSH 对应物」是能落到的机制。

### 3.1 A 懂平台（资料包 / 能力地图 / 术语 / 诚实边界）—— 代价：中高

| WorkBuddy 现状 | DSH 对应物 | 说明 |
|----------------|------------|------|
| 16 个 `SKILL.md`（YAML frontmatter name/description + 剧本，渐进披露） | `skill-filesystem` + `tool-skill`（同为 SKILL.md、目录发现、目录/loader 工具、按需加载） | **技能资产大概率可直接平移**（两边都是 markdown frontmatter 约定）；但需验证渲染形态差异 |
| `schema_tool/*`、`capability_map`、`inspect_mes_profile`、`entity_catalog`（entities.json 动态生成系统提示词） | 无对应：需写成 TS Cordis 工具插件（或经 SDK 协议由宿主提供） | **全部要重写**；实体目录 → 系统提示词的拼装逻辑是产品代码，与 harness 无关 |

**小结论**：Skills 平移成本低，但「懂平台」的真正载体——领域工具与资料包数据模型——重写成本集中在工具层。

### 3.2 B 查数分析（ERP HTTP / 实体守卫 / 图表 / 看板 / 导出）—— 代价：高

| WorkBuddy 现状 | DSH 对应物 | 说明 |
|----------------|------------|------|
| `platform_query` / `openapi_fetch` / `safe_http`（urllib + SSRF 白名单 + api_calls 日志） | 无现成「带鉴权业务 HTTP」工具；`web-fetch-http` 是面向 web 抓取 | 自写 TS 工具插件；**SSRF 守卫/实体白名单/每调用审计要在工具内或宿主侧重做** |
| `EntityGuardMiddleware`（默认关） | `guard` 只做循环卫生（重复调用/超时），无业务守卫语义 | 业务守卫 = 工具内校验或自研插件 |
| `render_analysis_chart` → SSE `chart` 事件 → ECharts 卡 | 无对应；DSH web 是独立产品壳 | 图表是**前端产品协议**：要么自建网关把 DSH 工具结果映射回 SSE chart，要么改走 DSH 壳（放弃现有卡） |
| 缺口透明 `explicit_gap`、页内≠全库 caveat | 提示词/工具策略可做 | 服务端硬控话术要自己在工具/宿主演进 |

**小结论**：B 是四块里迁移代价最高的一块——工具层全重写 + SSE/图表协议胶水，且业务价值零增长。

### 3.3 C 运维（playbook / 探活 / 审计 / HITL 写确认）—— 代价：中（映射最顺的一块）

| WorkBuddy 现状 | DSH 对应物 | 说明 |
|----------------|------------|------|
| `run_ops_scene` + `ops-query-playbook` Skill | 同 3.1：Skill 平移 + 工具重写 | — |
| 写确认 HITL：Middleware 挂起 → SSE confirm → API 直执 | `interaction/user-approval`：`ctx.approval.request()` → allowed-once/rejected/cancelled/unavailable，`approval/asked`+`approval/decided` 审计，策略 ask/never | **语义同构**；但「应答者」要自实现（Web 壳的 ui-user-questions / SDK 宿主侧自定义），且「确认后 API 直执不经模型」的 WorkBuddy 铁律是产品层逻辑，两侧都成立 |
| 审计（AuditToolMiddleware 默认开） | approval 审计 + 自定义事件 | 中 |
| 探活沙箱（apps/sandbox，独立内存 REST 服务） | 与 harness 无关，保留 | 低 |
| 故障树 / 401 / 空目录引导 Skill | Skill 平移 | 低 |

**小结论**：若只评价「C 运维」，DSH 的 approval seam 是四块里唯一能直接对口的机制；但为一块能力换内核不划算。

### 3.4 D 写码改码（本机沙箱 + GitHub）—— DSH 主场，但旁路产品逻辑仍在

| WorkBuddy 现状 | DSH 对应物 | 说明 |
|----------------|------------|------|
| local_dev：沙箱受限拷贝 + Cursor SDK Local Agent + 四道闸门 + 同步 + 预览 | **DSH coding 全套**：bash/fs/str_replace_editor/terminal(PTY)/sandbox/jobs/workflow/subagent/compaction/spill | 若「替换 Cursor Local 执行改码」：`DSH_CWD=沙箱拷贝` + `workspace-write`/沙箱策略 + minimal 组合即可跑；**闸门/同步/预览仍是宿主侧（FastAPI）产品逻辑** |
| cursor_dev：Cursor Cloud 直写 GitHub 工作分支 | 无直接对应（需自写 git/API 插件或保留 Cursor） | 保留 Cursor 更省 |
| 应急 LLM 工具环（LOCAL_DEV_AGENT=llm） | 可被 DSH minimal 组合直接替代（更稳的循环 + 压缩） | 这是 DSH 价值最实的一处 |

**小结论**：DSH 只在「执行器替换」上有真实增益（且要与 Cursor Local 实测对比）；用它替换整套 WorkBuddy 无意义——与 2026-08-24 结论一致。

### 3.5 硬约束专项（跨块）

| 硬约束 | DSH 可行性 | 备注 |
|--------|-----------|------|
| HITL 确认后 API 直执 | ✅ 可行（approval seam + 宿主直执） | 应答者需自实现 |
| JWT 用户隔离 | 🟡 可行（每用户 session root / 每用户进程 + API 层身份策略） | DSH 会话按 workspace/session root 组织，多用户映射是部署决策 |
| 换模型/供应商 | ✅ 强（llm-deepseek / llm-pi-ai 多 provider） | 与现状 ChatOpenAI 同级别 |
| 厂区资料包 / 多租户 | ✅ 强（preset 按会话组装，一进程多装配） | 比现状更灵活，但 mes_profiles 数据模型要搬 |
| 实体白名单守卫 | 🟡 需自研（guard 无业务语义） | 工具内校验可行 |
| 写审计落盘与会话绑定 | 🟡 可做（approval 审计 + 自定义事件） | 要自接业务表 |
| 流式并发（进程内单路） | 🟡 不自动解决 | 事件溯源可能允许多路，但要验证 |

---

## 4. 技术点对照总表

| 技术点 | WorkBuddy 现状 | DeepSeek Harness | 偏向 |
|--------|---------------|------------------|------|
| Agent Loop | LangGraph（deepagents） | Cordis `dsh-agent-loop`（create/resume、turn 事件） | 主对话：维持现状 |
| Tools | Python 函数列表（~50，无注册中心） | TS Cordis 插件注册 `ctx.tools` | 主对话：维持现状（重写成本高） |
| Skills | SKILL.md + FilesystemBackend（渐进披露） | skill-filesystem + tool-skill（同约定） | **可平移** |
| 硬拦截/审计 | AgentMiddleware wrap_tool_call | DSH 无 middleware 包；「中间件」= Cordis 事件瀑布（waterfall/serial 监听器），典型点是 llm/stream、agent/request、tools/pre|execute|post|result 管线；业务守卫可做成 guard/approval/工具内校验 | 现状更贴业务 |
| HITL | WriteConfirmMiddleware + SSE 卡 + writes API | user-approval seam + 自定义应答者 | 语义同构，实现要搬 |
| 会话持久化 | AsyncSqliteSaver checkpoint + UI 历史回填 | 事件溯源 JSONL/SQLite + 语义 checkpoint + 标题/遥测 | DSH 更完整，模型不同 |
| 上下文管理 | 40 条截断 + OverflowClip 卸载 | compaction 摘要 + tool-result pruner + spill | **DSH 更强**（自动摘要） |
| 流式协议 | SSE status/step/token/confirm/chart/done/error | 无产品协议（SDK events/notifications 或 web client 壳） | 现状（产品自建） |
| 车道/多态会话 | workbuddy_lanes（显式优先） | preset（按会话组装）+ 产品层路由 | 两者可共存 |
| 子 Agent | 无（写码旁路 Cursor） | 一等子 agent / workflow / jobs | DSH 强项（主环不需要） |
| 文件沙箱 | local_dev 受限拷贝（非 Docker） | sandbox（bwrap/Landlock/Seatbelt/ACL）+ workspace-write 等 | 执行器替换时 DSH 强 |
| 模型可换 | ChatOpenAI 任意 base_url | llm-deepseek / llm-pi-ai | 都够 |
| MCP | 审码 MCP（VS Code 扩展内自研 client） | mcp-client 包 | 可并存 |
| 桌面 | Electron + 嵌入式 Python runtime | Electron + Node（dsh web）或 SDK 内嵌 runtime 二进制 | 现状更贴合（若主环不动） |
| HA | flock 跨进程 + DATA_DIR 共享 | 未解决产品存储模型 | 与 harness 无关 |
| 成熟度 | 试点已跑（deepagents 0.7.7 已锁版本） | rc.8 / Studio rc.14，兼容性破坏可预期；官方多项能力「规划中」 | 企业主内核：现状 |

---

## 5. 三条落地路径（更新后）

```text
选项 A（现状强化）——维持推荐
  Vue / Electron → FastAPI → Deep Agents（A/B/C + 澄清/审码/确认）
                             → Cursor Local / Cloud（改码执行）
                             → 未来 CI（提交/部署）仍经 HITL
  （与 2026-08-24 锁定一致；本轮无需动作）

选项 B（DSH 替换本机写码执行器）——可行性上调，值得 P2 POC
  Deep Agents 不变；local_dev 的「改码执行」从 Cursor SDK Local Agent
  换成 DeepSeek Harness 运行时（Python SDK 驱动，DSH_CWD=沙箱拷贝，
  minimal 组合 + workspace-write 边界；闸门/同步/预览仍留在 FastAPI）
  新事实支撑：官方 Python SDK 免 Node、approval seam 可做审批、compaction 长任务更省 token
  风险：rc 版本、双执行器并存、与 Cursor Local 的实测对比

选项 C（全量重建：DSH 作产品内核）——技术可行，ROI 为负，不推荐
  形态：FastAPI 保留（BFF/SSE/确认卡/审计）→ 经 Python SDK 驱动 DSH 运行时
        （自定义 Cordis 插件承载 MES 工具 + 自实现审批应答者 + 会话/用户映射）
  代价：~50 个工具重写、SSE/chart/confirm 协议网关重写、桌面重打包、双栈运维
  收益：主环几乎只有 compaction/子代理两项加分，而写码已旁路
```

| 选项 | 适配度 | 风险 | 工期体感 | 本轮变化 |
|------|--------|------|----------|----------|
| A 现状强化 | ★★★★★ | 低 | 继续演进 | 无 |
| B DSH 仅写码执行 | ★★★☆ | 中（rc + 双执行器） | 周～月级 POC | **可行性上调**（Python SDK 免 Node） |
| C 全量重建 | ★★ | 极高 | 接近重做产品 | 依旧不推荐 |

---

## 6. 风险与成本（若走 C 或长期演进）

1. **版本风险**：Harness 仍 rc（0.1.0-rc.8）；Studio rc.14 是第三方桌面分发（「赋范」团队维护，非 DeepSeek 官方发布渠道），升级节奏与上游解耦，企业交付要自己跟版。
2. **双栈运维**：现状单 Python 栈（FastAPI + deepagents + 桌面嵌入式 Python）；走 C 后 TS 插件 + Python API 并存，测试/锁版本/打包都多一套。
3. **桌面打包**：现状 Electron 壳 + 嵌入式 Python 已出 dmg；DSH web 桌面 = Electron + Node 运行时（官方）或 SDK 内嵌二进制（无人值守组合，无 UI/审批）；产品壳换血风险高。
4. **会话迁移**：LangGraph checkpoint 状态图 vs DSH 事件溯源日志，语义不同；长会话「停止后继续」的既有保障（UI 历史回填）要重造。
5. **产品协议**：SSE status/step/chart/confirm + 26 个前端卡片 + `:::cursor_dev_*` 机器块全部绑定现有栈；换内核 = 网关与前端联动重写。
6. **多用户/审计/HA**：DSH 不解决产品存储模型；JWT 隔离、写审计、flock、DATA_DIR 共享都要在宿主侧重做。
7. **能力缺口**：DSH 官方路线图中「项目规则/Hooks/长期记忆、Git/审码、消息通道」等仍规划中——恰好是 WorkBuddy 已落地或计划中的能力。

---

## 7. 结论与建议

1. **主对话与 A/B/C 内核维持 Deep Agents（选项 A）**：本轮读码未发现任何足以推翻 2026-08-24 结论的新事实；DSH 的强项与 WorkBuddy 主环价值错位依旧。
2. **DSH 的价值出口是「写码执行器」**：且因为官方 Python SDK（内嵌运行时、免 Node、JSON-RPC 驱动）与 approval seam 的出现，选项 B 的可行性较 8-24 评估**上调**，值得做一次受控 P2 POC。
3. **P2 POC 建议口径**（沿用 8-24 并更新）：同一本机样例仓、同一需求话术、同一权限边界（`workspace-write`，禁 danger-full-access）；对比 Cursor Local 与 DSH 运行时的成功率/步数/token 费用/闸门通过率；验收通过标准 = 不明显劣于 Cursor Local 且运维成本可接受，**通过才替换，不通过维持现状**。
4. **触发全量重建（选项 C）的现实条件**（当前均不满足）：DSH 出 1.0 稳定版且 Web/桌面链路成熟；产品方向转向「研发用本机 coding Agent」而非 MES 微助手；或主环 compaction/子代理成本问题大到无法用 Deep Agents 补齐。
5. **可先落地的低成本借鉴**（不换内核）：把 DSH 的 compaction（阈值摘要）思路、`tools/execute` 超时 guard、工具结果 pruner/spill 策略，搬回 Deep Agents 侧（当前只有 40 条截断 + OverflowClip），改善长会话 token 消耗——这是 DSH 架构研究对本项目的**直接可兑现红利**。

---

## 8. 证据索引

| 区域 | 关键路径 |
|------|----------|
| WorkBuddy 主 Agent | `apps/agent/agents/agent.py`、`apps/agent/middleware/*`、`apps/agent/tools/*`、`apps/agent/skills/*/SKILL.md` |
| WorkBuddy API/流式 | `apps/api/agent_wrapper.py`、`routes/chat.py`、`workbuddy_lanes.py`、`stream_concurrency.py`、`sse_flush.py` |
| WorkBuddy 旁路 | `apps/local_dev/`、`apps/cursor_dev/`、`apps/sandbox/server.py`、`desktop/main.js` |
| WorkBuddy 自动化 | `apps/automations/`（自研 RRULE + tick + 企微） |
| 选型历史 | `docs/Agent开发/DeepAgents与DeepSeek-Harness技术选型分析.md`、`选型落地P0清单.md` |
| DSH 版本/定位 | `deepseek-harness-studio-main/README.md`（Studio rc.14 = Harness rc.8）、`packages/README.zh.md`（分组表） |
| DSH Python SDK | `python/sdk/README.zh.md`、`examples/jsonrpc-agent/`（minimal.cordis.yml + README） |
| DSH 审批/HITL | `packages/interaction/user-approval/README.zh.md` |
| DSH 组装模型 | `examples/headless-agent/cordis.yml`、`apps/cli/config/agent-presets/standard/agent.cordis.yml`、`packages/preset/README.zh.md` |
| DSH 会话/压缩 | `packages/session/README.zh.md`、`packages/compaction/README.zh.md`、`packages/skill/skill/README.zh.md` |
| DSH Web/桌面 | `packages/boot|host|client/README.zh.md`、`packages/client/web/src/boot.ts`、`apps/desktop/README.zh.md` |

---

## 修订记录

| 日期 | 说明 |
|------|------|
| 2026-08-28 | 首版：基于全仓双读的可行性再评估；结论维持选项 A，选项 B 可行性上调（Python SDK/approval seam 新事实），新增 POC 口径与低成本借鉴项 |
