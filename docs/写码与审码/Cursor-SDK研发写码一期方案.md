# Cursor SDK 研发写码一期方案

> 状态：**方案修订**（2026-08-04）— **统一主聊天界面**，不另开写码页  
> 范围：软件代码（非 PCB/EDA 设计文件）  
> 关系：与 MES / 审核等能力 **同一 ChatView**；后端执行引擎隔离，互不拖垮  
> 产品锚点：见 [`第二阶段产品方向.md`](../产品规划/第二阶段产品方向.md)  
> 执行拆解：[`Cursor-SDK研发写码每日实施清单.md`](Cursor-SDK研发写码每日实施清单.md)

---

## 1. 目标与边界

### 1.1 一期目标（可验收）

用户在 **现有主对话框** 里用自然语言提需求（写代码 / 改代码 / 开 PR / 聊天改方案同一会话）→ 后端按需调用 **Cursor SDK Cloud Agent** → 白名单仓库改代码 → 进度与回复流式出现在 **同一套气泡 + 过程面板** → 产出分支 / PR 链接 → **人工审核合入**。

体验对标主流助手（如 Cursor Chat）：**一个聊天框搞定**，不另做「研发写码」独立页。

### 1.1b 开箱原则（同事零配置）

| 角色 | 职责 |
|------|------|
| **管理员** | 上线前配齐：Cursor Team Key、GitHub App（org）、Cloud Agents、白名单仓、限流与配额 |
| **同事** | 只使用 WorkBuddy（ERP 登录 + 主对话）。**不需要**个人 Cursor 账号连 GitHub，不需要自备 API Key |

服务端仅一把 `CURSOR_API_KEY`（Team/Service Account）。详细步骤见 [`Cursor写码车道管理员上线清单.md`](Cursor写码车道管理员上线清单.md)；上线闸门：`python3 scripts/check_cursor_dev_ready.py`。

### 1.2 明确不做（一期）

- 自动 merge / 自动部署
- 自托管 Worker（Cloud 优先）
- PCB / EDA MCP
- 多智能体编排平台
- 独立写码站点 / 侧栏第二入口抢戏
- 私有 Git 全量放开（仅白名单仓）

### 1.3 与第二阶段关系

MES 实施运维仍是主锚点；写码能力在同一 UI 增强，后端旁路执行，不阻塞 M0–M4。

---

## 2. 隔离原则（引擎隔离，界面统一）

**隔离 = 后端执行与故障域分开；界面 = 跟主流一样只有一个对话。**

| 要 | 不要 |
|----|------|
| 写代码、查 MES、写方案、审核 **同一 ChatView** | 另开 `/dev-agent` 独立写码站 |
| Cursor 执行包 / 审计 / 限流与 Deep Agents **分开** | Cursor 挂了导致 MES 对话起不来 |
| 仓库选择用 **对话内卡片**（对标现有 IDE/Git 选仓卡） | 用户先学第二套导航 |

### 2.1 统一界面 + 双引擎

```text
ChatView（唯一对话 UI）
  → POST /api/chat/stream（现有 SSE：status / step / token / confirm / done）
      → 编排层（AgentRunner 或等价）
          ├─ 默认 / MES / 方案 / 贴码 / IDE·Git 审核
          │     → Deep Agents（现有 Skills/Tools）
          └─ 写码意图（白名单仓改代码 / 开 PR）
                → apps/cursor_dev（Cursor SDK Cloud）
                → 事件映射回同一 SSE，用户无感「换了个网站」
```

### 2.2 隔离检查清单

| 维度 | 做法 |
|------|------|
| UI | **仅** ChatView；无侧栏「研发写码」专页 |
| 选仓 | 对话内 `GitRepoPickCard` 同类卡片 / page_context 带 `git_repo` |
| API | Cursor 执行可仍用 `/api/cursor-dev/*` 供编排层调用，或 chat 内转发；**前端用户只打 chat** |
| 执行 | `apps/cursor_dev/` 不 import Deep Agents Tools |
| 状态 | Cursor `job_id` + `agent_id` 可挂在 thread 元数据；checkpoint 与 cursor job 分库存 |
| 失败域 | SDK/Key 失败 → 该轮助手回复报错；`/health` 与 MES 仍可用 |

---

## 3. 安全底线

1. **仓库白名单**：`CURSOR_DEV_REPO_ALLOWLIST`  
2. **分支前缀**：`dev/workbuddy-…`；禁止直推 main  
3. **HITL**：对话内确认卡（选仓 / 开 PR）；不合入  
4. **密钥**：仅服务端 `CURSOR_API_KEY`  
5. **限流 / 超时 / 审计**：同前  
6. **Prompt**：服务端系统前缀；续轮只追加用户话  

---

## 4. 架构与目录

```text
apps/cursor_dev/                 # 写码执行引擎（无独立前端页）
  config.py / allowlist.py / service.py / jobs.py / audit.py / prompts.py

apps/api/routes/cursor_dev.py    # 供编排/运维调用（status/repos/jobs/messages）
apps/api/agent_wrapper.py        # 扩展：写码轮次桥接 Cursor（保持 SSE 形态）
apps/web/src/views/ChatView.vue  # 唯一对话界面（不新增写码专页）
data/cursor_dev/                 # jobs / audit
scripts/smoke_cursor_dev*.py
```

已废弃：`CursorDevView.vue`、侧栏「研发写码」入口（`/dev-agent` 仅重定向到 `/`）。

---

## 5. API 草案

对用户前端：**继续只用** `/api/chat/stream`（及现有 history）。

编排层可调用：

| 方法 | 路径 | 作用 |
|------|------|------|
| GET | `/api/cursor-dev/status` | 可用性（过程区/卡片灰显用） |
| GET | `/api/cursor-dev/repos` | 白名单，供选仓卡 |
| POST | `/api/cursor-dev/jobs` | 首轮：create Agent + send |
| POST | `/api/cursor-dev/jobs/{id}/messages` | 同会话续聊：resume/send |
| POST | `/api/cursor-dev/jobs/{id}/confirm-pr` | 开 PR HITL |
| GET | `/api/cursor-dev/jobs/{id}/stream` | 单轮 SSE（可由 chat 代理转发） |

会话绑定：`thread_id` ↔ `cursor_job_id` / `agent_id`（存 `data/cursor_dev` 或 thread 元数据）。

---

## 6. 对话内状态机

```text
用户说话
  →（可选）弹出选仓确认卡
  → running：Cursor send + 流式 step/token 进同一过程面板/气泡
  → idle：可继续同一 thread 追问修改
  → 用户说「开 PR」或点确认卡 → creating_pr → 气泡出示 PR 链接
```

多轮 = 同一 Cursor `agent_id` 多次 `send`，体验与主聊天连续。

---

## 7. Cursor SDK 要点

- Cloud 显式配置；模型默认 `composer-2.5`（可配置）  
- 主路径：`create` + 多轮 `send` / `resume`；CLI 冒烟可用 `prompt`  
- 事件映射为现有 `status|step|token|done|error`  
- 失败域隔离；dispose/超时策略按会话  

### 系统前缀（首轮）

```text
你是代码实现 Agent，在用户的同一聊天会话中协作改仓库。
每一轮只做当前要求；用户未确认前不要创建 PR。
分支前缀：dev/workbuddy-
首轮需求：
{user_prompt}
```

---

## 8. 前端

- **只强化 ChatView**：选仓卡、开 PR 确认卡、PR 链接气泡（对标现有 HITL / Git 选仓）。  
- 过程面板继续展示「写码」步骤文案。  
- **禁止**再建独立写码页；**禁止**侧栏第二产品入口。  

---

## 9. 配置项

```bash
CURSOR_DEV_ENABLED=1
CURSOR_API_KEY=
CURSOR_DEV_REPO_ALLOWLIST=owner/repo
CURSOR_DEV_ALLOWED_USERS=
CURSOR_DEV_MAX_CONCURRENT=3
CURSOR_DEV_MAX_CONCURRENT_PER_USER=1
CURSOR_DEV_JOB_TIMEOUT_SEC=2700
CURSOR_DEV_MODEL=composer-2.5
CURSOR_DEV_AUTO_PR=1
CURSOR_DEV_SKIP_REVIEWER_REQUEST=1
CURSOR_DEV_BRANCH_PREFIX=dev/workbuddy-
```

---

## 10. 实施步骤摘要

详见每日清单。口径调整后：

| 日 | 要点 |
|----|------|
| D0–D1 | 配置 + cursor_dev status/repos（已有） |
| D2 | **撤销独立页**；清单改为「Chat 内选仓卡骨架」（本修订） |
| D3 | CLI Cloud 冒烟 |
| D4–D5 | jobs/messages + **桥进 chat/stream** |
| D6 | 对话内确认开 PR |
| D7–D8 | 限流隔离 + smoke + 试点 |

---

## 11. 验收标准

1. 用户只使用主对话即可完成：提需求 → 多轮改代码 → 拿到 PR 链接。  
2. 无独立写码页作为主路径；侧栏无「研发写码」专入口。  
3. MES 查询等原能力仍可用；Cursor 故障不拖垮主服务。  
4. 白名单 / HITL / 不合入 / 审计满足安全底线。  

---

## 12. 二期预留 / 已落地优化

**已在一期补齐（2026-08-05）：** 写码意图钉死、确认卡开 PR/失败重试、同 job 续聊、取消与超时、同仓冲突提示、审计 API、侧栏就绪、私有仓 Token 预检、完成后审核提示。

仍可扩展：

- 自动预审真正挂起 gate-90 任务（现为文案提示）  
- self-hosted runtime  
- 更细的意图分类（方案 / 写码 / 查询）  
- 管理台费用分摊与多仓编排  

---

## 13. 风险

| 风险 | 对策 |
|------|------|
| 同聊天误触发写码 | 选仓确认卡 + 白名单；模糊需求先澄清 |
| SDK beta / 费用 | 限流、熔断、usage 盯盘 |
| 与 Deep Agents 抢回复 | 写码轮明确走 Cursor 桥；避免双模型同轮抢答 |

---

## 14. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-08-04 | 初版：旁路独立页 |
| 2026-08-04 | 改为多轮对话独立页 |
| 2026-08-04 | **产品纠正**：取消独立写码 UI；统一主 ChatView；引擎仍隔离 |
| 2026-08-05 | **开箱原则**：管理员上线前配齐 Cursor↔GitHub；同事零配置；就绪检查脚本 |
