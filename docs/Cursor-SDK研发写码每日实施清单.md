# Cursor SDK 研发写码：每日完成项与实施步骤

> 状态：**执行清单**（2026-08-04）  
> 依据：[`Cursor-SDK研发写码一期方案.md`](./Cursor-SDK研发写码一期方案.md)  
> 原则：按日交付可验收增量；每天结束必须跑「主对话不受影响」回归；**不改** `/api/chat/stream` 默认逻辑。

---

## 总览（约 9 个工作日）

| 日 | 主题 | 当日结束时「能演示什么」 |
|----|------|-------------------------|
| D0 | 环境与账号就绪 | 有 Key、有测试仓、有 `.env` 项；未写业务代码也可 |
| D1 | 后端骨架 + 只读 API | `GET /status`、`GET /repos`；熔断时主服务仍起 |
| D2 | 前端入口壳 | 侧栏进 `/dev-agent`；与主对话互不影响 |
| D3 | SDK CLI 冒烟 | 命令行对测试仓跑通一次 Cloud Agent |
| D4 | Job 创建 + 状态机 | `POST /jobs` 落盘；白名单拒绝生效 |
| D5 | SSE 流式执行 | 网页/接口能看到写码过程事件 |
| D6 | HITL + 开 PR | 确认后出 PR 链接；审计有记录 |
| D7 | 限流 / 超时 / 取消 / 失败隔离 | 拔 Key 不影响 MES 对话 |
| D8 | Smoke + 试点收口 | 契约脚本绿；1～2 人真仓试用清单过关 |

进度勾选：把下方每日 `- [ ]` 改成 `- [x]` 即可跟踪。

---

## 每日固定回归（每天收工必做）

```bash
# 主链路（按仓库现有脚本择一或组合）
make smoke-api-contracts 2>/dev/null || python scripts/smoke_api_contracts.py
# 若本机常用：
# make smoke-embed-identity
```

额外约定：

- 当天改动 **禁止** 修改 `apps/agent/agents/agent.py` 工具列表来「顺便」调 Cursor。
- 当天若动了 `main.py`，只允许 `include_router` + `data/cursor_dev` 目录创建。
- 收工在本清单对应日勾选，并在 PR/日记中写一句「主对话回归：通过/失败」。

---

## D0 — 环境与账号就绪（0.5～1 天）

> **进度（2026-08-04）**：磁盘 `.env` 已确认：`ENABLED=1`、Key 已设、白名单 `LouisBoBo/pythonProject_zr_aicoding`。`available` 尚为 false 仅因未装 `cursor-sdk`（D3 安装后即可）。

### 完成项

- [x] 申请 / 备好 `CURSOR_API_KEY`（你已在编辑器配置；请确认已保存到磁盘 `.env`）
- [x] 准备测试仓：`LouisBoBo/py`（截图中的 URL 等价于此）
- [ ] 确认模型账号可用（目标：`composer-2.5`）← D3 CLI 再验
- [x] 在本地 `.env` / `.env.example` **只增加注释占位**
- [x] 约定白名单格式：`owner/repo`（亦接受 `https://github.com/owner/repo`）
- [x] `data/cursor_dev/.gitkeep` + `.gitignore` 忽略 jobs/审计产物

### D0 备忘

| 项 | 值 |
|----|-----|
| 测试仓 `owner/repo` | `LouisBoBo/pythonProject_zr_aicoding` |
| Key 来源 | Dashboard Integrations |
| 模型 | `composer-2.5`（默认） |

**请保存 `.env` 为：**

```bash
CURSOR_DEV_ENABLED=1
CURSOR_API_KEY=...          # 勿提交、勿再贴到聊天
CURSOR_DEV_REPO_ALLOWLIST=LouisBoBo/py
```

---

## D1 — 后端骨架 + 只读 API

> **进度（2026-08-04）**：后端骨架已落地；保存 `.env` 并重启 API 后可用 curl 验收。

### 完成项

- [x] 新建 `apps/cursor_dev/`：`config.py`、`allowlist.py`、`__init__.py`
- [x] 新建 `apps/api/routes/cursor_dev.py`：`GET /status`、`GET /repos`
- [x] `main.py`：`include_router` + `data/cursor_dev` 目录
- [x] `CURSOR_DEV_ENABLED=0` 或无 Key 时：`available=false` + `reason`，**进程不崩**
- [x] 鉴权：与现有路由一致（JWT）；未登录 401
- [x] `scripts/smoke_cursor_dev_d1.py` 单测（normalize / allowlist / 无 Key）

### 实施步骤

1. 实现 `config.py`：从环境变量读开关、白名单、限流数字；`feature_available()` 聚合「开关 + Key + sdk 可 import」。  
2. 实现 `allowlist.py`：解析 CSV；`normalize_repo()`；`is_allowed(repo) -> bool`。  
3. 路由：

   - `GET /api/cursor-dev/status` → `{ available, reason?, allowlist_count, model? }`  
   - `GET /api/cursor-dev/repos` → 白名单列表（available=false 时仍可返回空列表或 503，推荐 **200 + available=false**，方便前端灰显）

4. `main.py` 增加 `data/cursor_dev` 到目录创建循环。  
5. 用 curl + 登录 token 打两接口。  
6. 跑每日固定回归。

### 当日验收

| 用例 | 期望 |
|------|------|
| 无 Key / enabled=0 | status.available=false；`/health` ok；主 chat 可用 |
| 有 allowlist | repos 返回对应项 |
| 未登录 | 401 |

### 禁止

- 本日不引入对 Cloud Agent 的真实调用（可先不装 `cursor-sdk`，或 optional import）。

---

## D2 — 前端（统一主对话，不另开页）

> **进度（2026-08-04）**：**已纠正**。删除独立写码页与侧栏入口；`/dev-agent` → `/`。写码后续在 **ChatView** 内用选仓卡 + 同一 SSE 完成（对标 IDE/Git 选仓）。`api.js` 保留 status/repos 供对话卡片使用。

### 完成项

- [x] 撤销 `CursorDevView.vue` / 侧栏「研发写码」
- [x] `/dev-agent` 重定向到主对话
- [x] 方案改为「统一 Chat + 引擎隔离」
- [x] Chat 内写码选仓卡（`CursorDevRepoPickCard`，对标 Git 选仓；「我要开发功能」等会弹出）
- [x] **不**做第二套导航抢戏

### 实施步骤

1. 路由：`{ path: '/dev-agent', name: 'dev-agent', component: CursorDevView }`。  
2. 侧栏 `router-link` 到 `/dev-agent`；嵌入模式可隐藏（一期建议非 embed 显示即可）。  
3. 页面 onMounted 拉 status/repos；表单先 disable「开始」按钮（等 D4/D5）。  
4. 手动：登录 → 点入口 → 回「开启新对话」→ MES 话术仍走原 Chat。  
5. 跑每日固定回归（前端冒烟以手测为主）。

### 当日验收

- 双入口可切换；主 Chat 发一句查询不进写码页。  
- 写码页不依赖 Deep Agents 会话。

---

## D3 — SDK CLI 冒烟（不挂 Web）

> **进度（2026-08-04）**：已 `pip install cursor-sdk`；`requirements.txt` 已加依赖；`scripts/smoke_cursor_sdk_cli.py` dry 通过（models.list 含 `composer-2.5`）。配置齐全时 `availability=True`。重启 API 后对话选仓卡橙条应消失。Live：`SMOKE_CURSOR_LIVE=1 python3 scripts/smoke_cursor_sdk_cli.py`

### 完成项

- [x] `requirements.txt` 增加 `cursor-sdk>=1.0.24`
- [x] `scripts/smoke_cursor_sdk_cli.py`：显式 Cloud + dry/live 开关
- [x] dry：打印 models；区分未开 LIVE
- [ ] live（可选）：Cloud 改测试仓 README 冒烟行（需 `SMOKE_CURSOR_LIVE=1`）
- [x] 文档备注：勿进默认必跑 smoke；LIVE 耗用量

### 实施步骤

1. `pip install cursor-sdk`（开发机）。  
2. 脚本读取 `.env` 的 `CURSOR_API_KEY` 与 allowlist 第一项。  
3. 使用 **显式** `cloud=`（禁止默认 local）：极简需求如「在 README 增加一行 Controlled by WorkBuddy cursor-dev smoke」。  
4. `auto_create_pr=False` 先只验证能跑；或 True 若仓策略允许。  
5. 确认 dispose / `with` 无僵尸进程。  
6. **不改**前端；跑每日固定回归证明主链路未因新依赖导入而挂（API 启动时 optional import）。

### 当日验收

- CLI 对测试仓至少一次 `finished`（或明确可重试错误已记录）。  
- `import cursor_sdk` 失败时，API 进程仍能启动（D1 的 optional 路径）。

---

## D4 — Job 存储与创建 API

> **进度（2026-08-04）**：已落地 `prompts`/`jobs`/`audit`；`POST /api/cursor-dev/jobs`（须 confirmed）；`GET /jobs/{id}`；对话确认选仓后先建 job。执行与 SSE 已在 D5 接通。

### 完成项

- [x] `apps/cursor_dev/jobs.py`：创建 / 读写 job（`data/cursor_dev/jobs/`）
- [x] `apps/cursor_dev/audit.py`：追加写审计
- [x] `apps/cursor_dev/prompts.py`：系统前缀 + 用户需求拼接
- [x] `POST /api/cursor-dev/jobs`：校验登录、授权、白名单（空=不限）、prompt 长度；`confirmed=true` 必填
- [x] 非白名单（当名单非空）→ 400；未确认 → 400
- [x] Job 字段预留：`review_job_id=null`、`runtime=cloud`
- [x] Chat 确认选仓 → `createCursorDevJob` → 带 `cursor_dev_job_id` 续聊
- [x] `scripts/smoke_cursor_dev_d4.py`

### 实施步骤

1. 定义 Job schema：`id, user_id, repo, ref, prompt, create_pr, status, agent_id, run_id, pr_url, error, created_at, updated_at`。  
2. 状态：`draft|confirmed|queued|running|succeeded|failed|cancelled`（创建时直接 `queued` 若带确认）。  
3. `POST` body 示例：

```json
{
  "repo": "your-org/workbuddy-cursor-sandbox",
  "ref": "main",
  "prompt": "给 README 增加一段使用说明",
  "create_pr": true,
  "confirmed": true
}
```

4. 本日 **可以**只入队不执行（status=queued），或同步调 stub。推荐：入队 + 返回 job id，执行留给 D5。  
5. 前端：点「开始」弹出确认文案 → 确认后 `POST`；列表/详情展示 job 状态。  
6. 跑每日固定回归。

### 当日验收

| 用例 | 期望 |
|------|------|
| 白名单外 repo | 400 |
| confirmed 缺失/false | 400 |
| 合法创建 | 201 + job_id；磁盘有文件；审计有一行 |

---

## D5 — 真正执行 + SSE

> **进度（2026-08-04）**：执行与 SSE 已通。交互改为：**先正常对话澄清需求** → 助手输出 `cursor_dev_propose` → 弹确认卡（仓库+需求摘要）→ 确认即 Cursor；取消可继续聊并再次弹卡。

### 完成项

- [x] `apps/cursor_dev/service.py`：封装 create/send/stream/wait/dispose；仅 Cloud
- [x] 后台任务（`asyncio.to_thread` + queue）消费 queued job
- [x] `GET /api/cursor-dev/jobs/{id}/stream`：SSE 推送 `status|step|token|pr|done|error`
- [x] 前端订阅 SSE，过程区更新；结束后展示摘要（`streamCursorDevJob`；确认后不调 `startAssistantStream`）
- [x] 记录 `agent_id` / `run_id` 到 job
- [x] `scripts/smoke_cursor_dev_d5.py`（mock Cloud）

### 实施步骤

1. `service.run_job(job, event_sink)`：拼 prompts → Cloud Agent → 把 SDK 事件映射为内部事件。  
2. sync SDK 则用 `asyncio.to_thread` + queue 推事件，避免堵 loop。  
3. SSE 格式对齐现有 chat（便于复用 ProcessPanel 心智）：`data: {json}\n\n`。  
4. 前端：`EventSource` 或 fetch stream（与现网 chat 一致的方式优先）。  
5. 对测试仓跑通「改 README」类小需求。  
6. 跑每日固定回归。

### 当日验收

- 创建 job 后 SSE 有 running → done/failed。  
- 测试仓出现 commit 或可观测改动（视是否开 PR）。  
- 主对话同时开一窗仍可查询。
- **确认写码后过程区不得出现「筛选功能源码」等审核工具**（必须 Cursor 旁路）。

---

## D6 — HITL 固化 + 自动开 PR + 审计完善

### 完成项

- [ ] 启动前确认文案固定含：仓库、是否开 PR、分支前缀、**不会自动合入**
- [ ] `CURSOR_DEV_AUTO_PR=1` 时 Cloud `auto_create_pr=True`，`skip_reviewer_request=True`
- [ ] 从 run 结果 / 事件中解析 `pr_url`（及 branch 若有）写入 job
- [ ] 前端结果区展示可点击 PR 链接
- [ ] 审计字段齐全；日志中无 API Key
- [ ] **不实现** merge 接口

### 实施步骤

1. 确认弹窗文案与 `confirmed` 门禁联调（前端不传 confirmed 则后端拒）。  
2. Prompt 中写明分支前缀 `CURSOR_DEV_BRANCH_PREFIX`。  
3. 解析 PR：优先 SDK 结构化字段；否则从最终文本用保守正则提取 `https://github.com/.../pull/N`（记录解析来源）。  
4. 手测：开出 PR → 浏览器打开 → 人工 Review（不合入也可）。  
5. 跑每日固定回归。

### 当日验收

- 一次完整路径：确认 → 执行 → 页面出现 PR 链接 → `data/cursor_dev` 审计可查。  
- 代码库无 `/merge` 之类 API。

---

## D7 — 限流、超时、取消、失败隔离

### 完成项

- [ ] 全局限流 + 每用户限流（排队或 429）
- [ ] `CURSOR_DEV_JOB_TIMEOUT_SEC`：超时 → cancel（若支持）→ failed
- [ ] `POST /jobs/{id}/cancel`
- [ ] `CURSOR_DEV_ALLOWED_USERS` 非空时：不在名单 → 写码 403，主对话 200
- [ ] 拔掉 Key / `ENABLED=0`：写码页提示；`/health` 与 chat 正常
- [ ] 错误文案中文化：启动失败 vs 执行失败

### 实施步骤

1. `jobs.py` 统计 `running` 数量；超限拒绝创建。  
2. 执行包装 `asyncio.wait_for` / 截止时间检查。  
3. cancel：调用 `run.cancel()`（先 `supports("cancel")`）。  
4. 写隔离测试用例进 D8 脚本（本日可手测）。  
5. 跑每日固定回归。

### 当日验收

| 用例 | 期望 |
|------|------|
| 超并发 | 429 或明确排队错误 |
| 无 Key | 写码不可用；MES chat 可用 |
| 取消 | job=cancelled；尽量停止 Cloud run |

---

## D8 — Smoke 契约 + 试点收口

### 完成项

- [ ] `scripts/smoke_cursor_dev.py`：  
  - status 契约  
  - 未登录 401  
  - 非白名单 400  
  - 未确认 400  
  - enabled=0 时主 `/health` ok  
  - live 开 PR 仅 `SMOKE_CURSOR_LIVE=1`  
- [ ] Makefile / README 增加可选目标说明（不强制进默认 all-smoke）  
- [ ] 功能清单补 3～5 条用例（可写在本文件附录或 [`功能清单与测试用例.md`](./功能清单与测试用例.md)）  
- [ ] 1～2 名研发试点：真实小需求 → PR → 人工合入反馈  
- [ ] 盯 [usage](https://cursor.com/dashboard/usage) 一天，必要时下调并发
- [ ] **开箱上线**：按 [`Cursor写码车道管理员上线清单.md`](./Cursor写码车道管理员上线清单.md) 由管理员配齐；`python3 scripts/check_cursor_dev_ready.py` 通过后再对同事开放（同事零 Cursor/Git 配置）

### 实施步骤

1. 仿 `smoke_api_contracts.py` / `smoke_ide_bridge_m1.py` 风格写契约。  
2. 试点清单：仓库、需求样例、是否满意 PR 质量、费用感受。  
3. 将遗留项记入方案「二期预留」（审核挂接等）。  
4. 全量：主 smoke + `smoke_cursor_dev`（非 live）+ 一次 live（人工）。  
5. 管理员跑 `check_cursor_dev_ready.py`，确认 Team Key + GitHub App + Cloud Agents + 非空白名单仓。  

### 当日验收（一期 Done）

对照方案 §11 六条全部勾选；本清单 D0–D8 完成项全部 `[x]`。

---

## 详细实施顺序（跨日依赖图）

```text
D0 环境
 └─► D1 config/allowlist/status/repos ──► D2 前端壳
                      │                      │
                      └─► D3 CLI SDK 冒烟 ◄───┘（可与 D2 并行）
                                │
                                ▼
                         D4 POST /jobs + 落盘
                                │
                                ▼
                         D5 service + SSE
                                │
                                ▼
                         D6 HITL + PR + 审计
                                │
                                ▼
                         D7 限流超时取消隔离
                                │
                                ▼
                         D8 smoke + 试点
```

可并行：

- D2 与 D3（前端壳不依赖 live SDK）  
- D7 部分限流可在 D5 后提前做并发计数  

不可并行：

- D5 依赖 D3（已知 SDK 调用面）+ D4（有 job）  
- D6 依赖 D5  
- D8 依赖 D6/D7  

---

## 文件级检查清单（实现时逐个打勾）

### 新建

- [x] `apps/cursor_dev/__init__.py`
- [x] `apps/cursor_dev/config.py`
- [x] `apps/cursor_dev/allowlist.py`
- [ ] `apps/cursor_dev/prompts.py`
- [ ] `apps/cursor_dev/jobs.py`
- [ ] `apps/cursor_dev/audit.py`
- [ ] `apps/cursor_dev/service.py`
- [x] `apps/api/routes/cursor_dev.py`
- [x] ~~独立写码页~~（已废弃，统一 ChatView）
- [x] `apps/web/src/api.js`（cursor-dev status/repos，供对话卡）
- [x] `scripts/smoke_cursor_sdk_cli.py`
- [x] `scripts/smoke_cursor_dev_d1.py`
- [ ] `scripts/smoke_cursor_dev.py`
- [x] `data/cursor_dev/`（`.gitkeep` + gitignore）

### 修改（最小化）

- [x] `apps/api/main.py`（router + 数据目录）
- [x] `apps/web/src/router.js`
- [x] `apps/web/src/App.vue`（已撤销独立入口）
- [x] `.env.example`
- [x] `requirements.txt`（含 cursor-sdk）
- [ ] `README.md`（一小节链到方案 + 本清单）
- [ ] （可选）[`功能清单与测试用例.md`](./功能清单与测试用例.md) 增补 F-CURSOR-*  

### 明确不改

- [x] 不改 `ChatView` 意图路由去调 Cursor  
- [x] 不改 `apps/agent/agents/agent.py` 注册 Cursor Tool  
- [x] 不改 IDE Bridge 协议  

---

## 附录：建议试点需求（测试仓）

1. README 增加「由 WorkBuddy 研发写码车道创建」说明段。  
2. 新增 `hello_workbuddy.py` 打印版本号。  
3. 给已有函数补一条单测（若仓内已有 pytest）。  

每条需求对应一次独立 job，便于对照 PR 与审计。

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-08-04 | 初版：D0–D8 每日完成项、步骤、验收与文件清单 |
| 2026-08-04 | D0 仓库侧落地：`.env.example`、本地 `.env` 占位、`data/cursor_dev` gitignore |
| 2026-08-04 | D1 落地：`apps/cursor_dev` + `/api/cursor-dev/status|repos`；allowlist 支持 URL |
| 2026-08-04 | D2 落地：`/dev-agent` + 侧栏入口；执行按钮暂禁用 |
| 2026-08-04 | D2 修正：写码页改为多轮对话 UI；方案 API 改为 jobs + messages + confirm-pr |
| 2026-08-04 | **产品纠正**：废弃独立写码 UI；统一主聊天；D2 清单改口径 |
| 2026-08-04 | D3：安装 cursor-sdk；CLI dry 通过；LIVE 需正确分支/仓权限 |
| 2026-08-04 | D4：jobs/audit/prompts + POST/GET jobs；对话确认建 job |
