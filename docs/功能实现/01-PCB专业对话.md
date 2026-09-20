# 01 · PCB 专业对话

> **一句话**：工程师问工艺、材料、阻抗、AOI、IPC 术语等，ZR WorkBuddy 用中文把行业知识讲明白（Skill `pcb-domain-chat` + 系统提示）。  
> **不是**：去查本公司 MES 实时 KPI / 工单条数；也不是写码、审码、贴码车道。

---

## 1. 实现原理

### 1.1 我们到底实现了什么？

「阻焊和丝印谁先谁后」「飞针和电测怎么选」要的是**行业知识解释**，不是今天厂里有多少急单。  
PCB 专业对话：**只靠大模型 + 写好的规矩来答**，默认**不调用**会连 MES 的查数工具。

| 人配的 / 人问的 | 系统干的 | 达到的效果 |
|----------------|----------|------------|
| 工艺 / 材料 / IPC 术语问题 | Deep Agents + `pcb-domain-chat` Skill 直接中文答 | 科普到位，不假装连了库 |
| （无）MES 账号 / 资料包 | 本能力不依赖 | 没配 MES 也能聊 PCB |
| 改口问「今天急单」 | 下一轮切到查数 Skill / 工具 | 实时数走功能 02，不编造 |

**技术落点（整包）：**

| 层次 | 路径 |
|------|------|
| 前端 | `ChatView.vue` 默认 SSE（无 `workbuddy_lane`） |
| HTTP | `POST /api/chat/stream`（`apps/api/routes/chat.py`） |
| 编排 | `AgentRunner.stream_chat` → `create_deep_agent` |
| 系统提示 | `entity_catalog.build_system_prompt` 中「PCB 行业闲聊与专业答疑」节 |
| Skill | `apps/agent/skills/pcb-domain-chat/SKILL.md` |
| Checkpoint | `data/agent_checkpoints.sqlite`（按 **thread_id**） |

### 1.2 和「查 MES 数据」差在哪？

| | **PCB 专业对话（本篇）** | **MES 查数（功能 02）** |
|--|--------------------------|-------------------------|
| 典型问法 | 「IPC-6012 对阻焊有什么要求？」 | 「今天咱们厂有多少急单？」 |
| 依据 | 模型知识 + Skill 规矩 | MES HTTP 真数据 |
| 会否调 `query_platform_data` | **不应**为闲聊调用 | 会 |
| 报具体条数 / 良率 | 禁止没调查数就报 | 以工具返回为准 |

若闲聊里瞎编「今天查到 32 单」，用户会以为系统连了库——Skill 与系统提示都强调：**没调查数工具，就不要报具体 KPI。**

**技术上怎么隔开：**

| 点 | 实现 |
|----|------|
| 无专用 lane | `page_context.workbuddy_lane` 为空；不进贴码/审码/写码 |
| Skill 禁令 | `pcb-domain-chat/SKILL.md`：禁止为闲聊调 `query_platform_data` 等 |
| 系统提示边界 | `entity_catalog` PCB 节：结论 → 要点 → 注意点；实时数据再引导查数 |
| 会话键 | API / checkpoint 用 **`thread_id`**，不要和 UI 的 session 展示名混为一谈 |

### 1.3 为什么通常没有 tool call？

**人话：**  
知识问答不需要打 MES。多调一次查数工具，既慢又容易在接口空结果时「凑数」编造。规矩写清楚：闲聊直接答；要厂内实时数再走查数。

**技术点：**

| 点 | 函数 / 模块 | 怎么做的 |
|----|-------------|----------|
| 剧本 | `pcb-domain-chat/SKILL.md` | 何时用、禁止事项、回答结构 |
| 提示拼装 | `build_system_prompt` | 写入「无需工具」的 PCB 节 + 能力边界 |
| 本能力不挂 | `query_platform_data` | 此能力路径上**不应**为闲聊调用该工具 |

### 1.4 安全与依赖钉死了什么？

| 约束 | 技术实现 |
|------|----------|
| 不冒充 MES KPI | Skill + 系统提示；无 tool 结果不报条数 |
| 不抢写码/审码 | 默认无 `workbuddy_lane` |
| 仅需 LLM | `LLM_*`；**不需要** `MES_API_*` / 资料包 |
| SSE 首包缓冲 | 可选 `WORKBUDDY_SSE_PAD_BYTES`（`sse_flush.sse_comment_pad`） |

---

## 2. 实现流程（人话 + 技术点怎么落地）

> 每节先讲「人看到什么 / 为什么这样」，再给 **技术点表** 和调用链。PCB 对话**只走 SSE 主环**，不创建 Job、不调 MES HTTP。

### 2.1 人怎么走进这条路？

**人话：** 在对话里问 PCB 工艺/术语即可。发送前若没命中部署、提交、贴码、审码、写码，就走默认 SSE——没有单独的「PCB 按钮」或专用 lane。

```text
ChatView 发送前 → chatIntent.js 依次判断：
  looksLikeDeploy / looksLikeLocalCommitBatch / looksLikePasteCodeAnalyze
  / 审码 / 写码讨论
  → 都不命中 → 普通对话（含 PCB）
       ↓
POST /api/chat/stream（无 workbuddy_lane 或默认）
```

**技术点：**

| 点 | 怎么做的 |
|----|----------|
| 无专用 lane | `sanitize_page_context_lanes` 清非法值；本能力不设 `paste_code` 等 |
| 建议话术 | 快捷问题如「PCB电路板有哪些工序？」仍走同一条 SSE |
| 附件 | 纯文字问答通常无附件；有图则走统一上传路径校验 |

---

### 2.2 SSE 与鉴权、会话怎么接？

**人话：** 登录后流式出字；同一会话同时只跑一条流，避免历史被掐断。刷新后还能接着聊，靠的是 checkpoint 里的 **thread_id**。

```text
POST /api/chat/stream（routes/chat.py::chat_stream）
  Header: Authorization Bearer {JWT}
  Body: { messages, thread_id, page_context?, attachments? }
       ↓
require_auth → AgentRunner.stream_chat
  → try_acquire_stream_lock(...)
  → LangGraph AsyncSqliteSaver（data/agent_checkpoints.sqlite）
  → 可选 sse_comment_pad()（WORKBUDDY_SSE_PAD_BYTES）
```

**技术点：**

| 点 | 函数 / 模块 | 怎么做的 |
|----|-------------|----------|
| 会话键 | 请求 `thread_id` | `default` 会按用户改写；**不是**另套 `session_id` 当 checkpoint 主键 |
| 并发 | `try_acquire_stream_lock` | 同会话单流；忙则 `stream_busy` |
| 首包填充 | `sse_comment_pad` | 减轻代理缓冲导致「长时间无字」 |

---

### 2.3 系统提示 + Skill 怎么加载？

**人话：** 模型先看到「这是 PCB 闲聊、通常不用工具」的说明书，再按 Skill 用结论→要点→注意点作答；涉及本公司实时数据时，引导去查数（功能 02）。

```text
build_system_prompt()（entity_catalog.py）
  ├─ 「PCB 行业闲聊与专业答疑（无需工具）」整节
  ├─ 可查对象目录（边界说明；本能力不应去调）
  └─ 车道互斥说明

create_agent()（agent.py）
  ├─ create_deep_agent + FilesystemBackend(skills/)
  └─ 匹配加载 pcb-domain-chat/SKILL.md
```

**技术点：**

| 点 | 怎么做的 |
|----|----------|
| Skill 硬约束 | 用户问工艺/材料/IPC → **直接中文回答**；禁止为闲聊调 `query_platform_data`、`list_platform_capabilities` 等 |
| 结构 | 结论 → 要点 → 注意点 |
| 短确认 | 上轮若是写码/读码，「来吧」等**禁止**插入 PCB 科普开场 |

---

### 2.4 推理与返回（通常无 tool call）

**人话：** 正常情况是逐字出中文解释，没有「正在查询平台」的过程条。你改口问厂内数据时，下一轮才应出现查数工具。

```text
Deep Agents 一轮：
  输入 = system + checkpoint 历史 + 用户本轮
  输出 = 流式 token（正常无 tool_calls）

agent_wrapper → SSE：
  { type: "token", content: "..." }
  { type: "done", thread_id: "..." }

ChatView 逐字渲染；历史按 thread_id 从 SQLite 恢复
```

**技术点：**

| 边界情况 | 应有行为 |
|----------|----------|
| 用户改问「今天急单」 | 切到 `query-mes-data` 等，调查数工具（功能 02） |
| 用户短确认且上轮写码 | 走贴码/写码车道，不插 PCB 开场 |
| 用户问「平台能干什么」 | 走 `entity_catalog`「核心能力」介绍，不是 MES 模块清单 |

---

### 2.5 和写码 / 审码 / 贴码对照

| lane / 意图 | 典型路径 | 会不会改盘 |
|-------------|----------|------------|
| 默认（本篇） | `/api/chat/stream` | 否 |
| `paste_code` | SSE + 贴码提示 | 否 |
| `code_review` | SSE + Git/IDE 工具 | 否 |
| `code_dev` | SSE 讨论 + Job | 是（Job 后） |

---

### 2.6 出问题时先查哪？

| 现象 | 人话原因 | 技术上先看 |
|------|----------|------------|
| 一直转圈无字 | Key/网络/锁被占 | `LLM_*`；`stream_busy`；`WORKBUDDY_SSE_PAD_BYTES` |
| 闲聊却去查数 | Skill 未匹配或模型乱调工具 | tool_calls 日志；Skill 是否加载 |
| 闲聊编造工单条数 | 违反 Skill | 应只科普不报 KPI |
| 历史对不上 | 混用了 session 展示名 | 核对请求里的 **thread_id** |

---

## 3. 技术及用法（速查）

| 模块 | 关键函数 | 干什么 |
|------|----------|--------|
| `pcb-domain-chat/SKILL.md` | （Skill 剧本） | PCB 知识答疑；禁闲聊调 MES 工具 |
| `entity_catalog.py` | `build_system_prompt` | 拼入 PCB「无需工具」节 |
| `agent.py` | `create_agent` → `create_deep_agent` | 加载 Skills / 推理 |
| `routes/chat.py` + `agent_wrapper.py` | `chat_stream` / `stream_chat` | SSE |
| `sse_flush.py` | `sse_comment_pad` | 首包填充 |

**配置：**

| 变量 | 含义 |
|------|------|
| `LLM_*`（及兼容的 DeepSeek 相关） | 对话必需 |
| `WORKBUDDY_SSE_PAD_BYTES` | SSE 首包注释填充字节（减轻代理缓冲） |

本能力**不依赖** `MES_PROFILE_ID` / `MES_API_*`。

---

## 4. 后续可以怎么做、不要做什么

**可以做：**

1. 按厂内 WI/工艺卡做「受控知识包」（仍走 Skill，不冒充实时 WIP）  
2. 常见缺陷树（开路/短路/蚀刻不足）做成可点选引导问答  

**不要做：**

1. 用 PCB 闲聊答案冒充「已查 MES」的条数或良率  
2. 把未经验证的厂内规范硬写进系统提示当真理  
3. 为闲聊默认挂上 `query_platform_data`「顺便查一下」  

---

## 自测路径（验收）

1. 「阻焊和丝印一般顺序是什么？」→ 中文科普，无查数 tool。  
2. 「IPC 里常见的缺陷分类有哪些？（科普即可）」→ 结构清晰，不报厂内 KPI。  
3. 对比：「今天紧急未完工有哪些？」→ 应走查数（功能 02），不应只科普或瞎编条数。  
4. 确认请求体使用 **thread_id**，刷新后同线程历史可续。  
