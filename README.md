# WorkBuddy MES Monorepo

PCB MES 自然语言运维助手：**Agent 核心 + API + Web** 统一在一个仓库维护。

## 架构

```text
simplified-workbuddy/          ← 仓库根（唯一维护入口）
├── apps/
│   ├── agent/                 # Agent / 工具 / 实体目录 entities.json
│   ├── api/                   # FastAPI（默认 8765）
│   └── web/                   # Vue + Vite（默认 5180）
├── data/                      # 运行时数据（历史、上传、转换、导出）
├── scripts/dev.sh             # 本地一键启动
├── scripts/stop.sh
├── docker-compose.yml         # 容器编排（预发/运维）
├── Makefile
└── .env                       # 统一环境变量（勿提交密钥）
```

| 服务 | 端口 | 说明 |
|------|------|------|
| Web | 5180 | 前端，`/api` 代理到 API |
| API | 8765 | 对话 / 历史 / 上传 / 转换 / 写确认 / 审计 |
| 探活沙箱 | 8001 | `dev.sh` 启动；**探活请求**打这里（不是用户文档入口） |
| ERP 文档 | 8000 | 用户通常给的 docs（建目录）；生产/联调平台 |

## 快速开始（日常开发）

```bash
# 1. 依赖（首次）
pip install -r requirements.txt
cd apps/web && npm install && cd ../..

# 2. 配置
cp .env.example .env   # 填入 DEEPSEEK_API_KEY / USE_ERP 等

# 3. 一键启动 沙箱(8001) + API + Web
./scripts/dev.sh
# 或: make dev

# 浏览器打开 http://127.0.0.1:5180
# 对话示例：「根据 http://127.0.0.1:8000/docs 测试文档接口」
# （目录来自 8000；探活自动打沙箱 8001，不改生产）
# 停止: ./scripts/stop.sh
```

仅 CLI Agent：

```bash
python3 apps/agent/run.py cli
# 或根入口: python3 run.py cli
```

## 运维 / 部署

```bash
# 容器方式（需 Docker）
docker compose up --build -d

# 健康检查
curl http://127.0.0.1:8765/health
```

生产建议：
- API / Web **分进程或分容器**部署（compose 已拆分）
- ERP 作为外部依赖，用环境变量 `PLATFORM_BASE_URL` 指向
- 密钥只放在环境变量 / 密钥管理，不要写进镜像

## 日常改哪里

| 需求 | 改动位置 | 是否重启 |
|------|----------|----------|
| 加查询实体 / 别名 | `apps/agent/tools/query_tool/entities.json` | 重启 API（`./scripts/stop.sh && ./scripts/dev.sh`） |
| Agent 提示词规则 | `apps/agent/tools/query_tool/entity_catalog.py` | 同上 |
| **新增业务 Skill** | `apps/agent/skills/<name>/SKILL.md` | 同上（详见 Skills 指南） |
| **自定义 Middleware** | `apps/agent/middleware/` | 同上（详见 Middleware 指南） |
| HTTP 接口 | `apps/api/routes/*` | 开发模式 API 支持 reload |
| 前端 UI | `apps/web/src/*` | Vite 热更新 |

更细的查询工具说明见 [`docs/平台查询工具维护笔记.md`](docs/平台查询工具维护笔记.md)。  
**Deep Agents Skills**（以后扩功能主方式）见 [`docs/DeepAgents-Skills使用指南.md`](docs/DeepAgents-Skills使用指南.md)。  
**Middleware**（审计/硬拦截等横切逻辑）见 [`docs/DeepAgents-Middleware使用指南.md`](docs/DeepAgents-Middleware使用指南.md)。  
**第一阶段开发复盘**见 [`docs/第一阶段开发复盘.md`](docs/第一阶段开发复盘.md)。  
**第二阶段产品方向（已锁定）**见 [`docs/第二阶段产品方向.md`](docs/第二阶段产品方向.md)。  
**第二阶段开发计划（M1～M4）**见 [`docs/第二阶段开发计划.md`](docs/第二阶段开发计划.md)。  
**ERP 登录对接**见 [`docs/ERP登录对接说明.md`](docs/ERP登录对接说明.md)。  
**M2 写操作确认（HITL）**见 [`docs/M2写操作确认交付说明.md`](docs/M2写操作确认交付说明.md)。  
**第二阶段开发复盘**见 [`docs/第二阶段开发复盘.md`](docs/第二阶段开发复盘.md)。  
**表结构→业务能力分析**见 [`docs/表结构业务能力分析说明.md`](docs/表结构业务能力分析说明.md)。

## 从旧 mes-client 迁移说明

原独立目录 `mes-client/` 已并入本仓 `apps/api` + `apps/web`，请勿再启动旧路径下的服务，避免端口与代码版本不一致。
