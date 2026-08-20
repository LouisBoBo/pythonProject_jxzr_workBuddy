---
name: ops-query-playbook
description: >-
  运维值班 playbook：紧急/在制堆积、按状态汇总、导出清单、接口沙箱探活指引、
  谁导入了/写失败审计、登录与 MES 鉴权引导。实体一律以当前资料包目录为准。
  用户说「紧急」「异常堆积」「在制」「谁导入了」「接口通不通」「401」「查不到数据」「值班简报」时启用。
---

# 运维值班 Playbook

## 先列场景

```
list_ops_scenes()
run_ops_scene(scene="<id或中文>", export=false|true)
```

**禁止**写死某一套 MES 的实体 id。目录空则引导系统配置。

## 标准场景 → 工具

| 用户说法（例） | scene | 行为 |
|----------------|-------|------|
| 紧急工单 / 急单堆积 / 紧急单 | `urgent-backlog` | **必须**走紧急未完工口径（urgent+high 且未完工）。禁止只用 `priority=urgent` |
| 在制有多少 | `wip-snapshot` | 在制口径 + 可选导出 |
| 未完工 | `unfinished-snapshot` | 未完工口径 |
| 按状态各多少 | `status-breakdown` | `summarize_platform_data` |
| 导出清单 | `export-list` 或 scene+`export=true` | 绝对路径 + 行数 |
| 接口通不通 / 探活 | `api-health-sandbox` | **默认沙箱**；勿 live；与查数通不通区分 |
| 谁导入了 / 谁写过 | `write-audit-who` | `query_write_audit`（近 30 天） |
| 导入失败 | `write-audit-failed` | `event=write_failed`；重试须确认卡 |
| 401 / Token / MES 账号 | `login-mes-auth-help` | 区分 WorkBuddy 登录 vs MES 接口账号 |
| 没有可查对象 | `catalog-empty-help` | 引导 MES 接入 |
| 查不到数据 / 故障排查 | `ops-diagnose` | 只读就绪状态+日志分支，不写 MES |
| 值班简报 / 产线日报 | `ops-daily-brief` | 口径摘要 + 主对象状态/优先级分布（`markdown_report`）；绑不上则跳过 |
| 产线异常日报（PCB） | `plant-exception-daily` | 日报套版；可含 `chart` / `markdown_fence`，前端出图 |
| 分析概况 / 异常分布 | （也可）`analyze_platform_brief` | 轻量分析简报，非 SQL |

也可直接用 `query_metric("紧急未完工")` / `query_write_audit` / `analyze-api-health` 六步。与场景等价时 **优先 `run_ops_scene`**。

紧急链：`run_ops_scene('urgent-backlog')` 后若用户要留档，再 `export=true`（工具会提示 next_actions）。

**禁止**：把「紧急工单」理解成只筛 `priority=urgent`。用户未说「只要 urgent 这一档」时，一律用紧急未完工口径。

## 硬性约定

1. **写操作**：改状态/导入必须确认卡；未确认零写入；不要默写。
2. **探活**：`probe_api_catalog` 默认 `sandbox`；仅用户明确要求生产只读时才 `live`。
3. **鉴权**：不回显密码；不把 WorkBuddy token 当 MES token。
4. **换平台**：先 `inspect_mes_profile(user_intent=原话)` 重学当前目录；`missing` 挡住则请用户补配置，不要用上一套 MES 的场景结论。

## 回复结构

1. 场景名 + definition  
2. 清单表 / 分组表 / 审计表  
3. 有导出则报 `file` + `rows`  
4. 探活场景先讲清「沙箱 vs 查数 vs 生产」  

## 自检

- [ ] 用了当前目录实体，未套其它 MES id  
- [ ] 「紧急工单」走了紧急未完工口径（urgent+high 且未完工），未只用 `priority=urgent`  
- [ ] 筛选用了 API filters / 口径 filter_sets  
- [ ] 写操作未跳过确认  
- [ ] 探活未默认 live  
- [ ] 审计说明了时间窗与数据来源（助手审计）
