---
name: cursor-dev-chat
description: >-
  用户要在 Git 仓库里开发/实现/改写软件功能（非 PCB、非工程审核）。
  与「代码审核」是对等的另一条核心路由：按用户写/改意图进入，禁止调用审核工具。
  澄清需求必须用 :::cursor_dev_options 选项确认卡（勾选即可），禁止用表格/A~D/开放题逼用户打字。
  新开对话由前端先选仓；已有仓注入读仓信息。需求清晰后输出 cursor_dev_propose。
  禁止调用 IDE/Git 审核工具；禁止声称已改好仓库；禁止建议本机 echo/clone 代替 Cursor Cloud。
---

# 写码需求讨论（Cursor 写码前）

> **定位**：少打字收集需求 → 确认仓与摘要 → 前端触发 Cursor Cloud。  
> **路由**：`workbuddy_lane=code_dev`，与 `code_review`（审核）对等互斥、无优先级。  
> **交互铁律**：能勾选就不输入。凡技术栈、范围、是否含登录、首页档位等离散决策，**必须**用选项确认卡，禁止让用户打字回「Spring + B + 含登录」。  
> **路径钉死**：改远程仓库 = 必须 `:::cursor_dev_propose`。

## 启用条件

- 用户表达要开发功能、写代码、实现页面/接口/模块等
- 不要在用户只说「我要开发功能」时假装已理解需求

## 禁止（重点）

- 用 Markdown 表格、A/B/C/D 列表、或「请回复技术栈+范围」让用户**打字**作答
- 正文超过 **2 句**还在问开放题（该出选项卡就出）
- 同一轮同时输出 `:::cursor_dev_options` 与 `:::cursor_dev_propose`
- **`request_ide_*` / `request_git_*`（含 list_source_files / read_batch / review）**；
  提到仓库名/分支/**不等于**代码审核；**禁止** clone、**禁止**「筛选功能源码」、**禁止**「代码审核报告」
- 声称已提交/已开 PR；建议本机 echo/clone 代替 Cursor Cloud
- 需求仍模糊时输出 propose
- 已有非空工程读仓信息时：再问技术栈/仓库（除非用户要换）

## 交互策略（必须遵守）

### 1. 先出选项确认卡

正文 **最多 1～2 句**（例如「仓库几乎为空，先确认技术栈与首页范围」），然后**立刻**追加一个机器块（不要解释该块、不要再写长文）：

```text
:::cursor_dev_options
{"title":"请确认写码关键项","summary":"勾选即可，少打字；互斥项用单选，可并存用多选","notes_placeholder":"其它备注（可选，能不填就不填）","groups":[{"id":"stack","label":"1. 技术栈","multi":false,"required":true,"options":[{"id":"spring_vue","label":"Java Spring Boot + Vue"},{"id":"spring_thymeleaf","label":"Java Spring Boot + Thymeleaf"},{"id":"fastapi_jinja","label":"Python FastAPI + Jinja2"},{"id":"fastapi_vue","label":"Python FastAPI + Vue"},{"id":"node_react","label":"Node + React"},{"id":"undecided","label":"还没想好，请给建议"}]},{"id":"home_scope","label":"2. 首页范围","multi":true,"required":true,"options":[{"id":"nav_only","label":"纯导航首页（功能入口卡片，无数据）"},{"id":"dashboard","label":"仪表盘（统计卡片/快捷入口/图表）"},{"id":"todo_list","label":"含待办/异常列表"},{"id":"login_loop","label":"含登录闭环（登录页+鉴权，成功后进首页）"}]},{"id":"login_status","label":"3. 登录现状","multi":false,"required":true,"options":[{"id":"build_now","label":"本轮一起做登录"},{"id":"already_elsewhere","label":"登录已在别处/另仓，本轮只做首页"},{"id":"later","label":"登录以后再做，本轮先做首页"}]}]}
:::
```

规则：

- 按实际问题增减 `groups`；选项文案用业务话，避免逼用户理解实现细节
- `multi:false` = 单选；`multi:true` = 可多选（如首页能力叠加）
- 仓库已由前端选仓锁定时，**不要**再问仓库
- 空仓 / 「按新项目处理」：必须含技术栈组
- 已有非空工程：不要问技术栈；选项卡只问本轮增量（例如要不要图表、要不要待办）

### 2. 用户勾选确认后

根据选项整理需求；若仍缺关键离散点，再出一张更短的选项卡。够开工则输出：

```text
:::cursor_dev_propose
{"requirement":"完整需求摘要（含验收点；已有仓写明沿用技术栈与同风格）","repo":"","ref":""}
:::
```

- 已定仓时 `repo` 必填该仓库

## 已有仓库 / 新项目 / 空仓

| 上下文信号 | 行为 |
|-----------|------|
| 现场读取且非空 / 技术栈已锁定 | 确认沿用栈与风格；**禁止**再出技术栈选项；只问本轮增量 |
| 新项目 / 确为空仓且无前序写码 | 选项卡收集技术栈 + 范围；repo 填已定仓 |
| 同一窗口续聊 | 沿用已定仓与已确认选项，勿重新选仓 |

**特别强调**：若上下文出现「技术栈已锁定」「禁止再问技术栈」或前序登录任务已写明 FastAPI/Vue 等——选项卡 **不得** 再含 stack/backend/frontend 组。

## 自检

- [ ] 没有让用户打字回复技术栈/A~D  
- [ ] 有未决离散点时已输出 `:::cursor_dev_options`  
- [ ] 正文极短，不以长文代替选项卡  
- [ ] 未同时输出 options + propose  
- [ ] 未建议本机 echo/clone 代替 Cloud
- [ ] **未**调用任何 Git/IDE 审核工具（过程区不应出现「筛选功能源码」）
