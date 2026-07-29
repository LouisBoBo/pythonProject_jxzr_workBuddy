---
name: analyze-api-health
description: >-
  根据用户提供的 Swagger/OpenAPI 文档测试接口，或导入外部网关/访问日志分析 API 错误。
  凡「测文档接口 / 根据 docs 测 API / 上传 openapi / 导入访问日志 / 分析接口错误率」均启用。
  硬性约定：文档探活默认沙箱；外部日志导入用 source=import，与沙箱结论分开表述。
  不要与表结构摸底、模拟查/导混谈。
---

# API 接口健康分析（文档 × 日志）

## 硬性约定

| 步骤 | 用什么 |
|------|--------|
| **建目录** | 用户 docs URL / 上传 OpenAPI（不是 .jsonl/.log） |
| **探活** | 沙箱（默认），不写生产 → 报告写**文档接口总数** |
| **外部错误分析** | 上传网关日志 → `import` → 报告写**本次日志条数** |

- 勿把用户 docs 改成 `:8001`
- 外部导入结论须注明「来自导入日志」，不要说成沙箱探活通过
- **禁止串数**：文档 62 ≠ 日志 7 条；两套报告主数字不得混写
- **run_id**：探活/导入每轮生成；`summarize`/`analyze` 对 sandbox|import 默认 `run_id=latest` 只看本轮

---

## 流程 A：文档沙箱测试（固定 6 步）

1. `build_api_catalog(docs_url=…)` 或 `file_path=…`
2. `list_api_catalog(limit=40)`
3. `probe_api_catalog()`（`limit=0` 全量）
4. `summarize_api_doc_vs_logs`
5. `rank_problematic_apis`
6. `render_api_health_report(docs_url=…)` → 用 `report_markdown` 回复

---

## 流程 B：外部日志导入 → 分析接口错误（推荐）

用户说「导入访问日志 / 根据日志看哪些接口有错误」且附件为 `.jsonl` / `.log` 时：

**硬性禁止**：`read_file`、`ls`、`glob`、`transform_file`、`build_api_catalog`（日志不是 OpenAPI；也不要用历史目录把「文档 62 个接口」写进日志报告）。

**必须两步**：

1. `import_external_api_logs(file_path=消息中的[附件路径])`  
   （默认清除旧的 source=import，只保留本次文件）  
2. `analyze_api_errors_from_logs(source_filter="import")`  
   （**默认 with_catalog=false**，不要传 docs_url；报告只谈本次日志的调用条数与错误/正常接口）

若误用了其它工具，中间件会自动改走导入；收到「已自动导入」后仍须调用 `analyze_api_errors_from_logs`。

**硬性：日志分析 ≠ 文档探活**  
- 日志报告：只统计本次导入的调用（如 7 条 → 归并为若干接口），禁止把文档接口总数写进主报告。  
- 文档探活：走流程 A（`render_api_health_report`），此时才展示文档接口总数。  
- 仅当用户**同时**要求「对照某份 docs」时，才 `with_catalog=true` 或传 `docs_url`（对照放附录）。

**硬性：只根据日志真实出现的路径分析，禁止编造未出现的接口。**

**最终回复必须含「总体评估」**：
- ❌ 错误接口清单（表格）
- ✅ 正常接口清单（表格）
- 结论：错误有哪些、正常有哪些、优先处理哪条

### 支持的日志形态

- **jsonl**：`{"method":"GET","path":"/api/orders/1","status":500,"latency_ms":12,"ts":...}`
- **nginx**：combined 访问日志（可带末尾 request_time 秒）
- **csv**：表头含 `method,path,status,latency_ms,ts`

---

## 回复要求

- 文档测试：用「接口文档测试结论」报告结构  
- 外部错误分析：用「API 接口错误分析」报告（排行 + 状态码 + 失败样例）  
- 禁止用 `{order_id}` vs `{id}` 编造故障  
- 禁止把导入日志结论说成沙箱全量通过  

## 边界

| 诉求 | 用法 |
|------|------|
| 测文档接口 | 流程 A |
| 导入日志查错误 | 流程 B |
| 表结构业务能力 | `analyze-mes-schema` |
| 查/导演示 | `query-mes-data` / `import-export-data` |
