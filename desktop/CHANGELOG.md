# ZR WorkBuddy 桌面版更新记录

版本号以 `desktop/package.json` 的 `version` 为准；安装包文件名形如 `ZR WorkBuddy-x.y.z.dmg`。

## 0.1.10 — 2026-08-21

- 分析 M1：页内汇总强制 caveat；可选服务端聚合（路径/方法消毒）；日/周趋势折线
- 分析 M2：PCB 指标包扩展 + 江西口径模板；运营看板六卡对齐（工序在制报表、设备产量）
- 对话：图表/看板等正文流式结束后再展示，避免图先出、说明还在打字
- 安全：聚合接口仅 GET/POST，query 参数名消毒

## 0.1.9 — 2026-08-20

- 流式输出：表格生成中用等宽预排，结束后再成表，避免界面上下闪烁跳动
- 滚底节流：仅接近底部时跟随，减轻长表流式时的抖动

## 0.1.8 — 2026-08-20

- 能力块 B：对话出图（ECharts）+ PCB 运营看板（KPI 顶栏、深色皮肤、点图下钻）
- 演示编排：「打开 PCB 运营看板」；枚举中文展示（待开工/进行中等）
- 查数口径：filters 数组正确下发；默认 limit 50；紧急未完工条数自洽
- 资料包：每日打开自动同步；会话切换后图表/看板可恢复；正文流式输出修复

## 0.1.7 — 2026-08-19

- 重打包：纳入 0.1.6 晚间安全修复（路径穿越防护、safe_http loopback 校验、entities 原子写入）
- 实体合并：同 path 保留旧 id、补充 columns 字段

## 0.1.6 — 2026-08-19

- 写码成功后自动同步 MES 资料包（OpenAPI → entities.json，模型 → schema.md 增量）
- 新增 `refresh_mes_profile_from_runtime`：从运行中本机 MES 合并刷新可查对象
- 查数别名更智能：「库存列表」优先明细接口，降低看板汇总误匹配

## 0.1.5 — 2026-08-19

- 修复 Git 代码审核分批读源码崩溃（`_trim_file_contents` 误用 `None` 与整数比较）

## 0.1.4 — 2026-08-19

- 收敛 token：审核/写码系统提示与强制路由块瘦身，审核批源码默认 64KB 上限
- 本机写码强制 Cursor SDK；LLM 工具环需 `LOCAL_DEV_ALLOW_LLM_FALLBACK=1` 才可用
- 桌面查数自动走真实 MES（0.1.2）+ 查数工具返回瘦身（0.1.3 内容一并包含）

## 0.1.3 — 2026-08-19

- 查数工具返回瘦身：`list_platform_entities` 不再 N+1 打 MES；查数结果省略重复 raw records
- 系统提示词实体目录默认紧凑一行式（可 `SYSTEM_PROMPT_COMPACT_CATALOG=false` 恢复）
- 本机写码 LLM 回退路径工具结果截断（默认仍走 Cursor SDK）

## 0.1.2 — 2026-08-19

- 修复桌面版查数始终走 Mock 客户端、有 MES 资料包仍返回 0 条的问题
- 已配置资料包且解析出 api_base 时自动连接真实 MES/ERP（不依赖 `.env` 的 `USE_ERP`）

## 0.1.1 — 2026-08-19

- 本机写码默认 Cursor SDK Local Agent（沙箱 cwd + 同步闸门）
- 查数过程区中文表；当日完工缺筛参时诚实降级
- 系统配置文案统一为 MES / ERP
- 沙箱符号链接防护与同步字节上限
- `describe_entity` 兼容 list 项为字符串的接口

## 0.1.0 — 2026-08-17

- 首版 Mac 安装包：内嵌 CPython + API + 前端 dist
- 安装后在系统配置填写 Key / MES·ERP，无需本机 Python
