# 01 · PCB 专业对话

> 用户问工艺、材料、阻抗、AOI、IPC 术语等 → **直接用中文讲明白**，一般不查本公司 MES 实时数据。

---

## 1. 实现原理

### 1.1 这个功能解决什么问题？

工程师问「阻焊和丝印谁先谁后」「飞针和电测怎么选」，需要的是**行业知识解释**，不是去 MES 里查今天有多少板子。  
PCB 专业对话就是：**只靠大模型 + 项目里写好的规矩来答**，默认**不调用**查数、摸底那些会连 MES 的工具。

### 1.2 和「查 MES 数据」怎么区分？

系统里有两套能力，提示词里写死了边界：

| 用户问法 | 走哪条路 | 依据什么 |
|----------|----------|----------|
| 「IPC-6012 对阻焊有什么要求？」 | PCB 闲聊 | 模型通用知识 + `pcb-domain-chat` Skill |
| 「今天咱们厂有多少急单？」 | MES 查数（功能 02） | 打 MES HTTP 接口拿真数据 |

如果 PCB 闲聊里瞎编「今天查到 32 单」，用户会以为系统连了库——所以 Skill 和系统提示都强调：**没调查数工具，就不要报具体条数**。

### 1.3 技术上有哪些「刹车」？

1. **Skill 剧本**（`apps/agent/skills/pcb-domain-chat/SKILL.md`）  
   告诉模型：这是知识问答，不要为了闲聊去调 `query_platform_data`、`list_platform_capabilities` 等。

2. **系统提示**（`entity_catalog.py` 里「PCB 行业闲聊与专业答疑」一节）  
   规定回答结构：结论 → 要点 → 注意点；涉及**本公司实时数据**时再引导去查数。

3. **不挂写码 / 审码车道**  
   普通对话 `workbuddy_lane` 为空或默认，不会弹出选仓卡、审核报告壳。

### 1.4 依赖什么配置？

- 需要配好 **LLM**（设置页 API Key、模型名），否则对话起不来。  
- **不需要** MES 资料包、不需要 MES 接口账号——纯聊天也能用。

---

## 2. 实现流程（技术点怎么落地）

> 下面按真实代码路径写。PCB 对话**只走 SSE 主环**，不创建 Job、不调 MES HTTP。

### 2.1 意图：为什么走「默认对话」？

```text
ChatView 发送前 → chatIntent.js 依次判断：
  looksLikeDeploy / looksLikeLocalCommitBatch / looksLikePasteCodeAnalyze
  / looksLikeCodeReview / looksLikeCodeDevIntent
  → 都不命中 → 普通 MES/PCB 对话
```

| 技术点 | 实现 |
|--------|------|
| 无专用 lane | `page_context.workbuddy_lane` 为空或默认；`workbuddy_lanes.sanitize_page_context_lanes()` 清非法值 |
| 建议话术 | `ChatView.vue` 快捷问题含「PCB电路板有哪些工序？」，仍走同一条 SSE |
| 附件 | 若有上传图，走 `sanitize_client_file_paths()`；PCB 纯文字问答通常无附件 |

### 2.2 SSE 请求与鉴权

```text
POST /api/chat/stream（routes/chat.py::chat_stream）
  Header: Authorization Bearer {JWT}
  Body: { messages, session_id, page_context?, attachments? }
       ↓
require_auth → AgentRunner.stream_chat（agent_wrapper.py）
```

| 技术点 | 实现 |
|--------|------|
| 并发 | `try_acquire_stream_lock()`：同一会话同时只跑一条流，防 LangGraph checkpoint 掐断 |
| 历史 | LangGraph `AsyncSqliteSaver` 读 `data/agent_checkpoints.sqlite` |
| SSE 首包 | `sse_comment_pad()`：可选填充 `WORKBUDDY_SSE_PAD_BYTES`，减轻代理缓冲导致「长时间无字」 |

### 2.3 系统提示 + Skill 加载

```text
build_system_prompt()（entity_catalog.py）
  ├─ 「PCB 行业闲聊与专业答疑（无需工具）」整节
  ├─ 可查对象目录（给模型看边界，本功能不应去调）
  └─ 车道互斥说明

create_agent()（agent.py）
  ├─ create_deep_agent + FilesystemBackend(skills/)
  └─ 匹配加载 pcb-domain-chat/SKILL.md
```

**Skill 硬约束（`pcb-domain-chat/SKILL.md`）：**

- 用户问工艺/材料/IPC → **直接中文回答**  
- **禁止**为闲聊调用 `query_platform_data`、`list_platform_capabilities` 等  
- 结构：结论 → 要点 → 注意点；涉及厂内实时数据再引导查数（功能 02）

### 2.4 推理与返回（通常无 tool call）

```text
Deep Agents 一轮：
  输入 = system + checkpoint 历史 + 用户本轮
  输出 = 流式 token（正常无 tool_calls）

agent_wrapper 把 chunk 转成 SSE：
  { type: "token", content: "..." }
  { type: "done" }

ChatView 逐字渲染；刷新后历史从 SQLite 恢复
```

| 边界情况 | 应有行为 |
|----------|----------|
| 用户改问「今天急单」 | 下一轮 Skill 切到 `query-mes-data`，调 `query_platform_data` |
| 用户短确认「来吧」且上轮答应给代码 | 走贴码/写码车道，**不要**插入 PCB 科普开场 |
| 用户问「平台能干什么」 | 走 `entity_catalog` 里「核心能力」介绍，不是 MES 模块清单 |

### 2.5 和写码 / 审码 / 贴码分流（技术对照）

| lane / 意图 | 典型 API | 会不会改盘 |
|-------------|----------|------------|
| 默认（本篇） | `/api/chat/stream` | 否 |
| `paste_code` | `/api/chat/stream` + 贴码提示块 | 否 |
| `code_review` | `/api/chat/stream` + Git/IDE 工具 | 否 |
| `code_dev` | SSE 讨论 + `/api/local-dev/jobs` | 是（Job 后） |

### 2.6 常见排查

| 现象 | 查什么 |
|------|--------|
| 一直转圈无字 | LLM Key、网络、`stream_lock` 是否被占 |
| 闲聊却去查数 | Skill 未加载；看模型 tool_calls 日志 |
| 闲聊编造工单条数 | 违反 Skill；应只科普不报 KPI |

---

## 3. 技术及用法

| 技术 / 模块 | 怎么用 |
|-------------|--------|
| Deep Agents | 主对话环推理与生成 |
| Skill `apps/agent/skills/pcb-domain-chat/SKILL.md` | 规定：PCB 知识答疑；禁止为闲聊去调 MES 工具 |
| `entity_catalog.build_system_prompt()` | 拼进「PCB 行业闲聊」与「平台能干什么」介绍文案 |
| SSE | `apps/api/routes/chat.py` + `agent_wrapper.py` 流式回前端 |
| LLM | `LLM_*` / DeepSeek 等，经设置页配置 |

**关键路径**：`apps/agent/skills/pcb-domain-chat/`、`apps/agent/tools/query_tool/entity_catalog.py`（系统提示）、`apps/api/routes/chat.py`。

---

## 4. 后续扩展与优化建议

1. **可做**：按厂内 WI/工艺卡做「受控知识包」（仍走 Skill，不冒充实时 WIP）。  
2. **可做**：常见缺陷树（开路/短路/蚀刻不足）做成可点选的引导问答。  
3. **慎做**：把未经验证的厂内规范硬写进系统提示当真理。  
4. **不要做**：用 PCB 闲聊答案冒充「已查 MES」条数或良率。

---

## 自测话术

- 「阻焊和丝印一般顺序是什么？」  
- 「IPC 里常见的缺陷分类有哪些？（科普即可）」  
- 对比：「今天紧急未完工有哪些？」——应走查数，不应只科普。  
