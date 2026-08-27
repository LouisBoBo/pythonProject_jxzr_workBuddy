# 05 · API 接口健康分析

> 拿 Swagger/OpenAPI（或网关日志）做目录、沙箱探活、对照错误，输出**中文健康报告**——帮实施/运维看「接口文档靠不靠谱、哪条老挂」。

---

## 1. 实现原理

### 1.1 解决什么问题？

实施/运维手里常有：

- 一份 Swagger / OpenAPI（「理论上有哪些接口」）  
- 一堆网关错误日志（「实际上哪些在报错」）

人工对照很费时间。这个功能让 Agent **按固定步骤**建目录、探活、对日志、出中文报告——不是改业务代码，是**体检接口健康度**。

### 1.2 两条路径，不要混结果

| 路径 | 输入 | 干什么 | 结论里要写清 |
|------|------|--------|--------------|
| **A. 文档 × 沙箱探活** | OpenAPI URL 或上传的 json | 建目录 → 逐个发探测请求 → 看 2xx/4xx/超时 | 「来自沙箱探活」 |
| **B. 外部日志分析** | 用户上传 .jsonl / .log | 解析错误码、路径、频次 | 「来自导入日志」 |

Skill `analyze-api-health` 明确：不能把 B 的错误率直接说成 A 探活失败总数。

### 1.3 为什么默认走「沙箱」探活？

如果让模型随便对用户给的 URL 发请求，可能：

- 打到生产网关造成压力  
- 打到内网不该扫的地址（SSRF 风险）

所以探活默认走 `API_PROBE_SANDBOX_URL`（独立沙箱进程 `apps/sandbox/server.py`）或进程内 mock；  
只有白名单内的 URL 才允许真连外网（`API_PROBE_SANDBOX_URL_ALLOWLIST`）。

### 1.4 调用记录存哪？

每次 probe 写入 `DATA_DIR/api_calls/`（`call_store.py`），后面 `summarize_api_doc_vs_logs` 用来对照「文档声明的方法」和「实际打出去的记录」。

### 1.5 谁在执行？

Deep Agents 编排多步 Tool；HTTP 探测在 Python 里发，不是浏览器里发。  
不涉及 Cursor、不涉及 git。

---

## 2. 实现流程（技术点怎么落地）

> Skill `analyze-api-health` 规定 6 步顺序；HTTP 探测在 Python 发，默认走沙箱防 SSRF。

### 2.1 路径 A：文档 × 沙箱探活（标准 6 步）

```text
① build_api_catalog(source_path|url)     # catalog.py / api_health.py
     解析 OpenAPI → 内存目录（path, method, summary）

② list_api_catalog(page, page_size)
     分页列出可探活条目

③ probe_api_catalog(catalog_id, mode=sandbox|direct, ...)
     对选中接口发 HTTP
     → assert_http_url_allowed + urlopen_limited
     → append_api_call() 写入 DATA_DIR/api_calls/

④ summarize_api_doc_vs_logs()
     文档条数 vs 已探条数 vs 成功/失败比

⑤ rank_problematic_apis(top_n)
     按 5xx、超时、4xx 排序

⑥ render_api_health_report()
     中文 Markdown 报告 → SSE 流式返回
```

| 技术点 | 实现 |
|--------|------|
| 沙箱默认 | `API_PROBE_SANDBOX_URL` → `apps/sandbox/server.py` 代发 |
| 真连外网 | 仅 `API_PROBE_SANDBOX_URL_ALLOWLIST` 内 URL |
| 调用记录 | `call_store.py`；与 MES `query_platform_data` 出站日志同目录族 |
| Skill 禁止 | 不得把用户文档 URL 偷偷改成 `localhost:8001` |

### 2.2 路径 B：导入网关日志

```text
用户上传 .jsonl / .log（POST /api/upload）
  → import_external_api_logs(path)（log_import.py）
  → analyze_api_errors_from_logs(source=import)
  → 聚合 path、status、message、count
  → 模型中文解释；报告须注明「来自导入日志」
```

**与路径 A 不可混算：** B 的错误率不能写成 A 的探活失败总数。

### 2.3 SSE 编排（Agent 侧）

```text
POST /api/chat/stream（默认 lane）
  → Skill analyze-api-health 加载
  → 模型按 1→6 调 Tool（可多轮）
  → agent_wrapper 推 tool_status + 最终 token
```

无单独 REST「/api-health」；全流程在对话里完成。

### 2.4 与 MES 查数对比

| 项目 | API 健康 | MES 查数 |
|------|----------|----------|
| 工具入口 | `probe_api_catalog` | `query_platform_data` |
| 数据含义 | 接口通不通 | 业务行数据 |
| 默认目标 | 沙箱 / 白名单 URL | `PLATFORM_BASE_URL` + JWT |
| Skill | `analyze-api-health` | `query-mes-data` |

### 2.5 常见排查

| 现象 | 查什么 |
|------|--------|
| 探活全失败 | 沙箱进程是否起；`API_PROBE_SANDBOX_URL` |
| 文档解析空 | OpenAPI 缺 `servers`；build 阶段错误信息 |
| 报告成功率虚高 | 是否只探了子集；看 `list_api_catalog` 分页 |
| 日志导入失败 | 格式不认；`import` 返回的错误行号 |
| SSRF 被拒 | URL 不在 allowlist；应走 sandbox 模式 |

---

## 3. 技术及用法

| 技术 / 模块 | 怎么用 |
|-------------|--------|
| `tools/api_log_tool/catalog.py` | 从 OpenAPI 建目录 |
| `probe.py` | 探活请求与记录 |
| `call_store.py` | 调用日志存储（`DATA_DIR/api_calls`） |
| `api_health.py` | 摘要 / 排序 / 报告 |
| `log_import.py` | 外部日志导入 |
| Skill `analyze-api-health` | 规定 6 步与「导入日志」边界 |
| 配置 | `API_PROBE_SANDBOX_URL`、`API_PROBE_SANDBOX_URL_ALLOWLIST` |

文档：`docs/API健康/API接口健康分析说明.md`、`API沙箱探活使用指南.md`。

---

## 4. 后续扩展与优化建议

1. **可做**：定时探活 + 趋势（仍写 call_store，报告加时间窗）。  
2. **可做**：与资料包 OpenAPI 自动对齐「文档有、探活全 404」清单。  
3. **慎做**：默认探生产网关（须白名单 + 限流）。  
4. **不要做**：把沙箱失败率直接说成「生产不可用」。

---

## 自测路径

1. 给一份 OpenAPI，按 Skill 走完 6 步，应有中文报告。  
2. 导入一段网关错误日志，报告须注明来源为导入。  
3. 用户文档 URL 不应被改成硬编码沙箱 `8001`（Skill 明确禁止乱改）。  
