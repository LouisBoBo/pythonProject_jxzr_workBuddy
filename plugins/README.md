# WorkBuddy 功能插件包目录

本目录用于存放 **运行时插件包**（实现阶段：`plugins/<id>/` 各功能目录）。

**设计文档**在 [`docs/插件/`](../docs/插件/README.md)，不在此目录。

## 约定（实现阶段）

```text
plugins/
  README.md                 # 本文件
  <plugin-id>/              # 例如 api-health、automations
    plugin.yaml
    agent/
    api/
    web/
    tests/
```

运行时状态（enabled 列表等）落在 `data/plugins/state.json`，不提交仓库。

## 状态

**方案阶段 · 未开工**。详见 [架构设计方案](../docs/插件/架构设计方案.md)。
