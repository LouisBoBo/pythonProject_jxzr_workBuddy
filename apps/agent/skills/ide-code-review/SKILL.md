---
name: ide-code-review
description: >-
  审核本机工程功能源码：list → read_batch → 仅终稿进对话输出区。
  过程旁白禁止输出；配置/uni_modules 等已自动排除。
---

# 本机 IDE 代码审核

## 输出纪律（硬）

- **过程中**：只调工具，**不要**写「共 N 文件 / 第 N 批纪要」给用户（过程区由系统展示）
- **全部批次完成后**：输出区第一行必须是 `## 🔍 代码审核报告`
- **禁止**英文过渡句（Now I have… / Let me compile…）；直接从报告标题写起

## 范围

**审**：业务页面/组件/接口/store/utils 等功能源码  
**不审**：配置、锁文件、样式、文档、`uni_modules`、locale、static、测试与 mock

## 流程

1. `request_ide_list_source_files`
2. `request_ide_read_batch(0..N-1)` 连续调用（脑内记 findings，勿贴正文）
3. 终稿报告（合并各批）
