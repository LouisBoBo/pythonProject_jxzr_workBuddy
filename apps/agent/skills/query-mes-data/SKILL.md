---
name: query-mes-data
description: >-
  查询 MES/ERP 平台数据时使用。实体与别名以当前资料包可查对象目录为准
  （通常由接口文档生成）。用户说「查一下」「看看有哪些」「统计」「各多少」MES/业务数据时启用。
  未配置资料包时须提示先去系统配置接入。
  注意：用户说「平台/系统能干什么」指 WorkBuddy，不是本 Skill。
---

# 查询平台数据

## 何时使用

- 用户要查业务列表/明细（以当前目录为准，不要写死工单/排产）
- 需要先弄清平台有哪些可查对象再查询
- 查询结果为空或失败，需要排查是否选错实体
- 用户要「按状态各多少」一类轻量汇总
- 用户问「在制」「未完工」「紧急单」「插单」「当日完工」「出图」等指标/分析
- 跨平台通用分析：Skill `analyze-mes-data`；PCB 可选扩展：`analyze-pcb-mes`（须资料包启用）

## 工具选用

1. 不确定实体、刚换平台、或资料是否齐全：先 `inspect_mes_profile(user_intent=用户原话)`
2. `missing` 挡住查数时：告诉用户去系统配置补接口文档/MES 接口账号，**不要编造列表或条数**
3. `can_answer_now=true` 后再 `list_platform_entities` / `query_platform_data`
4. 查列表：`query_platform_data(entity="<英文id>", filters=?, limit=?)`
5. 看字段：`describe_entity(entity="<英文id>")`（`filter_fields` 才是可下发的筛选名）
6. 轻量汇总：`summarize_platform_data(entity="<英文id>", group_by=?, filters=?)`
7. **分析简报**：`analyze_platform_brief(entity=?)`（分组标签来自资料包 analysis 配置）
8. **出图**：先有 groups/categories+values，再 `render_analysis_chart(groups=…, user_intent=用户原话)`；`chart_type` 默认 `auto`（趋势→折线、分布→饼、默认柱；用户点名最高优先）。**禁止**追问用户用什么图。前端自动出图，**不要**再贴 `markdown_fence`，**不要**再贴与图相同的完整分组表
9. 指标口径：先 `list_query_metrics`，再 `query_metric`；「紧急工单/急单/插单」用 `query_metric("紧急未完工")` 或 `run_ops_scene("urgent-backlog")`，**不要**只传 `filters={"priority":"urgent"}`
10. 产线/异常日报：`run_ops_scene("plant-exception-daily")`（口径随当前资料包，不写死实体）

`entity` **必须用英文 id**（来自当前目录），不要传中文。口径名用中文或 id 均可，**禁止**把其它 MES 的实体 id 写进口径查询。

## 实体对照

- **不要硬编码**工单/排产等旧演示实体；一律以 `list_platform_entities` 返回为准
- 同义说法映射到同一 id；查空或失败要如实说明，**不要改查另一个实体充数**
- 目录中没有的对象：告知待对接或需补充接口文档，不要冒充

## 筛选

带条件时传 `filters`（字段名以 `describe_entity.filter_fields` 为准，取值用用户原话或样例里出现过的值）。
工具会把 filters 作为 MES API 的 query 参数下发；**禁止**全量拉取后口头过滤，也**禁止**套用其它 MES 的字段名/状态值。

## 推荐回复结构

1. 说明查的是哪个对象：用户原话 + 中文 label + 英文 id
2. 条数：`total` / `returned`；有 `filters_applied` 须复述条件
3. 用工具返回的 `markdown_table`（或 `display_rows`）展示，列名用中文
4. 「各多少 / 按状态汇总」用 `summarize_platform_data` 的 `groups`，不要臆造字段或分组值
5. 「分析一下 / 概况 / 异常分布」用 `analyze_platform_brief`，展示 `markdown_report`
6. 「出图 / 分析一下并可视化」用 `render_analysis_chart(user_intent=用户原话)`，**勿问用柱/折/饼**；series 必须来自工具
7. 「在制 / 未完工 / 紧急未完工 / 当日完工 / 工序在制 / AOI / 报废」用 `query_metric`，先复述工具返回的 `definition` 与 `filter_sets`；绑不上就如实说，不要套 pending/work-orders
8. 若返回含 `caveats`（常见：当日完工接口无日期筛参）：**必须**把 caveat 说给用户，禁止说成「今天完工了 N 条」；只能说「按已完工状态查出 N 条，未能限定当天」
9. 用户要导出时走 `export_platform_data`，报绝对路径 `file` 和行数 `rows`
10. 「产线异常日报」优先 `run_ops_scene('plant-exception-daily')`

## 自检

- [ ] 目录非空；为空或缺 MES 接口账号则提示配置，不编造
- [ ] 换平台后是否按当前目录作答（未沿用上一套实体 id）
- [ ] entity 是否与用户意图一致
- [ ] 是否调用了查询工具（不要空口编数据）
- [ ] 带筛选条件时是否传了 filters（看工具返回的 filters_applied）
- [ ] 回复是否有中文列名、条数，而不是只贴原始 JSON（过程区也应能看到中文表预览）
- [ ] 「紧急工单/急单」是否走了 `query_metric("紧急未完工")` / `run_ops_scene("urgent-backlog")`，而不是只筛 `priority=urgent`
- [ ] 「当日完工」若有 `caveats`，是否如实说明未能限定当天（禁止说成今天完工了 N 条）
