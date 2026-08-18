# Deep Agents Middleware 使用指南

本文说明 Middleware 在本项目中的位置、**何时用**、**怎么加**，以及和 Tools / Skills 的分工。

---

## 1. Middleware 是什么

Middleware（中间件）挂在 Agent **执行环路**上，在「调模型 / 调工具」前后插入横切逻辑：

```text
用户消息
  → [before_agent / before_model]
  → LLM 决定下一步
  → [wrap_tool_call] → 真正执行 Tool → 返回
  → [after_model / after_agent]
  → 回复用户
```

它和 Skill、Tool 不同：

| | 做什么 | 典型例子 |
|--|--------|----------|
| **Tool** | 业务能力（查库、导入） | `query_platform_data` |
| **Skill** | 教 Agent「这类事怎么做」（软约束） | `query-mes-data/SKILL.md` |
| **Middleware** | 强制执行的横切策略（硬拦截/审计） | 审计日志、实体守卫、配额、HITL |

一句话：

- Skill = 说明书（可忽略）
- Middleware = 安检门（代码级强制）

---

## 2. 你项目里已经有的 Middleware

Deep Agents 作为 harness，**默认就带一堆中间件**，你传 `skills=` / `backend=` 时会自动挂上，例如：

| 内置（概念） | 作用 | 你怎么触发 |
|--------------|------|------------|
| SkillsMiddleware | 加载 Skill 摘要与正文 | `skills=["/skills/"]` |
| FilesystemMiddleware | ls/read/write 等 | `backend=FilesystemBackend(...)` |
| SummarizationMiddleware | 长对话摘要 | 默认开启 |
| SubAgentMiddleware | `task` 子 Agent | 默认开启 |

另外，本仓库自定义了：

| 自定义 | 文件 | 默认 | 作用 |
|--------|------|------|------|
| `MesAuditToolMiddleware` | `middleware/audit_tools.py` | **开** | 记录每次 Tool 调用 |
| `MesEntityGuardMiddleware` | `middleware/entity_guard.py` | **关** | 拦「问计划却查工单」 |

接入点：`apps/agent/agents/agent.py` → `middleware=build_custom_middleware()`。

---

## 3. 何时该用 Middleware（结合 MES）

### 适合用 Middleware

| 场景 | 为什么 | 建议钩子 |
|------|--------|----------|
| 审计 / 留痕 | 每次导入、导出必须记日志 | `wrap_tool_call` |
| 硬规则拦截 | 「问生产计划禁止打 work-orders」 | `wrap_tool_call` 返回错误 ToolMessage |
| 配额 / 限流 | 单会话最多导入 N 次 | `wrap_tool_call` + state |
| 脱敏 | 工具结果里去掉手机号再回给模型 | `wrap_tool_call` 改写返回值 |
| 危险操作确认 | 导入前人工点同意 | `interrupt_on={"import_file_to_platform": True}` |
| 请求级租户注入 | 多企业时自动带 enterprise_id | `before_agent` / `wrap_model_call` |

### 不适合用 Middleware（改用别处）

| 场景 | 更好放哪 |
|------|----------|
| 「查计划时先 list 再 query」这类流程说明 | **Skill** |
| 实体别名、REST path | **entities.json** |
| 真正调 ERP HTTP | **Tool / platform_api** |
| 前端展示、会话列表 | **apps/api / apps/web** |

经验：能写进 Skill 的软规范先写 Skill；只有「必须强制执行、不能靠模型自觉」时再上 Middleware。

---

## 4. 常用钩子（怎么写）

继承 `langchain.agents.middleware.types.AgentMiddleware`，实现需要的钩子即可（同步 + 异步成对更稳，流式 API 会走 async）。

| 钩子 | 时机 |
|------|------|
| `before_agent` / `after_agent` | 整轮对话开始/结束 |
| `before_model` / `after_model` | 每次调 LLM 前后 |
| `wrap_model_call` | 包住 LLM 调用（可改请求/响应） |
| `wrap_tool_call` / `awrap_tool_call` | **包住 Tool**（审计、拦截最常用） |

最小骨架：

```python
from langchain.agents.middleware.types import AgentMiddleware

class MyMiddleware(AgentMiddleware):
    name = "MesMyMiddleware"  # 勿与内置重名

    def wrap_tool_call(self, request, handler):
        # 前置：检查 / 改参数
        result = handler(request)   # 调用真正的 Tool
        # 后置：改结果 / 记日志
        return result

    async def awrap_tool_call(self, request, handler):
        return await handler(request)
```

然后在 `middleware/__init__.py` 的 `build_custom_middleware()` 里 `append(MyMiddleware())`。

---

## 5. 在本项目中怎么挂上

`create_deep_agent(..., middleware=[...])`：

- 你的自定义中间件会**追加**进 Deep Agents 默认栈（一般插在核心中间件之后）
- `name` 若与某个默认中间件同名，在新版本可能**替换**该默认实例；自定义请用 `MesXxx` 前缀避免误伤

环境变量（仓库根 `.env`）：

```bash
# 工具审计（默认 true）
ENABLE_AUDIT_MIDDLEWARE=true

# 实体硬守卫（默认 false，确认策略后再开）
ENABLE_ENTITY_GUARD=false

# 写操作人工确认（默认 true；紧急回滚可 false）
REQUIRE_WRITE_CONFIRM=true
```

改 middleware 代码后重启 API：

```bash
./scripts/stop.sh && ./scripts/dev.sh
```

写确认详细说明见 [`M2写操作确认交付说明.md`](../产品规划/M2写操作确认交付说明.md)。

看审计日志（logger 名 `mes.agent.audit`）：

```bash
# 开发时可在启动前
export PYTHONLOGGING=INFO
# 或在 apps/api 里配置 logging.basicConfig(level=logging.INFO)
```

---

## 6. 和 Skills 的配合示例

「查生产计划却打成工单」可以两层防护：

1. **Skill `query-mes-data`**：教模型选 `production-plans`（软）
2. **Middleware `EntityGuard`**：若仍传 `work-orders` 且用户话含「排程/排产」，直接返回错误逼重试（硬）

推荐顺序：先 Skill → 仍不稳再开 Guard。

---

## 7. 自己新增 Middleware 步骤

1. 在 `apps/agent/middleware/` 新建 `xxx.py`，实现 `AgentMiddleware` 子类，设好唯一 `name`
2. 在 `middleware/__init__.py` 的 `build_custom_middleware()` 里按开关 append
3. （可选）在 `.env.example` 增加开关说明
4. 重启 API，用一次会调 Tool 的对话验证（审计应打日志 / 守卫应拦截）

---

## 8. 进阶：人工确认（HITL）

对写操作可在 `create_agent` 里：

```python
interrupt_on={
    "import_file_to_platform": True,
}
```

调用该工具时图会暂停，需在带 checkpointer 的运行时做 resume（CLI/API 要额外接审批 UI）。适合上线前的「导入必须人审」。

---

## 9. 分层总览（扩展时对照）

```text
apps/agent/
  tools/              # 能干什么（必须）
  tools/query_tool/entities.json
  skills/             # 怎么干（辅助剧本）
  middleware/         # 强制策略（横切，按需）
  agents/agent.py     # create_deep_agent 组装处
```

| 你想… | 改 |
|-------|-----|
| 多一个可查询实体 | `entities.json` |
| 多一段业务操作说明 | `skills/.../SKILL.md` |
| 强制审计 / 拦截 / 限流 | `middleware/...` |
| 多一个可调用函数 | `tools/` + 注册进 `TOOLS` |

---

## 10. 相关文件

```text
apps/agent/middleware/__init__.py      # 组装开关
apps/agent/middleware/audit_tools.py   # 审计示例（默认开）
apps/agent/middleware/entity_guard.py  # 守卫示例（默认关）
apps/agent/agents/agent.py             # middleware=...
docs/Agent开发/DeepAgents-Skills使用指南.md
docs/Agent开发/DeepAgents-Middleware使用指南.md  # 本文
docs/MES业务/平台查询工具维护笔记.md
```
