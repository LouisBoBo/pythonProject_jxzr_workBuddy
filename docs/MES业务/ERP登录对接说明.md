# WorkBuddy 登录对接说明

使用前须登录 **ZR WorkBuddy**。这是助手产品自己的登录，**与「系统配置 → MES 接入」上传的接口文档无关**。

上传 OpenAPI 只用来生成可查对象（查哪些 MES 列表、走哪条业务 API），不会改登录页、也不会改 `POST /api/auth/login` 的目标。

前端登录入口：

`POST {WorkBuddy API}/api/auth/login`

服务端再向 WorkBuddy 登录后端（设置里的平台访问地址，连不上则探活沙箱）转发：

`POST {PLATFORM_BASE_URL}/api/v1/auth/login`

## 流程

1. 打开 Web（默认 http://127.0.0.1:5180）→ 未登录跳转 `/login`
2. 前端调用本服务 `POST /api/auth/login`（账号 / 密码 / 企业编码，登录页下拉选择）
3. API 走 WorkBuddy 登录路径拿到 `access_token`（**不读取** MES 资料包里的 `login_paths`）
4. 前端本地保存 token + 用户名；后续对话 / 历史 / 上传带  
   `Authorization: Bearer <token>` 与 `X-User-Name: <username>`
5. 查 MES 数据时，用「系统配置 → MES 接入」里的 **MES 接口账号** 向业务系统换 JWT，再调资料包里的列表接口。不要把 WorkBuddy 登录 token 发给 MES。

## 联调账号（本地示例）

以当前联调环境实测可用（以你们环境为准）：

- 用户名：`admin`
- 密码：`admin123`
- 企业编码：可留空（登录页下拉仅展示企业名；未配置真实 `code` 时仍按空编码提交，与改前一致）

## 开关

| 变量 | 默认 | 说明 |
|------|------|------|
| `AUTH_REQUIRED` | `true` | `false` 时跳过登录校验（仅建议本地 Mock） |
| `PLATFORM_BASE_URL` | `http://localhost:8000` | WorkBuddy 登录后端根地址（不是上传的 MES `/docs`） |
| `API_PROBE_SANDBOX_URL` | `http://127.0.0.1:8001`（`dev.sh`） | 主地址连不上时，登录自动回落此沙箱 |

## 相关代码

- API：`apps/api/routes/auth.py`
- Web：`apps/web/src/views/LoginView.vue`、`auth.js`、`router.js`
- MES 查数：`apps/agent/tools/platform_api.py`（与登录接口分离；实体 path 来自资料包）

从 MES 页带 token 打开助手（iframe / 新开页）：见 [`平台嵌入说明.md`](平台嵌入说明.md)。
