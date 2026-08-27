# WorkBuddy 自动化任务学习笔记

> 日期：2026-08-27  
> 来源：对照完整版 WorkBuddy 客户端（`~/.workbuddy`、安装包内 `workbuddy-server`）与本仓库 **ZR WorkBuddy** 现状整理。  
> 用途：后续在 ZR WorkBuddy 实现「定时唤醒 Agent 干活」时的设计参考。

---

## 1. 产品机制（用户视角）

自动化任务（Automations）是 WorkBuddy 的**定时调度能力**：到点后，客户端带着预设指令**自动跑一遍 Agent**——相当于「定时唤醒一个我」去干活，可读文件、跑命令、联网查资料、生成报告等。

| 维度 | 说明 |
|------|------|
| **存储** | 本地 SQLite：`~/.workbuddy/workbuddy.db` |
| **触发** | WorkBuddy 客户端（Electron 主进程）按计划扫描并执行 |
| **执行范围** | 可指定 **workspace（cwd）**，Agent 在该目录下操作项目文件 |
| **创建方式** | 用户用自然语言描述；Agent 通过 **`automation_update` 工具**建任务 |

### 1.1 两种调度类型

| 类型 | 字段 | 说明 | 示例 |
|------|------|------|------|
| **循环执行** | `schedule_type = recurring` + `rrule` | 按 RRULE 重复 | 每天早上 9 点汇总昨天工作日志 |
| **单次执行** | `schedule_type = once` + `scheduled_at` | 指定时间点跑一次 | 明天下午 3 点提醒开会 |

还可设置 **生效区间** `valid_from` / `valid_until`，例如「3 月 18 日到 3 月 22 日期间每天跑」。

### 1.2 适用场景示例

- **定时巡检**：每天早上扫描客户项目交付目录，生成变更摘要  
- **知识库整理**：每周拉取乐享知识库新增内容做周报  
- **提醒类**：客户节点前一天的下午提醒准备材料  

### 1.3 自然语言创建示例

> 「每天早上 8 点半，帮我看一下 xx 目录有没有新文件，汇总发给我」

Agent 会确认任务内容、时间规则和作用范围后写入数据库；用户可随时查看、修改、暂停或删除。

---

## 2. 完整版实现架构

### 2.1 整体分层

```text
┌─────────────────────────────────────────────────────────────┐
│ 创建阶段（对话里）                                            │
│  用户自然语言 → CLI Agent → automation_update MCP 工具 → DB  │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 调度阶段（Electron 主进程）                                   │
│  SchedulerEngine（每 30s tick）→ AutomationMainService       │
│  → 到期且 ACTIVE → startAutomationRun                        │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│ 执行阶段（后台会话）                                          │
│  executeRunHandler → 创建 is_background_automation 会话      │
│  → CodeBuddy CLI（按 cwd）→ 结果写入 automation_runs / 收件箱 │
│  → 可选：微信/企微推送（automation_delivery_outbox）          │
└─────────────────────────────────────────────────────────────┘
```

源码包路径（从安装包 `app.asar` 反推）：`packages/workbuddy-server/src/automation/`。

### 2.2 数据模型（SQLite + Drizzle 迁移）

迁移文件参考：`~/.workbuddy/.workbuddy-sqlite-migrations/0000_workbuddy_sqlite_baseline.sql`。

| 表 | 作用 |
|------|------|
| `automations` | 任务定义：name、prompt、status、schedule_type、rrule、scheduled_at、valid_from/until、cwds(JSON)、model、push 开关、owner 等 |
| `automation_runtime_state` | 运行时：running、last_run_at、queued、missed_pending、progress、running_conversation_id 等 |
| `automation_runs` | 执行历史 / 收件箱（`thread_id` 为主键） |
| `automation_delivery_outbox` | 推送出站队列（微信等，带重试与 lease） |
| `sessions` | 普通会话；自动化产生的会话带 `is_background_automation = 1` |
| `workspaces` | 最近打开的工作目录 |

#### `automations` 核心字段

| 字段 | 含义 |
|------|------|
| `id` | 主键 UUID |
| `name` | 展示名 |
| `prompt` | **仅任务内容**（不含时间、目录；调度信息单独字段） |
| `status` | 如 `ACTIVE` / 暂停等 |
| `schedule_type` | `recurring`（默认）或 `once` |
| `rrule` | 循环规则，如 `FREQ=DAILY;BYHOUR=9;BYMINUTE=30` |
| `scheduled_at` | 单次任务的 ISO 8601 时间 |
| `valid_from` / `valid_until` | 生效区间（ISO 8601 日期或日期时间） |
| `next_run_at` / `last_run_at` | 下次 / 上次执行时间（Unix ms） |
| `cwds` | JSON 数组，工作目录列表 |
| `model_id` / `model_is_thinking` | 可选指定模型 |
| `skills_json` / `connector_ids_json` | 可选 Skill / Connector |
| `push_to_wechat` / `push_to_wecom_bot` | 结果推送开关 |
| `owner_user_id` / `owner_status` | 多用户归属 |
| `deleted_at` | 软删除 |

#### RRULE 示例（系统内部生成）

```text
FREQ=HOURLY;INTERVAL=1;BYDAY=MO,TU,WE,TH,FR,SA,SU
FREQ=DAILY;BYHOUR=9;BYMINUTE=30
FREQ=WEEKLY;BYDAY=MO;BYHOUR=10;BYMINUTE=0
FREQ=MONTHLY;...
```

`computeNextRunAt()` 根据 rrule、valid_from/until、last_run_at 计算 `next_run_at`。

### 2.3 创建：`automation_update` 工具

系统提示（`welcomemode` / `workbuddy-prompt.tpl`）规定 Agent 行为：

- 用 **`automation_update`** 做 create / update / view / delete（`mode="delete"` + `id`）
- **禁止**用 `rm`、`sqlite3`、shell 等直接改库
- 识别「每天 / 每周 / 定时 / 明天下午 3 点」等语义，即使用户没说「自动化」也应建任务
- `prompt` 只写任务本身；时间、工作目录映射到 `rrule`/`scheduled_at`、`cwds`

工具通过 **connector-proxy MCP**（本机 `http://127.0.0.1:.../mcp`）暴露；前端有 `automation_update_tool_result` 专用渲染。

### 2.4 调度：`SchedulerEngine`

文件：`scheduler-engine.ts`。

| 项 | 值 |
|----|-----|
| 轮询间隔 | **30 秒**（`RUN_TICK_MS = 30000`） |
| 启动 | `AutomationMainService.initialize()` → `scheduler.start()` |
| 每 tick | `listAutomations()` → 过滤 ACTIVE → `shouldRunNow()` → `onAutomationDue()` |

**shouldRunNow 条件（摘要）**：

- `status === ACTIVE`
- 未在 running / queued
- `next_run_at` 有效且 `<= now`
- `last_run_at < next_run_at`（防重复）

**AutomationMainService 额外能力**：

- 休眠/唤醒 **resume sweep**（`AutomationPowerLifecycle`）
- **错过执行窗口**（missed + recovery jitter，24h 窗口内可补跑）
- 未登录 → `waiting_login`，登录后再跑
- `valid_until` 过期 → expire
- 并发限制 + `pendingAutomationQueue` 排队
- 同 identity 去重（只跑 canonical 一条）

### 2.5 执行：`startAutomationRun` → 后台 Agent 会话

1. `runCoordinator.tryStartRun` 控并发  
2. 对 `automation.cwds` 中**每个工作目录**起一个 sub-run（`totalCount = cwds.length`）  
3. 调用 `executeRunHandler({ cwd, prompt: automation.prompt, automationMeta, ... })`  
4. Electron 创建会话：`isBackgroundAutomation: true`，cwd 指向指定 workspace  
5. 将 `prompt` 作为用户消息交给 **CodeBuddy CLI**（与正常对话同一套能力）  
6. 结果写入 `automation_runs`、更新 `automation_runtime_state`  
7. 可选：enqueue `automation_delivery_outbox` 推微信/企微  

**结果判定**：除 assistant 文本外，还识别 artifact 上传、本地文件变更、外部 action 等 evidence；无有效输出可能记为失败。

### 2.6 与「自动化部署」的区别

| 能力 | 自动化任务（Automations） | 自动化部署（本仓库功能 10） |
|------|---------------------------|------------------------------|
| 触发 | 定时 / RRULE | **人确认**后触发 |
| 目的 | 定时跑 Agent 指令 | 触发 CI / SSH 发版 |
| 存储 | `workbuddy.db` automations 表 | `settings.json` + deploy API |
| ZR 状态 | 未实现 | 已实现 |

---

## 3. 实现流程（端到端）

### 3.1 创建任务

```text
用户：「每天早上 8 点半扫 xx 目录，汇总新文件」
  → Agent 解析：name / prompt / rrule / cwds
  → automation_update(mode=create, ...)
  → 写入 automations 表，计算 next_run_at
  → 前端展示 automation_update_tool_result 卡片
```

### 3.2 定时触发

```text
SchedulerEngine.tick()（每 30s）
  → AutomationMainService.onAutomationDue(automation)
  → decideDueAutomation()（missed / waiting_login / expire / run）
  → startAutomationRun()
  → executeRunHandler() × len(cwds)
  → 后台 CLI 会话执行 prompt
  → handleExecutionResult() → finalizeRunAggregate()
  → inbox + runtime_state 更新 + 可选推送
```

### 3.3 查看 / 修改 / 删除

```text
用户：「把我那个巡检任务改成每周一」
  → automation_update(mode=view) 查现有
  → automation_update(mode=update, rrule=...)
  → 或 mode=delete + id
```

---

## 4. ZR WorkBuddy（本仓库）现状

| 能力 | 状态 | 说明 |
|------|------|------|
| Automations / RRULE / workbuddy.db | ❌ 未实现 | 无对应表、API、调度器 |
| 「自动化部署」 | ✅ 另有功能 | 见 [`../功能实现/10-人触发预发部署.md`](../功能实现/10-人触发预发部署.md) |
| 资料包日同步 | ✅ 弱类比 | [`../MES业务/每日打开自动同步资料包.md`](../MES业务/每日打开自动同步资料包.md)：启动/打开设置时按日同步，不可用户配置、无 RRULE |
| local_dev jobs | ✅ 弱类比 | `apps/local_dev/jobs.py`：写码任务状态机，**无定时触发** |
| 对话主环 | ✅ | `POST /api/chat/stream` + Deep Agents，可被自动化「唤醒」复用 |

桌面壳 `desktop/main.js` 仅拉起 API + 前端，**没有** `AutomationMainService`。

---

## 5. ZR 落地建议（待实现）

完整版是 **Electron 主进程调度 + CLI 后台会话**；ZR 是 **Electron + 内嵌 FastAPI + Deep Agents**，建议映射如下。

### 5.1 存储层

| 方案 | 说明 |
|------|------|
| A | `DATA_DIR` 下 SQLite，表结构与 WorkBuddy 对齐（便于以后互通） |
| B | 先 JSON + 原子写入（与 `local_dev/jobs` 风格一致），P0 更快 |

### 5.2 调度层

- API 进程内后台线程（类比 `apps/agent/mes_profile_daily_sync.py` 的 `schedule_daily_sync_openapi`）  
- 或 Electron `main.js` 定时调 `POST /api/automations/tick`（更接近完整版「客户端负责调度」）

### 5.3 执行层

- 到期后内部调用 `stream_chat(automation.prompt, workspace=..., thread_id=...)`  
- 会话标记背景自动化 / 独立 thread；结果落盘 + 前端「自动化收件箱」  
- **高风险写操作仍走现有确认卡**（与 [`../功能实现/00-总览与架构分流.md`](../功能实现/00-总览与架构分流.md) 一致）

### 5.4 创建层

- 对话增加 Tool：`automation_update`（或 Agent Skill 引导）  
- 可选：设置页 / 独立「自动化」列表 UI  

### 5.5 产品决策（P0 范围建议）

可先只做：**recurring + 单 cwd + 对话创建 + 列表查看**，不做微信推送。

需单独决策是否 P0：

- 微信/企微推送（`automation_delivery_outbox`）  
- 多 cwd 并行、missed recovery、owner 多用户隔离  
- 是否共用 `~/.workbuddy/workbuddy.db` 还是 `DATA_DIR` 独立库  

---

## 6. 本仓库可参考落点

| 层次 | 现有文件 | 自动化可借鉴 |
|------|----------|--------------|
| 弱定时 | `apps/agent/mes_profile_daily_sync.py` | 后台线程、按日 stamp、失败冷却 |
| 任务状态机 | `apps/local_dev/jobs.py` | job 落盘、status 流转 |
| 对话执行 | `apps/api/agent_wrapper.py` | `stream_chat` 无 UI 调用 |
| API 启动钩子 | `apps/api/main.py` | lifespan 里挂调度器 |
| 桌面壳 | `desktop/main.js` | 可选主进程 tick |

---

## 7. 附录：调研来源

| 来源 | 路径 / 说明 |
|------|-------------|
| 本地数据库 | `~/.workbuddy/workbuddy.db` |
| SQLite 迁移 | `~/.workbuddy/.workbuddy-sqlite-migrations/` |
| 系统提示 | `~/.workbuddy/plugins/.../welcomemode/*/prompt.tpl`；安装包 `workbuddy-prompt.tpl` |
| 调度/服务逻辑 | `/Applications/WorkBuddy.app/.../app.asar` 内 `workbuddy-server/src/automation/*` |
| 运行日志 | `~/.workbuddy/logs/*/workbuddyMainThread*.log`（`AutomationMainService`、`AutomationPowerLifecycle`） |

---

## 8. 示例：场景拆字段

用户：「每天早上 8 点半，帮我看一下 `/data/delivery/acme` 有没有新文件，汇总发给我」

| 字段 | 示例值 |
|------|--------|
| `name` | ACME 交付目录晨检 |
| `prompt` | 扫描交付目录中的新文件与变更，生成简明摘要（含路径、时间、变更类型）；若无变更则说明「无新文件」。 |
| `schedule_type` | `recurring` |
| `rrule` | `FREQ=DAILY;BYHOUR=8;BYMINUTE=30` |
| `cwds` | `["/data/delivery/acme"]` |
| `status` | `ACTIVE` |

注意：`prompt` 里不写「每天 8:30」和目录路径——这些由 `rrule`、`cwds` 承担。
