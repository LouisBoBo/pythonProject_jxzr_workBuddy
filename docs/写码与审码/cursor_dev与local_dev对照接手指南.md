# cursor_dev ↔ local_dev 对照与接手指南（P1-04）

> 日期：2026-08-21  
> 目的：两条写码链路**有意并行**，降低接手时「改 A 却动到 B」的成本。  
> 详细方案仍以：[`本机目录写码与沙箱隔离方案.md`](本机目录写码与沙箱隔离方案.md)、[`Cursor写码车道原理与完整流程.md`](Cursor写码车道原理与完整流程.md)、[`Cursor写码车道管理员上线清单.md`](Cursor写码车道管理员上线清单.md)。

---

## 1. 一句话分工

| 包 | 改哪里 | 谁执行 | 典型用户说法 |
|----|--------|--------|--------------|
| **`apps/local_dev`** | 本机工程目录（先沙箱再同步） | Cursor **Local** Agent（`cwd=sandbox`） | 「在本机这个工程加一页」 |
| **`apps/cursor_dev`** | 白名单 **GitHub** 仓库工作分支 | Cursor **Cloud** Agent | 「在白名单仓库改 …」 |

前端确认卡同一套 UI，用 `target: local | github`（及会话锚点）分流；**默认倾向 local**。

---

## 2. 代码落点（勿混改）

| 层 | local_dev | cursor_dev |
|----|-----------|------------|
| 业务包 | `apps/local_dev/`（`jobs.py`、`service.py`、`cursor_local_agent.py`、`fs_snapshot.py`…） | `apps/cursor_dev/`（`jobs.py`、`service.py`、`readiness.py`…） |
| HTTP | `apps/api/routes/local_dev.py`（tags「本机写码」） | `apps/api/routes/cursor_dev.py`（tags「Cursor 写码」） |
| 落盘 | `DATA_DIR/local_dev/`（含 `sandboxes/{job_id}/`） | `DATA_DIR/cursor_dev/`（job / 进度） |
| 环境 | 本机路径可选；Local Agent 依赖 Cursor SDK | `CURSOR_API_KEY`、白名单、`CURSOR_DEV_*` |
| 就绪检查 | 本机状态 / 工作区偏好接口 | `scripts/check_cursor_dev_ready.py` |

**共享（两边都碰、改前先看调用方）**

- 对话确认卡 / propose 解析：`ChatView` + `chatCursorDevParse.js` / `chatCursorDevPlan.js`
- 机器块：`:::cursor_dev_propose` / `:::cursor_dev_options`（`target` 字段）
- Agent 车道：`workbuddy_lane=code_dev`（与审核互斥）

---

## 3. 何时走哪条

| 场景 | 走 |
|------|----|
| 同事本机有工程、要立刻预览落盘 | **local_dev** |
| 改公司 GitHub 固定分支、同事零配 Git | **cursor_dev** |
| 只讨论/贴码、不落仓 | 都不建 job（贴码 / 讨论车道） |
| API 跑在远程服务器、要写用户笔记本磁盘 | **local_dev 不适用**（同机假设）；须桌面同机或另评 Bridge |

---

## 4. 同构点与刻意差异

**同构（接手时容易晕）**

- 都有 job 状态机、SSE/轮询进度、一人一任务限流、确认后才开写  
- 都经「讨论 → options/propose → 确认卡 → job」  

**刻意差异（不要强行合并）**

| | local_dev | cursor_dev |
|--|-----------|------------|
| 隔离 | 目录沙箱 + 同步闸门 | Cloud 侧 + 仓白名单 |
| 密钥 | 主要靠本机 Cursor/SDK 能力 | Team `CURSOR_API_KEY` |
| 失败面 | 路径权限、预览端口、import 闸门 | 配额、GitHub App、白名单 |
| 合入 | 用户本机目录即结果 | 工作分支 / 可选 PR，不合主干 |

短期**不**做「合成一个 service 包」；先靠本文档 + 路由中文 tags 降接手成本。真要收敛，单独立项（接口契约对齐后再抽共享 job 基类）。

---

## 5. 改动检查清单（必过）

改写码相关前先勾：

1. ☐ 本次是 **local / github / 两边都有**？只改对应 `apps/*/ ` 与 `routes/*`  
2. ☐ 是否动了 `:::cursor_dev_*` 字段？两边确认卡与后端解析都要测  
3. ☐ 是否动了 `workbuddy_lane` / 意图启发式？审核车道勿被写码抢走  
4. ☐ local：沙箱路径仍在 `DATA_DIR/local_dev/sandboxes/` 内（`relative_to`）  
5. ☐ github：白名单与确认卡仍挡非允许仓  
6. ☐ 冒烟：对应 `smoke` / 就绪脚本（Cloud 用 `check_cursor_dev_ready`）

---

## 6. 推荐阅读顺序（新人半天）

1. 本文 §1～§3  
2. [`本机目录写码与沙箱隔离方案.md`](本机目录写码与沙箱隔离方案.md) §1～§2  
3. [`Cursor写码车道原理与完整流程.md`](Cursor写码车道原理与完整流程.md) §1～§2  
4. [`Cursor写码车道管理员上线清单.md`](Cursor写码车道管理员上线清单.md)（仅 Cloud）  
5. 代码：先 `routes/local_dev.py` + `routes/cursor_dev.py` 的建 job 入口，再下钻 `service.py`
