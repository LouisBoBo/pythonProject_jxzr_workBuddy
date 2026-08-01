# ERP 登录对接说明

使用前须用**真实 ERP 账号**登录。账号数据来自公司平台，登录接口为：

`POST {PLATFORM_BASE_URL}/api/v1/auth/login`

## 流程

1. 打开 Web（默认 http://127.0.0.1:5180）→ 未登录跳转 `/login`
2. 前端调用本服务 `POST /api/auth/login`（账号 / 密码 / 企业编码，登录页下拉选择）
3. API 转发到 ERP `/api/v1/auth/login`，拿到 `access_token`
4. 前端本地保存 token + 用户名；后续对话 / 历史 / 上传带  
   `Authorization: Bearer <token>` 与 `X-User-Name: <username>`
5. Agent 调 ERP 时优先使用该用户 token（不再依赖环境变量服务账号）

## 联调账号（本地 ERP 示例）

以当前联调环境实测可用（以你们环境为准）：

- 用户名：`admin`
- 密码：`admin123`
- 企业编码：可留空（登录页下拉仅展示企业名；未配置真实 `code` 时仍按空编码提交，与改前一致）

## 开关

| 变量 | 默认 | 说明 |
|------|------|------|
| `AUTH_REQUIRED` | `true` | `false` 时跳过登录校验（仅建议本地 Mock） |
| `PLATFORM_BASE_URL` | `http://localhost:8000` | ERP 根地址 |

## 相关代码

- API：`apps/api/routes/auth.py`
- Web：`apps/web/src/views/LoginView.vue`、`auth.js`、`router.js`
- ERP token 透传：`apps/agent/tools/platform_api.py`（`set_request_erp_token`）

从 MES 页带 token 打开助手（iframe / 新开页）：见 [`平台嵌入说明.md`](./平台嵌入说明.md)。
