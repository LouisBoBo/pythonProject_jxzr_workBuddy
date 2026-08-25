# 通用 BI + PCB 专业分析 · 开工里程碑

> 日期：2026-08-20  
> 产品：**ZR WorkBuddy** · 能力块 B 升级  
> 承接：[`MES懂行助手四块能力方案.md`](../总览/MES懂行助手四块能力方案.md)、[`PCB数据分析验收话术.md`](PCB数据分析验收话术.md)  
> 原则：**对话是入口，看板是阵地**；换平台靠资料包，禁止写死实体 id；无数据则诚实缺口，禁止编造 KPI。

---

## 0. 目标对照

| 目标 | 定义 | 当前水位 |
|------|------|----------|
| **轻量分析（已有）** | 对话查数 → 汇总 → 单图；资料包可换厂 | ✅ 主链路可用 |
| **通用 BI** | 语义维/度 + 服务端聚合 + 下钻看板 + 治理 | ❌ 未做 |
| **专业 PCB 分析** | 工序 WIP / 良率 / 报废 / 产出 / 追溯 + 六张行业看板 | 🔶 仅有 metric_packs 雏形 + 话术 |

**推荐主线**：P0 打稳聚合与时间维 → **选定一个试点厂跑绿 P1 六张看板** → P2 再上自助 BI 工作台。

---

## 1. 里程碑总览

```text
M0 基线冻结（1～2 天）
 → M1 聚合引擎 + 时间窗（通用 BI 地基）
 → M2 PCB 六看板 @ 试点厂（专业分析 1.0）
 → M3 下钻与多图工作台（通用 BI 交互）
 → M4 治理 / 订阅 / 多厂模板（可规模化）
```

| 里程碑 | 周期建议 | 退出标准（DoD） |
|--------|----------|-----------------|
| **M0** | 0.5～1 周 | 试点资料包缺口勾选完成；本清单任务已建跟踪 |
| **M1** | 1.5～2 周 | 服务端聚合可用；「今日/本周」有日期筛或明确 caveat；单测绿 |
| **M2** | 2～3 周 | 试点厂六看板可出真数或诚实缺口；A09–A12 记 P/F |
| **M3** | 2 周 | 点图查明细；一页 ≥3 图；收藏看板 |
| **M4** | 按需 | 字段权限 + 定时简报 + 第二家厂套模板 ≤1 天配置 |

---

## 2. M0 · 基线冻结（开工前）

| ID | 任务 | 仓库/落点 | Owner 建议 | 产出 |
|----|------|-----------|------------|------|
| M0-1 | 选定试点 MES 资料包（如江西中软） | `data/mes_profiles/{id}/` | 实施 | 激活资料包 + OpenAPI 已同步 |
| M0-2 | 勾选 [`PCB数据分析验收话术.md`](PCB数据分析验收话术.md) 缺口表 | 同左 | 实施 + 开发 | **江西中软已于 2026-08-20 对照 entities/OpenAPI/schema 填完** |
| M0-3 | 列出缺的 OpenAPI path 或只读表白名单 | 现场接口文档 / DBA | 实施 | 对接工单列表 |
| M0-4 | 确认是否开只读 SQL（默认关） | 系统配置 `mes_analysis` | 产品 | 开关决策记录 |
| M0-5 | 冻结验收话术 A01–A18 执行表 | 文档 | QA | 空表待填 P/F |

**不做**：并行开多厂；先堆图表类型。

---

## 3. M1 · 聚合引擎 + 时间窗（通用 BI 地基）

> 解决：「页内 20 条当全库」「今日完工无日期」两大硬伤。

| ID | 任务 | 模块路径 | 说明 | 验收 |
|----|------|----------|------|------|
| M1-1 | **服务端聚合 API 封装** | `aggregate.py` | 默认页内；实体可选 `aggregate` 声明走 MES stats；SQL 仍默认关 | ✅ 契约 + 单测；无声明不改行为 |
| M1-2 | `summarize_platform_data` 升级 | `platform_query.py` | 走 `aggregate_by_field`；页内 `caveats` 不可删；失败降级 | ✅ |
| M1-3 | **时间维契约** | `analysis_config` + `metrics_pack` + `query_metric` | `time_field_hints`；绑不上 → `time_filter_applied=false` + 强制 caveat | ✅ |
| M1-4 | 趋势 series 生成 | `time_series.py` + `analyze_time_trend` | 按日/周 buckets → 自动 `line`；无日期列诚实失败 | ✅ |
| M1-5 | 聚合结果上限与审计 | API / agent_wrapper | 点数、超时、SQL 审计日志 | ⬜ |
| M1-6 | 文档 | `资料包分析配置说明.md` | 增加 `time_field_hints` / 实体 `aggregate` / 趋势 | ✅ |

**依赖**：试点厂至少一个带日期的 list/聚合接口，或只读 SQL 可达。

---

## 4. M2 · PCB 专业分析 1.0（六张看板）

> 行业语义 + 试点厂真数；通用引擎之上叠 PCB 模板。

### 4.1 六张看板定义

| 看板 ID | 名称 | 主图 | 口径 / metric | 无数据时 |
|---------|------|------|---------------|----------|
| K1 | 工序在制 WIP | 横向柱 / 漏斗 | `wip-by-process` | 缺口文案 + 引导补过站实体 |
| K2 | 急单堆积 | 饼 + 明细表 | `urgent-unfinished` / `urgent-backlog` | 已有链路，校准枚举 |
| K3 | 日产出趋势 | 折线 | `daily-output` / 时间聚合 | 无日期则不出「今日」结论 |
| K4 | AOI/检测不良 Top | 帕累托柱 | `aoi-fail-topn` + 缺陷码分组 | 禁止编良率 |
| K5 | 报废构成 | 饼（引线标注） | `scrap-rate`（须投入分母） | 仅有报废单则标「件数非率」 |
| K6 | 产线异常日报 | 简报 + 1～2 图 | `plant-exception-daily` | 绑不上的指标跳过 |

### 4.2 任务拆分

| ID | 任务 | 模块路径 | 说明 |
|----|------|----------|------|
| M2-1 | 扩展 `metric_packs/pcb.json` | `metric_packs/pcb.json` + `build_measure_contract` | ✅ 补 `daily-output`、缺陷码 Top、报废分子/分母角色；仍用 `entity_hints` |
| M2-2 | 试点厂 `metrics.json` 校准 | `mes_profiles/江西中软…/metrics.json` + 入库模板 `metrics.jx-zhongruan.example.json` | ✅ 日产出→设备排行；不良/良率/工序在制（报表）覆盖；换厂勿照抄 |
| M2-3 | 看板编排配置 | `dashboard_templates/pcb_ops.json` | ✅ K1→在制品报表；K3→设备产量优先；顺序 K1–K5；Lot 仍缺口 |
| M2-4 | 看板渲染工具 | 新建 `tools/query_tool/dashboard.py`：`render_pcb_dashboard` / `render_analysis_dashboard` | 一次跑多 metric → 多 `chart_option` SSE |
| M2-5 | 前端多图卡片 | `apps/web/src/components/` + `ChatView.vue` | 支持一轮回复多图；可选简易 Dashboard 页 |
| M2-6 | Skill | `analyze-pcb-mes/SKILL.md`、`analyze-mes-data` | 「打开 PCB 运营看板」→ 调 dashboard；禁止追问图表类型 |
| M2-7 | **真良率/报废率** | metrics 条款 | 必须同时有不良数与投入/检验总数；否则降级为「不良件数」 |
| M2-8 | Lot/拼板简报（可降级） | query + 可选链路 markdown | A12：有实体则出，无则缺口 |
| M2-9 | 验收 | [`PCB数据分析验收话术.md`](PCB数据分析验收话术.md) A09–A13 | 试点厂填 P/F；缺口项勾选表更新 |

**DoD**：对话「打开 PCB 运营看板」→ K1–K6 有图或明确缺口；零编造良率。

---

## 5. M3 · 下钻与多图工作台（通用 BI 交互）

| ID | 任务 | 模块路径 | 说明 |
|----|------|----------|------|
| M3-1 | 图 → 明细 | SSE chart 带 `drill`: `{entity, filters}`；前端点击扇区/柱 | 打开同会话表格或侧栏 |
| M3-2 | 分析工作台页 | `apps/web` 新路由如 `/analysis` | 非纯聊天：筛选条 + 多图栅格 + 明细表 |
| M3-3 | 保存看板 | API `apps/api/routes/` + 用户/资料包级 JSON | 名称、filters、卡片列表 |
| M3-4 | 组合图 | `analysis_chart.py` | 双轴、堆叠柱（仍自适应防堆叠） |
| M3-5 | 导出分析包 | export 图表 PNG/数据 CSV + 简报 md | 绝对路径可追溯 |

**DoD**：从 K4 点某一缺陷码 → 看到对应检验明细列表。

---

## 6. M4 · 治理与规模化

| ID | 任务 | 模块路径 | 说明 |
|----|------|----------|------|
| M4-1 | 字段级权限 | 查询结果投影 + 资料包 `column_policy.json` | 隐藏金额/客户等；B8 |
| M4-2 | 查询审计 | 已有写审计旁路扩「读/聚合」摘要 | 谁查了什么、条数、耗时 |
| M4-3 | 定时/打开推送简报 | 复用每日资料包同步节奏或 cron | 「早班 PCB 简报」推对话或导出目录 |
| M4-4 | 第二家厂套模板 | 仅配资料包 + metrics overlay | ≤1 天可出同结构看板（缺实体则缺口） |
| M4-5 | 只读 SQL 多引擎 | `readonly_sql.py` | SQLite 外扩 Postgres/SQL Server（VPN）；表白名单 |

---

## 7. 仓库模块对照（便于派工）

| 区域 | 路径 | 相关里程碑 |
|------|------|------------|
| Agent 查数/汇总 | `apps/agent/tools/query_tool/platform_query.py` | M1 |
| 指标包 | `metrics_default.json`、`metric_packs/pcb.json`、资料包 `metrics.json` | M1–M2 |
| 分析配置 | `analysis_config.py`、资料包 `analysis.json` | M1–M2 |
| 图表 | `analysis_chart.py`、`AnalysisChartCard.vue` | M1–M3 |
| 看板（新建） | `dashboard.py`、`dashboard_templates/` | M2–M3 |
| 运维场景 | `ops_playbook.py`、`ops_scenes*.json` | M2 K6 |
| Skills | `analyze-mes-data`、`analyze-pcb-mes`、`query-mes-data` | M2–M3 |
| API / SSE | `apps/api/agent_wrapper.py`、`routes/` | M1–M4 |
| Web | `ChatView.vue`、可选 `/analysis` | M2–M3 |
| 设置 | `settings_store` / `mes_analysis` 组 | M1 SQL、M4 |
| 文档/验收 | `docs/MES业务/*` | M0、M2-9 |
| 单测 | `test_analysis_chart.py`、新建 `test_aggregate.py`、`test_dashboard.py` | 每里程碑 |

---

## 8. 非目标（本路线图明确不做）

- 替代 MES 报工/过站核心系统  
- 默认写生产库、任意 NL2SQL 无白名单  
- 多租户 SaaS 级语义中台（可放到更远期）  
- 用 `pcb-domain-chat` 常识冒充厂内 KPI  

---

## 9. 建议排期（单小队）

| 周 | 焦点 |
|----|------|
| W1 | M0 + M1-1～M1-3 |
| W2 | M1-4～M1-6；启动 M2-1～M2-2（对接缺口并行） |
| W3–W4 | M2 六看板 + 验收 A09–A13 |
| W5–W6 | M3 下钻与工作台 |
| 之后 | M4 按客户合同取舍 |

---

## 10. 即时开工清单（本周可勾）

- [x] M0 江西中软缺口对照（entities / OpenAPI / schema）
- [x] PCB 运营看板 `render_analysis_dashboard` + 内置 `pcb_ops`（单卡失败不拖垮；缺卡诚实缺口）
- [x] 江西中软 `analysis.json` 启用 `metric_packs: ["pcb"]`（仅本资料包）
- [x] 看板编排 `run_analysis_demo`（「打开PCB运营看板」；资料包 `demos/` 可覆盖；不抢占普通日报）
- [x] P0 运营大屏：顶栏 KPI（来自已出图/口径，不编造）+ 深色演示皮肤
- [x] P1 点图下钻：点击扇区/柱 → 侧栏明细（有 rows 才筛；否则提示对话追问）
- [ ] 对话冒烟：「打开PCB运营看板」→ KPI+深色四图；点急单饼图出明细
- [x] M1-1/1-2：通用聚合模块 + `summarize_platform_data` 强制页内 caveat；可选实体 `aggregate` 声明
- [x] M1-3：`analysis.time_field_hints` + 当日口径 `time_filter_applied` / 禁止「今天完工了 N」
- [x] M1-4：`analyze_time_trend` 日/周分桶 + 折线；无日期列诚实失败
- [x] **P1-03（2026-08-21）**：出图自动补「本页≠全库」caveat；服务端聚合禁止默认说成全库比例；只读 SQL 默认关不变
- [x] M2-1：扩展 `metric_packs/pcb`（daily-output / 缺陷 Top / 报废分子分母角色）
- [x] M2-2：江西中软 `metrics.json` 校准（日产出→设备排行；工序在制→在制品报表）
- [x] 看板六卡对齐：K1 报表工序在制、K3 设备产量优先、顺序 K1–K5 + Lot 缺口
- [ ] A09–A13 / 「打开PCB运营看板」对话冒烟
- [ ] M1-5：聚合上限与审计（按需）

---

## 11. 关联文档

| 文档 | 用途 |
|------|------|
| [`PCB数据分析验收话术.md`](PCB数据分析验收话术.md) | A01–A18 与缺口勾选 |
| [`资料包分析配置说明.md`](资料包分析配置说明.md) | metrics / analysis / packs |
| [`分析图表MCP说明.md`](分析图表MCP说明.md) | 图表仅渲染、可选 MCP |
| [`实施高频场景清单.md`](实施高频场景清单.md) | 对话话术模板 |
| [`MES查数测试用例.md`](MES查数测试用例.md) | 查数回归 |
