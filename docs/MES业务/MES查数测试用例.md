# MES 查数 — 测试用例

用于验收：登录 WorkBuddy 之后，能按**当前资料包**的接口文档查到真实业务数据。

**范围澄清（验收必读）**

- **WorkBuddy 登录**（登录页）与 **MES 接口鉴权**（系统配置里的接口账号）是两套，互不替代。
- 可查对象来自已导入的 OpenAPI，不写死 `/api/v1` 或某一套 MES。
- 「MES 系统能干什么」走表结构摸底，**不要**用本用例的查数结果冒充 MES 全量能力。

判定约定：

- **P（通过）**：调用了查询工具；实体 id 与用户说法一致；返回真实条数/字段（或如实说明 MES 侧为空）；无 HTTP 401。
- **F（失败）**：401/404；编造数据；用工单充数点检/计划；把 WorkBuddy token 当 MES token；未配置资料包却假装查到。

---

## 前置（每条用例默认具备）

1. 已用 **WorkBuddy 账号**登录（登录页，与 MES 接口文档无关）。
2. **系统配置 → MES 接入**已完成：
   - 平台名称（资料包已激活）
   - 已上传表结构 `.md`（本用例不测摸底，可已上传）
   - 已导入接口文档（`/docs` 或 `openapi.json`），可查对象数量 > 0
   - 已填写 **MES 接口账号 / 密码**；若该平台 OpenAPI 要求企业编码则已填（当前江西中软示例为必填，如 `江西中软`）
3. MES 业务 API 可达（查数根地址来自接口文档 `servers` / `source_url`，不是网页端口）。
4. 保存配置后已热更新；建议新开一轮对话再测。

当前联调资料包只是**示例**：换平台后实体 id、路径、筛选字段都以对话里 `list_platform_entities` 为准，勿把本页 id 写进产品逻辑。

---

## TC-Q-01 查主业务列表（主路径）

| 项 | 内容 |
|----|------|
| **功能** | F-QUERY-01 / F-QUERY-03 |
| **测试问题** | 查当前目录里的主业务列表（示例：「查生产工单列表」） |
| **预期工具** | `query_platform_data`；entity **以当前目录为准**（江西中软示例为 `work-orders`） |
| **期望要点** | ① 实体与用户说法一致，不拿别的对象充数 ② 有条数与关键列（优先中文）③ 数据来自 MES 接口 ④ **不得** HTTP 401 |
| **通过标准** | 对话给出列表或「MES 返回 0 条」；过程区可见查询工具；列表可读；不出现未授权 |
| **失败典型** | 401；404 打错路径；沿用上一套 MES 的实体 id；把表结构模块清单当成业务数据 |
| **验收** | **P** · 2026-08-18 · 资料包「江西中软MES系统」· entity=`work-orders` · MES 12 条/本次 12 条 · 中文列（状态/优先级/产线/工单号/产品）· 无 401 |

---

## TC-Q-02 带筛选条件

| 项 | 内容 |
|----|------|
| **功能** | F-QUERY-01 |
| **测试问题** | 查一下状态是 pending 的工单（或该 MES 实际存在的状态值，如进行中） |
| **预期工具** | `query_platform_data`；entity 与 filters 字段均以当前目录 / `describe_entity` 为准 |
| **期望要点** | ① 传了 filters，不是全量拉取后口头说「都是 pending」 ② 结果状态与条件一致，或如实说明该状态无数据 |
| **通过标准** | 工具参数含筛选字段；回复不把其它状态的单混进来充数 |
| **验收** | **P** · 2026-08-18 · `filters={status: pending}` 已下发 · 仅 3 条且均为 pending |

---

## TC-Q-03 嵌套路径对象（换接口形态仍可用）

| 项 | 内容 |
|----|------|
| **功能** | F-QUERY-01 / F-QUERY-03 |
| **测试问题** | 查一下点检计划列表 |
| **预期工具** | `query_platform_data`，实体 id 以目录为准（当前示例 `inspection-plans`，路径 `/api/inspection/plans`） |
| **期望要点** | ① 走嵌套列表路径，不是误打 `/api/v1/...` ② **不要**用工单数据充数 |
| **通过标准** | 返回点检计划或如实空；实体与工单不同 |
| **验收** | **P** · 2026-08-19 · entity=`inspection-plans` · path=`/api/inspection/plans` · total=2 / returned=2 · 未走 `/api/v1` · 未用工单充数 |

当前资料包若无点检计划，改问目录里存在的另一嵌套对象（如设备保养计划），标准相同。

---

## TC-Q-04 未配 MES 接口账号（负向）

| 项 | 内容 |
|----|------|
| **功能** | F-QUERY-01（鉴权分离） |
| **前置** | WorkBuddy 已登录；资料包与 OpenAPI 已导入；**清空** MES 接口账号/密码后保存 |
| **测试问题** | 查生产工单列表 |
| **期望要点** | 提示到系统配置填写 **MES 接口账号**（可提到企业编码）；说明与 WorkBuddy 登录无关 |
| **通过标准** | **不**用 WorkBuddy 登录 token 去打 MES 而报 401；应明确缺 MES 接口凭证 |
| **收尾** | 测完把账号填回去，再跑 TC-Q-01 |
| **验收** | **P** · 2026-08-19 · `inspect_mes_profile(查生产工单列表)` · `can_answer_now=false` · missing 含「MES 接口账号」· 未用 WorkBuddy token 冒充打 MES |

---

## TC-Q-05 查数 ≠ MES 能力总览

| 项 | 内容 |
|----|------|
| **功能** | F-QUERY vs F-SCHEMA |
| **测试问题** | MES 系统能干什么？ |
| **预期工具** | 表结构摸底（`list_platform_capabilities` 等），**不是** `query_platform_data` |
| **通过标准** | 按表结构讲模块/场景；不把「能查 work-orders」当成 MES 全量能力 |
| **验收** | **P** · 2026-08-19 · intent=`survey` · next_tool=`list_platform_capabilities` · map_source=`inferred_from_schema` · capability_count=10 · 35 表 / 10 域 |

---

## TC-Q-06 轻量汇总（按真实字段）

| 项 | 内容 |
|----|------|
| **功能** | F-QUERY-06 |
| **测试问题** | 生产工单按状态各有多少？（或目录里该实体实际存在的分组字段） |
| **预期工具** | `summarize_platform_data`；entity 与 group_by 均以当前目录/返回列为准（「状态」可映射到 status / billStatus 等真实字段） |
| **期望要点** | ① 分组字段来自返回记录，不是臆造 ② 各组条数之和 ≤ 本次 returned ③ 有筛选时仍传 filters |
| **通过标准** | 对话给出各组 value + count；说明若 MES 总条数大于本页则比例只覆盖本页 |
| **验收** | **P** · 2026-08-18 · 按状态：in_progress 4 / pending 3 / completed 3 / closed 2，合计 12 |

---

## TC-Q-07 导出路径与行数

| 项 | 内容 |
|----|------|
| **功能** | F-QUERY-07 |
| **测试问题** | 把生产工单导出来（csv 或 excel） |
| **预期工具** | `export_platform_data` |
| **期望要点** | ① 回复含工具返回的**绝对路径** ② 含行数 `rows` ③ 不编造路径 |
| **通过标准** | 按路径能打开文件；行数与对话一致（或如实说明没有数据可导出） |
| **验收** | **P** · 2026-08-18 · CSV · 12 行 · 路径 `/Users/hebo/Desktop/work-orders_20260818_112802.csv` |

---

## TC-Q-08 指标口径（在制 / 紧急未完工）

| 项 | 内容 |
|----|------|
| **功能** | F-QUERY-08 |
| **测试问题** | 有多少在制工单？紧急未完工有哪些？（或「当日完工」） |
| **预期工具** | `query_metric`（可先 `list_query_metrics`）；entity/字段/取值绑定当前目录，不写死 `work-orders` |
| **期望要点** | ① 复述口径定义 ② filters 下发给 MES（可能多组 filter_sets）③ 当日完工若接口无日期参数须说明未能限定当天 |
| **通过标准** | 条数与口径一致；绑不上时如实说明，不套用其它 MES 的状态值 |
| **验收** | **P** · 2026-08-18 · 在制 4（`status=in_progress`）· 紧急未完工 3（urgent/high ∩ 未完工）· 当日完工：如实说明无 `end_date` 筛选，仅按 completed 返回 3 条且无 08-18 完工 |

---

## 建议执行顺序

1. TC-Q-01（必测，主验收）
2. TC-Q-02（有真实状态值时测）
3. TC-Q-03（确认没写死单层 `/api/{资源}`）
4. TC-Q-04（确认登录与查数鉴权已拆开）
5. TC-Q-05（确认不和摸底用例打架）
6. TC-Q-06（完善查数：汇总）
7. TC-Q-07（完善查数：导出）
8. TC-Q-08（指标口径）

记录格式：`P` / `F` + 日期 + 资料包 + 实际实体 id + 条数要点。

### 联调记录（江西中软 MES · 2026-08-18 / 08-19）

| 用例 | 结果 | 要点 |
|------|------|------|
| TC-Q-01 | P | 生产工单列表 `work-orders`，12 条，中文列表格 |
| TC-Q-02 | P | pending 3 条，筛选已作接口参数 |
| TC-Q-03 | P · 08-19 | `inspection-plans` · `/api/inspection/plans` · 2 条 |
| TC-Q-04 | P · 08-19 | 无 MES 账号时 `can_answer_now=false`，提示补接口凭证 |
| TC-Q-05 | P · 08-19 | 摸底 10 能力 / 35 表，不走查数 |
| TC-Q-06 | P | 按状态分组 4/3/3/2 |
| TC-Q-07 | P | 导出 CSV 12 行，给出绝对路径 |
| TC-Q-08 | P | 在制 4；紧急未完工 3；当日完工缺日期筛参时如实降级为已完工 3 条 |
| 换平台负向 | P · 08-19 | 空目录查数被挡，结果不含 `work-orders` |
| D 闸门 | P · 08-19 | 加实际结束时间：补列并回填计划日 18:00 |

---

## TC-A-01 分析出图（柱状）

| 项 | 内容 |
|----|------|
| **功能** | F-ANALYSIS-CHART |
| **测试问题** | 工单按状态分布并出柱状图 |
| **预期工具** | `summarize_platform_data` 或 `analyze_platform_brief` → `render_analysis_chart` |
| **通过标准** | 对话内出现分析图气泡或 `:::analysis_chart`；categories/values 与汇总一致；含本页 caveat |
| **验收** | （待测）详见 [`PCB数据分析验收话术.md`](PCB数据分析验收话术.md) A05 |

## TC-A-02 产线异常日报

| 项 | 内容 |
|----|------|
| **功能** | F-ANALYSIS-DAILY |
| **测试问题** | 出一份产线异常日报 |
| **预期工具** | `run_ops_scene('plant-exception-daily')` |
| **通过标准** | 有 `markdown_report`；绑不上口径跳过；可有 chart |
| **验收** | （待测）A08 |

## TC-A-03 只读 SQL 默认关

| 项 | 内容 |
|----|------|
| **功能** | F-ANALYSIS-SQL |
| **测试问题** | 帮我直接 SQL 查全库在制 |
| **期望** | 未开启时提示默认走 HTTP / 系统配置；不执行任意 SQL |
| **验收** | （待测）A17；单测 `test_analysis_chart.py` |

自动化冒烟：`PYTHONPATH=apps/agent:apps python3 scripts/smoke_mes_acceptance_0819.py`  
图表/SQL 单测：`cd apps/agent && python -m unittest tools.query_tool.test_analysis_chart -v`

更多 PCB 话术：[`PCB数据分析验收话术.md`](PCB数据分析验收话术.md)。
