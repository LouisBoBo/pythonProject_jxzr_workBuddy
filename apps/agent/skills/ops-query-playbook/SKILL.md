---
name: ops-query-playbook
description: >-
  实施/运维高频查询话术：按状态/优先级筛选、列表汇总、导出清单。
  实体与字段一律以当前 MES 资料包可查对象目录为准。
  用户说「异常」「紧急」「按状态筛」「汇总」「导出清单」时启用。
---

# 运维查询话术（Playbook）

## 先选对实体

1. `list_platform_entities` 确认当前资料包有哪些可查对象  
2. 用别名/label 映射到英文 `entity` id  
3. **禁止**目录里没有的实体；**禁止**改查另一实体充数  

未配置资料包时：提示先去「系统配置 → MES 接入」上传接口文档。

## 常用模式

### 1. 带筛选查询

```
query_platform_data(entity="<英文id>", filters={...}, limit=?)
```

字段名以 `describe_entity` 为准（常见如 `status` / `priority`）。用户说「异常/紧急」且无明确字段时：先说明按哪些 filters 试查，不要臆造字段。

### 2. 列表汇总

无 filters 时全量（注意 limit），再按返回的真实字段口头分组汇总。

### 3. 导出

```
export_platform_data(entity="<英文id>", output_format="csv"|"excel"|"json")
```

回复给出路径与行数；不要空口说「已导出」。

## 回复结构

1. 一句说明查的实体（用户原话 + 英文 id）  
2. 条数 + 关键字段  
3. 有过滤时点明条件；空结果如实说  

## 自检

- [ ] 目录非空且 entity 在目录中  
- [ ] 筛选用了 filters，而非全量后再假装过滤  
- [ ] 未把未对接对象当成已配置实体  
