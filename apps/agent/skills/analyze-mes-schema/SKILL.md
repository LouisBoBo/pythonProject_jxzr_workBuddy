---
name: analyze-mes-schema
description: >-
  根据当前 MES 资料包中的表结构文档分析业务能力；人话能力地图；
  按业务场景串相关表包；导出摸底报告（Markdown/Excel）。
  用户说「MES系统能干什么」「MES 有哪些功能」「根据表结构分析」
  「导出摸底报告」「某张表是什么」时启用。
  未上传表结构时须提示先去系统配置接入。
  注意：用户说「平台/系统能干什么」指 WorkBuddy 产品能力，不要用本 Skill 回答。
---

# 根据表结构分析 MES 业务能力

## 范围（必须先说清）

- **本 Skill = MES 业务能力摸底**：依据「系统配置 → MES 接入」已上传的表结构（`.md`）
- **查数 / 导入导出**：依据同一资料包的可查对象目录，**不要写进「MES系统能干什么」的结论**
- **「平台 / 系统」≠ MES**：那是 ZR WorkBuddy；介绍助手能力即可，勿走本 Skill

## 何时使用

- 人话总览：MES（表结构视角）有哪些业务模块
- 业务域 / 代表表 / 场景表包 / 摸底报告
- 术语澄清（表结构语境）

**不要**用本 Skill 回答「查一下当前业务数据」——那是 `query-mes-data`。  
**不要**用本 Skill 回答「这个平台能干什么」——那是 WorkBuddy 产品介绍。

## 工具顺序

1. 人话总览：`list_platform_capabilities()`
2. 某块详情：`describe_platform_capability(focus="…")`
3. 术语：`list_platform_glossary(keyword=?)`
4. 表结构：`analyze_schema_capabilities` / `list_schema_domains` / `list_schema_tables` / `describe_schema_table`
5. 场景表包：`list_business_scenarios` → `get_scenario_table_pack`
6. 导出报告：`export_schema_survey_report(format="both")`
7. 文档更新：`rebuild_schema_index()`

若工具报「未配置表结构」：引导用户去系统配置上传，不要编造模块清单。

## 回复要求

1. 先讲人话 one_liner + 代表表/场景
2. 开场或结尾点明：依据当前已配置的表结构文档
3. 导出成功后给出文件绝对路径
4. 单次不要罗列全部表

## 边界

| 诉求 | 用法 |
|------|------|
| MES 业务能力（表结构）/ 场景表包 / 摸底报告 | 本 Skill |
| 平台/系统/WorkBuddy 能做什么 | 直接介绍助手能力（不用本 Skill） |
| 查/导业务数据 | `query-mes-data` / `import-export-data` |
| 谁导入了文件 | `query_write_audit` |
| 接口健康（docs×日志） | `analyze-api-health` |
