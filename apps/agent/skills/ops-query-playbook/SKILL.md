---
name: ops-query-playbook
description: >-
  实施/运维高频查询话术：异常或紧急工单、按状态筛工单、生产计划/排产状态汇总、
  导出清单。用户说「异常工单」「紧急单」「pending 工单」「排产汇总」「计划有哪些」时启用。
  与纯「随便查一下」相比，本 Skill 强调 filters 与实体边界。
---

# 运维查询话术（Playbook）

## 实体边界（先选对再查）

| 用户说法 | entity |
|----------|--------|
| 工单 / 派工单 / WO / 异常工单 / 紧急工单 | `work-orders` |
| 生产计划 / 排产 / 排程 / PP | `production-plans` |

**禁止**用工单回答排产问题，或用计划数据冒充工单。

## 常用话术 → 工具

### 1. 异常 / 高优先级工单

```
query_platform_data(entity="work-orders", filters={"priority": "high"})
# 或 urgent
query_platform_data(entity="work-orders", filters={"priority": "urgent"})
```

若用户说「异常」且未指定字段：先查 `status=pending` 与 `priority=high`，合并说明；不要臆造「异常」字段。

### 2. 按状态筛工单

| 说法 | filters |
|------|---------|
| 待开工 / pending / 未开始 | `{"status": "pending"}` |
| 进行中 / in progress / 在制 | `{"status": "in_progress"}` |
| 已完成 / completed | `{"status": "completed"}` |
| 已取消 | `{"status": "cancelled"}` |

### 3. 生产计划状态

| 说法 | filters |
|------|---------|
| 草稿 / draft | `{"status": "draft"}` |
| 已确认 / confirmed | `{"status": "confirmed"}` |
| 已下达 / released | `{"status": "released"}` |

无 filters 时 `query_platform_data(entity="production-plans")`，再按返回的 `status` 口头汇总。

### 4. 导出

- 工单清单：`export_platform_data(entity="work-orders", output_format="csv"|"excel")`
- 排产清单：`export_platform_data(entity="production-plans", output_format="csv"|"excel")`
- 回复给出路径与行数；不要空口说「已导出」

## 回复结构

1. 一句说明查的实体（用户原话 + 英文 id）
2. 条数 + 关键字段（`order_no` / `plan_no` / `status` / `priority`）
3. 有过滤时点明过滤条件；空结果如实说，**不要改查另一实体**

## 自检

- [ ] entity 与说法族一致
- [ ] 筛选用了 filters，而非全量后再假装过滤
- [ ] 未把库存/订单当成已对接实体（目录没有则说明待对接）
