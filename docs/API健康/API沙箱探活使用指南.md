# API 沙箱探活使用指南

面向：**根据接口文档测试 API**（Swagger / OpenAPI URL 或上传文件）——即「能力 A：文档沙箱探活」。

**硬性约定：所有文档接口相关测试，默认都在沙箱里跑，不改生产平台数据。**  
用户对话里不必提「沙箱」——说「测试文档接口」即可。

若需求是「上传访问日志看哪些接口有错误」（能力 B），见 [API接口健康分析说明.md](API接口健康分析说明.md) 的「外部日志导入」；**不要**把文档接口总数写进日志报告。过程复盘：[API接口自动化测试复盘.md](API接口自动化测试复盘.md)。

---

## 1. 沙箱是什么

沙箱 = 探活时的安全执行环境，用来：

1. 按接口目录批量发请求（可含 POST / PUT / PATCH / DELETE）
2. 把结果写入 `data/api_calls/calls.jsonl`
3. 再对照目录做「可行 / 有问题 / 未见调用」分析

它**不会**走导入确认卡，也**不会**改 MES 业务落盘（uploads / writes 等）。

### 安全警告（alg:none）

探活沙箱登录会签发 **`alg:none` 无签名假 JWT**，响应带 `"sandbox": true`。

| 层 | 行为 |
|----|------|
| 沙箱 `:8001` | 仅本地探活；启动日志会打印 `SANDBOX-ONLY … alg=none` |
| WorkBuddy 登录映射 | **仅当**上游响应 `sandbox: true` 才读 `alg=none` 的 payload |
| WorkBuddy **会话** | 始终 `session_jwt` **HS256**；`alg=none` **一律拒绝**（见 `apps/agent/session_jwt.py`） |

**禁止**：把沙箱「不验签 / alg=none」抄到真实 MES 登录或生产会话校验。

---

## 2. 沙箱只有一种 mode，两种实现

先分清两层，避免把「没配 URL」理解成「不走沙箱」：

| 层级 | 值 | 含义 |
|------|-----|------|
| **mode** | 固定 `sandbox`（文档测试默认） | **一定在沙箱里测**，不打生产 |
| **sandbox_kind** | `local_mock` 或 `remote_url` | 沙箱**怎么实现**（自动选） |

`local_mock` **就是沙箱**，不是绕过沙箱。只是没配外部沙箱地址时，用进程内存模拟请求。

| sandbox_kind | 何时启用 | 实际做什么 | 能证明什么 |
|--------------|----------|------------|------------|
| **local_mock**（默认） | 未配置 `API_PROBE_SANDBOX_URL` | 仍在 `mode=sandbox`；进程内内存模拟 REST；**零网络打生产** | 目录能覆盖、工具链能跑通；**≠ 生产写接口真实可用** |
| **remote_url** | 已配置 `API_PROBE_SANDBOX_URL`（**`./scripts/dev.sh` 默认会配并启动本仓沙箱**） | 仍在 `mode=sandbox`；真实 HTTP 打到该沙箱地址 | 沙箱环境上的真实接口行为（仍不碰生产 `PLATFORM_BASE_URL`） |

```text
文档接口测试
  └─ 一律 mode=sandbox（在沙箱中）
        ├─ 未配 API_PROBE_SANDBOX_URL
        │     └─ 仍用沙箱，实现 = local_mock（Agent 进程内存模拟）
        └─ 已配 API_PROBE_SANDBOX_URL（dev.sh 默认）
              └─ 仍用沙箱，实现 = remote_url → 本仓 apps/sandbox :8001
```

开发一键启动：

```bash
./scripts/dev.sh
# Web              http://127.0.0.1:5180
# 用户文档（建目录）通常 http://127.0.0.1:8000/docs
# 探活沙箱（自动）   http://127.0.0.1:8001
# 停止             ./scripts/stop.sh
```

---

## 3. 用户怎么用（对话）

先 `./scripts/dev.sh`（启动探活沙箱 `:8001`，并为 API 注入 `API_PROBE_SANDBOX_URL`）。

### 分清：文档来源 ≠ 探活目标

| | 地址 | 作用 |
|--|------|------|
| **用户文档** | 通常 `http://127.0.0.1:8000/docs`（或上传 openapi） | 只用来 **建目录** |
| **探活沙箱** | `http://127.0.0.1:8001`（后台自动用） | 实际发测试请求，**不改生产** |

用户给的是平台 docs（8000），**不要**让用户改口成 8001/docs。

### 3.1 最常见

> 根据 http://127.0.0.1:8000/docs 测试文档接口

（`#/` 可有可无）

或：

> 我上传了 openapi.json，测一下这些接口哪些有问题

助手会自动：

1. `build_api_catalog(docs_url=用户给的 8000/docs 或 file_path)` — 建目录  
2. `probe_api_catalog()` — **默认打沙箱 8001**（含写，不改生产）  
3. `summarize_api_doc_vs_logs` — 按日志出结论  

### 3.2 只分析已有出站/探活日志（不探活）

> 根据最近日志，对照当前接口目录看哪些有问题

只走 `summarize_api_doc_vs_logs`（及排行/抽样），不强制探活。  
这仍属**能力 A**（对照的是当前目录 + sandbox/erp 日志）。

### 3.2b 上传外部访问日志（能力 B，非本文主流程）

> 根据日志看哪些接口有错误 + 附件 `.jsonl`/`.log`

走 `import_external_api_logs` → `analyze_api_errors_from_logs`（默认不挂目录）。  
主报告数字是**本次日志条数**，不是文档接口总数。详见健康分析说明。

### 3.3 明确要打生产（例外）

> 用生产只读探活核验一下 GET 接口

才会 `probe_api_catalog(mode="live")` —— **只读**，禁止写生产。

---

## 4. 配置（可选）

在仓库根 `.env`：

```bash
# ---------- 默认不用配：仍走沙箱，实现为 local_mock（内存）----------

# 若有独立沙箱 ERP（勿填生产地址）：
# API_PROBE_SANDBOX_URL=http://127.0.0.1:8001

# 沙箱 host 不在默认白名单时追加：
# API_PROBE_SANDBOX_URL_ALLOWLIST=sandbox.example.com

# 拉 OpenAPI 文档的 host 白名单（与目录构建共用思路）：
# API_DOCS_URL_ALLOWLIST=

# 生产平台（live 只读探活、以及日常查/导才用）：
# PLATFORM_BASE_URL=http://localhost:8000
```

白名单默认含：`127.0.0.1`、`localhost`、`PLATFORM_BASE_URL` 的 host。

---

## 5. 工具参数（给排障 / 进阶）

`probe_api_catalog` 默认值已按「文档测试 = 沙箱」设好：

| 参数 | 默认 | 含义 |
|------|------|------|
| `mode` | `sandbox` | 文档测试用这个；生产只读才改 `live` |
| `only_unseen` | `false` | 文档全量测试；只补洞可改 `true` |
| `reset_sandbox` | `true` | local_mock 清空内存；remote 会 `POST /__reset` |
| `include_writes` | sandbox 下默认 `true` | live 下禁止写 |
| `sample_id` | 每轮唯一 `seed-{ts}` | 按参数名选资源 id（如 `supplierId`→供应商） |
| `limit` | `0`（全量，上限 200） | 文档测试请保持 0，勿缩小漏测 |
| `keyword` / `tag` | 空 | 只测目录子集 |

**推荐 Agent 固定 6 步**：`build_api_catalog` → `list_api_catalog` → `probe_api_catalog` → `summarize_api_doc_vs_logs` → `rank_problematic_apis` → `render_api_health_report`。  
最终用 `report_markdown` 专业报告回复（总览表 + 业务模块）；`recursion_limit` 默认 100（`AGENT_RECURSION_LIMIT`）。

探活开始会清理历史 `sandbox`/`probe` 日志（保留 `erp`），避免旧 404 抬高错误率。  
`summarize`：调用≤3 且仅失败 1 次不标 problematic。

测完看日志：`data/api_calls/calls.jsonl`  
- 沙箱：`source=sandbox`，并带 `sandbox_kind=local_mock|remote_url`  
- 生产只读探活：`source=probe`  
- 日常业务出站：`source=erp`

---

## 6. local_mock（默认沙箱实现）

**仍是沙箱**（`mode=sandbox`，`source=sandbox`）。只是没有外部沙箱服务器时，在进程内存里模拟 REST：

- `POST /resource` → 创建（201）  
- `GET /resource` → 列表（200）  
- `GET/PUT/PATCH/DELETE /resource/{id}` → 读写删（id 默认 `sandbox-1`）  
- 进程重启或 `reset_sandbox=true` → 内存清空  

**不会**请求 `PLATFORM_BASE_URL`，**不会**改平台库。

因此回复里应写清：本次为沙箱（本地模拟）证据，未改生产；**不能**说成「生产写接口已验证」。

---

## 7. remote_url / 本仓沙箱服务

`./scripts/dev.sh` 会一并启动 `apps/sandbox/server.py`（默认 `http://127.0.0.1:8001`），并为 API 进程注入 `API_PROBE_SANDBOX_URL`。

手动只起沙箱：

```bash
python3 apps/sandbox/server.py
# http://127.0.0.1:8001/docs
```

---

## 8. 和「查工单 / 导入」的区别

| | 沙箱探活 | 模拟查/导 / 写确认 |
|--|----------|-------------------|
| 目的 | 测文档里的 HTTP 接口 | 演示业务数据操作 |
| 默认目标 | 沙箱（local_mock 内存 或 remote_url 沙箱机） | MockClient 或生产 ERP |
| 写生产 | 否（除非误配 URL） | 导入经确认卡可写生产 |

不要把沙箱探活结论写成「平台业务能力」或「已导入成功」。

---

## 9. 推荐验收话术

1. 「根据 http://127.0.0.1:8000/docs 测试文档接口」  
   → 目录来自 8000；探活打 8001 沙箱；声明未改生产  
2. 日志 `source=sandbox` + `sandbox_kind=remote_url`（dev.sh 已注入 URL）  
3. **不要**要求用户改成「根据 8001/docs」  
4. 说「生产只读探活」时才 `mode=live`，且无 POST/PUT/DELETE 打生产  

更完整的能力边界与 path_key 规则见：[API接口健康分析说明.md](API接口健康分析说明.md)
