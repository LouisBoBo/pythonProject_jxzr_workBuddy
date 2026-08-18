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

# API 健康分析无 LLM 冒烟（日志必跑；探活需 8081+8001）
make smoke-api-health
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
| 加查询实体 / 别名 | 「MES 接入」上传接口文档，或改资料包 `entities.json` | 上传后自动重载；改文件可重启 API |
| Agent 提示词规则 | `apps/agent/tools/query_tool/entity_catalog.py` | 同上 |
| **新增业务 Skill** | `apps/agent/skills/<name>/SKILL.md` | 同上（详见 Skills 指南） |
| **自定义 Middleware** | `apps/agent/middleware/` | 同上（详见 Middleware 指南） |
| HTTP 接口 | `apps/api/routes/*` | 开发模式 API 支持 reload |
| 前端 UI | `apps/web/src/*` | Vite 热更新 |

文档已按类别归档，完整索引见 [`docs/README.md`](docs/README.md)。

常用入口：

- [功能清单与测试用例](docs/总览/功能清单与测试用例.md)（新增功能须同步更新）
- [第二阶段产品方向](docs/产品规划/第二阶段产品方向.md) · [MES 四块能力方案](docs/总览/MES懂行助手四块能力方案.md)
- [Skills](docs/Agent开发/DeepAgents-Skills使用指南.md) · [Middleware](docs/Agent开发/DeepAgents-Middleware使用指南.md) · [查询工具维护](docs/MES业务/平台查询工具维护笔记.md)
- [桌面安装说明](docs/桌面与部署/桌面端安装与配置说明.md) · [写码管理员清单](docs/写码与审码/Cursor写码车道管理员上线清单.md)

写码上线闸门：`make check-cursor-dev`；旁路冒烟：`make smoke-cursor-dev`。

## 从旧 mes-client 迁移说明

原独立目录 `mes-client/` 已并入本仓 `apps/api` + `apps/web`，请勿再启动旧路径下的服务，避免端口与代码版本不一致。
