# Deep Agents 与 DeepSeek Harness 技术选型分析（WorkBuddy）

> 状态：**选型结论已锁定（主 harness = Deep Agents）** · **P0 落地进行中**（见 [`选型落地P0清单.md`](选型落地P0清单.md)）  
> 日期：2026-08-24  
> 产品名：对外统一 **ZR WorkBuddy**  
> 目的：就 WorkBuddy「企业深度定制 AI 应用」场景，对比 **Deep Agents Harness** 与 **DeepSeek Harness**，按业务功能点与技术点逐项分析，给出可执行结论。  
> 关联：[`选型落地P0清单.md`](选型落地P0清单.md)、[`DeepAgents-Skills使用指南.md`](DeepAgents-Skills使用指南.md)、[`DeepAgents-Middleware使用指南.md`](DeepAgents-Middleware使用指南.md)、[`MES懂行助手四块能力方案.md`](../总览/MES懂行助手四块能力方案.md)、[`ZR-WorkBuddy核心功能与技术实现说明.md`](../总览/ZR-WorkBuddy核心功能与技术实现说明.md)、[`本机目录写码与沙箱隔离方案.md`](../写码与审码/本机目录写码与沙箱隔离方案.md)、[`Cursor-SDK研发写码一期方案.md`](../写码与审码/Cursor-SDK研发写码一期方案.md)

---

## 0. 先分清三个易混概念

| 名称 | 是什么 | 与 WorkBuddy 关系 |
|------|--------|-------------------|
| **Deep Agents Harness** | LangChain 的 Agent 编排壳（`deepagents` / `create_deep_agent`） | **主对话已在用**：Tools + Skills + Middleware + Checkpoint |
| **DeepSeek Harness** | DeepSeek AI 的 coding-agent 可拼装运行时（`deepseek-ai/deepseek-harness`，`@deepseek-ai/dsh`） | **未采用**；最多可评估为写码执行层候选 |
| **DeepSeek 模型 / API** | `deepseek-chat` 等推理服务（`DEEPSEEK_*` / `LLM_*`） | **模型供应商**；可挂在 Deep Agents 或应急 LLM 工具环上，**不等于** DeepSeek Harness |

文档里说的「DeepSeek 工具环」指本机写码应急模式（`LOCAL_DEV_AGENT=llm`）：直接用对话模型做 tool-calling 循环改沙箱——**既不是 Deep Agents，也不是 DeepSeek Harness**。默认本机写码已改为 **Cursor SDK Local Agent**，避免 token 暴涨。

另注意：GitHub 上还有独立第三方仓库名含 `deepseek-harness`（协议适配器），**本文只讨论官方** `deepseek-ai/deepseek-harness`。

---

## 1. 选型前提：WorkBuddy 到底是什么

| 维度 | WorkBuddy 真实画像 |
|------|-------------------|
| 产品形态 | 企业微助手（MES 嵌入 / Web / 桌面），**非**通用 coding CLI |
| 主入口 | 自然语言对话 + SSE + 卡片（确认 / 图表 / 写码进度） |
| 能力权重 | **懂平台 / 查数 / 分析 / 运维** ≈ 主战场；**写码 / 审码** ≈ 核心但旁路；**自动提交 / 自动部署** ≈ 愿景（方案明确本期不做「写代码 → 测 → 合主干 → 自动部署」全自动流水线） |
| 硬约束 | HITL 写确认、路径沙箱、实体守卫、诚实缺口、厂区资料包、JWT 用户隔离 |
| 现有栈 | Python FastAPI + Vue + Deep Agents + Cursor SDK（Local / Cloud） |
| 交付约束 | 单人 / 小团队可维护；可换模型；可打 dmg；可对接现场 ERP HTTP |

用户能力清单（本文逐项覆盖）：

1. 可对话  
2. 懂平台业务  
3. 可查数  
4. 可分析数据  
5. 可运维  
6. 能写码  
7. 能改码  
8. 能审码  
9. 能自动化提交代码  
10. 能自动部署  

**选型原则**：谁更适合「业务 Agent 编排 + 企业策略」优先；谁更适合「coding runtime」其次，且可与主对话**分车道**。

---

## 2. 两套框架画像（对齐到选型）

| | **Deep Agents Harness** | **DeepSeek Harness** |
|--|-------------------------|----------------------|
| 出品 | LangChain（`langchain-ai/deepagents`） | DeepSeek AI（`deepseek-ai/deepseek-harness`） |
| 定位 | 业务 Agent 厚壳：Tools + Skills + Middleware + Checkpoint | Coding Agent 可拼装运行时：一切皆 Cordis 插件 |
| 语言 | Python，贴合现有 `apps/agent` | 主栈 TypeScript / Node；有 Python SDK，但高信任示例偏危险 |
| 成熟度 | 本仓库已落地（`create_deep_agent`、Skills、Middleware、`AsyncSqliteSaver`） | **Developer preview**，兼容性破坏可预期 |
| 强项 | 多工具业务环、横切强制、长会话、LangGraph 流式 / 持久化 | 文件 / Shell / 权限 / 子 Agent / 预设模式、本机 coding 体验 |
| 弱项 | 不是最强「纯写码 IDE」；写大仓易烧上下文（本仓库已旁路） | 不天生懂 MES / ERP；嵌进企业产品要重做壳；预览期风险 |
| 与模型关系 | 模型无关（DeepSeek / 通义 / 自建均可） | 默认真 DeepSeek 适配，也可接其它 provider |
| 默认界面 | 无强制 UI（由 WorkBuddy Vue / Electron 自建） | 自带 Web UI（如 `npx @deepseek-ai/dsh web` → `http://127.0.0.1:3080`） |
| 架构哲学 | 有默认、可覆盖（opinionated but extensible） | 全模块化、可替换（everything is a plugin） |

### 2.1 架构哲学对照

```text
Deep Agents Harness（LangChain）
  LangGraph 运行时
    → create_agent（薄壳）
      → create_deep_agent（厚壳：Skills / FS / Middleware 默认内置）
        → 本仓库 Tools + Skills + 自定义 Middleware

DeepSeek Harness（DeepSeek AI）
  Cordis 插件框架
    → 模型适配器（插件）
    → Agent Loop（插件）
    → 工具 / 权限 / 持久化 / UI（各自插件）
    → 通过配置拼装，而非继承固定中间件栈
```

### 2.2 DeepSeek Harness 能力摘要（选型相关）

- CLI / 包：`@deepseek-ai/dsh`；本地 Web 控制面，**不等于本地推理**（默认可仍走远程 API）。  
- Cordis：服务发现、typed events、可逆插件效果；`ctx.llm` / `ctx.tools` / `ctx.sessions` 等可替换。  
- 常见预设：Standard / PTC（Code Mode）/ Minimal / Creator；Creator 与 `danger-full-access` 信任边界极高，企业默认不可用。  
- 文件系统沙箱偏「工作区写权限」，**不是**完整机器 / 网络 / 进程隔离。  
- 适合：coding-agent 作者、要深度定制写码 loop 的团队。  
- 不适合：需要稳定公共 API、已完成安全评审、立刻量产交付的企业主内核（官方明确 preview）。

### 2.3 WorkBuddy 现状落点（事实）

| 能力 | 当前实现 |
|------|----------|
| MES 主对话（查数、摸底、运维、写码讨论、审码） | **Deep Agents** + 可配置 LLM（常为 DeepSeek） |
| 本机写码执行（默认） | **Cursor SDK Local Agent**（不经 Deep Agents / 不经 DeepSeek 工具环） |
| 本机写码应急 | `LOCAL_DEV_AGENT=llm`（手写 LLM 工具环） |
| GitHub 写码 | **Cursor Cloud**（`apps/cursor_dev/`） |
| DeepSeek Harness | **未接入** |

入口参考：`apps/agent/agents/agent.py`（`create_deep_agent`）、`apps/local_dev/`、`apps/cursor_dev/`。

---

## 3. 评分约定

| 标记 | 含义 |
|------|------|
| **优** | 框架天然匹配，或本仓库已验证 |
| **可** | 能做，但要大量自研胶水 / 重写产品协议 |
| **弱** | 能勉强塞，方向别扭或缺默认能力 |
| **不适** | 方向错配，或代价不合理 |

---

## 4. 按业务功能点逐项对比

### 4.1 可对话（统一入口、历史、流式、车道）

| 功能点 | Deep Agents | DeepSeek Harness | 说明 |
|--------|-------------|------------------|------|
| SSE 流式对话 + 过程步骤 | **优**（LangGraph + 现有 `agent_wrapper`） | **可**（自有 Web / 会话日志；接到 Vue / SSE 需重写网关） | WorkBuddy 前端协议已绑定 `status` / `step` / `token` / `chart` / `confirm` 等 |
| 多轮历史 / thread | **优**（checkpoint + history SQLite） | **可**（session log 强；与厂区用户隔离要自建） | 企业要按 JWT `sub` 隔离，两边都要自研存储策略 |
| 意图车道（MES / 写码 / 审码互斥） | **优**（Skills + `workbuddy_lane` + 系统提示） | **弱**（偏 coding preset，无业务车道语义） | 车道是产品协议，不是 coding loop 特性 |
| 停止生成 / 并发锁 | **优**（已有 cancel + stream lock） | **可** | 企业多用户并发多为自研问题，框架帮有限 |
| Embed 嵌入 MES 页 | **优**（`page_context` 注入 Agent） | **不适** | Harness Web UI 是独立产品壳，不是 iframe 嵌入助手 |

**小结论**：对话壳选 **Deep Agents**。

对应功能清单：`F-CHAT-*`、`F-HIST-*`、`F-EMB-*`、`F-CTX-*`。

---

### 4.2 懂平台业务（A：资料包 / 能力地图 / 术语 / 场景）

| 功能点 | Deep Agents | DeepSeek Harness | 说明 |
|--------|-------------|------------------|------|
| 读表结构 MD / OpenAPI 资料包 | **优**（`schema_tool` + virtual FS） | **可**（文件工具强，但缺领域工具语义） | 「懂平台」靠**领域 Tools + Skills**，不是靠写码能力 |
| 能力地图 / 场景表包 / 术语 | **优**（已有工具链） | **弱** | Harness 不会自带 `capability_map` / `entities` |
| 「摸底不假装查数」诚实边界 | **优**（Skill + Middleware 可强制） | **弱** | coding agent 默认倾向「去读仓库 / 跑命令」，易越界 |
| 换厂换资料包 | **优**（`mes_profiles` + `inspect_mes_profile`） | **弱** | 需整套业务配置面，与 harness 无关 |

**小结论**：A 必须 Deep Agents（或等价业务 Agent）；Harness 最多当「读文档的 coding 助手」，不是 MES 懂行助手。

对应：能力块 A、`F-SCHEMA-*`。

---

### 4.3 可查数（B：真 ERP HTTP / 实体 / 缺口）

| 功能点 | Deep Agents | DeepSeek Harness | 说明 |
|--------|-------------|------------------|------|
| JWT + 实体目录查 list API | **优**（`platform_query` 工具） | **可**（自写 tool 插件） | 业务价值在 Tool 实现；Deep Agents 接入成本更低（Python 同栈） |
| 实体守卫 / 错实体拦截 | **优**（Middleware） | **可**（权限插件可做，但非默认） | 企业硬约束更适合 Middleware 模型 |
| 显式缺口 `explicit_gap` | **优**（metrics overlay） | **弱** | 产品策略两边都能塞提示词，Deep Agents 已落地 |
| 登录与查数鉴权分离 | **优**（已有） | **可** | 与 harness 无关，但 Python API 已成型 |

**小结论**：查数选 **Deep Agents**；Harness 重写工具层 ROI 极差。

对应：`F-QUERY-*`、`F-AUTH-*`（登录 ≠ MES 接口账号）。

---

### 4.4 可分析数据（出图 / 看板 / 指标 / 导出）

| 功能点 | Deep Agents | DeepSeek Harness | 说明 |
|--------|-------------|------------------|------|
| 指标口径 / 简报 / 汇总 | **优** | **弱** | 依赖资料包 `metrics.json` 与聚合 caveat |
| `render_analysis_chart` → ECharts 卡 | **优**（工具结果 → SSE `chart`） | **不适** | Harness UI 不是 `AnalysisChartCard` 协议 |
| PCB 看板 / 下钻 | **优** | **不适** | 前端业务组件绑定主对话流 |
| 页内 ≠ 全库 caveat | **优**（服务端强制） | **弱** | 企业合规话术要服务端硬控 |
| 导出报告 / 下载链 | **优** | **可** | 与现有 `/api/download` 绑定 |

**小结论**：分析展示链路选 **Deep Agents + 现有 Web**。

对应：`F-QUERY-08`～`F-QUERY-11`、`F-CHAT-13`。

---

### 4.5 可运维（C：值班 playbook / 探活 / 审计 / HITL）

| 功能点 | Deep Agents | DeepSeek Harness | 说明 |
|--------|-------------|------------------|------|
| 固定运维场景 `run_ops_scene` | **优** | **弱** | Playbook 是业务剧本，不是 shell 排障 |
| API 沙箱探活（不打生产） | **优** | **可**（shell / HTTP 工具） | 本仓库已有默认不伤生产的探活沙箱 |
| 写操作 HITL 确认卡 | **优**（Middleware 拦工具 + API 直执） | **可**（权限审批） | Deep Agents 路径已验证「确认后不二次过模型」 |
| 写审计 / 谁导入了 | **优** | **弱** | 企业审计落盘与会话绑定 |
| 故障树 / 401 / 空目录引导 | **优**（Skill） | **弱** | |

**小结论**：运维值班选 **Deep Agents**。Harness 的 permission 适合「改文件要不要批」，不适合「导入生产数据要不要批」。

对应：`F-DUTY-*`、`F-WRITE-*`、`F-APIH-*`。

---

### 4.6 能写码 / 能改码（D：本机沙箱 + GitHub）

| 功能点 | Deep Agents | DeepSeek Harness | 说明 |
|--------|-------------|------------------|------|
| 对话澄清 + 确认卡（propose） | **优**（Skill `cursor-dev-chat`） | **弱** | 需求澄清仍在业务对话里 |
| 本机沙箱改码 + 同步闸门 | **弱（不宜主环）**；应急 LLM 工具环曾烧 token | **优（coding 本职）** | Harness 文件系统 / 权限 / 预设为写码而生 |
| GitHub 远程改仓 | **弱** | **可** | 本仓库用 **Cursor Cloud** 更贴「同事零配 Git」 |
| 截图对齐写 UI | **优（视觉注入 + 讨论）** / 执行靠 Cursor | **可** | 视觉仍要外挂；执行层谁都行 |
| `stack_chain` / 写后查数闸门 | **旁路已有**（`local_dev`） | **可**（插件化） | 闸门是产品逻辑，与 harness 解耦 |

**小结论**：

- **讨论与确认**：Deep Agents  
- **执行改码**：不要塞回 Deep Agents 主环；候选是 **Cursor（现状）** 或 **DeepSeek Harness（若自建 coding runtime）**  
- 用 Harness **替换 Cursor** 才有意义；用它 **替换整套 WorkBuddy** 没有意义  

对应：`F-DEV-*`、能力块 D。

---

### 4.7 能审码

| 功能点 | Deep Agents | DeepSeek Harness | 说明 |
|--------|-------------|------------------|------|
| 贴码分析 | **优** | **可** | 轻量对话即可 |
| IDE Bridge 分批读 / Git 浅克隆审 | **优**（工具 + Skill） | **可** | Bridge / MCP 是自研；Harness 可接 MCP，但要重做产品流 |
| 正式中文审核报告壳 | **优** | **弱** | 报告格式是业务协议 |
| 与写码车道硬互斥 | **优** | **弱** | 产品状态机，不在 coding harness 默认能力里 |

**小结论**：审码产品流选 **Deep Agents + Bridge**；Harness 不是审码产品壳。

对应：`F-CODE-*`、`F-IDE-*`。

---

### 4.8 能自动化提交代码（愿景）

| 功能点 | Deep Agents | DeepSeek Harness | 说明 |
|--------|-------------|------------------|------|
| 推工作分支 / PR | **弱**（需外挂 git 工具或 Cursor） | **优**（shell / git + 权限批） | coding harness 更自然 |
| 白名单仓 / 禁合主干策略 | **可**（Middleware / 旁路策略） | **可**（permission preset） | 企业策略仍要自研 |
| 与 MES 写确认同级的「合码确认」 | **优（产品卡）** | **可** | UI / 协议在 WorkBuddy Web |

**小结论**：自动提交**执行层**偏 Harness 或 Cursor / CI；**门禁与确认 UI** 仍归业务层（Deep Agents / API）。

说明：当前方案边界为「确认后写码，可审码验收；不合主干、不自动部署」。自动化提交是演进项，不改变主 harness 选型。

---

### 4.9 能自动部署（愿景）

| 功能点 | Deep Agents | DeepSeek Harness | 说明 |
|--------|-------------|------------------|------|
| 触发 CI / CD、发布流水线 | **可**（Tool 调 API） | **可**（shell / workflow） | 两边都能调；关键是审批与环境隔离 |
| 生产变更双人确认 / 变更窗 | **优（业务 HITL）** | **弱** | 企业变更治理不是 coding 默认能力 |
| 部署后回读 MES 验收 | **优**（`post_dev_query` 同类） | **弱** | 要接查数工具链 |

**小结论**：自动部署应是 **「业务 Agent 编排 + CI 执行」**，不是换成 DeepSeek Harness 就能得到；Harness 最多当执行器之一。

---

## 5. 按技术点逐项对比

| 技术点 | Deep Agents | DeepSeek Harness | WorkBuddy 偏向 |
|--------|-------------|------------------|----------------|
| **Agent Loop** | LangGraph tool 环，已调通 SSE | Cordis 插件 loop，可换 | 主对话：Deep Agents |
| **Tools 注册** | LangChain tools，Python 同栈 | Cordis tool 插件，偏 TS | 主对话：Deep Agents |
| **Skills / 剧本** | 一等公民（渐进披露） | 有 skills，但生态偏 coding | 业务剧本：Deep Agents |
| **Middleware / 硬拦截** | 一等公民（写确认、守卫） | 权限 / 审批插件 | 企业策略：Deep Agents |
| **文件系统沙箱** | `FilesystemBackend` `virtual_mode`（限制在 Agent 根） | `workspace-write` / sandbox（写码向） | 读资料：DA；改仓：Local / Harness / Cursor |
| **Checkpoint / 恢复** | `AsyncSqliteSaver` 已用 | session append-only log | 主会话：Deep Agents |
| **子 Agent** | SubAgentMiddleware | 一等子 Agent / workflow | 复杂任务两边都行；业务优先 DA |
| **HITL** | 工具级中断 + 确认卡 | 权限审批 UX | 数据写：DA；文件写：Harness / Cursor |
| **前端产品壳** | 自有 Vue（正确） | 自带 Web UI @3080 | **必须自有壳**，勿换 `dsh` Web |
| **桌面 Electron 打包** | Python runtime 已嵌入 | Node 22+ 另嵌一套 | 现交付：Deep Agents 栈 |
| **模型可替换** | 强 | 可（多 provider） | 都够；DA 已解耦 |
| **MCP** | 可接 | 原生友好 | 审码 MCP：可并存 |
| **生产成熟度** | 已跑试点 | Developer preview | 企业交付：Deep Agents |
| **与 ERP HTTP 集成** | 成熟 | 要从零插件化 | Deep Agents |
| **Token / 成本控制** | 主环可控；写码勿进主环 | coding 轨迹可控性更好 | 写码旁路 |
| **双栈运维成本** | 单 Python Agent | 若替换主环 → TS + Python 双栈 | 避免主环换 Harness |
| **安全边界** | 路径 / SSRF / 写确认已纵深 | 文档明确非完整机器隔离；Creator / danger 高风险 | 企业默认严策略：DA + 旁路沙箱 |
| **流式协议与图表事件** | 已与 Vue 对齐 | 需重新映射 | Deep Agents |
| **厂区资料包 / settings 覆盖** | 已有分层配置 | 无关 / 需重做 | Deep Agents |
| **HA / DATA_DIR / flock** | 已有部署说明 | 不解决产品存储模型 | 与主 harness 无关，但迁栈成本高 |

---

## 6. 能力覆盖总表（一眼决策）

| 用户说的能力 | 最佳宿主 | Deep Agents | DeepSeek Harness |
|--------------|----------|-------------|------------------|
| 可对话 | 业务 Agent | ✅ 主选 | 仅作旁路 UI → 不适 |
| 懂平台业务 | 业务 Agent + 资料包 | ✅ 主选 | ❌ 不适主路径 |
| 可查数 | 业务 Tools | ✅ 主选 | 可插件但差 |
| 可分析数据 | 业务 Tools + Vue | ✅ 主选 | ❌ 不适 |
| 可运维 | Playbook + HITL | ✅ 主选 | ❌ 不适主路径 |
| 能写码 / 改码 | Coding 执行器 | 讨论 ✅ / 执行 ❌ | 执行 ✅（候选） |
| 能审码 | 业务车道 + Bridge | ✅ 主选 | 可辅助 |
| 自动化提交 | CI / git 执行器 + 确认 | 编排 ✅ | 执行 ✅ |
| 自动部署 | CI / CD + 变更治理 | 编排 ✅ | 执行可 |

---

## 7. 三种架构选项

```text
选项 A（现状强化）——推荐
  Vue / Electron
    → FastAPI
      → Deep Agents（A/B/C + 澄清 / 审码 / 确认）
      → Cursor Local / Cloud（改码执行）
      → 未来：CI（提交 / 部署）由 API Tool 触发，仍经 HITL

选项 B（Harness 替换写码执行）
  Deep Agents 不变
  本机改码：DeepSeek Harness 替代 Cursor Local
  GitHub：仍 Cursor Cloud 或 Harness + git
  代价：第三条执行栈、preview 风险、桌面要带 Node

选项 C（全量迁 DeepSeek Harness）——不推荐
  用 dsh 当产品内核
  重写：MES Tools、HITL、图表协议、嵌入、厂区资料包、桌面
  收益：几乎只剩「写码手感」；A/B/C 全部倒退
```

| 选项 | 适配度 | 风险 | 工期体感 |
|------|--------|------|----------|
| A 现状强化 | ★★★★★ | 低 | 继续演进 |
| B Harness 仅写码执行 | ★★★ | 中高（preview + 双执行器） | 数周～月级 POC |
| C 全量替换 | ★ | 极高 | 接近重做产品 |

---

## 8. 为何企业深度定制更吃 Deep Agents（补充论证）

WorkBuddy 的核心难点不在「会不会写代码」，而在：

1. **领域工具很多**：平台查询、实体目录、图表、审计、审核分批……要稳定 tool calling  
2. **硬约束要代码强制**：写确认 HITL、路径守卫、实体白名单——这是 Middleware，不是靠模型自觉  
3. **软约束要可演进**：Skills 剧本可按客户 / 场景加，不必改框架  
4. **会话要可恢复**：SSE、checkpoint、长对话摘要  
5. **模型和厂商要可换**：今天 DeepSeek，明天通义 / 自建，harness 不能绑死一家  
6. **和现有 Python 后端同栈**：FastAPI、配置、测试、桌面打包都已经是这条链  

Deep Agents 为「模型 + 工具环 + 中间件 + 持久化」这种**业务 Agent**准备；DeepSeek Harness 更偏**可拼装的 coding-agent 运行时**（CLI / Web / 权限 / 插件），强项在通用写码体验，不在「和 ERP / MES / HITL 拧成一体」。

### 8.1 DeepSeek Harness 何时才值得看

适合考虑它（或类似 Claude Code 类 runtime）的情况：

- 产品主形态就是「给研发用的本机 Agent IDE / CLI」  
- 愿意用它的 TypeScript / Cordis 插件体系重做执行环  
- 接受和现有 Python Agent 双栈运维  

对 WorkBuddy：

- **主对话迁过去**：成本高、收益低  
- **写码**：已有 Cursor Local / Cloud；再叠一层 DeepSeek Harness 容易变成第三条平行世界（除非 POC 证明明显更优且可替换 Cursor Local）  

### 8.2 与「DeepSeek 模型」的关系

- 继续用 DeepSeek 当对话 / 应急模型即可（`LLM_*` / `DEEPSEEK_*`）。  
- **不必**为了用 DeepSeek 模型而换 DeepSeek Harness。  
- 模型选择与 harness 选择正交：同一模型在不同 harness 下的工具行为、上下文、成本可以完全不同。

---

## 9. 建议落地策略

> **当前档：P0（2026-08-24 开工）** · 检查表见 [`选型落地P0清单.md`](选型落地P0清单.md) · Cursor 规则 `.cursor/rules/agent-harness-deep-agents.mdc`

| 优先级 | 动作 | 状态 |
|--------|------|------|
| **P0** | 锁定架构：**Deep Agents = 主 harness**；写码继续旁路（Cursor） | **已关闭**（2026-08-24） |
| **P0** | 继续强化：结构化车道、HITL、缺口透明、资料包、分析 / 运维 Tools | **基线已有**（巩固项，见 P0 清单） |
| **P1** | 自动提交 / 部署：做成「确认卡 → API → CI」；**人触发提交**（如「提交今天的代码」）→ **只审本批** → 确认 → 工作分支 commit | **P1-1b 待验收**（默认关写码收尾自动门禁；见方案文档） |
| **P2（可选 POC）** | 仅评估「本机写码执行」用 DeepSeek Harness 是否比 Cursor Local 更稳更便宜；**通过才替换执行器，不碰主对话** | 未开 |
| **明确不做** | 用 `dsh web` 替换 WorkBuddy 产品壳；用 Harness 重写查数 / 看板 / 值班 | 约束生效 |

若做 P2 POC，建议最小验收：

1. 固定同一本机样例仓、同一需求话术、同一权限边界（禁止 `danger-full-access`）  
2. 对比：成功率、步数、token / 费用、闸门（`stack_chain`）通过率、同步后预览是否可开  
3. 桌面是否必须额外捆绑 Node 22+；失败降级是否仍回 Cursor / llm  
4. **通过标准**：不明显劣于 Cursor Local，且运维成本可接受，才进入「选项 B」设计；否则维持选项 A  

---

## 10. 最合理总结结论

### 10.1 一句话

**WorkBuddy 应以 Deep Agents 作为企业深度定制的主 harness；DeepSeek Harness 最多作为「写码执行层」的可选替代（与 Cursor 竞争），绝不应替换主对话与 A/B/C 运维分析内核。**

### 10.2 为什么这是最合理的

1. **产品重心是「懂 MES 的对话助手」**，不是「通用 coding IDE」。Deep Agents 的 Tools / Skills / Middleware / Checkpoint 与 A/B/C、HITL、诚实缺口、厂区资料包同构；DeepSeek Harness 的强项在文件 / Shell / 权限 / coding preset，和主价值错位。  
2. **本仓库已经用对了分车道**：主环 Deep Agents，改码 Cursor 旁路——同时解决「企业策略」与「写码成本 / 隔离」。全迁 Harness 会毁掉这条已验证边界。  
3. **DeepSeek Harness 仍是 developer preview**，企业试点交付、桌面打包、接口稳定、安全评审都不合适做主内核。  
4. **「自动提交 / 自动部署」不依赖换 harness**：依赖确认门禁 + CI / CD Tool + 环境隔离；编排仍应在业务 Agent，执行交给 git / CI（或 Cursor / Harness）。  
5. **模型与框架解耦**：继续用 DeepSeek 当对话 / 应急模型即可；不必为了用 DeepSeek 模型而换 DeepSeek Harness。  

### 10.3 可写进方案的正式表述

> 企业深度定制 AI 应用（ZR WorkBuddy）的技术选型为 **「Deep Agents 业务编排 + 可插拔写码执行器（现状 Cursor；可选评估 DeepSeek Harness）+ CI 承担合码 / 部署」**；**DeepSeek 作为模型供应商，DeepSeek Harness 不作为产品主框架。**

---

## 11. 附录：WorkBuddy 当前分层（对照选型）

```text
┌─────────────────────────────────────────────────────────┐
│  交付层：Vue3 + Electron（ZR WorkBuddy）                  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / SSE
┌──────────────────────▼──────────────────────────────────┐
│  API：FastAPI（登录 / 对话 / 写确认 / 写码审码 / 设置）    │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Agent：Deep Agents + Skills + Middleware + Tools         │  ← 主 harness（锁定）
└──────────┬───────────────────────────────┬──────────────┘
           │                               │
           ▼                               ▼
     MES HTTP / 资料包              Cursor Local / Cloud
                                   （写码执行旁路）
                                   未来可选：DeepSeek Harness
                                   仅作执行器 POC
```

关键路径：

| 区域 | 路径 |
|------|------|
| Agent 入口 | `apps/agent/agents/agent.py` |
| Skills 指南 | `docs/Agent开发/DeepAgents-Skills使用指南.md` |
| Middleware 指南 | `docs/Agent开发/DeepAgents-Middleware使用指南.md` |
| 本机写码 | `apps/local_dev/` |
| GitHub 写码 | `apps/cursor_dev/` |
| 四块能力方案 | `docs/总览/MES懂行助手四块能力方案.md` |

---

## 12. 修订记录

| 日期 | 说明 |
|------|------|
| 2026-08-24 | 首版：按可对话 / 懂平台 / 查数 / 分析 / 运维 / 写改码 / 审码 / 自动提交 / 自动部署及技术点完整选型；结论锁定选项 A |
| 2026-08-24 | P0 开工：Cursor 规则 + [`选型落地P0清单.md`](选型落地P0清单.md)；旁路 / 车道基线核对 |
