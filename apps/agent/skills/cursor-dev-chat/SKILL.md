---
name: cursor-dev-chat
description: >-
  用户要开发/实现/改写软件功能（非 PCB、非工程审核）。
  与「代码审核」是对等的另一条核心路由：按用户写/改意图进入，禁止调用审核工具。
  澄清需求必须用 :::cursor_dev_options 选项确认卡（勾选即可），禁止用表格/A~D/开放题逼用户打字。
  默认写码目标为本机目录（沙箱隔离后由 Cursor SDK Local Agent 改码再同步）；
  GitHub + Cursor Cloud 为第二入口（target=github）。
  截图 1:1/复刻：以【截图理解】视觉规格为准，禁止臆造模块、禁止 Element 白卡片模板交差。
  重做/重新设计/要有设计感：优先 Skill「ui-product-design」；旧「按截图位置」只作字段参考，禁止再锁五卡骨架。
  做/改/重写界面时必须同时遵循 Skill「ui-product-design」：有产品设计感，禁止照抄已有页布局。
  需求清晰后输出 cursor_dev_propose（默认 target=local）。
  禁止调用 IDE/Git 审核工具；禁止声称已改好仓库；禁止建议本机 echo/clone 代替确认卡落盘。
---

# 写码需求讨论（确认卡前）

> **定位**：少打字收集需求 → 确认目标与摘要 → 前端触发写码。  
> **默认目标**：本机目录（沙箱内由 **Cursor SDK Local Agent** 改码 → 成功后同步）；GitHub Cloud 为可选项。  
> **计费**：本机 Tab = Cursor 用量（非 DeepSeek 工具环）；GitHub Tab = Cursor Cloud。  
> **应急**：环境变量 `LOCAL_DEV_AGENT=llm` 可回退旧 DeepSeek/对话模型工具环。  
> **路由**：`workbuddy_lane=code_dev`，与 `code_review`（审核）对等互斥、无优先级。  
> **交互铁律**：能勾选就不输入。凡技术栈、范围、是否含登录、首页档位等离散决策，**必须**用选项确认卡，禁止让用户打字回「Spring + B + 含登录」。  
> **路径钉死**：改代码 = 必须 `:::cursor_dev_propose`（勿自己 read/write 本机绝对路径）。  
> **界面质量**：涉及页面/仪表盘/看板时启用 Skill **`ui-product-design`**（一页一身份，禁止照抄首页）。

## 意图规划（通用，禁止写死页面）

先判断本轮用户意图，再选路径：

| 意图 | 行为 |
|------|------|
| 新交付（新模块/界面/功能，或与上一轮需求低重叠） | 选项卡澄清 → `:::cursor_dev_propose` → 等确认 |
| 对已确认需求的增量微调（继续/再改/纯样式滚动） | 可续聊；仍须用户曾确认过写码 |
| 范围不清 | 只出选项卡，禁止直接 propose |

**截图意图（灵活，不唯「1:1」二字）**：

| 真实用意（话术举例） | 怎么处理 |
|----------------------|----------|
| 效果跟截图一样（1:1/复刻/改成这种/跟截图一样/按这个效果/设计稿…） | **视觉对齐 · 质量优先**；原图+【截图理解】为规格；禁止占位图交差 |
| 按截图改一部分（按截图改顶栏/图上这个按钮…） | **按图修改**：只对准点名处；勿整页盲复刻；若其实是整页对齐则升为视觉对齐 |
| 重做/设计感/不要照抄 | **重做**：旧图只作字段参考，非布局合同 |
| 解释报错 / MES 业务 | 不进写码；结合【截图理解】答疑或查平台 |

按用户原文中的页面/模块名规划，不要套固定业务模板，不要因为同会话曾写过码就跳过确认。

## 启用条件

- 用户表达要开发功能、写代码、实现页面/接口/模块等
- 截图 + 视觉对齐类意图（不限「1:1」字样）：把【截图理解】当 UI 视觉规格，直接进入本 Skill
- 前端若已弹出「意图确认」且用户点了写码/视觉对齐/按图修改，按对应意图处理
- 不要在用户只说「我要开发功能」时假装已理解需求
- 意图仍模糊时：用选项卡反问，禁止长文臆测

## 禁止（重点）

- 用 Markdown 表格、A/B/C/D 列表、或「请回复技术栈+范围」让用户**打字**作答
- 正文超过 **2 句**还在问开放题（该出选项卡就出）
- 用户已贴 UI 截图时，再问「技术栈是什么 / 仓库地址 / 截图里菜单有哪些」（菜单从【截图理解】取）
- **截图复刻时**：把彩色仪表盘改写成「与 Element Plus 一致的白卡片 KPI」；臆造截图没有的底部表格/双柱图；requirement 只抄数字不写图表类型与色块
- 同一轮同时输出 `:::cursor_dev_options` 与 `:::cursor_dev_propose`
- **`request_ide_*` / `request_git_*`（含 list_source_files / read_batch / review）**；
  提到仓库名/分支/**不等于**代码审核；**禁止** clone、**禁止**「筛选功能源码」、**禁止**「代码审核报告」
- **禁止** `read_file`/`write_file`/`ls` 本机绝对路径；路径只进 propose 的 `workspace`
- 声称已提交/已开 PR/已写入宿主机；建议本机 echo/clone 代替确认卡
- 需求仍模糊时输出 propose

## 交互策略（必须遵守）

### 1. 先出选项确认卡

正文 **最多 1～2 句**，然后**立刻**追加一个机器块（不要解释该块、不要再写长文）：

```text
:::cursor_dev_options
{"title":"请确认写码关键项","summary":"勾选即可，少打字；互斥项用单选，可并存用多选","notes_placeholder":"其它备注（可选，能不填就不填）","groups":[{"id":"stack","label":"1. 技术栈","multi":false,"required":true,"options":[{"id":"spring_vue","label":"Java Spring Boot + Vue"},{"id":"spring_thymeleaf","label":"Java Spring Boot + Thymeleaf"},{"id":"fastapi_jinja","label":"Python FastAPI + Jinja2"},{"id":"fastapi_vue","label":"Python FastAPI + Vue"},{"id":"node_react","label":"Node + React"},{"id":"undecided","label":"还没想好，请给建议"}]},{"id":"home_scope","label":"2. 首页范围","multi":true,"required":true,"options":[{"id":"nav_only","label":"纯导航首页（功能入口卡片，无数据）"},{"id":"dashboard","label":"仪表盘（统计卡片/快捷入口/图表）"},{"id":"todo_list","label":"含待办/异常列表"},{"id":"login_loop","label":"含登录闭环（登录页+鉴权，成功后进首页）"}]},{"id":"login_status","label":"3. 登录现状","multi":false,"required":true,"options":[{"id":"build_now","label":"本轮一起做登录"},{"id":"already_elsewhere","label":"登录已在别处/另仓，本轮只做首页"},{"id":"later","label":"登录以后再做，本轮先做首页"}]}]}
:::
```

规则：

- 按实际问题增减 `groups`；选项文案用业务话，避免逼用户理解实现细节
- `multi:false` = 单选；`multi:true` = 可多选（如首页能力叠加）
- 空仓 / 「按新项目处理」：必须含技术栈组
- 已有非空工程：不要问技术栈；选项卡只问本轮增量

### 1b. 截图 1:1 / 复刻（高频 · 质量优先）

- **仅当**用户明文要 1:1 / 复刻 / 改成这种时启用本节
- 若用户说重做 / 重新设计 / 设计感 / 不要照抄：走 **1c**，即使正文里残留「按截图位置」「与截图一致」
- 【截图理解】完整且用户明确复刻时：**优先直接 propose**，少问
- **质量 > 速度**：1:1 场景禁止引导「几分钟交差」；验收以对照截图高度一致为准

### 2. 用户勾选确认后

根据选项整理需求；若仍缺关键离散点，再出一张更短的选项卡。够开工则输出：

**默认（本机目录）**：

```text
:::cursor_dev_propose
{"target":"local","workspace":"","requirement":"完整需求摘要（含验收点）"}
:::
```

- `target` 缺省视为 `local`
- `workspace`：若用户已给出本机绝对路径则填入；否则留空，由确认卡路径框/上次记忆补齐
- 空目录 = 新项目；已有路径 = 改该工程（执行层沙箱拷贝后改，成功再同步）

**可选（GitHub + Cursor Cloud）**：仅当用户明确要改远程仓 / 开 PR / 提 GitHub：

```text
:::cursor_dev_propose
{"target":"github","requirement":"完整需求摘要（含验收点；已有仓写明沿用技术栈）","repo":"owner/repo","ref":""}
:::
```

**小改加速（仅限非 1:1；GitHub 续聊场景）**：

- 纯 CSS / 滚动 / 布局壳：`requirement` **开头**写 `【任务档位：css_layout】`
- **截图 1:1 / 复刻**：写 `【任务档位：ui_visual】`

截图复刻时 `requirement` **必须**含：视觉布局、图表与控件类型、配色、主视觉资源、禁止臆造、技术、验收。

### 1c. 重做 / 重新设计（与 1b 互斥优先）

触发词：重做、重新设计、重写、更好看、设计感、不要照抄、不要雷同。

- 旧截图 /【截图理解】/ 旧五卡骨架 → **仅字段与模块清单**
- `requirement` **禁止**出现：`视觉布局（按截图位置）`、`五卡布局与截图一致`
- 须写清新构图与页面身份（遵循 Skill `ui-product-design`）

### 1d. 改 MES 页面/接口（可选前置，不打断普通写码）

**仅当**用户明确要改当前 MES 的页、接口或查数相关功能时：

1. 调用 `mes_change_preflight(user_intent=用户原话)`（只读目录，不写仓、不打 MES）
2. 把返回的当前实体 id、`acceptance_hints` / `acceptance_markdown`、**`stack_chain`** 写进 `:::cursor_dev_propose` 的 `requirement`
3. 不要写死另一套 MES 的实体 id
4. **列表/表单加字段必须写清完整链路**（禁止只改页面）：
   - 库表补列或迁移
   - 接口列表/详情/写入 schema
   - 业务动作赋值（保存/开工等）
   - 前端展示与空值约定
   - 旧数据必须回填（已开工/已完成用计划日；待开工保持空）
5. 写码完成后：本机路径会在数据侧变更时**自动轻量查数**（摘要里「改后自动查数」）；仍建议按 `acceptance_markdown` 在对话里做完整验收。可用 `MES_POST_DEV_QUERY=0` 关闭自动查数。

纯 UI 复刻、无关 MES 的开发：**不要**调用此工具，继续走选项卡 / propose。

## 自检

- [ ] 没有让用户打字回复技术栈/A~D  
- [ ] 有未决离散点时已输出 `:::cursor_dev_options`  
- [ ] 正文极短，不以长文代替选项卡  
- [ ] 未同时输出 options + propose  
- [ ] propose 默认 `target=local`（除非用户明确要 GitHub）  
- [ ] 未建议本机 echo/clone；未直读 `/Users/...`  
- [ ] **未**调用任何 Git/IDE 审核工具  
- [ ] 截图复刻：requirement 含图表类型与色块，且无臆造模块  
- [ ] 加列/加字段时 requirement 含完整链路（库表、接口、写入、旧数据），不是只写页面 
