# WorkBuddy Agent 核心与 API 层可行性技术报告

> 范围：`apps/agent/`（Agent 运行时）与 `apps/api/`（FastAPI 层），附根目录依赖清单。
> 所有结论均引用具体文件与行号；未读取 `desktop/runtime/` 与 `node_modules`。

## ① Agent 运行时架构（循环 / 状态 / 工具 / 技能 / 中间件）

**框架定性：DeepAgents（LangGraph 之上），非自研循环、非 DeepSeek Harness。**
`apps/agent/agents/agent.py:1-11` 明确"架构锁定（选型落地 P0）：主 harness = Deep Agents；勿用 DeepSeek Harness 替换本模块"，并在 `:277-288` 直接调用 `create_deep_agent(model=…, tools=…, system_prompt=…, backend=FilesystemBackend, skills=["/skills/"], middleware=build_custom_middleware(), checkpointer=…)`。底层是 LangGraph 编译图：checkpointer 传入 `AsyncSqliteSaver`/`InMemorySaver`（`:226-234`），流式走 `agent.astream_events(…, version="v2")`（`apps/api/agent_wrapper.py:390-394`），状态含 `messages` 与多节点（`apps/agent/checkpoint_store.py:165-175`）。CLI 入口 `apps/agent/run.py:110-132`（`agent.invoke` + `thread_id="single-shot"`）；`config.py:143` 将 LangGraph 默认 recursion_limit 25 提到 500。

**模型：OpenAI 兼容协议。** `build_model()`（`agent.py:138-157`）用 `langchain_openai.ChatOpenAI`，base_url 可为 DeepSeek/SiliconFlow/任意 `LLM_BASE_URL`（`config.py:112-126`），默认模型 `deepseek-chat`，经 `llm_model_guard.assert_llm_model_allowed` 校验（`agent.py:147`）。

**工具：普通 Python 函数列表，无注册表。** `TOOLS` 清单（`agent.py:86-135`）约 50 个函数即工具（deepagents 签名接受 `Callable`），分群：平台查询（`list_platform_entities/query_platform_data/describe_entity`…）、分析与出图（`render_analysis_chart/render_analysis_dashboard`）、导入导出（`import_file_to_platform/export_platform_data/transform_file/preview_file`）、写入审计（`query_write_audit`）、表结构/能力地图（`schema_tool/*`）、API 健康（`api_log_tool/api_health.py` 十余个）、`search_web`。条件挂载：`IDE_REVIEW_ENABLED` 时加 `request_ide_*`（`:244-256`）；`READONLY_SQL_ENABLED` 时加 `readonly_sql`（`:259-262`）；`request_git_*` 始终挂载（`:265-273`）。

**实体目录（entity catalog）**：`tools/query_tool/entity_catalog.py` 从当前 MES 资料包 `entities.json` 加载（`:65-93`，按 path+mtime 缓存），`resolve_entity_id` 三段匹配：精确 id/label/别名 → 包含 → 中文分词打分（`:125-172`，词表 `_TOKEN_ZH:32-46`）；`build_system_prompt()` 由目录生成系统提示词（`:334+`），含 PCB 领域专家定位与多轮续写硬约束。

**技能（Skills）**：`apps/agent/skills/` 下 16 个目录（analyze-api-health、analyze-mes-data、analyze-mes-schema、analyze-pcb-mes、code-review、commit-batch-review、cursor-dev-chat、git-code-review、ide-code-review、import-export-data、ops-query-playbook、paste-code-analyze、pcb-domain-chat、query-mes-data、skill-template、ui-product-design），每个含 `SKILL.md`（YAML frontmatter：name/description + 正文操作剧本）。加载方式：`SKILL_SOURCES=["/skills/"]`（`agent.py:82`）+ `FilesystemBackend(root_dir=AGENT_ROOT, virtual_mode=True)`（`:160-165`）——虚拟根限制在 apps/agent 内，防止 Agent 读到仓库根 `.env`。已读示例：query-mes-data（先 `inspect_mes_profile` 再查数）、ops-query-playbook（场景→工具映射表）、analyze-api-health（文档探活默认沙箱、日志导入与沙箱结论分离）。

**中间件（Middleware）**：`apps/agent/middleware/__init__.py:21-50` 按环境变量组装：`AccessLogRouteMiddleware`（默认开）把对 `.jsonl/.log` 的误用工具调用（read_file/ls/transform_file…）自动改道 `import_external_api_logs`（`access_log_route.py:94-124`）；`HostPathGuardMiddleware`（默认开）拦截 `/Users/...` 本机绝对路径 read_file；`AuditToolMiddleware`（默认开）记录每次工具调用名/参数摘要/耗时（`audit_tools.py:23-66`）；`EntityGuardMiddleware`（默认关）拦截明显选错实体的查询（`entity_guard.py`）；`WriteConfirmMiddleware`（默认开，HITL）——对 `WRITE_TOOLS={import_file_to_platform}`（`write_tools.py:5-9`）不执行真实 handler，只生成只读预览并落盘 pending action，返回带 `__write_confirm__` 标记的 ToolMessage（`write_confirm.py:41-90`）。

**large_tool_results/**：是 DeepAgents 内置 OverflowClip 中间件的产物目录——超大工具结果按 `{tool_call_id}` 卸载到 `/large_tool_results/`（vendored deepagents `_overflow_clip.py`；目录内为 `call_00_*…` 的 JSON 转储，共 40 个），非本仓库业务代码。

## ② 会话与持久化

- **Checkpoint**：`checkpoint_store.py:34-58` 进程内单例 `AsyncSqliteSaver`（aiosqlite，WAL + busy_timeout=30000），库在 `DATA_DIR/agent_checkpoints.sqlite`（`:27-31`，可被 `AGENT_CHECKPOINT_PATH` 覆盖，`config.py:147`）。流式必须用异步 saver（同步会直接报错，`:3-5`）。
- **UI 历史为真相源**：`ensure_thread_messages`（`checkpoint_store.py:190-275`）每轮把前端 `conversations.db`（`DATA_DIR/history/`，`:85-86`）的 user/assistant 正文读回 checkpoint：去掉本轮即将写入的末尾 user（`:158-162`）、按 `CONTEXT_MAX_MESSAGES=40` 截窗（`config.py:149`）、单条 12000 字符截断（`:151`）、整表替换用 `RemoveMessage(REMOVE_ALL_MESSAGES)`（`:178-187`）——保证"停止生成后继续说"不丢上下文。
- **会话 JWT**：`session_jwt.py` HS256 自签（拒绝 alg=none，`:100-101`），payload 含 iss=zr-workbuddy/typ=wb_session/sub/username/exp，TTL 默认 28800s（`:15`），密钥持久于 `DATA_DIR/.session_jwt_secret`（0600，`:27-54`）。
- **站点配置**：`settings_store.py` 白名单 `ALLOWED_KEYS`（`:24-96`，覆盖 LLM/视觉/ERP/CURSOR/DEPLOY 等）、`SECRET_KEYS`（`:98-110`）用 XOR 流密钥 + HMAC 加密落 `settings.json`（`enc:v1:` 前缀，`:154-180`）；解析优先级 settings.json → 环境变量（`:4-5`）。
- **MES 资料包**：`mes_profile.py` 站点级 `DATA_DIR/mes_profiles/{id}/`，文件：schema.md、entities.json、capability_map.json、metrics.json、openapi.json、profile.json（`:26-31`）；未配置时**不回退仓库演示数据**（`:8-9`）。`mes_profile_daily_sync.py` 启动后按日自动同步 localhost MES OpenAPI（每日一次，失败 15 分钟冷却）。
- 用户偏好 `user_prefs.py` 按用户名落 `data/user_prefs/{user}.json`（仅 `last_local_workspace` 键，`:44`）。

## ③ API 面与流式协议

`apps/api/main.py`：FastAPI 应用 "MES Agent API"（`:66-70`），默认端口 8765（`routes_config.py:30`）。挂载路由（`:116-129`）：auth、chat、history、files、writes、ide_bridge、settings、mes_profile，及可选的 cursor_dev / local_dev / automations（导入失败降级不拖垮启动，`:28-44`）；`/exports` 静态挂载（`:131`）；`/health`（`:134-161`，含 instance_id/pid/版本）、`/health/ready`（`:164-199`，探 DATA_DIR 可写 + 跨进程锁）、`/api/debug/llm`（`:202-254`，DNS+`/models` 探测）；`WEB_DIST_DIR` 存在时挂 SPA 静态托管（`:257-352`，含路径穿越与敏感文件名守卫）；CORS 由 `cors_config.py` 解析（`*` 时强制关 credentials，生产环境禁止 `*`，`:48-54`）。startup 钩子：日同步资料包（`:73-87`）、自动化调度器（`:90-104`，30s tick，与用户流式互斥抢锁）。

**认证**：`routes/auth.py` 登录仅认环境变量 `PLATFORM_BASE_URL`（防改设置劫持，`:71-73`），依次试 `/api/v1/auth/login`、`/api/auth/login`（`:92-93`），连不上回落 `API_PROBE_SANDBOX_URL`（`:76-88`）；成功后签发 WorkBuddy 会话 JWT（`:251+`）；另有 `exchange` 用宿主平台 token 换会话（`:355+`）；`AUTH_REQUIRED` 默认 true（`:31`），`require_auth` 为各路由依赖（`:399+`）。

**流式协议（SSE）**：`routes/chat.py:85-202` `POST /api/chat/stream` 返回 `text/event-stream`（`Cache-Control: no-cache, no-transform`、`X-Accel-Buffering: no`），事件序列为 `data: {json}` 行；事件类型 status / step / token / confirm / done / error；首包注释填充 + 过程事件再冲一次（`sse_flush.py`：默认 512 字节 padding、默认不额外 sleep，`:14-36`）；断连经 `request.is_disconnected()` 置 cancel_event（`:119-121`）。同步接口 `POST /api/chat`（`:57-77`）。

**Agent 包装**：`agent_wrapper.py` `AgentRunner` 单例（`:109-124`），`_ensure_agent` 首次异步建 Agent（AsyncSqliteSaver，`:166-177`）；`_TOOLS_SIG` 版本号防热更新后复用旧 Agent（`:114`）；`_build_message`（`:204-324`）做入模前拼装：平台上下文前缀、车道强制路由、MES profile 上下文块、截图经视觉模型转文字注入（`tools/vision_describe.py`）、日志附件强制走 `import_external_api_logs`；`_stream_chat_locked`（`:341+`）消费 `astream_events`：`on_tool_start`→step 事件、`on_tool_end`→step 结束 + chart/dashboard + confirm 事件（`:444-681`）、`on_chat_model_stream`→token 事件（`:839-879`），含代码审核分批的"压制旁白/等报告标题/丢英文过渡句"逻辑（`:375-384, 850-869`），`on_chat_model_end` 兜底放整段（`:882-915`），recursion 超限给"继续审核"提示（`:923-934`），流末从 pending store 回补 confirm（`:989-1008`）。

**工具 UI 元数据**：`agent_tool_ui.py` 提供工具名→中文标题映射（`:16-75`）、入参摘要/结果预览解析（`:197+, 296+`）、写确认提取（`:623+`）、chunk 文本抽取（`:680+`），供过程区渲染，不 dump 原始大内容。

**路由一览**：auth=登录/换票/me；chat=同步+SSE 对话+上传；history=会话历史 SQLite 持久化（按用户隔离，`routes/history.py:38-57`）；files=文件管理器（上传/下载/预览/审计）；writes=写操作确认/取消/审计（确认经原子认领执行，`routes/writes.py:121-197`）；ide_bridge=IDE 扩展注册/心跳/长轮询取任务/配对；settings=系统配置热生效（保存后 `Config.reload_runtime()`）；mes_profile=资料包接入（上传表结构/OpenAPI/实体）；cursor_dev=Cursor 写码旁路（Cloud Agent）；local_dev=本机目录写码沙箱；automations=自动化任务 CRUD+立即运行。

## ④ 车道 / 并发机制

**车道（lanes）**：`workbuddy_lanes.py` 定义三条互斥车道 `code_dev / code_review / paste_code`（`:15-19`）；`resolve_workbuddy_lane`（`:165-171`）**优先显式 `page_context.workbuddy_lane`**（`:123-125`），缺失才回退消息内确认标记（`CODE_DEV_MARKERS:29-35`、`CODE_REVIEW_MARKERS:37-42`），并标注来源 explicit/marker/none（`:24-26, 115-162`）；`sanitize_page_context_lanes` 未知值清空（`:218-230`）。`agent_lane_message.py` 把车道与页面上下文（entity/plan_no/order_no/仓库/工程）拼成 `[平台上下文]` 前缀（`:15-58`）与强制路由追加（`:88-124`），自动化调度执行另加专用前缀（`:76-85`）。

**并发**：进程内**串行**流式——`AgentRunner._stream_lock` + `try_acquire_stream_lock`（0.15s 短等，超时快速失败返回 `stream_busy` 错误事件而非排队，`stream_concurrency.py:1-52`），原因是单条 aiosqlite 连接并发 astream 会空流（`:3-5`；真并发需换 Postgres checkpointer，`:5`）。跨进程：`ha/fs_lock.py` 基于 flock 的 `InterProcessLock`（可重入线程锁+文件锁，`:29-98`），保护共享 DATA_DIR 下的 writes/api_calls（HA 多实例场景，`docker-compose.ha.yml` 存在；`/health/ready` 探锁）。

## ⑤ 依赖清单与关键第三方库

`requirements.txt`（根）：`deepagents>=0.1.0`、`langchain-openai`、`openai`、`langgraph-checkpoint-sqlite`、`aiosqlite`、`pandas`、`openpyxl`、`fastapi`、`uvicorn[standard]`、`python-multipart`、`python-dotenv`、`cursor-sdk`。`requirements.lock.txt` 锁定：`deepagents==0.7.7`、`langchain==1.3.15`、`langchain-core==1.6.0`、`langgraph==1.2.11`、`langgraph-checkpoint==4.2.0`、`langgraph-checkpoint-sqlite==3.1.1`、`langgraph-prebuilt==1.1.0`、`langchain-openai==1.6.0`、`openai==3.3.1`、`anthropic==0.125.0`、`langchain-google-genai==4.3.4`、`tiktoken==0.14.0`、`sqlite-vec==0.1.9`、`pydantic==2.13.4`、`fastapi==0.141.1`、`cursor-sdk==1.0.28`。**结论：不存在 "deepagents 之外的 DeepSeek Harness" 依赖**；LLM 交互全部经 OpenAI 兼容协议（`ChatOpenAI`/`httpx`/urllib），供应商可换（DeepSeek、SiliconFlow、智谱 GLM-4V 视觉、智谱 Web Search）。

## ⑥ 与外部系统交互

- **MES 平台（ERP）查询/写入**：`tools/platform_api.py` 两层设计 MockClient/ERPClient（`:4-8`），urllib 直连，通用登录回落路径（`:36-41`），请求级用户 ERP token 经 contextvars 覆盖（`:63-78`）；每调用写 `api_calls` 日志（`:45-60`）；URL 全部过 `safe_http.assert_http_url_allowed`。查询工具链 `query_tool/platform_query.py`、`openapi_fetch.py` 目标为 `PLATFORM_BASE_URL`（`config.py:129`），可查对象由资料包 entities.json 决定。
- **WorkBuddy 平台登录（ERP 登录）**：`routes/auth.py`——只认 `PLATFORM_BASE_URL` 环境变量，回落 `API_PROBE_SANDBOX_URL`（`:76-88`）；MES 查数鉴权账号另配 `MES_API_USERNAME/PASSWORD/ENTERPRISE_CODE`（`config.py:132-136`，`settings_store.py:41-43`）。
- **探活沙箱**：`tools/api_log_tool/probe.py`——live 模式仅 GET/HEAD 打生产（`:5`），sandbox 模式可测全部方法：未配 `API_PROBE_SANDBOX_URL` 时进程内本地模拟、配了则过 host 白名单真实打沙箱（`:6-9, 33-35`）；`api_health.py` 提供 build/list/probe/render 报告工具，SKILL 约定"文档探活默认沙箱"。
- **可选只读 SQL**：`readonly_sql` 需 DSN + 表名白名单才启用（`config.py:164-172`）。
- **写码/审核/部署旁路**：cursor-sdk（Cloud Agent）经 `apps/cursor_dev`；本机沙箱写码经 `apps/local_dev` + `apps/sandbox`；VS Code 桥接经 `apps/ide-bridge`（长轮询任务）；自动化经 `apps/automations/scheduler.py`；这些与主 Agent 工具环解耦（`agent.py:4-5` "写码执行旁路 Cursor"）。

---

## 对你而言最重要的 10 个事实

1. 主 Agent 是 **DeepAgents 0.7.7 harness（LangGraph 图）**，不是自研循环、不是 DeepSeek Harness（`apps/agent/agents/agent.py:1-11, 277-288`）。
2. 模型层是 **OpenAI 兼容 ChatOpenAI**，默认 `deepseek-chat`，可换任意供应商；无硬编码 deepagents 之外的 SDK（`agent.py:138-157`、`config.py:112-126`）。
3. 工具是**普通 Python 函数列表**（约 50 个），无注册中心；条件挂载 ide/git/sql 工具（`agent.py:86-135, 244-273`）。
4. **写操作 HITL**：`import_file_to_platform` 默认被中间件挂起，人工在 SSE confirm 卡确认后由 API 直调执行（`middleware/write_confirm.py`、`routes/writes.py:121-197`）。
5. **流式进程内单路**：单条 AsyncSqliteSaver 连接导致并发 astream 会空流，故用 0.15s 短等 + 快速失败（`stream_concurrency.py`）；真并发需 Postgres checkpointer。
6. Checkpoint 与 UI 历史双向一致：每轮以 `conversations.db` 为准同步 LangGraph checkpoint（`checkpoint_store.py:190-275`），保证"停止后继续"不丢上下文。
7. SSE 事件协议为 **status/step/token/confirm/done/error**，带防代理攒包注释填充（`routes/chat.py:85-202`、`sse_flush.py`）。
8. **车道互斥**：code_dev / code_review / paste_code 三路，显式 `page_context.workbuddy_lane` 优先于消息标记（`workbuddy_lanes.py:115-171`）。
9. 实体目录/系统提示词全部**由 MES 资料包 entities.json 动态生成**，换平台不改代码（`entity_catalog.py:65-93, 334+`）。
10. 登录只认环境变量 `PLATFORM_BASE_URL`（回落探活沙箱），与"系统配置→MES 接入"上传的接口文档完全隔离，防劫持（`routes/auth.py:71-93`）。
