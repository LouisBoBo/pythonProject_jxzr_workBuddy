# 02 · MES 数据查询、导出与分析

> 用自然语言查工单/设备/品质等真数据，可导出文件，可出图、出看板；**没接口就诚实说缺口**，不编 KPI。

---

## 1. 实现原理

### 1.1 查数、导出、分析三件事，底层是一条链

可以记成：**先有一张「能查什么」的菜单，再按菜单去打 MES 接口，最后把结果变成表 / 文件 / 图**。

```text
OpenAPI（接口文档）
    → 解析生成 entities.json（可查对象目录，每个对象有 id、字段、接口路径）
    → 用户自然语言提问
    → 大模型选对 entity id 和筛选条件
    → platform_api.py 带 Token 发 HTTP 请求
    → 返回 JSON → 模型整理成中文表 / 或交给图表工具出 payload
```

**导出**：把同一份查询结果写到 `exports/` 目录，给用户路径下载。  
**分析 / 看板**：不是让模型「手绘 ASCII 图」，而是 Python 工具算好 ECharts 需要的 JSON，前端 `AnalysisChartCard` 负责画。

### 1.2 两个账号，别混

| 账号 | 干什么 | 配在哪 |
|------|--------|--------|
| WorkBuddy 登录 | 进产品、看历史 | 登录页 / ERP 对接 |
| MES 接口账号 | 查数、导入写 MES | 系统配置 → MES 接入 |

没配 MES 接口账号时，工具会失败或提示去配置——**不能**用登录账号冒充 MES 账号。

### 1.3 「诚实降级」是什么意思？

现场 MES 接口常有缺口，例如：

- 没有按「当天」筛的参数字段  
- 没有 Lot / 拼板追溯接口  
- 某实体文档写了但接口 404  

工具和提示词要求：**查空就说查空，接口不支持就说缺口**，禁止换另一个实体 id「凑数」，禁止编良率 KPI。  
这是产品可信度，不是技术炫技。

### 1.4 谁在执行？

- **理解人话、选实体、解释口径**：Deep Agents + Skills（`query-mes-data` 等）  
- **真 HTTP 请求**：`platform_api.py`（Python `requests` / httpx，带 JWT）  
- **画图数据结构**：`analysis_chart.py`、`analysis_dashboard.py` 等  
- **不经过** Cursor，不改业务仓库代码

---

## 2. 实现流程（技术点怎么落地）

> 查数没有单独 REST「/query」接口，而是 **Agent 在 SSE 对话里调 Python Tool**；真 HTTP 在 `platform_api.py`。

### 2.1 资料包落地：entities.json 从哪来

```text
系统配置上传 / API：
  POST /api/mes-profile/upload-openapi
  POST /api/mes-profile/import-openapi-url
  POST /api/mes-profile/upload-entities（人工精修覆盖）
       ↓
mes_profile_persist.persist_openapi_text()
  → data/mes_profiles/{MES_PROFILE_ID}/openapi.json
  → openapi_to_entities.py 合并 → entities.json
```

| 技术点 | 实现 |
|--------|------|
| 激活资料包 | `PUT /api/mes-profile/active` 写 `MES_PROFILE_ID` 到 settings |
| 缓存 | `load_catalog()` 按 `entities.json` path+mtime 内存缓存 |
| 日同步 | `GET /api/mes-profile` 时 `schedule_daily_sync_openapi()` 后台拉最新 OpenAPI |
| 写码后合并 | `mes_profile_refresh.refresh_mes_profile_from_runtime()` 本机改 API 后可合并目录 |

### 2.2 对话查数：Tool 调用链

```text
用户：「今天有多少工单？」
  → POST /api/chat/stream（默认 lane）
  → Skill query-mes-data

模型 tool call 链（典型）：
  1. list_platform_entities() / describe_entity(entity)
       resolve_entity_id() 把中文说法对齐 entities.json 里的 id
  2. query_platform_data(entity, filters, limit)
       get_client() → ERPClient / MockClient
       client.query() → HTTP + JWT（MES_API_*）
  3. present_query_result() → markdown_table + 中文列名
  4. 模型流式解释口径（是否限定「当天」）
```

| 技术点 | 实现 |
|--------|------|
| 出站安全 | `assert_http_url_allowed()` + `urlopen_limited()` |
| 调用日志 | `append_api_call(source=erp)` 写入 `DATA_DIR/api_calls` |
| 诚实降级 | 接口无日期参 / 查空 → 工具返回空或 missing；提示词禁止换实体充数 |
| 账号 | `get_client()` 读 `MES_API_USERNAME/PASSWORD/ENTERPRISE_CODE`，与 WB 登录 JWT 无关 |

### 2.3 导出

```text
export_platform_data(entity, filters, format=csv|xlsx|json)
  → 先 query 再写 EXPORT_DIR/{timestamp}.{ext}
  → 回复绝对路径；受 EXPORT_MAX_ROWS 限制
```

### 2.4 分析图表与看板（非模型手绘）

```text
汇总：summarize_platform_data() / analyze_time_trend() / query_metric()
出图：render_analysis_chart() → 返回 ECharts option JSON
看板：run_analysis_demo(playbook='pcb-ops-board')
      → render_analysis_dashboard() → 多 panel payload

agent_wrapper 解析工具结果 → SSE 可能带 dashboard/chart 结构
ChatView → chatAnalysisChartParse.js
  → AnalysisChartCard.vue / AnalysisDashboardCard.vue（ECharts）
```

| 技术点 | 实现 |
|--------|------|
| 页内汇总 caveat | `summarize_*` 强制说明「当前页/当前批 ≠ 全库 COUNT」 |
| 可选 MCP 出图 | `ANALYSIS_CHART_MCP` 打开时走 `chart_mcp_client` |
| 历史持久化 | 图表 JSON 存在会话消息里，切会话再回来仍可见 |

### 2.5 运维场景（ops-query-playbook）

`ops_playbook.py` 预置场景模板（急单链、值班简报）：  
仍是多次 `query_platform_data`，只是步骤和话术固定，Skill 教模型按 playbook 名调用。

### 2.6 常见排查

| 现象 | 查什么 |
|------|--------|
| 「未配置可查对象」 | `entities.json` 是否存在；`MES_PROFILE_ID` |
| 401/403 | `MES_API_*`；`PLATFORM_BASE_URL` |
| 有数但口径错 | 看 `query_platform_data` 的 filters 入参 |
| 看板空白 | 浏览器控制台；payload 是否被 `chatAnalysisChartParse` 识别 |
| Lot 瞎编 | 应返回缺口；查 `metrics.json` / 接口是否真有追溯 |

---

## 3. 技术及用法

| 技术 / 模块 | 怎么用 |
|-------------|--------|
| `tools/query_tool/platform_query.py` | 列表、查询、摘要主入口 |
| `tools/platform_api.py` | 真正 HTTP 调 MES |
| `openapi_to_entities.py` | OpenAPI → 可查对象 |
| `analysis_chart.py` / `analysis_dashboard.py` | 图表 / 看板 payload |
| `metrics_pack.py` / `time_series.py` / `aggregate.py` | 指标与聚合 |
| `ops_playbook.py` | 值班场景（急单链等） |
| Skills | `query-mes-data`、`analyze-mes-data`、`analyze-pcb-mes`、`ops-query-playbook`、`import-export-data`（导出半边） |
| 前端 | `AnalysisChartCard.vue`、`AnalysisDashboardCard.vue`、ECharts |
| 配置 | `MES_PROFILE_ID`、`MES_API_*`、`USE_ERP`、`EXPORT_*`；可选 `READONLY_SQL_*`（默认关） |

资料包日同步：`mes_profile_daily_sync.py` / 文档 `docs/MES业务/每日打开自动同步资料包.md`。

---

## 4. 后续扩展与优化建议

1. **可做**：按厂补 `metrics.json` / 分析配置，减少「口径口头约定」。  
2. **可做**：缺口清单（如 Lot/拼板）产品化展示，领导演示已要求主动说。  
3. **慎做**：默认打开只读 SQL 直连库（安全面大，现默认关）。  
4. **不要做**：接口没有的字段用模型编造良率/在制。

---

## 自测话术

- 「今天有多少工单？」  
- 「紧急未完工有哪些？导出 Excel」  
- 「打开 PCB 运营看板」  
- 「Lot 追溯怎么查？」（应缺口或 caveat，勿瞎编）  

详见：`docs/MES业务/MES查数测试用例.md`、`PCB数据分析验收话术.md`。  
