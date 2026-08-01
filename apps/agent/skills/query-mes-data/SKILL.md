---
name: query-mes-data
description: >-
  查询 MES/ERP 平台数据时使用。覆盖工单、生产计划（排产计划/排程计划等同义说法）、
  实体选择、筛选与字段核对。用户说「查一下」「看看有哪些」「统计」MES/业务数据时启用。
  注意：用户说「平台/系统能干什么」指 WorkBuddy，不是本 Skill。
  异常/紧急/按状态筛等运维高频说法可与 ops-query-playbook 一并参考。
---

# 查询平台数据

## 何时使用

- 用户要查工单、生产计划、排产、排程等
- 需要先弄清平台有哪些实体再查询
- 查询结果为空或失败，需要排查是否选错实体

## 工具选用

1. 不确定实体时：先 `list_platform_entities` 或 `get_platform_summary`
2. 查数据：`query_platform_data(entity="<英文id>", filters=?, limit=?)`
3. 看字段：`describe_entity(entity="<英文id>")`

`entity` **必须用英文 id**（如 `work-orders`、`production-plans`），不要传中文。

## 实体对照（严禁混用）

| 用户说法 | entity | 说明 |
|----------|--------|------|
| 工单、生产工单、派工单、在制工单、异常工单、WO | `work-orders` | 执行层工单 |
| 生产计划、排产计划、排程计划、排产、排程、主生产计划 | `production-plans` | 同一类计划数据 |

**禁止**用工单数据回答「生产计划/排产/排程」类问题；查空或失败要如实说明，不要改查另一个实体充数。

库存、销售订单等若目录无实体：告知待对接，不要用工单/计划冒充。

## 筛选示例

- pending 工单：`filters={"status": "pending"}`
- 高优先级：`filters={"priority": "high"}`
- 草稿计划：`filters={"status": "draft"}`

更多话术见 Skill `ops-query-playbook`。

## 推荐回复结构

1. 说明查的是哪个实体（可用用户原话 + 英文 id）
2. 条数与关键字段（计划号 `plan_no` / 工单号 `order_no` 等）
3. 如需汇总，按真实返回字段分组，不要臆造字段

## 自检

- [ ] entity 是否与用户意图一致
- [ ] 是否调用了查询工具（不要空口编数据）
- [ ] 带状态/优先级时是否传了 filters
- [ ] 回复是否把工单误称为生产计划
