# 05 · API 接口健康分析

> **一句话**：你给一份 OpenAPI（或上传网关日志）→ Agent 按固定步骤建目录、沙箱探活（或解析日志）、排序问题接口 → 输出**中文健康报告**。  
> **不是**：沙箱探活失败就等于「生产挂了」；也不是把路径 A（文档×探活）和路径 B（导入日志）的数字混算成一套成功率。

---

## 1. 实现原理

### 1.1 我们到底实现了什么？

实施/运维手里常有：一份 Swagger/OpenAPI（「理论上有哪些接口」），再加一堆网关错误日志（「实际上哪些在报错」）。人工对照很费时间。  
所以做了 **API 接口健康分析**：Agent 按 Skill 规定的步骤建目录、探活或导日志、对错误、出中文报告——**体检接口健康度**，不改业务代码仓。

| 人给的 | 系统干的 | 达到的效果 |
|--------|----------|------------|
| OpenAPI URL 或文件 | `build_api_catalog` → 内存/落盘目录 | 知道「文档声明了哪些 path+method」 |
| 「探一下」 | `probe_api_catalog`（默认沙箱） | 2xx/4xx/超时有记录 |
| 「对照一下」 | `summarize_api_doc_vs_logs` + `rank_problematic_apis` | 文档条数 vs 已探条数 vs 问题榜 |
| 「出报告」 | `render_api_health_report` | 中文 Markdown 健康报告 |
| 网关 `.jsonl` / `.log` | `import_external_api_logs` → `analyze_api_errors_from_logs` | 注明「来自导入日志」的错误聚合 |

**技术落点（整包）：**

| 层次 | 路径 |
|------|------|
| 编排工具 | `apps/agent/tools/api_log_tool/api_health.py` |
| 底层 | `catalog.py`、`probe.py`、`log_import.py`、`call_store.py` |
| Skill | `apps/agent/skills/analyze-api-health/SKILL.md` |
| 沙箱进程 | `apps/sandbox/server.py`（默认 `http://127.0.0.1:8001`） |
| 对话入口 | `POST /api/chat/stream`（**无**独立 `/api-health` REST） |
| 落盘 | `data/api_catalog/`、`data/api_calls/calls.jsonl` |

### 1.2 两条路径，差在哪？不要混结果

| | **路径 A：文档 × 沙箱探活** | **路径 B：外部日志分析** |
|--|----------------------------|--------------------------|
| 输入 | OpenAPI URL / `.json` / `.yaml` | 用户上传的 `.jsonl` / nginx `.log` / CSV |
| 主步骤 | build → list → probe → summarize → rank → render | import → analyze |
| 主数字含义 | **文档接口总数**、探活成功/失败 | **本次导入条数**、错误频次 |
| 报告须写清 | 「来自沙箱探活」 | 「来自导入日志」 |
| 禁止 | 把用户 docs URL 改成硬编码 `:8001` | 用 `build_api_catalog` / `read_file` 硬啃日志；与 A 串数 |

**技术上怎么隔开：**

| 点 | 实现 |
|----|------|
| Skill 双剧本 | `analyze-api-health`：A 走 6 步，B 走 2 步；禁止混算 |
| 日志 source | `call_store` 记录带 `source` / `run_id`（sandbox vs import） |
| 误用改道 | `MesAccessLogRouteMiddleware`：对日志误调改道 `import_external_api_logs` |
| `list` 分页参数 | **`offset` / `limit`**，不是 `page` / `page_size` |

### 1.3 为什么默认走「沙箱」探活？

**人话：**  
- 模型若随便对用户 URL 狂打请求 → 可能压生产，也可能 SSRF 打到内网。  
- 所以探活默认走独立沙箱（`API_PROBE_SANDBOX_URL` ≈ `:8001`）或进程内 mock；真连外网须白名单。

**技术点：**

| 点 | 函数 / 模块 | 怎么做的 |
|----|-------------|----------|
| 沙箱代发 | `probe.run_catalog_probe` + `API_PROBE_SANDBOX_URL` | remote_url → `apps/sandbox/server.py` |
| URL 安全 | `assert_http_url_allowed` / `urlopen_limited` | 禁止乱打非白名单域名 |
| 调用落盘 | `call_store.append_api_call` | 写 `DATA_DIR/api_calls/`，供 summarize 对照 |
| live 模式 | `mode=direct`（非默认） | 仅白名单；一般 GET/HEAD → `PLATFORM_BASE_URL` |

### 1.4 安全与边界钉死了什么？

| 约束 | 技术实现 |
|------|----------|
| 无专用 REST | 全流程对话 Tool；不另起「健康服务」框架 |
| 沙箱失败 ≠ 生产不可用 | Skill + 报告文案强制注明来源 |
| A/B 数字不混 | `source_filter` / `run_id=latest`；报告分栏 |
| Token 不进日志 | `append_api_call` 剥离敏感头 |
| 文档 URL 白名单 | `API_DOCS_URL_ALLOWLIST`（拉 OpenAPI） |

---

## 2. 实现流程（人话 + 技术点怎么落地）

> 每节先讲「人看到什么 / 为什么这样」，再给 **技术点表** 和调用链。

### 2.1 路径 A：文档 × 沙箱探活（标准 6 步）

**人话：** 给 OpenAPI → 建目录 → 分页浏览条目 → 对沙箱（或白名单）发探测 → 对照文档与调用记录 → 排出问题接口 → 出中文报告。过程在对话里完成，过程区能看到工具状态。

```text
POST /api/chat/stream
  → Skill analyze-api-health
  → ① build_api_catalog(docs_url|file_path)     # catalog.py
  → ② list_api_catalog(tag?, keyword?, offset=0, limit=40)
  → ③ probe_api_catalog(mode=sandbox|direct, …)
         → probe.run_catalog_probe
         → append_api_call → data/api_calls/calls.jsonl
  → ④ summarize_api_doc_vs_logs(...)
  → ⑤ rank_problematic_apis(top_n=…)
  → ⑥ render_api_health_report() → report_markdown（SSE 流式）
```

**技术点：**

| 点 | 函数 / 模块 | 怎么做的 |
|----|-------------|----------|
| 建目录 | `build_api_catalog` / `catalog.build_catalog_from_*` | 落 `data/api_catalog/{api_index,meta}.json` |
| 列表分页 | `list_api_catalog` | **`offset`/`limit`**（max 100），不是 page |
| 探活 | `probe_api_catalog` | 默认 sandbox；`limit=0` 表示全量上限约 200 |
| 对照 | `summarize_api_doc_vs_logs` | 文档条数 vs 已探 vs 错误率阈值 |
| 排序 | `rank_problematic_apis` | 按 5xx、超时、4xx 等 |
| 报告 | `render_api_health_report` | 中文 Markdown |

---

### 2.2 路径 B：导入网关日志

**人话：** 上传一段网关错误日志 → 导入解析 → 按 path/status 聚合 → 中文解释。报告必须写「来自导入日志」，不能写成「沙箱探活失败了 N 次」。

```text
用户上传 .jsonl / .log（POST /api/upload → data/uploads/）
  → import_external_api_logs(file_path, format=auto, …)   # log_import.py
       → resolve_upload_path（仅 uploads 内）
       → parse_log_file → append_api_call(source=import)
  → analyze_api_errors_from_logs(source_filter=import, with_catalog=false, …)
  → 模型中文解释；禁止与路径 A 的探活总数混算
```

**技术点：**

| 点 | 函数 | 怎么做的 |
|----|------|----------|
| 路径校验 | `resolve_upload_path` | 只允许 `data/uploads` 内文件 |
| 默认不绑目录 | `with_catalog=False` | 避免把导入错误率说成文档探活失败率 |
| run 隔离 | `run_id` / `replace_previous` | 新导入可清掉上一批 import 记录 |

---

### 2.3 沙箱进程与配置怎么接？

**人话：** 本地开发用 `dev.sh` 起沙箱，默认监听 `127.0.0.1:8001`。探活打沙箱，不直接打用户生产网关；用户文档 URL 也**不能**被模型偷偷改成 `localhost:8001`。

```text
apps/sandbox/server.py
  → 内存 REST + /docs /openapi.json /health /__reset
  → 与生产 MES/网关隔离

probe 默认：
  API_PROBE_SANDBOX_URL=http://127.0.0.1:8001
  → 无 URL 时退进程内 local_mock
```

**技术点：**

| 点 | 怎么做的 |
|----|----------|
| 沙箱开关 | `API_PROBE_SANDBOX_URL` / `API_PROBE_SANDBOX_PORT` / `_HOST` |
| 扩展白名单 | `API_PROBE_SANDBOX_URL_ALLOWLIST`、`API_DOCS_URL_ALLOWLIST` |
| Skill 禁改 URL | 不得把用户 docs 改成硬编码沙箱地址 |

---

### 2.4 与 MES 查数、资料包 OpenAPI 对照

| 项目 | API 健康（本篇） | MES 查数（功能 02） |
|------|------------------|---------------------|
| 工具入口 | `probe_api_catalog` 等 | `query_platform_data` |
| 数据含义 | 接口通不通 / 日志错不错 | 业务行数据 |
| 默认目标 | 沙箱 / 白名单 URL | `PLATFORM_BASE_URL` + JWT |
| Skill | `analyze-api-health` | `query-mes-data` |
| REST | **无**专用；对话 Tool | 对话 Tool（查数） |

资料包里的 OpenAPI 可给路径 A 当 `file_path` 输入，但健康结论仍属「探活/日志」，不是业务行数。

---

### 2.5 出问题时先查哪？

| 现象 | 人话原因 | 技术上先看 |
|------|----------|------------|
| 探活全失败 | 沙箱没起 / URL 配错 | 沙箱进程；`API_PROBE_SANDBOX_URL`；`/health` |
| 文档解析空 | OpenAPI 缺 servers / 格式不对 | `build_api_catalog` 返回错误；`api_catalog/meta` |
| 报告成功率虚高 | 只探了子集 | `list_api_catalog` 的 offset/limit；`probe` 的 limit |
| 日志导入失败 | 格式不认 / 路径越界 | `import` 错误行号；是否在 `uploads/` |
| SSRF 被拒 | URL 不在 allowlist | 应走 `mode=sandbox`；查 allowlist |
| A/B 数字对不上 | 混算了 | 报告是否分清 source；`run_id` |

---

## 3. 技术及用法（速查）

| 模块 | 关键函数 | 干什么 |
|------|----------|--------|
| `api_health.py` | `build_api_catalog`、`list_api_catalog`、`probe_api_catalog`、`summarize_api_doc_vs_logs`、`rank_problematic_apis`、`render_api_health_report`、`import_external_api_logs`、`analyze_api_errors_from_logs` | Agent 可见 Tool 编排 |
| `catalog.py` | `build_catalog_from_url/file`、`load_index` | OpenAPI → 目录 |
| `probe.py` | `run_catalog_probe` | 探活请求与记录 |
| `call_store.py` | `append_api_call`、`query_api_calls` | `DATA_DIR/api_calls` |
| `log_import.py` | `import_log_file`、`parse_log_file` | 外部日志导入 |
| Skill | `analyze-api-health` | 6 步 A / 2 步 B 与边界 |
| 沙箱 | `apps/sandbox/server.py` | 隔离探活目标 |

**配置：**

| 变量 | 含义 |
|------|------|
| `API_PROBE_SANDBOX_URL` | 沙箱基址（dev 默认 `http://127.0.0.1:8001`） |
| `API_PROBE_SANDBOX_PORT` / `_HOST` | 沙箱监听 |
| `API_PROBE_SANDBOX_URL_ALLOWLIST` | 沙箱可代发的 host 扩展 |
| `API_DOCS_URL_ALLOWLIST` | 拉取 OpenAPI 的 host 扩展 |
| `API_CALL_LOG_MAX_LINES` | 调用日志保留行数（默认约 50000） |

**数据文件：** `data/api_catalog/api_index.json`、`data/api_calls/calls.jsonl`、导入附件在 `data/uploads/`。

文档：[`../API健康/API接口健康分析说明.md`](../API健康/API接口健康分析说明.md)、[`../API健康/API沙箱探活使用指南.md`](../API健康/API沙箱探活使用指南.md)；**实现以本篇为准**。

---

## 4. 后续可以怎么做、不要做什么

**可以做：**

1. 定时探活 + 趋势（仍写 `call_store`，报告加时间窗）  
2. 与资料包 OpenAPI 自动对齐「文档有、探活全 404」清单  
3. 报告结构化落库，方便「上周 Top 问题是否已修」  

**不要做：**

1. 把沙箱失败率直接说成「生产不可用」  
2. 把路径 B 的错误率写成路径 A 的探活失败总数  
3. 默认无白名单地探生产网关（须 allowlist + 限流）  
4. 另起一套专用 REST「健康微服务」替换对话 Tool 编排（除非产品明确要独立页）  

---

## 自测路径（验收）

1. 给一份 OpenAPI，按 Skill 走完 6 步 → 应有中文报告，并写清「沙箱探活」。  
2. 导入一段网关错误日志 → 报告须注明「来自导入日志」，数字不与 A 混。  
3. `list_api_catalog` 用 `offset`/`limit` 翻页，确认不是 `page`/`page_size`。  
4. 用户文档 URL 不应被改成硬编码沙箱 `8001`。  
