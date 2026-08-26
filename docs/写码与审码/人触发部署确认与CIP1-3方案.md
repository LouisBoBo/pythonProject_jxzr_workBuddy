# 人触发部署确认与 CI（P1-3）

> 状态：**P1-3a/b/c 已落地 · 2026-08-25**（确认卡 + workflow_dispatch + 状态轮询；默认关；P1-2 **跳过**）  
> 产品名：对外统一 **ZR WorkBuddy**  
> 依据：选型分析 §4.9 / §9「确认卡 → API → CI」；与 [`写码后审码门禁与自动提交P1方案.md`](写码后审码门禁与自动提交P1方案.md)（P1-1）同构  
> 关联：[`本机目录写码与沙箱隔离方案.md`](本机目录写码与沙箱隔离方案.md)、[`选型落地P0清单.md`](../Agent开发/选型落地P0清单.md)

---

## 大白话（实现前必读）

### 自动部署到底是什么？

**不是** WorkBuddy 自己悄悄把你电脑上的文件拷到服务器。  
**是**：你说一句「部署到预发」→ 弹出确认卡 → 你点确认 → WorkBuddy **按一下仓库里已经配好的「发布按钮」（CI）** → 由 CI 去打包、去更新服务器。

可以想成：

| 角色 | 干什么（生活类比） |
|------|-------------------|
| **你** | 下单：「把这版发到预发」 |
| **WorkBuddy** | 收银员：核对订单、让你确认、替你点「开始发货」 |
| **CI（如 GitHub Actions）** | 仓库里的流水线工人：取货（拉代码）、装箱（打包）、送到店（更新服务器） |
| **预发/生产服务器** | 店铺：真正跑网站/服务的那台机器 |

所以产品里的「自动部署」= **对话里一键触发已有发布流水线**，不是从零发明一套运维系统。

### CI 是什么？是在 GitHub 里吗？

**CI** = Continuous Integration（持续集成），大白话就是：**仓库边上的一台「自动工人」**。

你把代码推到 GitHub 之后，可以事先写好一份说明书（workflow）：  
「一接到通知，就自动：拉代码 → 打包 →（可选）部署到某台服务器」。  
这份说明书跑起来，就叫一次 CI / 流水线。

| 问题 | 答 |
|------|-----|
| CI 是不是 GitHub？ | **不完全是。** GitHub 是放代码的地方；**GitHub Actions** 是 GitHub 自带的一种 CI。 |
| 必须用 GitHub 吗？ | 第一刀方案建议用 **GitHub Actions**（很多项目已经在用）。也有 GitLab CI、Jenkins 等，以后可接，先不铺开。 |
| CI 跑在哪？ | 一般在 **云上的临时机器**（GitHub 提供的 runner），不是跑在你笔记本上，也不是跑在 WorkBuddy 对话框里。 |
| WorkBuddy 和 CI 啥关系？ | WorkBuddy **不自己当 CI**；人确认后，去 **通知** GitHub：「请跑那个部署 workflow」。 |

所以：代码在 GitHub；**打包/部署的自动化**往往也配在同一个 GitHub 仓库的 Actions 里——容易让人觉得「CI 就是 GitHub」，其实是 **GitHub 仓库 + Actions 流水线** 两件事。

### 问3：Workflow 文件名从哪来？没有怎么办？

系统配置里的 **Workflow 文件名** = 目标仓 `.github/workflows/` 目录下的 **yml 文件名**（例如 `deploy-staging.yml`）。

- **有现成部署流水线**：打开目标仓 → Code → `.github/workflows/` → 看文件名，填进系统配置。  
- **只有 Dependabot / update-graph 之类**：那些**不是**部署流水线，不要填。  
- **什么都没有 / 还是占位 exit 0**：拷贝本仓库示例  
  [`示例-deploy-staging.yml`](示例-deploy-staging.yml)  
  （已按 `pythonProject_zr_aicoding`：Vite 前端构建 + FastAPI 后端 + SSH/rsync）  
  到目标仓路径：`.github/workflows/deploy-staging.yml`，并配置 Secrets（见该文件头注释）。

GitHub 暂时打不开时：先在本机准备好该文件内容；网络恢复后一次性提交到目标仓即可。

### 问1：打包的是本地项目，还是远程仓库？

**答：打包远程仓库里「已经推上去」的那一版。**

分两步想：

1. **你电脑上的目录** = 草稿本。改代码、预览都在这里。草稿可以很乱、还没保存到公司仓库。  
2. **Git 远程仓库（GitHub 等）** = 正式存档。只有 push 上去的版本，别人才拿得到、CI 才能打包装箱。

因此：

- 要部署 → 一般先 **提交并推送**（P1-1 已做的事）  
- CI 去远程仓库 **拉某一分支/某次提交** → 在 CI 机器上打包  
- **不会**把你笔记本上「还没推送」的临时文件直接当上线包（否则别人服务器上跑的和仓库对不上，也没法追溯）

一句话：**改在本地，发版看远程已推送的版本。**

### 问2：发布是不是要提供服务器？怎么配？

**答：要有一台（或一套）「能跑这套系统的预发/生产环境」，但通常不是 WorkBuddy 给你新买一台云主机。**

- **服务器 / 预发环境**：客户或你们运维本来就有（或单独准备一台预发机）。上面装好运行所需的东西（Docker、Nginx、K8s 等——按项目现有方式，本方案不规定死）。  
- **怎么让「一键部署」连得上这台机**：不写在聊天里，写在 **CI 配置 + 密钥** 里，例如：  
  - 仓库里有一个发布脚本/workflow（如「部署到预发」）  
  - 密钥（SSH、镜像仓库密码等）放在 CI 的 Secrets，只有流水线能用  
  - WorkBuddy 只保存：开没开部署、允许发到哪些环境（默认只有预发）、触发哪个 workflow

WorkBuddy **不负责**：在对话里教 AI 登录服务器敲命令。

### 问2b：部署到腾讯云怎么配？（实操清单）

**答：用腾讯云轻量应用服务器 / CVM 当预发机，走「GitHub Actions → SSH/rsync → 公网 IP」**（见 [`示例-deploy-staging.yml`](示例-deploy-staging.yml)）。  
不走腾讯云 CODING / SCF 等另一套流水线；第一刀统一用 **GitHub Actions 推到云主机**。  
WorkBuddy **只负责**：人确认之后触发那条已配好的流水线；**不负责**在对话里代登录服务器敲命令。

以下以 **轻量应用服务器 + 宝塔面板**、业务仓 `LouisBoBo/pythonProject_zr_aicoding`（Vite 前端 + FastAPI 后端）为参照；换项目时只改路径与 Secrets 值。

#### 总览

| 谁 | 存什么 |
|----|--------|
| **本机 Mac** | SSH **私钥**（`~/.ssh/tc_staging_deploy`） |
| **腾讯云服务器** | 对应 **公钥**（`~/.ssh/authorized_keys`）+ 站点目录 |
| **GitHub Secrets** | 私钥全文 + 公网 IP + SSH 用户 + 远端路径 |
| **目标仓 workflow** | `.github/workflows/deploy-staging.yml`（由示例拷贝） |
| **WorkBuddy 系统配置** | 开自动化部署、仓库名、Workflow 文件名、Token |

#### 步骤 1：记下公网 IP 与防火墙（必做，否则 Actions 必挂）

1. 腾讯云控制台 → 轻量应用服务器 / CVM → 实例详情 → **IPv4 地址**（例：`175.178.238.31`）。  
2. **防火墙 / 安全组**放行入站：**TCP 22**，来源填 **`0.0.0.0/0`（全部）**——不能只放行你自己的办公网 IP。  
   GitHub Actions runner 在国外，IP 不固定；本机 SSH 通 **不能** 说明 Actions 能通。  
3. 业务端口 **80/443** 按需放行；若装了宝塔：宝塔「安全」里同样放行 **22**。  
4. 用任意「在线端口检测」查 `公网IP:22`，须显示**开放**后再点部署。

#### 步骤 2：本机生成密钥对（私钥在 Mac，不在网页）

私钥**不会**在腾讯云控制台长期展示；需本机生成（或创建密钥对时**仅一次**下载的 `.pem`）。

```bash
# 在 Mac 终端
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/tc_staging_deploy
```

- 生成后：`~/.ssh/tc_staging_deploy` = **私钥**；`~/.ssh/tc_staging_deploy.pub` = **公钥**。  
- **公钥**开头：`ssh-ed25519 AAAA...`（或 `ssh-rsa ...`）→ 只给服务器。  
- **私钥**开头：`-----BEGIN OPENSSH PRIVATE KEY-----` → 只给 GitHub Secret `STAGING_SSH_KEY`。  
- **不要**把 `ssh-ed25519`/`ssh-rsa` 那一行当成私钥填进 Secret。

**给 CI 用必须去掉私钥密码**（Actions 无法交互输入 passphrase）：

```bash
ssh-keygen -p -f ~/.ssh/tc_staging_deploy
# 输入旧密码后，新密码两次直接回车（置空）
```

#### 步骤 3：把公钥写入服务器（常见踩坑）

在服务器上（`root` 或 `ubuntu`）执行时：必须粘贴 **Mac 上 `cat ~/.ssh/tc_staging_deploy.pub` 打出来的整行**，  
**禁止**写成 `echo 'cat ~/.ssh/...'`（那会把字面命令写进文件，密钥无效）。

```bash
# 在服务器上
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo '粘贴Mac上.pub的整行' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

本机验证（应不再要密码；用户按实际能登录的为准，宝塔/OpenCloudOS 常见 `root`）：

```bash
ssh -i ~/.ssh/tc_staging_deploy root@公网IP
```

#### 步骤 4：服务器建站点目录（宝塔路径）

即使宝塔里还没「添加网站」，也先建目录，供 rsync 写入：

```bash
# 在服务器上
mkdir -p /www/wwwroot/zr-aicoding/frontend/dist
mkdir -p /www/wwwroot/zr-aicoding/backend
ls -la /www/wwwroot/zr-aicoding
```

| 路径 | 用途 |
|------|------|
| `/www/wwwroot/zr-aicoding` | = Secret `STAGING_APP_PATH` |
| `.../frontend/dist` | Vite 构建产物 |
| `.../backend` | FastAPI 代码（不含 venv） |

可选：宝塔 → 网站 → 添加站点，根目录指到 `.../frontend/dist`，方便用 80 看前端。  
`STAGING_RESTART_CMD` 可先空；后端用 Supervisor/systemd 跑起来后再填重启命令。

#### 步骤 5：GitHub Secrets（目标业务仓）

路径：目标仓 → **Settings** → **Secrets and variables** → **Actions**。

| Secret | 示例值 | 说明 |
|--------|--------|------|
| `STAGING_SSH_HOST` | `175.178.238.31` | 公网 IP 或域名 |
| `STAGING_SSH_USER` | `root` | 与 `ssh -i` 能登录的用户一致 |
| `STAGING_SSH_KEY` | （私钥全文） | `cat ~/.ssh/tc_staging_deploy`，含 BEGIN/END；勿提交 git、勿发聊天 |
| `STAGING_APP_PATH` | `/www/wwwroot/zr-aicoding` | 远端工程根 |
| `STAGING_RESTART_CMD` | （可选） | 如 `sudo supervisorctl restart zr-aicoding-api` |

#### 步骤 6：Workflow + WorkBuddy

1. 将 [`示例-deploy-staging.yml`](示例-deploy-staging.yml) 拷到目标仓 `.github/workflows/deploy-staging.yml` 并推送（分支需与 WorkBuddy 触发 ref 一致，如 `hebo`）。  
2. WorkBuddy → **系统配置 → 自动化部署**：开启；填仓库、`deploy-staging.yml`、GitHub Token。  
3. 对话说「部署到预发」→ 确认卡 → 等 Actions；失败看对应 job 日志（缺 Secret / SSH 被拒 / 构建失败）。

#### 自检清单

- [ ] 本机 `ssh -i ~/.ssh/tc_staging_deploy 用户@公网IP` 免密成功  
- [ ] 私钥无 passphrase（或 CI 无法使用）  
- [ ] **腾讯云防火墙 + 宝塔安全：TCP 22 来源 `0.0.0.0/0`（本机通 ≠ Actions 通；国外端口检测须显示 22 开放）**  
- [ ] 服务器存在 `$STAGING_APP_PATH/{frontend/dist,backend}`  
- [ ] 四个必填 Secrets 已配（重启命令可暂空）  
- [ ] 目标仓已有真实构建的 `deploy-staging.yml`（非 `exit 0` 占位；部署步骤不跑阻断性 pytest）  
- [ ] WorkBuddy 自动化部署已开  

> **实测踩坑（2026-08-25）**：本机 SSH 正常、Secrets 齐全，Actions 仍在 `Deploy via SSH` 报「无法连接 :22」。
> 境外检测 22/80/443 均超时，且机房出网也访问不了 github.com —— 属**国内机 ↔ 境外双向不通**，不是密钥问题。
> **旁路**：系统配置将 `DEPLOY_CI_PROVIDER` 设为 `local_ssh`，填本机私钥路径与项目路径；确认后由 WorkBuddy API 在本机构建并 rsync（不经 Actions，不经模型）。默认仍为 `github_actions`，其它功能不受影响。
> 外部端口检测 `公网IP:22` 为关闭 → 轻量防火墙未对全世界放行 22，GitHub 国外 runner 连不上。放行后再部署即可。

### 和「装 ZR WorkBuddy 自己」不是一回事

| | 含义 |
|--|------|
| 桌面 dmg / 网页部署手册 | 把 **WorkBuddy 产品**装到用户电脑或机房 |
| 本方案 P1-3 | 用户用 WorkBuddy，去发布 **他正在改的那个业务项目**（ERP/MES 等） |

别混成一件事。

### 用户眼里的完整故事（最短版）

```text
1. 在本机改代码、看预览
2. 说「提交今天的代码」→ 审一下 → 确认 → 推到远程工作分支
3. 说「部署到预发」→ 确认卡（发哪、发哪一版）→ 点确认
4. 等几分钟，预发网站变成新版本；对话里能点开流水线看成功/失败
```

第 3～4 步才是 P1-3；第 1～2 步已有（写码 + P1-1）。

---

## 0. 边界（先读）

| 做 | 不做 |
|----|------|
| 人说话触发「部署 / 发布」 | 写码成功后自动部署 |
| 确认卡 → **API 直执** → 触发 **既有 CI/CD** | Agent / 模型 ssh、kubectl、docker 直改生产 |
| 默认仅 **预发 / 白名单环境** | 无人全自动「写码 → 测 → 合主干 → 生产」 |
| 独立意图 / API（类 `commit_batch`） | 塞进 MES 查数、全仓审码、写码 SSE 主环 |
| 部署对象 = **已推送的工作分支 / tag / commit** | 自动合入 `main` / `master` |

**纠偏**：P1-3 的「自动化部署」= **人确认后的流水线触发**，不是无人值守发布。

---

## 1. 目标流程

```text
前置（可选，不强制绑死本切片）
  本机/Cloud 改码 →（可选审码）→ P1-1 提交并推到工作分支
        ↓
用户：「部署到预发」/「发布这次改动」/「跑一下发布流水线」
        ↓
意图识别 deploy_batch（独立；不是 code_dev / code_review / commit_batch）
        ↓
门禁：可部署引用 + 环境白名单 +（可配）最近 CI/批审是否通过
        ↓
确认卡：环境 · ref（branch/tag/sha）· 风险摘要 · 流水线链接占位
  ├─ 取消 / 超时 → 结束（不触发）
  └─ 确认 → POST /api/.../deploy  （API 直执，不经模型）
        ↓
触发 CI/CD（workflow_dispatch / 仓库已有发布 API）
        ↓
状态回传：queued → running → succeeded | failed（+ run URL）
        ↓
（可选 P1-3b）部署后健康检查 / 查数验收 —— 复用运维·查数 Tools，不写进部署执行器
```

### 1.1 Happy / 边界 / 失败

| | 表现 |
|--|------|
| **Happy** | 用户触发 → 门禁过 → 确认 → CI 启动 → 卡/过程条显示 run 链接与终态 |
| **边界：无可部署 ref** | 说明「请先提交并推送工作分支 / 指定 tag」；不弹可确认的部署卡 |
| **边界：环境不在白名单** | 拒绝；列出允许环境 |
| **边界：生产环境** | 默认关闭；若开启须二次确认文案（P1-3c，可后置） |
| **失败：CI 触发失败** | API 报错；磁盘与 git 不变；可重试触发（幂等键见 §5） |
| **失败：流水线中失败** | 展示 failed + 日志链接；**不**由 Agent 自动回滚（回滚另开确认或运维手册） |

---

## 2. 路由隔离（硬约束）

与全仓审码、提交批审完全独立；可共用「确认卡 UI 积木」，**状态机与 API 必须分开**。

| 维度 | 全量审码 | 提交批审（P1-1） | **部署（P1-3）** |
|------|----------|-----------------|------------------|
| **触发** | 「审核这个工程」 | 「提交今天的代码」 | 「部署到预发 / 发布」 |
| **前端** | `workbuddy_lane=code_review` | `looksLikeLocalCommitBatch` → API | **`looksLikeDeploy` → API**（新建） |
| **后端** | Deep Agents + Skill | `POST .../commit-batch` | **`POST .../deploy`（新建）** |
| **范围** | 全仓分批 | 本批业务源码 | **一个 git ref + 一个环境** |
| **执行** | 读盘 / LLM 报告 | git commit/push | **触发 CI，不写宿主机业务树** |
| **输出** | 审核报告 | 提交确认卡 | **部署确认卡 + run 状态** |

**禁止**：

- 部署意图走进 `code_dev` 再写一轮码  
- 部署确认后由模型「再调一次 tool 就算发布」  
- 与 `commit_batch` 共用同一 job 状态机（避免提交卡与部署卡串台）  
- 在 MES / 查数对话里隐式触发生产部署  

```text
「审核工程」 → code_review → Deep Agents
「提交代码」 → commit_batch → local-dev commit API
「部署预发」 → deploy     → deploy API → CI
```

---

## 3. 部署对象从哪来

优先级（实现时按序）：

1. **用户显式指定**（确认卡选环境 + branch / tag / sha；消息里点名）  
2. **本会话最近一次成功的 commit_batch** 所推送的工作分支 + tip commit  
3. **工作区配置的默认工作分支**（`LOCAL_DEV_WORK_BRANCH` 等）在 remote 上的 tip —— 仅当 1、2 为空且 remote 可达  

**禁止**：无 ref 时默认部署 `main`；禁止「目录里未提交脏文件」直接当部署物。

---

## 4. 门禁（发布前）

| 检查 | 默认 | 说明 |
|------|------|------|
| 环境 ∈ 白名单 | **强制** | 如 `staging`；`production` 默认不在名单 |
| ref 存在于约定 remote | **强制** | 避免部署本地未推送 commit |
| 禁主干名 | **强制** | 不把「部署」做成「合 main」；合主干仍人工 / 另流程 |
| 最近批审无阻断 | **可配** | 与 P1-1 门禁结果关联；缺结果时可警告仍允许（预发） |
| 外部 CI 最近同 ref 已绿 | **可配** | 有则展示；无则跳过（不阻塞预发默认路径） |

有**强制项失败** → 确认卡主按钮禁用（与提交卡「有阻断不可提交」同构）。

---

## 5. 确认后执行（API 直执）

```text
awaiting_deploy
  ├─ confirm → create deploy_run（幂等 key）→ 调 CI trigger → status=queued
  ├─ cancel / timeout → skipped
  └─ retry（仅 trigger 失败或可重入的 CI）→ 同幂等策略
```

| 项 | 约定 |
|----|------|
| 执行者 | **FastAPI（或 local-dev 旁路服务）**，禁止模型 shell |
| CI 适配 | 第一刀只接 **一种**：如 GitHub `workflow_dispatch`（仓库 + workflow 文件 + ref + inputs） |
| 密钥 | 仅服务端；`GITHUB_TOKEN` / deploy token 不进前端、不进 Prompt |
| 幂等 | `deploy_run_id` 或 `(user, env, ref, workflow)` 短窗去重，防双击 |
| 超时 | 确认卡超时 = 取消；CI 等待另设轮询上限，超时标 `unknown` 并给 run URL |
| 回滚 | **本切片不做自动回滚**；卡上链到手册 /「申请回滚」占位（P1-3d） |

---

## 6. 配置（建议旋钮，实现时再进 `.env.example`）

| 变量 | 建议默认 | 含义 |
|------|----------|------|
| `DEPLOY_ENABLED` | `0` | 总开关；**推荐系统配置**，`.env` 兜底 |
| `DEPLOY_ENV_WHITELIST` | `staging` | 逗号分隔；生产须显式加入 |
| `DEPLOY_ALLOW_PRODUCTION` | `0` | `1` 才允许白名单含 production |
| `DEPLOY_CI_PROVIDER` | `github_actions` | `github_actions`（默认）或 `local_ssh`（本机构建+SSH 旁路；境外 CI 连不上国内机时用） |
| `DEPLOY_GITHUB_WORKFLOW` | 空 | workflow 文件名，如 `deploy-staging.yml` |
| `DEPLOY_GITHUB_REPO` | 空 | `owner/repo` |
| `DEPLOY_DEFAULT_REF` | 空 | 确认卡默认分支；也可回落工作分支配置 |
| `DEPLOY_GITHUB_TOKEN` | 空 | 触发 Actions；系统配置里加密存储 |
| `DEPLOY_REQUIRE_PUSHED_REF` | `1` | 必须 remote 可见 |
| `DEPLOY_CONFIRM_TIMEOUT_SEC` | `600` | 确认卡超时=取消 |
| `DEPLOY_POLL_TIMEOUT_SEC` | `1800` | 状态轮询上限 |

解析顺序与写码车道相同：**系统配置（settings.json）非空 → `.env` → 默认**。保存系统配置后热生效，不必改死 `.env`。

---

## 7. 与现有能力的关系

| 能力 | 关系 |
|------|------|
| P1-1 提交推送 | **常见前置**；部署默认吃「已推送工作分支」 |
| P1-2 Cloud PR | **跳过**；不依赖开 PR 才能部署预发 |
| 全仓审码 | 独立；部署门禁不跑全仓 `request_*_read_batch` |
| 运维 Playbook / 查数 | **验收可选复用**；不把部署 trigger 塞进 `run_ops_scene` |
| 桌面 / HA 部署文档 | 指 **WorkBuddy 自身**安装；与「用户项目经 CI 发布」不是同一件事 |

---

## 8. 切片（按序）

| 切片 | 内容 | 状态 |
|------|------|------|
| **P1-3a** | 方案 + `looksLikeDeploy` 互斥冒烟 + 配置契约 + `GET/POST .../deploy/*` 门禁探测（不触发 CI） | ✅ **已关闭**（2026-08-25） |
| **P1-3b** | 确认卡 UI + GitHub `workflow_dispatch`（仅 staging 白名单） | ✅ **已关闭**（2026-08-25；默认 `DEPLOY_ENABLED=0`） |
| **P1-3c** | 状态轮询 / 刷新 + run URL；GitHub 不可达可重试 | ✅ **已关闭**（2026-08-25；`POST /deploy/poll`） |
| **P1-3d** | 部署后健康检查 / 查数验收（可选） | ✅ **本机 SSH 探活已落地**（2026-08-26；`DEPLOY_HEALTH_URL`；查数验收仍可选） |
| **P1-3e** | 生产环境二次确认 + 变更窗（企业治理） | ⬜ 缓开 |

**收工标准（P1-3b+c）**：人说「部署到预发」→ 确认 → Actions 出现一次 run → 对话里能看到成功/失败链接；全程不改 MES/写码主环行为。

---

## 9. 风险与谨慎项

| 风险 | 对策 |
|------|------|
| 误伤写码 / 提交 | 独立 intent + 独立 API；单测互斥（仿 `smoke_chat_intent`） |
| Token 泄露进 LLM | trigger 只在 API；日志脱敏 |
| 双击重复发布 | 幂等 key + 确认卡单飞 |
| 把「部署」做成合主干 | 禁 main；文案与门禁双拦 |
| 范围膨胀 | 第一刀只 staging + 一种 CI；不做多云抽象 |

动手前自检（与仓库谨慎写码规则对齐）：

1. **Happy**：预发白名单 + 已推送 ref → 确认 → 一次 workflow  
2. **边界**：未推送 / 环境非法 / 总开关关闭  
3. **失败**：CI API 4xx/5xx → 用户可见错误，可重试，不落脏 git  

---

## 10. 变更日志

| 日期 | 说明 |
|------|------|
| 2026-08-25 | 首版方案建档；P1-2 跳过；**未实现代码** |
| 2026-08-25 | **P1-3a**：`looksLikeDeploy` 互斥 + `deploy_config`/`deploy/prepare`（`can_trigger_ci=false`）+ 冒烟；默认不发版 |
| 2026-08-25 | **P1-3b**：确认卡 + `POST /deploy/confirm` → `workflow_dispatch`（mock 单测；默认关） |
| 2026-08-25 | 部署旋钮进「系统配置」；settings.json 优先，`.env` 兜底 |
| 2026-08-25 | **P1-3c**：`POST /deploy/poll` + 确认卡轮询/刷新；GitHub 不可达不崩 |
| 2026-08-25 | 增加可拷贝示例 [`示例-deploy-staging.yml`](示例-deploy-staging.yml) |
| 2026-08-25 | 示例改为真实构建/SSH 部署（frontend npm build + backend rsync） |
| 2026-08-25 | 补充腾讯云 CVM（公网 IP + 安全组 22 + Secrets）配置说明 |
| 2026-08-25 | **问2b 扩写**：轻量+宝塔实操（密钥生成/公私钥区分/去 passphrase/authorized_keys 踩坑/站点目录/Secrets/自检） |
| 2026-08-25 | 根因：Actions SSH exit 255 = 腾讯云 22 未对公网开放；示例 workflow 加固探测+BatchMode；部署不再跑 pytest |
| 2026-08-25 | **本机 SSH 旁路**：`DEPLOY_CI_PROVIDER=local_ssh`（临时 worktree 构建 + rsync）；默认仍 `github_actions`，写码/审码/提交批不变 |
| 2026-08-26 | **P1-3d 探活**：`DEPLOY_HEALTH_URL` + 重试；预发 ERP `systemd`（8009）与 80/8000 隔离；确认卡展示探活 |
