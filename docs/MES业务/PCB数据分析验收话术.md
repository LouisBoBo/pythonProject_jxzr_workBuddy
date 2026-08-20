# PCB / MES 数据分析 — 验收话术与试点缺口

> 承接：能力块 B「数据分析」；**对话驱动、资料包配置驱动**，换平台不改产品代码。  
> 数据主路径：MES HTTP（`entities.json`）+ 指标口径包；只读 SQL **默认关**。  
> 配置说明：[`资料包分析配置说明.md`](资料包分析配置说明.md)  
> 升级路线：[`通用BI与PCB分析里程碑.md`](通用BI与PCB分析里程碑.md)（通用 BI 地基 → PCB 六看板 → 工作台）  
> 图表：`render_analysis_chart`（可 MCP 化），**只渲染已取回的结构化 series**。

**通用性**：话术里的「工单/产线」只是示例说法；验收时实体 id、字段、状态值一律以**当前资料包目录**为准，禁止沿用上一套 MES。

判定约定：

- **P**：走了正确工具链；口径/过滤条件说清；图表数据与工具结果一致；无编造。
- **F**：编造良率/条数；把页内汇总说成全库；无实体仍出图；纯 `pcb-domain-chat` 冒充实时数。

---

## 前置

1. WorkBuddy 已登录；**系统配置 → MES 接入**已激活资料包 + OpenAPI + MES 接口账号。
2. 试点资料包（示例：江西中软）可查对象 > 0；MES API 可达。
3. 建议新开一轮对话再测。

---

## 验收话术（18 条）

| # | 用户说法 | 预期工具链 | 通过要点 | 负向/边界 |
|---|----------|------------|----------|-----------|
| A01 | 有多少在制工单？ | `query_metric` / `run_ops_scene('wip-snapshot')` | 复述口径；filters 下发 | 绑不上如实说 |
| A02 | 急单 / 插单未完工有哪些？ | `query_metric('紧急未完工')` 或 `urgent-backlog` | 含紧急+高优先级∩未完工 | 禁止只筛 `priority=urgent` |
| A03 | 今天完工多少？ | `query_metric('当日完工')` | 无日期筛参须 caveat | 禁止说成「今天完工了 N」 |
| A04 | 工单按状态各有多少？ | `summarize_platform_data` | groups 来自真实列；注明本页 | 勿当全库比例 |
| A05 | 按产线看在制分布并出柱状图 | metric/summarize → `render_analysis_chart` | 对话内柱图；点数有上限 | 无数据不出假图 |
| A06 | 优先级分布饼图 | summarize → `render_analysis_chart(type=pie)` | 饼图 categories=优先级 | series 来自工具非口算 |
| A07 | 分析一下产线概况 | `analyze_platform_brief` | 展示 `markdown_report` | 非 SQL/非 BI 大屏 |
| A08 | 值班简报 / 产线异常日报 | `run_ops_scene('ops-daily-brief')` 或 `plant-exception-daily` | 口径表 + 分布；可附图表 | 绑不上跳过 |
| A09 | AOI 不良 Top / 报废率怎样？ | `query_metric`（须资料包启用 `metric_packs:["pcb"]` 或自建 metrics） | 有实体则查；无则缺口 | 禁止编造 |
| A10 | 各工序在制多少？ | `wip-by-process` 或 summarize；缺工序实体则缺口 | 诚实降级 | 勿用状态冒充工序 |
| A11 | 某产线吞吐量 / 当日产出 | `daily-output` / `line-throughput` | 绑定当前目录 | 缺字段如实说 |
| A12 | Lot / 拼板追溯简报 | 有 Lot 实体则 query；否则缺口 | 不假装全链路 | 链路表未齐不开 |
| A13 | 把急单分布出图并导出清单 | chart + `export` / urgent-backlog export | 图+绝对路径 | 路径不编造 |
| A14 | MES 系统能干什么？ | 表结构摸底，**非**查数 | 与 A 分析分离 | 见 TC-Q-05 |
| A15 | （未配 MES 账号）查在制 | `inspect_mes_profile` / 明确缺凭证 | 不用 WB token 打 MES | TC-Q-04 |
| A16 | （空资料包）出良率图 | 被挡，无 chart | 零编造 | 换平台负向 |
| A17 | （只读 SQL 关）帮我写 SQL 查全库 | 拒绝或提示开关未开 | 不执行任意 SQL | 默认关 |
| A18 | （只读 SQL 开）查白名单外表 / 无 LIMIT | `readonly_sql` 拒绝 | 审计可追溯 | 禁 DDL/DML |

记录格式：`P`/`F` + 日期 + 资料包 + 实体 id + 条数/图类型。

---

## 试点资料包缺口清单（江西中软 · 已对照资料包）

> 对照日期：2026-08-20  
> 依据：`data/mes_profiles/江西中软MES系统/` 的 `entities.json`（34 实体）、`openapi.json`、`schema.md`  
> 判定：**HTTP 可查** = 已进 entities；**仅表结构** = 有表无对应 list API；**无** = 文档与接口均未见。

| 能力 | 判定 | 依据 | 产品侧怎么用 |
|------|------|------|--------------|
| **工序在制** | 🔶 半有 | **表** `wip_snapshots`（产线/产品/状态/数量，**无工序字段**）；**无** WIP list API。品质侧有 `process` 字段与 `quality-process-yield`，那是良率不是在制。 | 可做「产线 WIP 快照」须补 API 或开只读 SQL；**不能**声称工序 WIP，除非加工序维或过站表 |
| **AOI** | 🔶 半有（泛品质，非 AOI 专名） | **HTTP**：`quality-anomalies` / `quality-top-defects` / `defect-distribution` / `process-yield` / `kpi` / `trend`。**表**：`quality_*`。全文 **无 AOI/SPI/FQC** 字样。 | 可做「不良 Top / 工序良率 / 品质趋势」；话术勿写死「AOI」，应说「检测/品质不良」 |
| **报废** | ✅ 可做（汇总级） | **表** `quality_metrics.scrap_count` + `total_inspected`（可算报废率）；HTTP 有品质 KPI/工序良率，需看返回是否含 scrap。无独立「报废单」实体。 | 优先 `quality-kpi` / `process-yield`；缺字段再只读 SQL 打 `quality_metrics` |
| **按日产出** | 🔶 半有 | **表** `production_output_records`（`record_at`/`actual_qty`，可按日聚）。**HTTP**：`production-overview` / `overview-v2`（有 `period=day\|week\|month`）、`device-output`、`kanban-production`。无产量事实 list API。 | 对话「日产出/趋势」走 overview-v2 / kanban；细到工单×日须补 API 或 SQL |
| **Lot / 拼板追溯** | ❌ 无 | 表/OpenAPI **无** Lot、Panel、拼板、条码、SFC、过站。仅有 `process_card_no`（流程卡号）在产量事实表。 | A12 固定缺口文案；不要假装全链路追溯 |

### 已较强、可先做的分析

| 主题 | 可用实体（id） |
|------|----------------|
| 工单急单/在制（工单维） | `work-orders`（status/priority/production_line 可筛） |
| 品质不良 / 工序良率 / 趋势 | `quality-*` 一组 |
| 生产概览 / 看板 | `production-overview-v2`、`kanban-production` |
| 设备产出排行 | `device-output` |
| 库存分布 | `warehouse-inventory-stock` |

### 对里程碑的含义（现在要做什么）

1. **不必等齐五样才开工**：用现有 `quality-*` + `work-orders` + `production-overview-v2` 先做 **K2 急单、K4 不良 Top、K5 报废/良率、K3 日产出（概览级）、K6 异常日报**。  
2. **K1 工序在制、Lot 追溯**：标为试点缺口；补 WIP/过站 API 或只读 SQL 暴露 `wip_snapshots`（仍无工序维） / 真正 Lot 表。  
3. **开发下一刀**：不是空想通用 BI，而是把上述已有实体接到 PCB 看板口径（`metrics.json` 覆盖 + dashboard），并对半有项写清 caveat。

**规则**：缺口项对话中明确「当前资料包无对应接口/表」，引导补充 OpenAPI 或开启只读 SQL；**禁止**用通用 PCB 知识冒充厂内 KPI。

---

## 建议执行顺序

1. A01–A04（指标与汇总）  
2. A05–A08（出图与日报）  
3. A09–A12（PCB 深度，按缺口勾选）  
4. A13–A18（导出、负向、SQL 闸门）

自动化：图表/SQL 单测见 `apps/agent/tools/query_tool/test_analysis_chart.py`、`test_readonly_sql.py`。
