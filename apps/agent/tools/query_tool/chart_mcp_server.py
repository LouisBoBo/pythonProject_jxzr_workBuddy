"""图表 MCP stdio server：暴露 render_chart / validate_chart_spec（不取数、不连 MES）。

启动（仓库根或任意 cwd）：
  PYTHONPATH=apps/agent python -m tools.query_tool.chart_mcp_server

Agent 侧可选 ANALYSIS_CHART_MCP=1 经 chart_mcp_client 调用；默认进程内渲染即可。
"""
from __future__ import annotations

import json
import sys
from typing import Any


def _read_message() -> dict[str, Any] | None:
    """MCP Content-Length 帧；兼容 NDJSON 单行。"""
    header = b""
    while True:
        ch = sys.stdin.buffer.read(1)
        if not ch:
            return None
        header += ch
        if header.endswith(b"\r\n\r\n"):
            break
        # NDJSON 无 Content-Length：一行一条
        if b"\n" in header and b"Content-Length" not in header:
            line = header.strip()
            if not line:
                header = b""
                continue
            try:
                return json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                return None
    text = header.decode("utf-8", errors="replace")
    length = 0
    for line in text.split("\r\n"):
        if line.lower().startswith("content-length:"):
            try:
                length = int(line.split(":", 1)[1].strip())
            except ValueError:
                length = 0
    body = sys.stdin.buffer.read(length) if length else b""
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


def _write_message(msg: dict[str, Any]) -> None:
    raw = json.dumps(msg, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(
        f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw
    )
    sys.stdout.buffer.flush()


def _tool_result(obj: Any) -> dict[str, Any]:
    text = json.dumps(obj, ensure_ascii=False)
    return {"content": [{"type": "text", "text": text}], "structuredContent": obj}


def _handle_tools_call(params: dict[str, Any]) -> Any:
    from tools.query_tool.analysis_chart import build_echarts_option

    name = str(params.get("name") or "")
    args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
    if name == "validate_chart_spec":
        ctype = str(args.get("chart_type") or "bar").lower()
        ok = ctype in ("bar", "line", "pie")
        cats = args.get("categories") if isinstance(args.get("categories"), list) else []
        vals = args.get("values") if isinstance(args.get("values"), list) else []
        return _tool_result(
            {
                "ok": ok and bool(cats) and bool(vals) and len(cats) == len(vals),
                "chart_type_ok": ok,
                "point_count": min(len(cats), len(vals)),
                "hint": None if ok else "chart_type 须为 bar/line/pie",
            }
        )
    if name != "render_chart":
        return _tool_result({"error": f"未知工具: {name}"})

    built = build_echarts_option(
        chart_type=str(args.get("chart_type") or "bar"),
        title=str(args.get("title") or "分析图"),
        categories=list(args.get("categories") or []),
        values=list(args.get("values") or []),
        series_name=str(args.get("series_name") or "数量"),
    )
    return _tool_result(
        {
            "ok": True,
            "option": built["option"],
            "chart_type": built["chart_type"],
            "title": built["title"],
            "categories": built["categories"],
            "values": built["values"],
            "point_count": built["point_count"],
            "caveats": built.get("caveats") or [],
            "mcp_tool": "render_chart",
        }
    )


def main() -> None:
    while True:
        msg = _read_message()
        if msg is None:
            break
        mid = msg.get("id")
        method = msg.get("method")
        if method == "initialize":
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "workbuddy-analysis-chart",
                            "version": "0.1.0",
                        },
                    },
                }
            )
            continue
        if method == "notifications/initialized":
            continue
        if method == "tools/list":
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "tools": [
                            {
                                "name": "render_chart",
                                "description": "将 categories/values 渲染为 ECharts option（不取数）",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "chart_type": {
                                            "type": "string",
                                            "enum": ["bar", "line", "pie"],
                                        },
                                        "title": {"type": "string"},
                                        "categories": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "values": {
                                            "type": "array",
                                            "items": {"type": "number"},
                                        },
                                        "series_name": {"type": "string"},
                                    },
                                    "required": ["categories", "values"],
                                },
                            },
                            {
                                "name": "validate_chart_spec",
                                "description": "校验图表参数是否合法",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {
                                        "chart_type": {"type": "string"},
                                        "categories": {"type": "array"},
                                        "values": {"type": "array"},
                                    },
                                },
                            },
                        ]
                    },
                }
            )
            continue
        if method == "tools/call":
            try:
                result = _handle_tools_call(msg.get("params") or {})
            except Exception as e:  # noqa: BLE001
                result = _tool_result({"error": f"{type(e).__name__}: {e}"})
            _write_message({"jsonrpc": "2.0", "id": mid, "result": result})
            continue
        if mid is not None:
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "error": {"code": -32601, "message": f"Method not found: {method}"},
                }
            )


if __name__ == "__main__":
    main()
