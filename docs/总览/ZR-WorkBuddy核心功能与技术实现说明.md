# ZR WorkBuddy · 核心功能与技术实现说明

> 日期：2026-08-21（P0-01 话术降维 · P0-12 完成度口径）  
> 产品名：对外统一 **ZR WorkBuddy**  
> 定位：挂在已有 MES 上的「实施/运维微助手」——同一对话入口完成 **读懂资料包 → 查数分析（缺口透明）→ 运维值班 → 确认后写码改功能**（A/B/C/D **均为核心能力**）。  
> **对外承诺边界**：卖「懂资料包 + 能查能值班 + 能改码（确认后）+ 缺口说清楚」；**不卖**「全能 MES 大脑 / 已可承担多家厂生产变更责任的平台」。  
> **完成度**：**四块能力都齐 ≠ 产品完成**；演示须 A/B/C 与缺口一并打穿，禁止只秀 D 写码。  
> 不替代 MES 本身，不默认直写生产库；深度追溯/全库聚合受制于现场 HTTP 接口是否齐（见 PCB 验收话术缺口表）。  
> 关联：[`MES懂行助手四块能力方案.md`](MES懂行助手四块能力方案.md)、[`领导演示核心功能清单.md`](领导演示核心功能清单.md)、[`WorkBuddy总体实现方案.md`](WorkBuddy总体实现方案.md)、[`问题与风险点确认清单.md`](问题与风险点确认清单.md)

---

## 1. 整体怎么搭的（框架与分层）

```text
┌─────────────────────────────────────────────────────────┐
│  交付层                                                  │
│  网页：Vue3 + Vite + Element Plus + ECharts             │
│  桌面：Electron 壳 + 内嵌 CPython 运行时 + 同上前端      │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────────┐
│  API 层：FastAPI + Uvicorn                               │
│  登录 / 对话流 / 历史 / 设置 / 资料包 / 写确认 / 写码审码 │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Agent 层：Deep Agents + LangChain/LangGraph + ChatOpenAI│
│  Tools（查数/摸底/运维/图表…）+ Skills（剧本）+ Middleware│
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     MES HTTP API   资料包文件    Cursor SDK（写码）
     （真业务数据）  （表结构/OpenAPI） Cloud / Local
```

| 层次 | 技术选型 | 作用 |
|------|----------|------|
| 前端 | **Vue 3**、**Vite**、**Vue Router**、**Element Plus**、**Axios**、**ECharts** | 对话 UI、配置页、图表/看板卡、SSE 流式 |
| 桌面 | **Electron 33** + **electron-builder** | 打 dmg；内嵌 Python + API + 前端，装完配 Key 可用 |
| 后端 API | **FastAPI**、**Uvicorn**、SQLite（会话历史等） | 鉴权、SSE 对话、资料包、写操作确认、写码/审码（核心能力） |
| 智能体 | **Deep Agents**、**LangChain OpenAI**、**LangGraph Checkpoint（SQLite）** | 工具调用、Skill 加载、会话状态（选型见 [`DeepAgents与DeepSeek-Harness技术选型分析.md`](../Agent开发/DeepAgents与DeepSeek-Harness技术选型分析.md)） |
| 写码执行 | **Cursor SDK**（Cloud Agent / Local Agent） | 确认后改仓或改本机沙箱目录 |
| 数据主路径 | MES/ERP **HTTP**（JWT + `entities.json`） | 查数/导出；可选只读 SQL（默认关） |

仓库主目录大致是：`apps/web`（前端）、`apps/api`（网关）、`apps/agent`（Agent/工具）、`apps/local_dev` / `apps/cursor_dev`（写码）、`desktop`（安装包）。

---

## 2. 产品壳（所有能力共用）

| 功能 | 怎么实现 |
|------|----------|
| 登录 | API 对接 MES/ERP 登录或本地鉴权；未登录进不了对话 |
| 系统配置 | 设置页 + `settings_store`：LLM Key、MES 资料包、接口账号、Cursor Key、只读 SQL 开关等 |
| MES 资料包 | `data/mes_profiles/{厂}`：表结构 MD、`openapi.json` → 生成 `entities.json`；换厂换包不写死实体 id |
| 对话 + 历史 | `POST /api/chat/stream`（SSE）；历史存 SQLite，按用户隔离 |
| 意图分流 | Agent 系统提示 + Skills（摸底 / 查数 / 运维 / 写码 / 审码），不确定时先澄清 |

**原则**：WorkBuddy 登录 ≠ MES 接口账号；查数必须单独配 MES 凭证。

---

## 3. 能力块 A · 很懂这个 MES

**做什么**：回答「平台能干什么、有哪些表/链路、术语什么意思」——依据**文档**，不假装查了实时库。

| 功能 | 实现要点 |
|------|----------|
| 人话能力地图 | `list_platform_capabilities` 等，表结构推断模块 |
| 场景表包 | `get_scenario_table_pack`：工单下达→入库等，按当前文档匹配表名 |
| 单表释义 / 术语 | `describe_schema_table`、`list_platform_glossary` |
| 文档 vs 接口 | `compare_schema_vs_catalog` |
| 导出摸底报告 | `export_schema_survey_report` → Markdown/Excel |
| 资料包自检 | `inspect_mes_profile`（缺什么说什么） |

**框架/落点**：Agent Tools + `schema_tool/*`；Skill 约束「摸底不走查数」。问「今天有多少工单」应路由到 **B**。

---

## 4. 能力块 B · 数据分析

**做什么**：自然语言查真数、指标口径、汇总、出图、PCB 运营看板、导出。

| 功能 | 实现要点 |
|------|----------|
| 明细查询 / 筛选 | `query_platform_data` → MES list API；filters 正确展开（含数组） |
| 汇总 | `summarize_platform_data`（当前多为页内分组 + caveat，全库聚合是后续 M1） |
| 指标口径 | `query_metric` + `metrics_default.json` / 资料包 `metrics.json` / `metric_packs/pcb.json` |
| 分析简报 / 运维场景 | `analyze_platform_brief`、`run_ops_scene` |
| 单图 | `render_analysis_chart` → SSE `chart` → **ECharts**（`AnalysisChartCard`） |
| 看板 + KPI + 下钻 | `render_analysis_dashboard` / `run_analysis_demo`（「打开 PCB 运营看板」）+ `ops_presentation`；前端 `AnalysisDashboardCard` |
| 枚举中文 | `value_labels`（展示中文，filters 仍英文码） |
| 导出 | `export_platform_data` → 绝对路径 |
| 可选只读 SQL | `readonly_sql`：白名单 + 仅 SELECT + LIMIT（默认关） |
| 每日同步资料包 | `mes_profile_daily_sync`：按日打开触发刷新 |

**框架/落点**：HTTP 主路径；前端 Vue + ECharts；SSE 在 `agent_wrapper` 把工具结果推成 `token` / `chart` / `dashboard`。

**边界**：无数据诚实缺口；禁止编造良率；页内条数 ≠ 全库总数（服务端聚合引擎尚未做完，见 [`通用BI与PCB分析里程碑.md`](../MES业务/通用BI与PCB分析里程碑.md)）。

---

## 5. 能力块 C · 协助运维

**做什么**：值班话术固化成 playbook，一句话跑标准链。

| 功能 | 实现要点 |
|------|----------|
| 急单 / 在制 / 未完工 | `run_ops_scene('urgent-backlog'|…)` |
| 值班简报 / 产线异常日报 | `ops-daily-brief`、`plant-exception-daily` |
| 接口通不通 | 沙箱探活（默认不打生产） |
| 谁导入了 / 失败原因 | `query_write_audit` + 审计文件 |
| 写操作确认 | HITL 确认卡；未确认零副作用 |
| 401 / 空目录 / 排障树 | 固定场景引导 |

**框架/落点**：`ops_playbook` + Skill `ops-query-playbook`；写确认走 `writes` 路由与前端确认卡。手册见 [`运维值班手册.md`](../MES业务/运维值班手册.md)。

---

## 6. 能力块 D · 加界面加功能（写码 / 审码）

**做什么**：对话澄清需求 → **确认后**才改代码；可审码；不合主干、不自动部署。

| 功能 | 实现要点 |
|------|----------|
| GitHub 写码 | Cursor **Cloud Agent**；仓库白名单；推工作分支 |
| 本机目录写码 | Cursor **Local Agent**（SDK sandbox）→ 快照 diff → 同步目标目录 + SQLite 闸门 |
| 截图对齐 | 视觉理解 + 选项/确认卡 |
| 审本机工程 | IDE Bridge 配对 VS Code，只读分批读源码出报告 |
| 审远程仓 | 浅克隆 + 分批审核 |
| 贴码讨论 | 分析粘贴代码，不落仓 |
| 写码后轻量查数 | `post_dev_query`（本机改完数据侧可抽检） |
| 写码后刷目录 | OpenAPI 合并进 `entities.json` |

**框架/落点**：`apps/cursor_dev`、`apps/local_dev`、`cursor-sdk`；前端选仓卡 / 进度卡；与 Deep Agent 主对话分车道，避免误写。

---

## 7. 一次对话在系统里怎么走

1. 用户在 Vue 聊天框发话（可带附件）  
2. 前端 `streamMessage` → FastAPI `/api/chat/stream`  
3. `agent_wrapper` 跑 Deep Agent：选 Skill、调 Tools  
4. 工具打 MES HTTP 或读资料包 / 触发 Cursor Job  
5. SSE 推送：`status` / `step` / `token` / `chart` / `dashboard` / `confirm`  
6. 前端过程区 + 正文（流式）+ 图表卡；结束写入历史（含 charts/dashboards）

流式表格：生成中用等宽预排，结束后再渲染正式 HTML 表，减轻闪烁。

---

## 8. 当前水位 vs 明确不做

**已可演示（试点水位）**：A 摸底、B 查数/出图/PCB 看板/KPI 下钻（缺接口报缺口）、C 值班场景、D 本机/GitHub 写码与审码（核心能力；确认后改仓，不合主干/不自动部署）、双交付网页+桌面。

**还在路上**：通用 BI 的服务端聚合与时间维（M1）、真厂 WIP/Lot 等接口补齐、字段级权限、完整六看板校准、写码全自动测/合主干/部署、SSO/RAG 等企业底座。

**完成度口径（P0-12）**：**A/B/C/D 四块都能演示 ≠ 产品完成**。对外只称试点/内部交付；领导演示必须主动报真缺口（Lot/WIP 等），禁止「只秀写码」造成能力幻觉。

**明确不做 / 不对外宣称**：另做一套 MES；默认 NL2SQL 扫生产库；无确认默写数据或默改仓库；「全能 MES 大脑」或「已可多家厂承担生产变更责任」；「四块齐了就可以量产复制」。

---

## 9. 关键模块路径（便于对照代码）

| 区域 | 路径 |
|------|------|
| Agent 入口 | `apps/agent/agents/agent.py` |
| 查数 / 指标 / 图表 | `apps/agent/tools/query_tool/` |
| 表结构摸底 | `apps/agent/tools/schema_tool/` |
| SSE / 工具标签 | `apps/api/agent_wrapper.py` |
| API 路由 | `apps/api/main.py`、`apps/api/routes/` |
| 对话前端 | `apps/web/src/views/ChatView.vue` |
| 图表 / 看板卡 | `apps/web/src/components/AnalysisChartCard.vue`、`AnalysisDashboardCard.vue` |
| 本机写码 | `apps/local_dev/` |
| GitHub 写码 | `apps/cursor_dev/` |
| 桌面打包 | `desktop/`、`scripts/package-desktop.sh` |

---

## 10. 演示与验收文档

| 文档 | 用途 |
|------|------|
| [`领导演示核心功能清单.md`](领导演示核心功能清单.md) | 给领导演示的话术与勾选表 |
| [`PCB数据分析验收话术.md`](../MES业务/PCB数据分析验收话术.md) | B / PCB 细验收 |
| [`MES摸底固定话术.md`](../MES业务/MES摸底固定话术.md) | A 摸底 10 句 |
| [`运维值班手册.md`](../MES业务/运维值班手册.md) | C 值班场景 |
| [`通用BI与PCB分析里程碑.md`](../MES业务/通用BI与PCB分析里程碑.md) | B 升级路线 |
