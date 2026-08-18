# Cursor 写码车道 · 管理员上线清单

> **原则：同事零配置。**  
> Cursor ↔ GitHub、API Key、白名单、Cloud Agents **全部由管理员在上线前配好**。  
> 同事只需：打开 WorkBuddy → ERP 登录 → 对话写码。

---

## 1. 给谁看

| 角色 | 要做什么 |
|------|----------|
| 管理员 / 运维 | 按本文一次性配通；上线前跑就绪检查 |
| 业务同事 | **不需要** Cursor 账号、不需要连 GitHub、不需要填 API Key |

---

## 2. 架构（为何同事不用配）

```text
同事浏览器 → WorkBuddy（ERP 登录）
                 ↓
         服务端唯一 CURSOR_API_KEY（Team）
                 ↓
         Cursor Cloud Agent（团队已授权的 GitHub App）
                 ↓
         白名单 GitHub 仓库（固定工作分支；默认不开 PR）
```

写码消耗记在 **Team Key** 账单上，不按同事个人 Cursor 订阅分摊配置成本。

---

## 3. 上线前必做（管理员）

### 3.1 Cursor Team

1. 使用公司 **Cursor Team**（不要用个人 Pro 当生产 Key）
2. 开通 **Cloud Agents**，完成 [Set Up](https://cursor.com/agents)
3. [Integrations](https://cursor.com/dashboard/integrations) → GitHub → Connect  
   - GitHub App 安装到 **公司 org**（或至少覆盖白名单仓）
   - 权限含读/写目标仓
4. 生成 **Team / Service Account API Key**（须属于「已连 GitHub」的同一 Team）
5. 在 [Usage / Spending](https://cursor.com/dashboard/usage) 设好支出上限，避免一上线就 `resource_exhausted`

### 3.2 GitHub 仓库

对每个白名单仓：

- [ ] 仓库 **非空**（至少有默认分支 + 1 个 commit；空仓 Cursor 无法 verify ref）
- [ ] Cursor GitHub App 对该仓可见
- [ ] 已约定工作分支策略：单仓固定分支（如 `hebo`）或按用户前缀（`dev/wb/<user>`）
- [ ] 同事若要本地拉分支验收，仍走公司现有 Git 权限（与 Cursor 授权无关）

### 3.3 WorkBuddy 服务端 `.env`

```bash
CURSOR_DEV_ENABLED=1
CURSOR_API_KEY=...                 # 仅服务端；Team Key；勿提交仓库
CURSOR_DEV_REPO_ALLOWLIST=org/a,org/b   # 生产建议非空
# CURSOR_DEV_ALLOWED_USERS=         # 空=所有已登录用户可用；可按需收紧
CURSOR_DEV_MODEL=composer-2.5       # 优先地区友好模型（Composer）；少用受限厂商作默认
CURSOR_DEV_AUTO_PR=0                # 推荐：只推工作分支，不自动开 PR
# 单仓固定工作分支（如仓内只保留 main + hebo）
CURSOR_DEV_WORK_BRANCH=hebo
CURSOR_DEV_STARTING_REF=hebo        # 与 WORK_BRANCH 一致；Cloud 从该分支起改
# 未设 WORK_BRANCH 时才用按用户命名：
# CURSOR_DEV_BRANCH_PREFIX=dev/wb/
CURSOR_DEV_MAX_CONCURRENT=3
CURSOR_DEV_MAX_CONCURRENT_PER_USER=1
# 强烈建议（私有仓预检 + 误开 PR 自动关闭）
GITHUB_TOKEN=...                    # 或 CURSOR_DEV_GITHUB_TOKEN=
```

重启 API 后生效。

**说明：** Cursor 网页「Set Up Cloud Agents / Environment」若报地区模型不可用，可跳过；WorkBuddy 用 `CURSOR_DEV_MODEL=composer-2.5` 走 API 写码即可（以冒烟为准）。

### 3.4 就绪检查（上线闸门）

```bash
cd simplified-workbuddy
python3 scripts/check_cursor_dev_ready.py
# 或: make check-cursor-dev
```

全部硬性 `OK` 再对业务开放。脚本会打印工作分支、`AUTO_PR`、Token 是否配置。失败项按脚本提示处理（缺 Key / 空仓 / 白名单等）。

可选：登录后请求 `GET /api/cursor-dev/status`，查看 `readiness` 字段。

### 3.5 冒烟（推荐）

对白名单仓跑一次极小改动（README 加一行）。WorkBuddy 确认写码成功且 GitHub **工作分支**出现新 commit（如 `hebo`，而非 `main`），即视为 **Cursor↔GitHub 已通**。

默认 `AUTO_PR=0` 时不应自动出现 PR；过程结束后对话内会给出「合入 main」指引（compare / 开 PR 链接）。

本地无 LLM 旁路冒烟（不依赖真实 Cursor 配额时可用 mock/脚本）：

```bash
make smoke-cursor-dev
```

---

## 4. 同事开箱怎么用

1. 打开公司 WorkBuddy 地址（由运维提供）
2. ERP 账号登录
3. 在主对话说明要开发的功能 → 勾选确认 → **确认并开始写码**
4. 看过程面板与结果；按「合入 main」卡片在浏览器完成人工合入

**不要**让同事做：

- 注册/登录 Cursor 网页去连 GitHub  
- 自己申请 `CURSOR_API_KEY`  
- 在本机配置 Integrations / Cloud Agents  

若写码报「未授权 / 校验分支失败」，找 **管理员** 查 Team 授权与白名单仓，而不是让同事重配 Cursor。

---

## 5. 故障分工

| 现象 | 谁处理 | 方向 |
|------|--------|------|
| 写码车道不可用 / Key 未配置 | 管理员 | `.env` / 重启 API |
| verify branch，但 GitHub 网页正常 | 管理员 | Integrations Reconnect；确认 Key 属已授权 Team；App 覆盖该仓；核对 `WORK_BRANCH`/`STARTING_REF` 是否存在 |
| 空仓 / 无默认分支 | 管理员或仓负责人 | 先 push 初始 commit |
| 误开了 PR | 管理员 | 确认 `AUTO_PR=0`；有 Token 时服务会尝试自动关闭误开 PR |
| `resource_exhausted` | 管理员 | Usage 配额、停掉卡住的 Cloud 任务、降并发 |
| 需求不清 / 选错仓 | 同事 + 对话澄清 | 产品内完成，无需改 Git 授权 |

---

## 6. 安全提醒

- Key / Token 只放服务端与密钥管理，不进前端、不进聊天、不进 Git  
- 生产务必配置仓库白名单；禁止直推 `main`（改动落在工作分支）  
- 合入仍须人工审核（一期不做自动 merge）

---

## 7. 相关文档

- [`Cursor写码车道原理与完整流程.md`](Cursor写码车道原理与完整流程.md)  
- [`Cursor-SDK研发写码一期方案.md`](Cursor-SDK研发写码一期方案.md)  
- [`Cursor-SDK研发写码每日实施清单.md`](Cursor-SDK研发写码每日实施清单.md)  
