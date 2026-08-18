# WorkBuddy Bridge（VS Code）v0.4.4

## 日常用法（推荐，接近一劳永逸）

1. **安装一次**：`make package-vscode-bridge` → 安装 `dist/*.vsix` → Reload Window
2. **配对一次**：网页侧栏「配对 VS Code」→ VS Code `WorkBuddy: Pair` 输入 6 位码
3. 之后：**开机自动 Connect**。网页 JWT 过期也不用再配对（长期凭证默认约 **90 天**）
4. 到期 / 换电脑 / 凭证失效：再 Pair 一次即可

## 和「每次贴 token」的区别

| | 旧方式 | 现在 |
|--|--------|------|
| 凭证 | 网页登录 JWT（很快过期） | Bridge 长期凭证 `wb1.…` |
| 频率 | 几乎每次过期都要重配 | 约 90 天一次 |
| 操作 | 翻设置 / 手贴 | 网页点一下 + 输 6 位码 |

## 能力

- 诊断 + 本地规则 + `file_contents` 回传；MCP 默认关
- Bridge 离线可用 `request_git_review` 审本机目录 / Git 仓
- **安全**：任务 `workspace_root` 仅限当前打开/最近工程；拒绝路径穿越与 `.env`/密钥类文件

新人接入见仓库 `docs/写码与审码/IDE代码审核开发者接入手册.md`。
