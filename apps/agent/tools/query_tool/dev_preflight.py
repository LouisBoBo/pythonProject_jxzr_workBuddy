"""改 MES 相关功能前的只读前置清单。不写仓、不查数。"""
from __future__ import annotations

from typing import Annotated, Any

from tools.query_tool.entity_catalog import catalog_summary, resolve_entity_id
from tools.query_tool.ops_playbook import list_ops_scenes
from tools.query_tool.platform_query import list_query_metrics


def mes_change_preflight(
    user_intent: Annotated[
        str | None,
        "用户要改的功能原话，可选；用于高亮当前目录里可能相关的实体",
    ] = None,
) -> dict[str, Any]:
    """写码前对照当前资料包：可查对象、指标、值班场景、表结构是否已配。

    不改仓库、不打 MES。换平台后清单跟着目录变。非 MES 写码（纯 UI 复刻）不必调用。
    """
    catalog = catalog_summary()
    hinted: list[dict[str, Any]] = []
    intent = (user_intent or "").strip()
    if intent:
        eid = resolve_entity_id(intent)
        if eid:
            hit = next((r for r in catalog if r.get("entity") == eid), None)
            if hit:
                hinted.append(hit)
    schema_ready = False
    schema_hint = "未检测到表结构文档"
    try:
        from tools.schema_tool.mes_schema_parser import build_index

        index = build_index()
        schema_ready = bool(index.get("tables"))
        schema_hint = (
            f"表 {index.get('table_count') or 0} 张，域 {index.get('domain_count') or 0} 个"
            if schema_ready
            else "已配置表结构但未能解析到表，请检查上传的 .md"
        )
    except Exception as e:
        schema_hint = f"{type(e).__name__}：表结构未能解析"

    metrics = []
    try:
        metrics = [
            {"id": m.get("id"), "label": m.get("label"), "bindable": m.get("bindable")}
            for m in (list_query_metrics().get("metrics") or [])
        ]
    except Exception:
        metrics = []
    scenes = []
    try:
        scenes = [
            {"id": s.get("id"), "label": s.get("label")}
            for s in (list_ops_scenes().get("scenes") or [])
        ]
    except Exception:
        scenes = []

    accept: list[str] = []
    for row in (hinted or catalog)[:3]:
        label = row.get("label") or row.get("entity")
        eid = row.get("entity")
        accept.append(f"查「{label}」列表（entity=`{eid}`）应仍能返回或如实 0 条，无 401")
    if any(m.get("bindable") for m in metrics):
        m = next(m for m in metrics if m.get("bindable"))
        accept.append(f"问「{m.get('label')}」应走口径 `{m.get('id')}`，不要套其它 MES 的实体 id")
    if not accept:
        accept.append("资料包可查对象为空：先到系统配置接入 MES，再谈数据侧验收")

    return {
        "catalog_count": len(catalog),
        "entities": [
            {"entity": r.get("entity"), "label": r.get("label"), "aliases": r.get("aliases") or []}
            for r in catalog[:40]
        ],
        "intent_hits": hinted[:5],
        "schema_ready": schema_ready,
        "schema_hint": schema_hint,
        "metrics": metrics[:12],
        "ops_scenes": scenes[:16],
        "write_checklist": [
            "确认前不要声称已改仓库；走 :::cursor_dev_propose 等用户确认。",
            "requirement 写清完整链路：界面 → 接口 schema → 库表补列/迁移 → 业务写入 → 旧数据按状态回填。",
            "禁止只加前端空列；写操作（导入/改状态）仍须确认卡；本工具不会写入。",
        ],
        "stack_chain": [
            "库表/模型有字段；已有库 ALTER 或迁移",
            "列表/详情/创建/更新接口返回或接收该字段",
            "保存或状态流转会写入，不只展示",
            "前端列表/表单/详情同一字段；空值有约定",
            "旧数据必须回填（已开工/已完成用计划日+约定时刻；待开工保持空）",
        ],
        "acceptance_hints": accept[:5],
        "reply_hint": (
            "若本轮是改 MES 页/接口：把 entities 与 acceptance_hints 写进 propose.requirement。"
            "纯 UI 复刻/无关 MES 的写码不要生搬这份清单。"
        ),
    }
