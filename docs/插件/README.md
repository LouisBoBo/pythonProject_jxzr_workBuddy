# WorkBuddy 功能插件

本目录存放 **整功能热插拔插件** 的设计文档与开发约定。

- **方案文档**：在本目录（`docs/插件/`）
- **插件包代码**（实现阶段）：在仓库根 [`plugins/<id>/`](../../plugins/)  
- **内核**：`apps/`（对话 SSE、AgentRunner、共享 Middleware 等，不可卸载）

## 文档索引

| 文档 | 说明 |
|------|------|
| [架构设计方案.md](./架构设计方案.md) | 总体设计、契约、路线图；**§10 成本与价值评估 / 分档实施（路线 B/C）** |
| [plugin-yaml-example.md](./plugin-yaml-example.md) | 插件清单 `plugin.yaml` 模板 |

## 关联文档

- [DeepAgents 与 DeepSeek Harness 选型](../Agent开发/DeepAgents与DeepSeek-Harness技术选型分析.md)
- [功能实现总览](../功能实现/00-总览与架构分流.md)
- [DSH 架构调研（插件模型参考）](../Agent开发/dsh-architecture-report.zh.md)

## 状态

**方案阶段 · 未开工**。默认建议 **路线 B（模块化 + 重启生效）**，详见 [架构设计方案 §10](./架构设计方案.md#10-成本与价值评估)。
