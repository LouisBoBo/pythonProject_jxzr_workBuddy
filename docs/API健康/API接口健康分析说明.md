# API 接口健康分析说明

本能力包含**两条互不串数的链路**：

| | A. 文档沙箱探活 | B. 外部日志错误分析 |
|--|-----------------|---------------------|
| 输入 | Swagger/OpenAPI URL 或文件 | 网关/Nginx/JSONL/CSV 访问日志 |
| 主数字 | **文档接口总数**（如 62） | **本次日志调用条数**（如 7）+ 归并后的接口数 |
| 默认报告 | `render_api_health_report` | `analyze_api_errors_from_logs`（`with_catalog=false`） |
| 日志 source | `sandbox` / `erp` | `import` |

文档探活细节见 [API沙箱探活使用指南.md](API沙箱探活使用指南.md)；过程复盘见 [API接口自动化测试复盘.md](API接口自动化测试复盘.md)。

**硬性约定**

- 文档接口相关测试**一律默认在沙箱**进行，不写生产。  
- 纯「根据日志看错误」**不要**把历史接口目录的「文档 N 个接口」写进主报告。  
- 两条链路的结论分开表述，禁止混为一谈。

## 与既有能力边界

| | 表结构摸底 | 模拟查/导 | 本功能 A | 本功能 B |
|--|--|--|--|--|
| 输入 | 本地数据字典 | 实体目录 | docs URL / OpenAPI | 访问日志附件 |
| 问题 | 业务能管啥 | 演示数据操作 | 文档接口是否可探活通过 | 日志里哪些接口失败 |
| 证据 | 静态文档 | Mock/ERP 实时 | `calls.jsonl`（sandbox） | `calls.jsonl`（import） |

写确认、导入导出、表结构摸底工具链**不改语义**；仅在 ERP 真实 HTTP `_request` 上附加日志落盘（失败写盘不影响业务返回）。

---

## 能力 A：目录来源与探活

### 目录来源

1. **URL**：`build_api_catalog(docs_url="http://127.0.0.1:8000/docs")` → 拉同源 OpenAPI  
2. **文件**：`build_api_catalog(file_path=...)` — OpenAPI `.json`/`.yaml`，或含 `Method|Path|说明` 的 Markdown 表  

索引落盘：`data/api_catalog/api_index.json`  
**注意：** `.jsonl` / `.log` **不是** OpenAPI，禁止用本工具吃访问日志。

### URL 白名单（SSRF）

默认允许：`127.0.0.1`、`localhost`、`PLATFORM_BASE_URL` 的 host。  
扩展：`API_DOCS_URL_ALLOWLIST=host1,host2`

| 用户给的文档页 | 优先拉取 |
|----------------|----------|
| `/docs`、`/redoc` | `/openapi.json` |
| `/swagger-ui.html`、`/swagger-ui/` | `/v3/api-docs` → `/v2/api-docs` … |

### 推荐流程（处理过程 6 步）

```
build_api_catalog → list_api_catalog → probe_api_catalog
→ summarize_api_doc_vs_logs → rank_problematic_apis → render_api_health_report
```

`probe_api_catalog` 默认 sandbox（可含写、打 `API_PROBE_SANDBOX_URL`、不改生产）。  
**建目录**仍用用户给的 docs（如 `:8081`），与探活地址（`:8001`）分开。  
最终回复采用 `render_api_health_report` 的 `report_markdown`。  
`AGENT_RECURSION_LIMIT` 默认 100。

| sandbox_kind | 条件 | 说明 |
|--------------|------|------|
| **local_mock** | 未设 `API_PROBE_SANDBOX_URL` | 内存模拟；须注明 ≠ 生产写实测 |
| **remote_url** | 已设沙箱 URL（`dev.sh` 默认） | 真实 HTTP 打沙箱，不碰生产 ERP |

唯一例外：用户明确要求生产只读核验 → `mode="live"`。

完整操作说明：**[API沙箱探活使用指南.md](API沙箱探活使用指南.md)**

---

## 能力 B：外部日志导入（分析接口错误）

```
上传 access.log / api-errors.jsonl
  → import_external_api_logs(file_path=…)     # 默认清除旧 source=import
  → analyze_api_errors_from_logs(source_filter="import")  # 默认 with_catalog=false
  → 用 report_markdown 回复
```

主报告只含：

- **日志调用条数**（文件行数，如 7）  
- **日志中的接口数**（path 模板归并后，如 4）  
- ❌ 错误接口表 / ✅ 正常接口表  

**不要**出现「文档 62 个接口」作为覆盖主数字。  
仅当用户**同时**要求对照某份 docs 时，才传 `docs_url` 或 `with_catalog=true`（对照放**附录**）。

支持格式：`jsonl` / `nginx` / `csv`（`format=auto`）。  
样例：`data/samples/api_access_sample.jsonl`、`data/samples/api_access_sample.nginx.log`。

### Agent 行为兜底

| 机制 | 作用 |
|------|------|
| 聊天上传 `accept` | 允许 `.jsonl` / `.log` |
| `MesAccessLogRouteMiddleware` | 误用 `read_file`/`ls`/`transform_file`/`build_api_catalog` 时自动改走导入 |
| `agent_wrapper` 附件提示 | 强制两步导入→分析，禁止 `with_catalog` |
| `resolve_upload_path` | 绝对路径 / 文件名 / `stem_timestamp.ext` |

---

## 调用日志

`ERPClient._request` / 登录尝试 / 沙箱探活 / 外部导入 写入 `data/api_calls/calls.jsonl`：

- 字段：`ts`、`method`、`path`、`path_key`、`status`、`latency_ms`、`ok`、`error`、`source`
- `source`：`erp` | `sandbox` | `import`（分析时务必过滤，勿混算）
- **不记录** Authorization / token
- MockClient **不写**日志
- 行数上限：`API_CALL_LOG_MAX_LINES`（默认 50000）

探活开始会清理历史 `source=sandbox|probe`（保留 `erp`），并为本轮写入 **`run_id`**。  
外部导入默认清理旧 `source=import`，并写入新的 **`run_id`**。  
`summarize` / `analyze` / `rank` 在 source 为 sandbox|import 时默认 **`run_id=latest`**（只看本轮）；需要跨轮对比时传 `run_id="all"`。

### path_key 通用规则

| 原始段 | path_key 段 |
|--------|-------------|
| `42`、数字 id | `{id}` |
| UUID | `{id}` |
| OpenAPI `{order_id}` / `{id}` / `{userId}` 等 | `{id}` |
| 字面量 `work-orders` | 保持不变 |

因此文档与调用对照时视为同一接口；**不得**据此推断「参数名不一致导致接口坏了」。

---

## Agent 工具一览

| 工具 | 链路 | 作用 |
|------|------|------|
| `build_api_catalog` | A | URL 或 OpenAPI 文件 → 重建目录 |
| `list_api_catalog` | A | 查看目录 |
| `probe_api_catalog` | A | 沙箱/只读生产批量探活 |
| `summarize_api_doc_vs_logs` | A | 目录 × 日志总览 |
| `rank_problematic_apis` | A | 问题排行 |
| `inspect_api_path` / `query_api_call_log` | A/B | 抽样与原始查询 |
| `render_api_health_report` | A | 文档探活专业报告 |
| `import_external_api_logs` | B | 导入外部访问日志 |
| `analyze_api_errors_from_logs` | B | 日志错误分析报告 |

Skill：`apps/agent/skills/analyze-api-health/SKILL.md`

---

## 判定含义（目录对照 / 探活）

| 状态 | 含义 |
|------|------|
| 可行 (healthy) | 有成功调用，错误率/延迟在阈值内；**调用≤3 且仅失败 1 次**视为低样本噪声 |
| 有问题 (problematic) | 高错误率（非低样本）、连接失败、偏慢 |
| 未见调用 (unseen) | 目录有、日志无 —— **不等于坏** |
| 文档未收录 (undocumented) | 日志有、目录无 |

---

## 验收要点

- 既有查工单 / 导入确认卡 / 表结构摸底话术行为不变  
- **能力 A**：8081 文档 → 报告展示文档接口总数（如 62），沙箱探活通过  
- **能力 B**：只上传 `api_access_sample.jsonl` → 报告为 **7 条调用 / 4 个接口**，主报告无「文档 62」、无历史 nginx 串入  
- 故意断网或错误 path 时日志有 `ok=false`，业务工具仍返回 `error` 结构而非崩溃  

### 无 LLM 冒烟（回归）

```bash
# 仓库根目录；日志分析必跑；探活需本机 8081 + 8001（没有则 SKIP）
make smoke-api-health

# CI / 强制探活也必须过：
SMOKE_REQUIRE_PROBE=1 make smoke-api-health
```
