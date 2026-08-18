# API 接口自动化测试复盘总结

> 日期：2026-07-28（含外部日志分析与「文档/日志串数」纠偏）  
> 仓库：`simplified-workbuddy`  
> 能力：  
> ① 文档（OpenAPI/Swagger）× 沙箱探活 × 出站日志 → 接口健康结论  
> ② 外部访问日志导入 → 接口错误分析（与 ① **数据与报告隔离**）  
> 说明文档：[`API接口健康分析说明.md`](API接口健康分析说明.md)、[`API沙箱探活使用指南.md`](API沙箱探活使用指南.md)

本文复盘从「文档沙箱探活」到「外部日志错误分析」的交付、踩坑、取舍与后续建议。

---

## 1. 目标与结果

### 1.1 能力 A：文档沙箱探活

**目标：**  
用户给出平台 Swagger/OpenAPI（URL 或上传文件）→ Agent 建目录、沙箱全量探活、对照调用日志 → 输出「可行 / 有问题 / 未见调用」专业报告。  
约束：**不破坏**既有查/导、写确认、表结构摸底；**默认不写生产**。

**结果：**  
以 Spring 文档 `http://localhost:8081/swagger-ui.html`（**62** 个接口）为验收样例，沙箱 `http://127.0.0.1:8001` 全量探活可达 **62/62 通过**。

### 1.2 能力 B：外部访问日志错误分析

**目标：**  
用户上传网关/Nginx/JSONL 访问日志 → 导入 → 只根据**本次日志**给出错误/正常接口清单。  
约束：与能力 A **不得串数**（文档 62 ≠ 日志条数）；不误用 `read_file` / `build_api_catalog` 处理上传日志。

**结果：**  
样例 `data/samples/api_access_sample.jsonl`：**7 条调用 → 归并 4 个接口**；错误排行仅含日志内真实失败路径；主报告**不再出现**「文档 62 个接口」。

| 维度 | 状态 |
|------|------|
| 文档 URL / 上传文件 → 统一接口目录 | ✅ |
| Spring `swagger-ui.html` → `/v3/api-docs` | ✅ |
| 出站调用落盘 `data/api_calls/calls.jsonl` | ✅ |
| 沙箱探活（local_mock / remote_url :8001） | ✅ |
| 文档×日志对照 + 问题排行 + 抽样 | ✅ |
| 创建→预置 id→查改删联动 | ✅ |
| 固定 6 步处理过程 + 专业报告 | ✅ |
| 外部日志导入（jsonl / nginx / csv，`source=import`） | ✅ |
| 日志错误分析报告（错误/正常总体评估） | ✅ |
| **文档探活报告 ↔ 日志分析报告数据隔离** | ✅ |
| 上传 `.jsonl`/`.log` 聊天附件放行 | ✅ |
| 误用工具自动改走导入（Middleware） | ✅ |
| 生产全量写探活 / 网关级 APM | ❌ 明确不做 |

---

## 2. 两条能力必须分开（核心产品约定）

| | 能力 A：文档探活 | 能力 B：日志错误分析 |
|--|------------------|---------------------|
| 用户话术 | 「根据 docs 测试接口」 | 「根据日志看哪些接口有错误」 |
| 输入 | docs URL / OpenAPI 文件 | `.jsonl` / `.log` / csv 访问日志 |
| 主数字 | **文档接口总数**（如 62） | **本次日志调用条数**（如 7）+ 归并接口数 |
| 工具链 | `build → list → probe → summarize → rank → render_api_health_report` | `import_external_api_logs` → `analyze_api_errors_from_logs`（默认 `with_catalog=false`） |
| 日志 source | `sandbox` / `erp` | `import`（导入前默认清旧 import） |
| 报告 | 「接口文档测试结论」 | 「API 接口错误分析」 |
| 禁止 | 把用户 docs 改成 `:8001` | 把历史目录「文档 N 个」写进主报告；`build_api_catalog` 吃日志 |

**验收反例（已修）：** 用户只上传 jsonl，报告却写「覆盖：文档 **62** 个接口；本次日志命中 4 个」——把两套能力串在一起。

---

## 3. 交付物总览

### 3.1 能力 A 链路

```text
用户 docs URL / 上传 OpenAPI
        │
        ▼
 build_api_catalog  ──►  data/api_catalog/api_index.json
        │
        ▼
 list_api_catalog → probe_api_catalog (sandbox) ──► calls.jsonl (source=sandbox)
        │
        ▼
 summarize + rank → render_api_health_report
```

### 3.2 能力 B 链路

```text
用户上传 access.jsonl / nginx.log
        │
        ▼
 import_external_api_logs  ──► 清除旧 source=import → 写入本次记录
        │
        ▼
 analyze_api_errors_from_logs(source_filter=import, with_catalog=false)
        │
        ▼
 report_markdown（7 条调用 / N 个接口 / 错误表 / 正常表）
```

可选：用户**同时**要求对照某份 docs → `with_catalog=true` 或 `docs_url=…`，对照仅进**附录**，不改主表数字。

### 3.3 核心代码与文档

| 类别 | 路径 |
|------|------|
| 目录解析 | `apps/agent/tools/api_log_tool/catalog.py` |
| 调用日志 | `apps/agent/tools/api_log_tool/call_store.py` |
| 外部日志导入 | `apps/agent/tools/api_log_tool/log_import.py` |
| 探活引擎 | `apps/agent/tools/api_log_tool/probe.py` |
| Agent 工具 | `apps/agent/tools/api_log_tool/api_health.py` |
| 访问日志路由中间件 | `apps/agent/middleware/access_log_route.py` |
| 沙箱服务 | `apps/sandbox/server.py`（默认 8001） |
| Skill | `apps/agent/skills/analyze-api-health/SKILL.md` |
| 附件强制路由 | `apps/api/agent_wrapper.py`（`_build_message`） |
| 说明 | `docs/API健康/API接口健康分析说明.md`、`docs/API健康/API沙箱探活使用指南.md` |

### 3.4 试用话术

```text
# 能力 A
根据 http://localhost:8081/swagger-ui.html 测试这个接口文档中的接口

# 能力 B
根据日志看哪些接口有错误   + 附件 api_access_sample.jsonl
```

样例文件：`data/samples/api_access_sample.jsonl`、`data/samples/api_access_sample.nginx.log`。

---

## 4. 关键设计取舍

| 议题 | 决定 | 原因 |
|------|------|------|
| 目录来源 vs 探活目标 | **分开** | docs 多为 `:8081`；探活打 `:8001` |
| 默认探活模式 | **始终 sandbox** | 含写方法；live 仅明确要求 |
| path_key | 模板段/数字/UUID → `{id}` | 禁止「参数名不同=故障」幻觉 |
| 文档报告 vs 日志报告 | **默认隔离** | `analyze` 默认 `with_catalog=false` |
| 重复导入 | **默认替换**旧 `source=import` | 避免 nginx 样例污染 jsonl 结论 |
| 缺 id 的接口 | **不跳过**，创建/预置后再测 | 用户要求全量 |
| 一键测文档 | **撤回**，保留 6 步 | 过程可见 + 报告更完整 |

---

## 5. 踩坑与修复（按主题）

### 5.1 文档拉取 404

- Spring `swagger-ui.html` 误走 FastAPI `/openapi.json` → 候选优先 `/v3/api-docs`。

### 5.2 幻觉根因「`{order_id}` vs `{id}`」

- `path_pattern_key` 统一模板段；Skill 禁止该推断。

### 5.3 假性高错误率（沙箱）

- 历史 sandbox 404 + 跨资源 id 填错 → 探活前清 sandbox 日志、资源族 seeding、低样本噪声规则。

### 5.4 LangGraph `Recursion limit of 25`

- `AGENT_RECURSION_LIMIT` 默认 **100**；探活结果压缩。

### 5.5 上传日志：路径找不到 / 误用工具

- **现象：** Agent 对 `data/uploads/*.jsonl` 调 `read_file`/`ls`/`transform_file`/`build_api_catalog` → `path_not_found` 或「不支持 .jsonl」；UI 误标「已读取技能说明」。  
- **修复：**  
  - 聊天 `accept` 放行 `.jsonl`/`.log`；  
  - `MesAccessLogRouteMiddleware` 拦截误用并自动 `import_external_api_logs`；  
  - `agent_wrapper` 附件强制路由 + 失败结果不再误标技能；  
  - `resolve_upload_path` 支持文件名 / `stem_timestamp.ext` 模糊匹配。

### 5.6 日志分析串入「文档 62 个接口」（本次重点）

- **现象：** 用户只上传 7 行 jsonl，报告写「文档 **62**」；错误榜混入上次 nginx 的 `inventory`。  
- **根因：**  
  1. `analyze_api_errors_from_logs` 默认 `with_catalog=true`，挂上历史 `api_index`；  
  2. 多次导入累加 `source=import`，跨文件污染。  
- **修复：**  
  - 默认 `with_catalog=false`；对照仅附录；  
  - 导入默认 `replace_previous` 清旧 import；  
  - 主报告指标固定为「日志调用条数 / 日志中的接口数」；  
  - Skill / 附件提示禁止对纯日志走 `build_api_catalog`。

### 5.7 Nginx 延迟单位

- `$request_time`（秒）正确 ×1000 为 ms；异常偏大延迟在报告中标注，避免 P95 显示成「约 20 分钟」。

---

## 6. 验收快照

### 6.1 文档探活（8081 × 8001）

| 项 | 值 |
|----|-----|
| 文档 | `http://localhost:8081/swagger-ui.html` → `/v3/api-docs` |
| 接口数 | **62** |
| 探活 | sandbox → `127.0.0.1:8001` |
| 通过 | 62 / 失败 0 |

### 6.2 外部日志（api_access_sample.jsonl）

| 项 | 值 |
|----|-----|
| 调用条数 | **7** |
| 归并接口 | **4** |
| ❌ 错误 | `DELETE /api/suppliers/delete/{id}`、`GET /api/orders/details/{id}` |
| ✅ 正常 | `POST /api/parts/create`、`GET /api/customers/get/{id}` |
| 主报告 | **不得**出现文档 62 / swagger 对照行 |

---

## 7. 经验教训

1. **目录源 ≠ 探活靶 ≠ 日志样本**：三套数字不能写进同一句「覆盖」。  
2. **默认值决定事故面**：`with_catalog=true` 会把「上一次文档会话」污染「这一次只看日志」。  
3. **导入必须可替换**：否则样例 nginx + jsonl 混算，用户会认为「瞎编接口」。  
4. **Agent 会误用通用文件工具**：上传目录不在虚拟 FS 内时，要用中间件 + 消息强制路由兜底。  
5. **日志是证据也是噪声**：探活清 sandbox；导入清旧 import；分析按 source 过滤。  
6. **报告 UX = 主数字一眼可懂**：日志报告先写「7 条 / 4 个接口」；文档报告才写「62 个接口」。

---

## 8. 已知限制

- 沙箱通过 ≠ 生产网关 / 鉴权 / 数据约束下的真实可用性。  
- `local_mock` 只证明工具链，不证明后端实现。  
- 预置 id / stub body 不能覆盖复杂业务校验。  
- path 归并后「7 条调用」可能对应「少于 7 个接口形态」，报告需同时展示两者。  
- 未做：定时巡检、CI 门禁、多环境对比、`probe_run_id` 级汇总隔离。

---

## 9. 后续建议

| 优先级 | 项 |
|--------|-----|
| P1 | 「8081 → 探活抽样 + jsonl 分析」无 LLM 冒烟：`make smoke-api-health` / `scripts/smoke_api_health.py` |
| P1 | 探活 / 导入按 `run_id` 隔离，汇总默认只看本轮 |
| P2 | 失败接口一键 `inspect` 进报告附录 |
| P2 | 可选真实预发沙箱做合同级验收 |

---

## 10. 一句话总结

**做成了两条互不串数的闭环：① 用户给文档 → 沙箱全量探活 → 文档健康报告（如 62/62）；② 用户上传访问日志 → 导入替换 → 仅基于本次日志的错误分析（如 7 条 / 4 接口）。并在路径解析、id 联动、日志噪声、递归上限、附件误用、文档/日志串数上完成多轮纠偏；默认不写生产，与查导/写确认/表结构摸底并存。**
