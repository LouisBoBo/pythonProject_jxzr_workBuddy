# PCB 每日早报 → 企业微信推送方案

> 日期：2026-08-27  
> 状态：**P0 已实现**（群机器人 Webhook + executor 旁路推送）  
> 关联任务：`每日PCB+AI新闻推送`（`automations.json`）

---

## 1. 目标

定时任务执行成功后，将 PCB+AI 早报**自动推送到企业微信群**，无需人工打开 ZR WorkBuddy 复制粘贴。

| 环节 | P0 状态 |
|------|---------|
| 定时生成早报 | ✅ 已有（Agent + `search_web`） |
| 运行记录落盘 | ✅ `data/automations/runs.json` |
| 企微群推送 | ✅ `apps/automations/delivery.py` |
| 推送状态展示 | ✅ 运行记录列表 + 详情抽屉 |

---

## 2. 推送通道选型

| 方式 | 复杂度 | P0 |
|------|--------|-----|
| **群机器人 Webhook** | 低 | ✅ 采用 |
| 应用消息 API | 中 | P2 |
| 自建应用 + SSO | 高 | 远期 |

Webhook 地址：

```text
POST https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={WECOM_WEBHOOK_KEY}
```

消息类型：`markdown`（单条上限约 4096 字节）。

---

## 3. 端到端流程

```text
Scheduler（30s tick）
  → executor.execute_automation
  → Deep Agents + search_web 生成 summary
  → store.update_run（status=succeeded）
  → delivery.deliver_automation_run（若 push_to_wecom=true）
      → run_summary_text.format_wecom_markdown
      → wecom_bot.send_markdown（失败同步重试 1 次）
  → store.update_run（delivery_status / delivered_at / delivery_error）
```

**原则**

- **先落盘、再推送**：Agent 成功 ≠ 推送成功；运行记录始终可查。
- **推送在 executor 旁路**：不走 Deep Agents 主环，模型不持有 webhook。
- **密钥不进任务 JSON**：`WECOM_WEBHOOK_KEY` 仅环境变量 / 系统配置。

---

## 4. 配置

### 4.1 系统配置（推荐）

路径：**设置 → 自动化推送**

| 配置项 | 说明 |
|--------|------|
| **群机器人 Webhook** | 可填完整地址或仅 `key=` 后的值（加密存于 `data/settings.json`） |
| **开启自动化结果推送** | 总开关；关闭后只生成运行记录、不调用企微 |
| **推送联调模式** | 开启后仅打日志、不真发（联调用） |

保存后立即热生效，无需重启 API。

### 4.2 环境变量（可选兜底）

`.env` 中同名变量可在未填系统配置时回落使用（不推荐作为主配置方式）：

```bash
# WECOM_WEBHOOK_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# WECOM_PUSH_ENABLED=1
# WECOM_PUSH_DRY_RUN=0
```

### 4.3 任务字段（`automations.json`）

```json
{
  "name": "每日PCB+AI新闻推送",
  "push_to_wecom": true
}
```

- `push_to_wecom: true` — 该任务成功后尝试推送
- 未配置 webhook 或总开关关闭 → `delivery_status=skipped`

### 4.4 运行记录扩展字段

| 字段 | 说明 |
|------|------|
| `delivery_status` | `sent` / `failed` / `skipped` |
| `delivered_at` | 推送成功 Unix 时间戳 |
| `delivery_error` | 失败原因（截断） |

---

## 5. 代码落点

| 模块 | 路径 |
|------|------|
| 摘要 → 企微 Markdown | `apps/automations/run_summary_text.py` |
| Webhook 发送 | `apps/automations/wecom_bot.py` |
| 推送编排 | `apps/automations/delivery.py` |
| 执行挂钩 | `apps/automations/executor.py` |
| 单测 | `apps/automations/test_wecom_delivery.py` |
| API 字段 | `apps/api/routes/automations.py` |
| 前端开关 | `AutomationEditDialog.vue` |
| 推送状态列 | `AutomationsView.vue` |

---

## 6. 企微侧准备

1. 企业微信 → 目标群 → **群设置 → 群机器人 → 添加**
2. 复制 Webhook 中 `key=` 后的值
3. 打开 ZR WorkBuddy **系统配置 → 自动化推送**，填写 Key 并开启「自动化结果推送」
4. 验证通道（可选 curl）：

```bash
curl 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的KEY' \
  -H 'Content-Type: application/json' \
  -d '{"msgtype":"markdown","markdown":{"content":"## 测试\nPCB早报推送通道 OK"}}'
```

返回 `{"errcode":0,"errmsg":"ok"}` 即成功。

4. 重启 API：`./scripts/stop.sh && ./scripts/dev.sh`
5. 自动化页 →「每日PCB+AI新闻推送」→ **立即测试**，检查群内消息与运行记录「推送」列。

---

## 7. P0 清单（已完成）

- [x] 企微 Webhook 发送模块（`safe_http` 白名单 `qyapi.weixin.qq.com`）
- [x] 摘要格式化（与前端 `formatRunSummaryForCopy` 对齐）
- [x] `executor` 成功后旁路推送 + 失败重试 1 次
- [x] 运行记录写入 `delivery_status`
- [x] 编辑弹窗「推送到企业微信」开关
- [x] 运行记录列表展示推送状态
- [x] `.env.example` 说明
- [x] 单测（格式化 + dry-run 推送）

---

## 8. P1 / P2 待办

| 阶段 | 内容 |
|------|------|
| P1 | `POST /runs/{id}/retry-delivery`；`delivery_outbox` 异步重试；设置页配置 webhook |
| P2 | 应用消息 API（按人推送）；多 webhook；与企微 SSO 打通 |

---

## 9. 风险与边界

| 项 | 说明 |
|----|------|
| 链接不稳定 | 无 URL 时只发文字来源 |
| 机器人限频 | 约 20 条/分钟；每日 1 条无压力 |
| API 需在线 | 09:00 触发前 API 进程须已启动 |
| 密钥泄露 | 企微后台可重置机器人 key |
