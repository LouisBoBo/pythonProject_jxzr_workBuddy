# DeepSeek Harness（DSH）架构技术报告

> 调研对象：`/Users/hebo/Downloads/deepseek-harness-studio-main/`（DeepSeek Harness Studio，基于 deepseek-ai/deepseek-harness rc.8 的桌面化分支，版本 `0.1.0-rc.8`，见 `package.json:3`）。所有结论均附 `文件:行号` 证据。注意：README 中引用的 `docs/subsystems/*` 目录在本 checkout 中不存在（为生成物/缺失），本报告不引用该目录内容。

## 1. DSH 是什么

DSH 是一个**基于插件的 Agent Harness（智能体运行框架）**，不是单一应用。根目录 `AGENTS.md:3` 一句话定义："DeepSeek Harness is a plugin-based agent harness on vendored Cordis: **everything is a plugin**"（一切皆插件，运行时建立在 vendored 的 Cordis 插件框架之上，`pnpm-workspace.yaml:42` 将 vendor/cordis 钉版本为 workspace 成员）。

- **定位**：为"构建 agentic 应用/Agent 工作流"提供完整运行时——会话、模型、工具、Skills、插件、子 Agent、持久化、Web GUI 全部打包为可组合的 Cordis 插件（`packages/README.md:5`：npm scope `@deepseek-ai/dsh-*`；插件通过 `ctx.effect()`/`ctx.on()`/`ctx.waterfall()` 注册服务与事件）。
- **目标平台是"三端"**：① **桌面端**（Electron，`README.md:65` "使用 Electron 承载 … Web 工作区，并由桌面主进程启动和管理本地 `dsh web` 服务"，macOS/Windows 安装包，`README.en.md:16`）；② **Web 端**（浏览器 GUI，`apps/web` 为 Vite 入口，`apps/web/package.json` "Web application entry: vite build over the @deepseek-ai/dsh-client-web shell library; dist/ served by apps/cli's dsh web"）；③ **CLI 端**（`dsh` 命令，`apps/cli/README.md:5-16`：`dsh --profile <name>`、`dsh web`、`dsh --profile headless "job"`、`dsh plugin` 四种入口模式）。此外还有 Python SDK（`python/README.md:3` "driving DeepSeek Harness as a subprocess … JSON-RPC on stdio"）与自动化 ACP 服务（`packages/acp/README.md`）。
- **版本关系**：本仓库是 [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) 的派生（Studio，`README.md:427`），整合上游 rc.8 的核心与 Web 能力，另加插件中心、Preset 广场、皮肤等桌面能力（`README.md:85`）。模型默认为 DeepSeek 系（`packages/bundle/base/cordis.patch.yml:40-42` 默认 `provider: deepseek-official / model: deepseek-v4-flash`），但 LLM 层是 provider-neutral 的（`packages/llm/README.md:5`）。

## 2. Monorepo 形态

- **工作区**：`pnpm-workspace.yaml:1-24` 包含 `vendor/*`、`packages/*/*`、`native/landlock-run`（Landlock 原生启动器）、`apps/*`、`apps/desktop/runtime`、`website`、`examples`（仅依赖解析，非构建目标，`pnpm-workspace.yaml:18-20`）、`python/sdk-runtime`。根 `package.json:20-26`：`build` = `scripts/build.ts --profile official` + 桌面；`build:lib:host` = `tsc -b tsconfig.host.json && tsdown --env.DSH_BUILD_FACE host`；`build:lib:client` 同理（`--env.DSH_BUILD_FACE client`）；另有 `build:web`（`apps/web` Vite）、`build:desktop`（Electron）。
- **三个 app**：
  - `apps/cli`：`dsh` 启动器/Profile 装配（`apps/cli/README.md:5-16`），`src/bin.ts:44-53` 按模式动态 import。
  - `apps/web`：Web GUI 的薄入口，`apps/web/src/main.ts:6-13` 仅 `new AppWebEntry(el).run()`；真正的引导逻辑在 `@deepseek-ai/dsh-client-web`。
  - `apps/desktop`：Electron 主进程 + preload + Host 生命周期监督（`apps/desktop/README.md:5` "supervises the existing loopback Web Host and keeps it alive from the system tray"）。
- **51 个分组目录、约 233 个叶子包**（`packages/` 下实测）。`packages/README.md:11-61` 的分组表给出每个分组的一句话职责，核心分组如下（引该表行号）：

| 分组 | 一句话职责（`packages/README.md` 行号） |
|---|---|
| `core/` (13) | 产品 API 主干：会话、提示词、工具、Agent 服务与具体循环 |
| `api/` (14) | 远端 BFF 装配与 Typert RPC 网关 |
| `typert/` (15) | 类型图生成、产物加载与运行时注册表 |
| `goal/` (16) | 同会话目标持久化与生命周期 |
| `schedule/` (17) | 会话内定时跟进 |
| `feedback/` (18) | 人类反馈 |
| `identity/` (19) | 共享匿名身份 |
| `llm/` (20) | LLM 能力族：抽象服务 + provider 适配器 |
| `e2b/` (21) | E2B 远端沙箱 provider（POC） |
| `subprocess/` (22) | 子进程能力族：Service Definition + 本地进程树 provider |
| `shell/` (23) | Bash 能力族：执行器缝 + 本地实现 + 模型侧工具 |
| `terminal/` (24) | 持久 PTY 能力族：owner 作用域会话 |
| `code-runtime/` (25) | 代码执行能力族：Definition + worker-thread provider + Code Mode Consumer |
| `sandbox/` (26) | 进程限制缝；bwrap/Landlock/Seatbelt 后端 |
| `fs/` (27) | 文件系统能力族：缝、本地实现、模型侧文件工具 |
| `lsp/` (28) | LSP 能力族：缝、stdio provider、`lsp` 工具 |
| `skill/` (29) | Skill 能力族：provider 注册表、本地 provider、模型侧目录/加载器 |
| `compaction/` (30) | 压缩能力族：Definition + 基础 provider + 命令 Consumer |
| `context/` (31) | 模型可见请求上下文（工作区指令、时间上下文） |
| `subagent/` (32) | 子 Agent 能力族：provider 注册契约 + 模型侧委派工具 |
| `jobs/` (33) | 通用后台任务运行时 + `job_*` 控制工具 |
| `workflow/` (35) | Workflow 缝、worker-thread 引擎、`workflow`/`ralph` 工具 |
| `web/` (36) | Web 能力族：搜索/抓取 provider + 模型侧 web 工具 |
| `attachment/` (37) | 持久附件身份/校验/本地内容寻址存储 |
| `spill/` (38) | 超大工具输出落盘 + 预览/定位 |
| `todo/` (39) | `todo_write` 工具 |
| `plan/` (40) | 计划协作状态（plan mode） |
| `preset/` (41) | 按会话从 `cordis.yml` 组装 Agent（Preset） |
| `guard/` (42) | 循环卫生守卫：重复调用提醒 + `tools/execute` 超时执行器 |
| `bundle/` (43) | 可安装的 `dsh --profile` 补丁层 |
| `extensions/` (44) | Agent 自修改：运行时插件检视 + 模型编写的插件挂载/卸载 |
| `hooks/` (45) | Hook 桥 + 共享 Claude Code/Codex 线协议库 |
| `session/` (46) | 持久会话数据面：persistence 缝 + JSONL/SQLite 后端、projection 缝、标题、遥测 |
| `session-query/` (47) | 会话检索族：逻辑语料、有界读取、血缘、SQLite 全文搜索 |
| `settings/` (48) | 用户设置缝 + 文件 provider |
| `credentials/` (49) | 凭证引用缝 + env-over-`.env` provider |
| `storage/` (50) | 非会话存储中枢 + 后端 + 域表单 |
| `workspace/` (51) | 工作区实体 |
| `sdk/` (52) | 进程外运行时 SDK：JSON-RPC 协议、TS 客户端、服务端插件 |
| `acp/` (53) | 仅自动化 Agent Client Protocol 服务端 |
| `interaction/` (54) | 人机协作面：审批/交互缝、权限 Preset、命令、ask-user 工具 |
| `boot/` (55) | 共享 app-bin 启动胶水 |
| `host/` (56) | Web GUI 的 host 半边：API 网关 + HTTP 路由服务 |
| `client/` (57) | Web GUI 的浏览器半边：shell、wire、对象服务、slots、`ui-*` 插件 |
| `examples/` (58)、`test-support/` (59)、`util/` (60) | 演示 bundle / 测试设施 / 零依赖工具 |

- **核心包**（任务指定）：`core/agent`（`dsh-agent`，Agent 接口+注册表+事件词表）、`core/agent-loop`（`dsh-agent-loop`，唯一的具体循环）、`core/session`（事件源会话日志）、`core/tools`（工具注册表+执行管线）、`core/scope`（作用域原语）、`core/system-prompt`（提示词/工具 schema 装配）、`llm`（LLM 缝）、`session/*`（持久化数据面）、`subagent/*`、`workflow/*`、`goal/*`、`guard/*`、`sandbox/*`、`web/*`、`api/*`、`client/*`、`boot/*`、`host/*`。**没有独立的 `middleware`、`tool`、`mcp` 包**：工具在 `core/tools`；MCP 在 `packages/mcp/mcp-client`；"中间件"是 Cordis 事件分发的三种模式（见第 5 节）。

## 3. Agent 运行时模型

**抽象与实现分离**：`dsh-agent`（`core/agent/README.md:5`）定义所有插件编程所依赖的 `Agent` 句柄与 `agent/*` 事件词表，"it has zero loop dependency, so the loop is swappable"（零循环依赖，循环可替换）。`dsh-agent-loop` 是唯一含具体循环逻辑的包（`core/agent-loop/README.md:5-7`："This is the only package in the harness that contains concrete loop logic"）。注册表服务 `ctx.agents` 提供 `create()/resume()` 工厂（`core/agent/README.md:42-43`），循环包通过 `ctx.agents.setFactory()` 注册自己（`core/agent-loop/README.md:21`）。

**具体驱动**：`ReactLoopAgent`（`packages/core/agent-loop/src/agent.ts:64`）。循环被建模为 **turn（轮）→ step（步）** 两级嵌套：
- `send()/followup()/steer()/inject()` 把输入分派到 `next-turn`/`next-step` 两个 FIFO 收件箱（`agent.ts:113-132`），`cancel()` 协作式中止（`agent.ts:134-140`）；收件箱每个变更先落一条 `agent/inbox/spliced` 持久事件再改内存投影（`core/agent-loop/README.md:60`）。
- `kick()`（`agent.ts:210-223`）循环调用 `turn()`；`turn()`（`agent.ts:246-330`）打开 `turn/start`，循环 pre-step 认领输入→`step/start`→追加 `user/message`→`step()`→`step/end`，最后 `turn/end`（含 `completed/max-tokens/blocked/aborted/error` 原因，`agent.ts:319`）。
- `step()`（`agent.ts:332-420`）：`buildRequest()`（`agent.ts:426-514`）从会话日志 `deriveMessages()` 推导出完整请求（系统提示词+工具 schema+历史），经 `llm.stream()` 流式拉取 `assistant/chunk`（逐块 `session.append`，`agent.ts:350`），`BlockAssembler` 组装成 `assistant/message`；若含 `tool-call` 块则调用 `executeToolCalls()`（`agent-loop/src/tool-calls.ts:59-101`），按 `isConcurrencySafe` 分类：exclusive 调用为屏障、parallel 调用进入有界滚动池（默认 10，`core/agent-loop/README.md:40`），策略/结果/上下文保持模型顺序。
- **事件即扩展面**：分发有三种模式（`core/agent/src/dispatch.ts:63-82`）：`emit`（fire-and-forget 通知）、`serial`（按序 await）、`waterfall`（"Around-middleware dispatch (Cordis waterfall)"，即洋葱式中间件，`dispatch.ts:72`）。循环在每个边界发事件：`agent/request`、`agent/pre-step`（可拒绝/改写进入的批量输入）、`agent/request-error`（重试恢复瀑布）、`agent/turn-stopping`、`agent/status` 等（`core/agent/README.md:53-55`）。
- **与 LangGraph/DeepAgents 的差异**：① DSH 不是图/节点编排框架——没有显式 state graph，而是"单一事件驱动循环 + 插件在事件边界介入"，新行为通过插件而非改图（`core/agent-loop/README.md:74-83` "Everything that goes beyond 'call the model, run the tools, repeat' belongs to plugins"）；② 每个请求都**从 append-only 会话日志派生**（`core/agent-loop/src/agent.ts:1-3` "Every request is derived from the session log"），而非维护独立对话状态对象；③ 多 Agent 不在循环内——`subagent` 是独立能力族，进程内 provider 通过 `ctx.agents.create()` + 持有的 `AgentHandle` 创建子 Agent，进程外走 ACP/Codex/Claude Code/SDK（`core/agent-loop/README.md:81`、`packages/subagent/README.md:7-16`）；④ 相比 DeepAgents 的"单个自然语言工具"哲学，DSH 提供完整类型化工具注册表、作用域上下文、Code Mode（模型写代码调工具）等更重的基础设施。

## 4. 会话与持久化

- **内存会话**：`core/session`（`dsh-session`）是**事件溯源日志**：`Session` 是 agent 全部交互历史的 append-only 唯一事实源，"the LLM message history is *derived* from it"（`core/session/README.md:5`）；其上维护 ordered surface 投影（`deriveMessages()`，`core/session/README.md:40`）。`SessionStore`（`ctx.sessions`）只创建/持有会话，持久化故意不在这里实现（`core/session/README.md:11`）。事件词表通过 `SessionEventMap` 声明合并扩展（`core/session/README.md:73`）。
- **持久化数据面**：`packages/session/README.md:7-16`——`session-persistence`（缝，`ctx.sessionPersistence`）、`session-checkpoint-policy`（语义持久化检查点，包装 `ctx.llm` 和 `ctx.tools`）、`session-persistence-jsonl`（JSONL 文件后端）、`session-persistence-sqlite`（可选 SQLite，压缩物理 chunk 行）。另有 projection 面（`session-projection`/`-cache`/`-stats`）、标题（`session-title*`，LLM 生成或确定性回退）、遥测（`session-telemetry-otel`）。非会话数据走 `storage/`（JSON/SQLite 后端 + 类型化域表单，`packages/storage/README.md:7-13`）。
- **上下文窗口与压缩**：`packages/compaction/README.md:9-12`——`compaction`（缝，`ctx.compaction`）、`compaction-basic`（token 压力检测+摘要后端）、`compaction-tool-result-pruner`（无模型工具结果裁剪）、`command-compact`（人类命令）。机制上压缩=在日志中追加 `user/message`（摘要）或仅内容 `tool/result` 的 **replacement** 事件，其 `surfaceOp: 'replace'` 在 surface 层遮蔽旧节点但**不删除原始日志**（`core/session/README.md:93, 105`：replace 使旧条目从未来请求消失、原始记录仍 append-only 保留；KV-cache 从首个被遮蔽 token 起失效）。模型可见的请求上下文（工作区指令、时间、文件/会话引用）由 `context/` 组以非工具插件注入（`packages/context/README.md:5-14`）。

## 5. Skill 与中间件

- **Skill**：`packages/skill/README.md:5-13`——`skill`（`ctx.skills` provider 注册与查找）、`skill-badge`（内置 dsh 徽章 skill）、`skill-filesystem`（从本地文件系统发现 skill）、`tool-skill`（把 skill 目录与加载器暴露给模型）。"This capability remains outside the core control spine and can use local, embedded, or remote providers"（`packages/skill/README.md:14`）。本质：**可复用、可发现的方法/步骤/约束文本**（README.md:142 "可复用的方法、步骤与约束"），通过目录快照 + 加载器工具进入模型上下文。
- **中间件（middleware）**：没有 `middleware` 包；"中间件"就是 **Cordis 事件瀑布（waterfall）** 与串行（serial）监听器。`core/agent/src/dispatch.ts:72` 明确注释 "Around-middleware dispatch (Cordis waterfall)"。典型中间件点：`llm/stream`（拦截/包装每次流式模型调用，`packages/llm/llm/README.md:47`）、`agent/request`（改写每次请求配置）、`agent/pre-step`（拒绝/注入输入）、`tools/pre-execute`→`tools/execute`→`tools/post-execute`→`tools/result` 工具管线（`core/tools/README.md:5`）。外部 shell-hook 协议（Claude Code/Codex 的 `hooks.json`）由 `hooks/` 组翻译到同一套事件面上（`packages/hooks/README.md:5`："a 'native hook' is just an ordinary Cordis plugin on those extension points"）。

## 6. 扩展性表面

- **插件模型**：一切皆 Cordis 插件；装配 = 分层 patch：`dsh --profile` 把 `dsh.profile.bundles` 的每个 bundle 的 `cordis.patch.yml` 依序叠加，再叠用户 patch（`apps/cli/README.md:32-38`）。bundle 即"可安装的 patch 层"（`packages/bundle/README.md`，base/headless/web-app 三档，`packages/bundle/base/cordis.patch.yml` 是默认装配清单）。
- **插件中心**：`packages/plugin-center/` 只有 `contracts`（无 README，内容为契约/测试），完整链路在 Desktop（`apps/desktop/README.md:33-35`：npm `dsh-plugin` 关键字发现 → 校验 SHA-256/归档/Bundle 声明 → 事务化安装/启停/卸载，含快照回滚日志）。
- **Preset（Agent 预设）**：`packages/preset/README.md:5`——一个目录含一个 `agent.cordis.yml`，挂到某 agent 的作用域上下文，实现"每会话独立工具+提示词组合"；内置 preset 在 `apps/cli/config/agent-presets/{code,cordis,minimal,standard}`。
- **自修改运行时**：`packages/extensions/README.md:5-11`——`tool-cordis` 让模型检视/挂载/卸载动态包，`cordis-host-runner` 用 `node:vm` 沙箱执行 host 半边定义，`cordis-client-runner` 是浏览器半边，`ui-cordis` 是 UI（demo：`examples/web-cordis/`）。
- **MCP**：`packages/mcp/README.md`——`mcp-client` "MCP client bridge that registers external server tools on `ctx.tools`"；支持 stdio 与 Streamable HTTP（`examples/mcp-memory/README.md:7-11`，暴露为 `mcp__<serverName>__<tool>`）。
- **人机交互**：`packages/interaction/README.md:9-13`——`ctx.commands`、`ctx.approval`（一次性审批）、`ctx.permissionPresets`（权限预设：只读/工作区写入/完全访问）、`ctx.userQuestions` + `tool-ask-user`。

## 7. 沙箱与代码执行

- **进程沙箱**：`sandbox/` 组（`packages/sandbox/README.md:5-12`）：`sandbox` 缝（`ctx.sandbox`）+ `sandbox-local`（平台后端）+ `sandbox-policy`（持久会话策略）。`sandbox-local/README.md:5`：Linux 优先 bwrap（Bubblewrap）再 Landlock，macOS 用 Seatbelt（`sandbox-exec`），Windows 用 ACL restricted-token runner；`sandbox-local/README.md:9` 不支持平台/不可用 runner 以 `SANDBOX_UNAVAILABLE` fail-closed，"execution never silently falls through unconfined"。原生 Landlock 启动器在 `native/landlock-run`（`@deepseek-ai/node-addon-landlock-run`，`sandbox-local/README.md:17`）。
- **文件系统围栏**：`fs-sandbox` 扩展 `fs-local`，按 per-call mode+工作区根做路径围栏（read-only 拒绝写、workspace-write 限制在会话工作区+临时根）（`packages/fs/README.md:12`）；`fs-observation-policy` 是 read-before-edit + 版本守卫的策略门插件（`packages/fs/README.md:13`）。
- **代码执行**：`code-runtime/`（缝，`ctx.codeRuntime`）+ `code-runtime-worker-thread`：每个程序一个全新 `worker_threads.Worker`，"**Containment, not a security boundary**"（`code-runtime-worker-thread/README.md:5`），含空环境、堆上限、`computeMs`（实测忙时预算）+`maxWallMs`+`maxOutputBytes`（64MiB）三预算（`README.md:23-29`）；对应 Code Mode（`run_code` 工具 + 按语言生成的类型化 SDK，`core/tools/README.md:116-125`）。Python 侧另有 `code-runtime-python` 后端（`packages/code-runtime/README.md:10`）。
- **其他执行面**：`subprocess/`（可脱离进程树、node-pty、集合/落盘，`packages/subprocess/README.md:9-10`）、`terminal/`（持久 owner 作用域 PTY 会话，`packages/terminal/README.md:5-11`）、`shell/`（bash-local/bash-sandbox/pwsh 执行器，`packages/shell/README.md:9-15`）、`e2b/`（POC：把 fs/subprocess 世界整体放入 E2B 远端 Linux 沙箱，`packages/e2b/README.md:5-13`）。

## 8. Web/桌面交付与运行时分拆

**Host/Client 双半架构**是 DSH 的关键分拆：进程内 Node 侧叫 Host（`packages/host/README.md:5` "The host side of the dsh web GUI: the API gateway every client shape shares, and the plain HTTP server it rides on"），浏览器侧叫 Client（`packages/client/README.md:5` "The browser side of the dsh web GUI: shell boot, browser-host communication, shared UI services, and feature plugins"）。二者通过 Typert RPC（`api/gateway`，`packages/api/README.md:5-12`）通信。

- **启动链**：`dsh web`（= `--profile web`，`apps/cli/README.md:13`）→ base bundle + web-app bundle（`packages/bundle/web-app/cordis.patch.yml`）→ `host/webserver` 起 HTTP（默认 `127.0.0.1:3080`，`cordis.patch.yml:127-130`）→ `host/frontend-static` 提供 SPA dist（`packages/host/README.md:11`）→ `client/modules`（`ClientModuleRegistry`）注入启动清单。
- **`window.__DSH_BOOT__` 注入**（本任务重点）：`packages/client/modules/src/index.ts:252-286` 的 `injectBootManifest()` 把客户端入口图（entry graph）序列化为 `<script>window.__DSH_BOOT__ = ${json}</script>` 注入 index.html 头部（`index.ts:281`），同时注入 `window.__ModuleLoader__` 排队 facade（`index.ts:255-276`）；`ClientModuleRegistry` 扫描 `dsh.client` 声明、把 bundle 路由挂到 `/plugins/<id>/client.js`（`index.ts:295-360`）。浏览器侧 `packages/client/web/src/boot.ts:46-58`：`AppWebEntry.run()` 读 `win.__DSH_BOOT__` 与 `win.__ModuleLoader__`，创建客户端模块系统 → 预取 `immediately` 层 → 挂载 vendored Cordis Loader（`loader.internal = this.modules`，`boot.ts:100`）→ 等待所有 entry 激活 → 交给 `uiRenderer.mount()`（`boot.ts:80-85`）。这也是系统提示"apps/web Vite 入口不是独立应用"的原因——没有 `dsh web` 注入 `__DSH_BOOT__` 就无法启动（`packages/bundle/web-app/src/index.ts:151` 亦有此说明）。
- **浏览器↔Host 传输**：`client/connection`——`/api` 单一路由 + Fetch 桥；unary 用 HTTP POST，下行事件用两条 WebSocket：`/api/events.mux` 与 `/api/events.host`（`packages/client/connection/README.md:5,13`）。`/api` 有浏览器信任围栏：必须 loopback 权威或匹配 `trustedHosts`，防 DNS rebinding（`connection/README.md:9`）。
- **桌面端**：`apps/desktop/README.md:5`——Electron 主进程启动 `dsh web`（`--no-open`，README.en.md:79）、就绪检测、退出时停 Host、托盘保活；preload 暴露固定目录选择/插件中心方法（`README.md:71`、`apps/desktop/README.md:33-43`）；打包时在独立进程用 Electron Node 模式运行 staged 的 `@deepseek-ai/dsh` CLI（`apps/desktop/README.md:49-55`）。
- **构建面**：Host 与 Client 分别编译：`tsconfig.host.json` / `tsconfig.client.json` + `tsdown.config.ts:5-25`（`DSH_BUILD_FACE` 决定是 host 全量构建还是 client 浏览器 bundle 构建）；客户端插件热更新走 `pnpm run dev:web`（`package.json:148` `tsx scripts/dev-web.ts --poll`）。

## 9. 自动化：调度与后台任务

- **`schedule/`**（`packages/schedule/README.md:5-11`）：会话本地提醒，持久状态就在原会话日志里（无独立数据库、无公开服务）；进程本地 timer 只在会话有存活 root Agent 时等待，冷会话恢复时补跑到期工作；到期任务经 Agent 普通 follow-up 队列进入同一对话（demo：`examples/web-schedule/`）。
- **`jobs/`**（`packages/jobs/README.md:5-13`）：通用后台任务运行时——`jobs`（`ctx.jobs` 注册表+生命周期契约）、`jobs-local`（进程内实现）、`tool-jobs`（`job_*` 控制工具：观察/取消/等待/完成通知）。用途：长耗时的工具（如后台 bash）以 owner 隔离的 job 协议运行（`packages/shell/README.md:14` tool-bash 集成后台 job）。
- **子 Agent 后台化**：`subagent/README.md:106`——模型侧委派工具默认同步收集；后台委派注册为普通 Task（job），另有 durable 的 **continuable 子 Agent**（`startContinuable`，冷恢复、`send_message` 跟进、`interrupt` 中止，`packages/subagent/subagent/README.md:19-27`）。工作流引擎 `workflow/` 以 worker thread 隔离执行模型编写的编排脚本（`packages/workflow/README.md:9-12`）。

## 10. 开发者体验：如何扩展与构建/测试

- **加工具**：任何 Cordis 插件调 `ctx.tools.register(defineTool({...}))`，schema 自动进系统提示词（`core/tools/README.md:57,65-91` 给出 `defineTool` 完整示例）；工具可带 `presentCall/presentResult` 渲染意图供 UI 使用（`core/tools/README.md:109-114`）。加 Skill：在 skill 目录放 SKILL.md 由 `skill-filesystem` 发现，或用 `dsh plugin` 装 Skill Pack（`packages/skill/README.md:9-12`）。加插件：写 bundle patch 层或经插件中心装 npm 包（第 6 节）。
- **示例**：`examples/` 六个可运行叶子（`examples/README.md:3-20`）：`headless-agent`（一次性任务出结果）、`jsonrpc-agent`（Python SDK 驱动）、`web-cordis`（自引用改自身插件树）、`web-schedule`（会话内提醒）、`acp-agent`（ACP 自动化服务端，含数十个 `cordis.yml` 组合变体）、`mcp-memory`（三个第三方记忆 MCP 服务器 overlay）。每组一个 `cordis.yml`，可用 `pnpm run demo:*` 或 `dsh web --patch ...` 运行。
- **构建**：tsc 项目引用 + tsdown 打包（host/client 双面，`package.json:22-24`）；`scripts/build.ts` 官方装配；大量生成/校验脚本（`package.json:68-135`：tool-catalog、cordis-catalog、module-graph、persistence-catalog 等均"生成+CI 校验"成对）。
- **测试**：Vitest 为主（`package.json:37` `vitest run`），外加 e2e（`vitest.e2e.config.ts`）、快照（`vitest.snapshot.config.ts`）、Web 快照/性能/压力（`vitest.web*.config.ts`）、GUI（`test:gui` 跑 client+host）；`vitest.config.ts` 对文件级 100% 覆盖率有门禁（配合 `scripts/coverage-uncovered-locations.cjs` 报告未覆盖行）；Windows 上 bash 依赖套件被排除、pwsh 套件保留（`vitest.config.ts:26-38`）。类型检查 `tsc -b tsconfig.host.json` + client；lint 用 oxlint；CI 门禁集中在 `scripts/run-gates.ts`（`package.json:54-67`）。

---

## DSH 核心事实清单（60 词）

DSH 是基于 vendored Cordis 的插件式 Agent Harness，"一切皆插件"（AGENTS.md:3）。Agent 抽象（dsh-agent）与唯一具体循环（dsh-agent-loop）分离，循环由 turn/step 两级驱动，每个请求从 append-only 事件日志派生。工具走 pre/execute/post/result 管线；中间件即 Cordis waterfall。子 Agent、工作流、沙箱（bwrap/Landlock/Seatbelt）、Web GUI（Host/Client 双半，window.__DSH_BOOT__ 注入）全部插件化，桌面端由 Electron 监督本地 dsh web。
