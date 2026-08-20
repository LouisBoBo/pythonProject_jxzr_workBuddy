# MES 分析图表 MCP（可选）

> 默认：Agent 进程内 `render_analysis_chart` 直接生成 ECharts option。  
> 可选：`ANALYSIS_CHART_MCP=1` 时经 stdio MCP 复用同一渲染实现（供 Cursor / 外部工具链调用）。  
> **取数仍走 WorkBuddy 鉴权与 HTTP/metric 工具**；MCP **只渲染**，不连 MES、不传库密码。

## 启动 MCP server

```bash
cd <repo>
PYTHONPATH=apps/agent python -m tools.query_tool.chart_mcp_server
```

工具：

| 名称 | 作用 |
|------|------|
| `render_chart` | categories/values → ECharts option |
| `validate_chart_spec` | 校验 chart_type / 点数 |

## Agent 侧开关

| 变量 | 说明 |
|------|------|
| `ANALYSIS_CHART_MCP=1` | `render_analysis_chart` 优先走 MCP，失败降级本地 |
| `ANALYSIS_CHART_MCP_COMMAND` | 覆盖启动命令（空格分隔） |
| `ANALYSIS_CHART_MCP_TIMEOUT_SEC` | 默认 20 |

Cursor `mcp.json` 示例（仅渲染，勿配置 MES DSN）：

```json
{
  "mcpServers": {
    "workbuddy-analysis-chart": {
      "command": "python",
      "args": ["-m", "tools.query_tool.chart_mcp_server"],
      "env": { "PYTHONPATH": "apps/agent" }
    }
  }
}
```

## 安全

- 禁止把客户 MES 全量明细塞进 chart（工具内 `_MAX_POINTS=40`）
- 禁止第三方托管 chart 服务出站传厂内数据
- 多用户 API 默认用进程内渲染，勿对每个请求挂长生命周期 stdio MCP
