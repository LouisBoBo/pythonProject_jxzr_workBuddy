# 自动化任务（Automations）

> 日期：2026-08-27  
> 目的：记录 **完整版 WorkBuddy** 自动化任务（定时调度）的机制与学习结论，作为 **ZR WorkBuddy** 后续落地的参考。

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [WorkBuddy自动化任务学习笔记.md](./WorkBuddy自动化任务学习笔记.md) | 完整版机制、数据模型、调度执行链路、ZR 落地建议 |
| [PCB早报企微推送方案.md](./PCB早报企微推送方案.md) | PCB 每日早报 → 企业微信群机器人（P0 已实现） |

界面与 API 落点：

| 层次 | 路径 |
|------|------|
| 前端页面 | `apps/web/src/views/AutomationsView.vue` |
| 编辑弹窗 | `apps/web/src/components/AutomationEditDialog.vue` |
| 任务模板 | `apps/web/src/automationTemplates.js` |
| API | `apps/api/routes/automations.py` |
| 企微推送 | `apps/automations/delivery.py`、`wecom_bot.py` |
| 推送配置 | **系统配置 → 自动化推送**（`apps/api/routes/settings.py`） |
| 落盘 | `data/automations/automations.json` |

---

## 读法建议

1. **要先懂完整版怎么做的** → 打开学习笔记全文（原理 + 流程 + 表结构）。
2. **要在 ZR 里开做** → 重点看笔记第四节「ZR WorkBuddy 现状」与第五节「落地建议」。
3. **别和下面两项混淆**：
   - **自动化部署**（功能 10）：人确认后触发 GitHub Actions / SSH，不是定时任务 → [`../功能实现/10-人触发预发部署.md`](../功能实现/10-人触发预发部署.md)
   - **资料包日同步**：API 启动时按日拉 OpenAPI，不可用户配置 → [`../MES业务/每日打开自动同步资料包.md`](../MES业务/每日打开自动同步资料包.md)

---

## 状态

| 项目 | 状态 |
|------|------|
| 完整版 WorkBuddy（客户端） | 已实现（`~/.workbuddy/workbuddy.db` + Electron 调度） |
| ZR WorkBuddy 自动化界面 | **已实现**（`/automations` 页 + 任务 CRUD API） |
| ZR WorkBuddy 定时调度执行 | **已实现**（API 内 scheduler + Deep Agents；与用户流式对话互斥） |
| 企微群推送（P0） | **已实现**（群机器人 Webhook；见 [PCB早报企微推送方案.md](./PCB早报企微推送方案.md)） |
