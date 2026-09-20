# 02 · MES 数据查询、导出与分析

> **一句话**：用自然语言查工单/设备/品质等 **MES 真数据**，可导出文件，可出图、出看板；接口没有就诚实说缺口。  
> **不是**：让模型编造 KPI；也不是走 Cursor 改代码。查数在 Deep Agents 对话里调 Python Tool，真 HTTP 在 `platform_api`。

---

## 1. 实现原理

### 1.1 我们到底实现了什么？

可以记成：**先有一张「能查什么」的菜单（entities），再按菜单打 MES 接口，最后把结果变成表 / 文件 / 图。**

| 人配的 / 人问的 | 系统干的 | 达到的效果 |
|----------------|----------|------------|
| 自然语言（「今天有多少工单」） | 模型选 entity + filters → `query_platform_data` → HTTP | 中文表 + 口径说明 |
| 「导出 Excel」 | `export_platform_data` 写入 `EXPORT_DIR` | 可下载文件 |
| 「出图 / 打开运营看板」 | `render_analysis_chart` / `run_analysis_demo` 等算 ECharts JSON | 前端卡片真画图，非 ASCII 手绘 |
| OpenAPI / 精修 entities | mes-profile API 落盘资料包 | 换厂可换目录 |

**技术落点（整包）：**

| 层次 | 路径 |
|------|------|
| 对话入口 | `POST /api/chat/stream`（默认 lane） |
| Tools | `apps/agent/tools/query_tool/platform_query.py` 等 |
| 结果展示 | `query_present.present_query_result` |
| HTTP 客户端 | `apps/agent/tools/platform_api.py` → `get_client()` |
| 出站安全 | `safe_http` / `assert_http_url_allowed` |
| 图表 | `analysis_chart.py`、`analysis_dashboard.py`、`analysis_demo.py` |
| 前端 | `chatAnalysisChartParse.js`、`AnalysisChartCard.vue`、`AnalysisDashboardCard.vue` |
| Skills | `query-mes-data`、`analyze-mes-data`、`analyze-pcb-mes`、`ops-query-playbook` |
| 资料包 | `data/mes_profiles/{MES_PROFILE_ID}/` |
| 下载 | `GET /api/download/{filename}`（仅 `EXPORT_DIR` 内） |

### 1.2 和「PCB 闲聊 / 写码」差在哪？

| | **本篇：查数/导出/分析** | PCB 闲聊（01） | 写码（08） |
|--|--------------------------|----------------|------------|
| 数据从哪来 | MES HTTP 真结果 | 模型知识 | 改仓库代码 |
| 谁执行 HTTP | `platform_api.get_client` | 无 | 无（Cursor/Job） |
| 没接口时 | **诚实降级**说缺口 | 科普即可 | — |
| 会否改业务仓 | 否 | 否 | 是（确认后） |

**两个账号别混：**

| 账号 | 干什么 |
|------|--------|
| ZR WorkBuddy 登录 | 进产品、看历史 |
| MES 接口账号（`MES_API_*`） | 查数、导入写 MES |

没配 MES 接口账号时工具会失败或提示配置——**不能**用登录账号冒充 MES 账号。

**技术上怎么隔开：**

| 点 | 实现 |
|----|------|
| 不经 Cursor | 查数 Tool 在 Agent 进程内 HTTP，不创建写码 Job |
| 诚实降级 | 查空 / 缺参 / 404 → 返回空或 missing；提示词禁止换实体充数、禁止编良率 |
| 出站 | `safe_http` 断言 URL，禁止乱打非允许域名 |

### 1.3 为什么图表要「工具算 JSON、前端画」？

**人话：**  
让模型手绘 ASCII 或「描述一下柱状图」不可验收。Python 算出 ECharts option / dashboard payload，前端组件渲染，领导演示才能稳定复现。

**技术点：**

| 点 | 函数 / 模块 | 怎么做的 |
|----|-------------|----------|
| 单图 | `render_analysis_chart` | 返回 ECharts option JSON |
| 看板 | `render_analysis_dashboard` / `run_analysis_demo` | 多 panel payload（如 `pcb-ops-board`） |
| 前端识别 | `chatAnalysisChartParse.js` | 从流/消息里抠出图表结构 |
| UI | `AnalysisChartCard` / `AnalysisDashboardCard` | ECharts 渲染 |

### 1.4 安全上钉死了什么？

| 约束 | 技术实现 |
|------|----------|
| 不编 KPI | Skills + 工具返回；无数据不说有 |
| 外发 HTTP | `safe_http` / URL 校验 |
| 下载不越界 | `GET /api/download/{filename}` 限制在 `EXPORT_DIR` |
| 只读 SQL | `READONLY_SQL_*` **默认关**，勿当默认查数路径 |
| 导出目录 | `EXPORT_DIR`（可与桌面约定） |

---

## 2. 实现流程（人话 + 技术点怎么落地）

> 查数没有单独 REST「/query」接口，而是 **Agent 在 SSE 里调 Python Tool**；真 HTTP 在 `platform_api.py`。

### 2.1 资料包（能查什么）从哪来？

**人话：** 系统配置里上传或拉取 OpenAPI，生成/合并 `entities.json`；也可人工精修后上传覆盖。激活资料包决定当前厂别目录。

```text
POST /api/mes-profile/upload-openapi
POST /api/mes-profile/import-openapi-url
POST /api/mes-profile/upload-entities（人工精修覆盖）
  → mes_profile_persist.persist_openapi_text()
  → data/mes_profiles/{MES_PROFILE_ID}/openapi.json
  → openapi_to_entities 合并 → entities.json

PUT /api/mes-profile/active → 写入 MES_PROFILE_ID
GET /api/mes-profile 时可能 schedule_daily_sync_openapi（日同步）
```

**技术点：**

| 点 | 函数 / 模块 | 怎么做的 |
|----|-------------|----------|
| 目录缓存 | `load_catalog` | 按 `entities.json` path + mtime 内存缓存 |
| 写码后刷新 | `mes_profile_refresh.refresh_mes_profile_from_runtime` | 本机改 API 后可合并目录 |
| 实体对齐 | `resolve_entity_id` / `describe_entity` | 中文说法对齐目录 id |

---

### 2.2 对话查数：Tool 调用链

**人话：** 你问一句，模型先搞清「查哪个对象、什么条件」，再真请求 MES，把结果整理成中文表和口径说明（例如是否真的按「当天」筛到了）。

```text
用户：「今天有多少工单？」
  → POST /api/chat/stream（默认 lane）
  → Skill query-mes-data（或分析类 Skill）

典型 tool call：
  1. list_platform_entities() / describe_entity(entity)
  2. query_platform_data(entity, filters, limit)
       → get_client() → ERPClient / MockClient
       → client.query() → HTTP + JWT（MES_API_*）
  3. present_query_result(...)（query_present.py）
       → markdown 表 + 中文列名 + 口径 hint
  4. 模型流式解释

汇总类还可：
  summarize_platform_data / query_metric / analyze_time_trend / analyze_platform_brief
```

**技术点：**

| 点 | 函数 / 模块 | 怎么做的 |
|----|-------------|----------|
| 主查询 | `query_platform_data` | 查 MES；结果经 `present_query_result` 展示 |
| 列表/描述 | `list_platform_entities`、`describe_entity` | 对齐实体与字段 |
| 汇总/指标 | `summarize_platform_data`、`query_metric`、`analyze_time_trend`、`analyze_platform_brief` | 聚合与简报；页内汇总须 caveat「≠ 全库 COUNT」 |
| 出站 | `assert_http_url_allowed` + 受限 urlopen | 安全 HTTP |
| 调用日志 | `append_api_call(source=erp)` | 写入 `DATA_DIR/api_calls` |
| 账号 | `get_client()` | 读 `MES_API_*` / `PLATFORM_BASE_URL`，与 WB 登录 JWT 无关 |

---

### 2.3 导出怎么落到文件？

**人话：** 说「导出 Excel/CSV」时，工具先按同样条件查出数据，再写到导出目录；回复里给路径，前端可点下载链接。

```text
export_platform_data(entity, filters, format=csv|xlsx|json)
  → 先 query 再写 EXPORT_DIR/{timestamp}.{ext}
  → 回复路径
  → 用户经 GET /api/download/{filename} 下载（仅允许 EXPORT_DIR 内文件名）
```

**技术点：**

| 点 | 怎么做的 |
|----|----------|
| 目录 | `AgentConfig.EXPORT_DIR`（环境变量 `EXPORT_DIR`） |
| 下载安全 | `routes/chat.py` 的 download：`resolve` 后必须落在导出目录内 |
| Skill | `import-export-data` 覆盖导出侧指引（导入见功能 03） |

---

### 2.4 分析图表与看板

**人话：** 要趋势图或 PCB 运营看板时，工具返回结构化 payload；对话里出现图表卡/看板卡，不是让模型「画」出来。

```text
render_analysis_chart(...)     → ECharts option
run_analysis_demo(playbook=…)  → render_analysis_dashboard → 多 panel
  → agent_wrapper 解析工具结果 → SSE / 消息结构
  → ChatView → chatAnalysisChartParse.js
  → AnalysisChartCard.vue / AnalysisDashboardCard.vue
```

**技术点：**

| 点 | 函数 / 模块 | 怎么做的 |
|----|-------------|----------|
| 单图 / 看板 | `render_analysis_chart`、`render_analysis_dashboard`、`run_analysis_demo` | 算 payload |
| 运维剧本 | `ops_playbook.py` + Skill `ops-query-playbook` | 急单链、值班简报等仍多次 `query_platform_data`，步骤固定 |
| PCB 分析 Skill | `analyze-mes-data`、`analyze-pcb-mes` | 分析口径与可选 PCB 扩展 |
| 历史 | 图表 JSON 落在会话消息 | 切会话再回来仍可见 |

---

### 2.5 出问题时先查哪？

| 现象 | 人话原因 | 技术上先看 |
|------|----------|------------|
| 「未配置可查对象」 | 资料包未激活或 entities 空 | `MES_PROFILE_ID`；`entities.json` |
| 401/403 | MES 账号或 Base URL 错 | `MES_API_*`；`PLATFORM_BASE_URL`；`USE_ERP` |
| 有数但口径错 | filters / 日期字段不对 | `query_platform_data` 入参；接口是否支持「当天」 |
| 看板空白 | payload 未识别 | 控制台；`chatAnalysisChartParse` |
| Lot / 追溯瞎编 | 接口缺口 | 应返回缺口；查 metrics / OpenAPI 是否真有 |

---

## 3. 技术及用法（速查）

| 模块 | 关键函数 | 干什么 |
|------|----------|--------|
| `platform_query.py` | `list_platform_entities`、`describe_entity`、`query_platform_data`、`summarize_platform_data`、`query_metric`、`analyze_time_trend`、`analyze_platform_brief` | 查数与汇总入口 |
| `query_present.py` | `present_query_result` | 中文表与展示结构 |
| `platform_api.py` | `get_client`、query/HTTP | 真调 MES |
| `file_ops.py` | `export_platform_data` | 导出到 `EXPORT_DIR` |
| `analysis_chart.py` / `analysis_dashboard.py` / `analysis_demo.py` | `render_analysis_chart`、`render_analysis_dashboard`、`run_analysis_demo` | 图 / 看板 |
| `ops_playbook.py` | 场景模板 | 值班/急单等 |
| Skills | `query-mes-data`、`analyze-mes-data`、`analyze-pcb-mes`、`ops-query-playbook` | 剧本 |
| 前端 | `chatAnalysisChartParse.js`、`AnalysisChartCard.vue`、`AnalysisDashboardCard.vue` | 渲染 |
| mes-profile 路由 | upload/import/active 等 | 资料包 |

**配置：**

| 变量 | 含义 |
|------|------|
| `MES_PROFILE_ID` | 激活资料包 |
| `MES_API_*` | MES 接口账号等 |
| `PLATFORM_BASE_URL` | 平台 Base URL |
| `USE_ERP` | 是否走真实 ERP 客户端（相对 Mock） |
| `EXPORT_DIR` | 导出目录 |
| `READONLY_SQL_*` | 只读 SQL（**默认关**） |

资料包日同步见 `mes_profile_daily_sync.py` / [`../MES业务/每日打开自动同步资料包.md`](../MES业务/每日打开自动同步资料包.md)。查数用例见 [`../MES业务/MES查数测试用例.md`](../MES业务/MES查数测试用例.md)。

---

## 4. 后续可以怎么做、不要做什么

**可以做：**

1. 按厂补 `metrics.json` / 分析配置，减少口径口头约定  
2. 缺口清单（如 Lot/拼板）产品化展示  

**不要做：**

1. 接口没有的字段用模型编造良率/在制  
2. 默认打开只读 SQL 直连库当主查数路径  
3. 为「好看」换一个无关实体 id 充数  

---

## 自测路径（验收）

1. 「今天有多少工单？」→ 有表或诚实空结果，不编数字。  
2. 「紧急未完工有哪些？导出 Excel」→ `EXPORT_DIR` 有文件；`/api/download/...` 可下。  
3. 「打开 PCB 运营看板」→ 出现看板卡（非纯文字描述）。  
4. 「Lot 追溯怎么查？」→ 缺口或 caveat，勿瞎编。  
