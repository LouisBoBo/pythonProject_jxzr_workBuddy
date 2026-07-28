---
name: analyze-mes-schema
description: >-
  根据中软 MES 数据库表结构文档分析平台业务能力；人话能力地图；
  按业务场景串相关表包；导出摸底报告（Markdown/Excel）。
  用户说「平台能干什么」「有哪些功能」「根据表结构分析」「工单到入库相关表」
  「导出摸底报告」「品质/仓储能力」「TBL_MO 是什么」时启用。
  只谈表结构业务能力；不把查工单/排产/导入导出当成平台能力。
---

# 根据表结构分析业务能力

## 范围（必须先说清）

- **本 Skill = 平台业务能力摸底**：依据 `docs/中软MES数据库表结构.md`
- **查工单 / 查排产 / 导入导出 = 助手模拟演示**：可另用查询/导入 Skill，**不要写进「平台能干什么」的结论**，也不代表已改造真实平台能力

## 何时使用

- 人话总览：平台（表结构视角）有哪些业务模块
- 业务域 / 代表表 / 场景表包 / 摸底报告
- 术语：IPQC、OQC、线边仓等（表结构语境）

**不要**用本 Skill 回答「查一下当前工单/排产数据」——那是模拟演示查询。

## 工具顺序

1. 人话总览：`list_platform_capabilities()`
2. 某块详情：`describe_platform_capability(focus="仓储")`
3. 术语：`list_platform_glossary(keyword=?)`
4. 表结构：`analyze_schema_capabilities` / `list_schema_domains` / `list_schema_tables` / `describe_schema_table`
5. 场景表包：`list_business_scenarios` → `get_scenario_table_pack`
6. 导出报告：`export_schema_survey_report(format="both")`
7. 文档更新：`rebuild_schema_index()`

## 回复要求

1. 先讲人话 one_liner + 代表表/场景；**不要**用「助手可查工单」充当平台能力
2. 开场或结尾点明：依据本地表结构文档；模拟查/导是另一套演示能力
3. 导出成功后给出文件绝对路径
4. 单次不要罗列全部表

## 边界

| 诉求 | 用法 |
|------|------|
| 平台业务能力（表结构）/ 场景表包 / 摸底报告 | 本 Skill |
| 查/导工单、生产计划（模拟演示） | `query-mes-data` / `import-export-data` |
| 谁导入了文件 | `query_write_audit` |
| 接口健康（docs×日志） | `analyze-api-health` |
