# MES 摸底固定话术（A 验收）

用于验收「懂平台」：只走表结构摸底工具，**不**查业务数据、**不**声称已查实时库。

资料包示例：江西中软 MES（约 35 表 / 10 域）。换平台后模块名以当前 `list_platform_capabilities` 为准。

判定：

- **P**：调用了摸底类工具（`inspect_mes_profile` / `list_platform_capabilities` / `list_business_scenarios` / `describe_schema_table` 等）；不混可查对象实体 id；不说「已查到 N 条工单」。
- **F**：走了 `query_platform_data`；编造模块；用上一套 MES 的表名。

---

## 10 句固定话术

| # | 用户说法 | 期望工具（优先） | 期望要点 | 验收 |
|---|----------|------------------|----------|------|
| 1 | MES 系统能干什么？ | `inspect_mes_profile` → `list_platform_capabilities` | 人话模块 + 代表表；标明依据表结构 | **P** · 2026-08-19 · survey · 10 能力 · inferred_from_schema |
| 2 | 资料包配好了吗？ / 换平台能不能用？ | `inspect_mes_profile` | known / missing / next_tool；缺什么说什么 | **P** · 工具已落地（见冒烟换平台负向） |
| 3 | 生产相关有哪些表？ | `list_schema_tables` 或能力详情 | 只列当前文档表，不拿 OpenAPI 实体冒充 | 手工对话 |
| 4 | 工单从下达到入库涉及哪些表？ | `get_scenario_table_pack` / `list_business_scenarios` | 场景表包；`tables_found` 来自当前文档 | 手工对话 |
| 5 | `work_orders` 这张表是干什么的？ | `describe_schema_table` | 字段含义；不声称实时条数 | 手工对话 |
| 6 | MES 里「工单」和「排产」有什么区别？ | `list_platform_glossary` 或能力/术语 | 表结构语境术语，不查数 | 手工对话 |
| 7 | 仓储模块大概管什么？ | `describe_platform_capability` | 该域 one_liner + 代表表 | 手工对话 |
| 8 | 文档和接口对得上吗？ | `compare_schema_vs_catalog` | 匹配 / 仅文档 / 仅接口；默认不抽检 | **P** · 08-18 · 匹配 12 / 仅文档 23 / 仅接口 17 |
| 9 | 导出一份摸底报告 | `export_schema_survey_report` | 给出绝对路径 | 手工对话 |
| 10 | 今天有多少工单？ | **应路由到 B**（`query_platform_data` / `query_metric`） | 不得用表结构瞎编条数 | 手工：确认不走纯摸底编数 |

---

## 冒烟命令

```bash
# 含 TC-Q-05 / 换平台负向 / 当日完工降级 / D 闸门 / 嵌套路径
PYTHONPATH=apps/agent:apps python3 scripts/smoke_mes_acceptance_0819.py
```

对话冒烟建议新开一轮，先问第 1、2、8、10 句。
