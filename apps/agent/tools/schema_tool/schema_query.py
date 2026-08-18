"""
中软 MES 表结构分析工具（只读文档，不影响 ERP 查询/导入）。

供 Agent 调用：列出业务域、检索表、查看单表、汇总业务能力。
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from tools.schema_tool.mes_schema_parser import (
    build_index,
    find_table_full,
    schema_doc_path,
)

# 表前缀 → 业务能力粗分类（启发式，供分析参考，非权威）
_PREFIX_CAPABILITY = {
    "SYS": "系统与权限（组织、用户、角色、参数、字典）",
    "BD": "基础数据（客户、物料、工序、工作中心、供应商、模板）",
    "MSG": "消息推送与预警",
    "EAP": "设备联机 / 采集 / 设备参数与报警",
    "ERP": "ERP 对接 / 同步相关",
    "QM": "品质管理（化验、检验、客诉、药水）",
    "EAM": "设备维保与维修",
    "SFC": "车间执行（包装、配方、过站日志）",
    "MO": "生产工单 / 制造订单",
    "WMS": "仓储物流",
    "SRM": "供应商协同 / 收料",
    "SPC": "统计过程控制",
    "OQC": "出货检验",
    "FA": "FA/分析相关",
    "MEP": "物料工艺参数",
    "ESOP": "电子作业指导 / 变更",
    "NP": "模板变更",
    "SHEET": "板材关联",
    "OUTSOURCE": "外协",
    "PM": "设备点检模板关联",
    "ABNORMAL": "异常锁机锁卡",
    "PATTERN": "图形电镀生产记录",
}


def list_schema_domains() -> dict[str, Any]:
    """列出中软 MES 数据字典中的业务域（章节）及每域表数量。

    用于回答「平台有哪些业务模块/域」；不读 ERP，只解析本地表结构文档。
    """
    try:
        index = build_index()
    except Exception as e:
        return {"error": str(e), "hint": "请在「系统配置 → MES 接入」上传表结构文档"}
    domains = [
        {
            "domain_id": d.get("domain_id"),
            "domain": d.get("domain"),
            "table_count": d.get("table_count"),
        }
        for d in index.get("domains") or []
    ]
    return {
        "source": index.get("source"),
        "domain_count": len(domains),
        "table_count": index.get("table_count"),
        "domains": domains,
        "note": "来自本地表结构文档，不是实时数据库；与当前 WorkBuddy 可查询实体（entities.json）无关。",
    }


def list_schema_tables(
    domain: Annotated[
        str | None, "域名称关键字，如「品质」「系统」「设备」「基础数据」"
    ] = None,
    keyword: Annotated[
        str | None, "表名或中文名关键字，如 MO、工单、物料、检验"
    ] = None,
    offset: Annotated[int, "分页偏移，从 0 开始"] = 0,
    limit: Annotated[int, "每页条数，默认 30，最大 80"] = 30,
) -> dict[str, Any]:
    """按业务域或关键字列出数据表（分页）。"""
    try:
        index = build_index()
    except Exception as e:
        return {"error": str(e)}
    limit = max(1, min(int(limit or 30), 80))
    offset = max(0, int(offset or 0))
    rows = list(index.get("tables") or [])
    if domain:
        d = domain.strip()
        rows = [t for t in rows if d in (t.get("domain") or "") or d in (t.get("domain_id") or "")]
    if keyword:
        k = keyword.strip().upper()
        rows = [
            t
            for t in rows
            if k in (t.get("table") or "").upper()
            or k in (t.get("label") or "").upper()
            or k in (t.get("meaning") or "").upper()
        ]
    total = len(rows)
    page = rows[offset : offset + limit]
    slim = [
        {
            "seq": t.get("seq"),
            "table": t.get("table"),
            "label": t.get("label"),
            "domain": t.get("domain"),
            "meaning": (t.get("meaning") or "")[:120],
            "field_count": t.get("field_count"),
        }
        for t in page
    ]
    return {
        "returned": len(slim),
        "total_matched": total,
        "has_more": offset + limit < total,
        "offset": offset,
        "limit": limit,
        "tables": slim,
        "note": "仅本地字典摘要。查单表字段请用 describe_schema_table。",
    }


def describe_schema_table(
    table: Annotated[str, "表名（如 TBL_MO）或中文名关键字（如 工单、物料）"],
) -> dict[str, Any]:
    """查看单张表的业务含义、字段与关联关系。"""
    try:
        found = find_table_full(table)
    except Exception as e:
        return {"error": str(e)}
    if not found:
        return {
            "error": f"未找到表: {table}",
            "hint": "可先 list_schema_tables(keyword=...) 再精确表名",
        }
    # 字段过多时截断，避免撑爆上下文
    fields = found.get("fields") or []
    truncated = False
    if len(fields) > 40:
        fields = fields[:40]
        truncated = True
    rels = found.get("relations") or []
    if len(rels) > 30:
        rels = rels[:30]
        truncated = True
    return {
        "table": found.get("table"),
        "label": found.get("label"),
        "domain": found.get("domain"),
        "meaning": found.get("meaning"),
        "database": found.get("database"),
        "field_count": found.get("field_count"),
        "fields": fields,
        "relations": rels,
        "truncated": truncated,
        "note": "来自表结构文档；不能直接用 query_platform_data 查此表，除非已配置到 entities.json。",
    }


def analyze_schema_capabilities(
    focus: Annotated[
        str | None, "可选聚焦关键字，如 品质、仓储、设备、工单、物料"
    ] = None,
    detail_level: Annotated[
        Literal["summary", "domain"],
        "summary=总览；domain=按业务域列出代表表",
    ] = "summary",
) -> dict[str, Any]:
    """根据表结构文档快速分析 MES 系统业务能力（模块/能力地图）。

    适用：「根据表结构分析业务能力」「中软 MES 有哪些模块」「品质/仓储能力」等。
    不连接数据库，不修改 entities.json，不影响现有查/导/导入确认功能。
    """
    try:
        index = build_index()
    except Exception as e:
        return {"error": str(e)}

    tables = list(index.get("tables") or [])
    if focus:
        f = focus.strip()
        tables = [
            t
            for t in tables
            if f in (t.get("domain") or "")
            or f in (t.get("label") or "")
            or f in (t.get("meaning") or "")
            or f.upper() in (t.get("table") or "").upper()
        ]

    # 按域聚合
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for t in tables:
        dname = t.get("domain") or "未分类"
        by_domain.setdefault(dname, []).append(t)

    # 按前缀聚合能力（聚焦时只统计过滤后的表，与报告逻辑一致）
    by_prefix: dict[str, int] = {}
    for t in tables:
        p = t.get("table_prefix") or "?"
        by_prefix[p] = by_prefix.get(p, 0) + 1

    capabilities = []
    for prefix, cnt in sorted(by_prefix.items(), key=lambda x: -x[1]):
        cap = _PREFIX_CAPABILITY.get(prefix, f"其它（前缀 {prefix}）")
        capabilities.append({"prefix": prefix, "table_count": cnt, "capability": cap})

    domain_briefs = []
    for dname, items in by_domain.items():
        # 代表表：字段多或名称含核心词
        scored = sorted(
            items,
            key=lambda x: (
                -int(x.get("field_count") or 0),
                -int(x.get("relation_count") or 0),
            ),
        )
        top = scored[:5]
        domain_briefs.append(
            {
                "domain": dname,
                "table_count": len(items),
                "representative_tables": [
                    {
                        "table": x.get("table"),
                        "label": x.get("label"),
                        "meaning": (x.get("meaning") or "")[:80],
                    }
                    for x in top
                ],
            }
        )

    # 与当前可操作实体对照（只读提示）
    try:
        from tools.query_tool.entity_catalog import catalog_summary

        live = catalog_summary()
    except Exception:
        live = None

    out: dict[str, Any] = {
        "source": index.get("source") or str(schema_doc_path()),
        "table_count_in_doc": index.get("table_count"),
        "domain_count": index.get("domain_count"),
        "focus": focus,
        "capabilities_by_prefix": capabilities,
        "note": (
            "本结果由本地数据字典推断，用于实施摸底；"
            "不等于已对接 REST。当前对话可查询实体仍以 entities.json 为准。"
        ),
    }
    if detail_level == "domain" or focus:
        out["domains"] = domain_briefs
    else:
        out["domains"] = [
            {"domain": d["domain"], "table_count": d["table_count"]} for d in domain_briefs
        ]
    if live is not None:
        out["demo_entities_not_platform_capability"] = live
        out["demo_note"] = (
            "entities.json 仅为助手模拟演示（查/导），不是表结构平台能力清单。"
        )
    return out


def rebuild_schema_index() -> dict[str, Any]:
    """强制重建表结构索引缓存（文档更新后可调用）。"""
    from tools.schema_tool.mes_schema_parser import INDEX_CACHE

    try:
        index = build_index(force=True)
        return {
            "status": "ok",
            "table_count": index.get("table_count"),
            "domain_count": index.get("domain_count"),
            "cache": str(INDEX_CACHE),
        }
    except Exception as e:
        return {"error": str(e)}
