---
name: import-export-data
description: >-
  文件导入、导出与格式转换时使用。用户说「导入工单」「导出 Excel」「转成 CSV」、
  上传附件要求写入平台或下载结果时启用。
---

# 导入 / 导出 / 转换

## 何时使用

- 把 CSV/Excel/JSON 导入平台实体
- 把平台数据导出为文件
- 仅做格式互转（不写平台）

## 标准流程

### 导入

1. 确认目标实体英文 id（对照 `list_platform_entities` 或实体目录）
2. 有本地路径时：`preview_file` 预览列名与样例行
3. `import_file_to_platform(file_path=..., target_entity="work-orders"|...)`
4. 向用户报告成功/失败条数；有 `errors` 则摘要说明

### 导出

1. 确认实体 id
2. `export_platform_data(entity=..., output_format="csv"|"excel"|"json")`
3. 告知导出路径与行数

### 仅转换格式

- `transform_file` 或走前端「文档转换」能力；不要误导入平台

## 注意

- `target_entity` / `entity` 只用英文 id
- 导入前检查文件存在、编码与列是否大致匹配
- 大批量导入受 `MAX_IMPORT_ROWS` 限制；超限要提示用户拆分
- 不要把导出文件路径编造出来；以工具返回为准

## 自检

- [ ] 导入目标实体是否正确
- [ ] 是否先预览再导入（有文件时）
- [ ] 是否把工具返回的真实路径告诉用户
