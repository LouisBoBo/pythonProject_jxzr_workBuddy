"""
平台查询工具：封装平台数据查询操作，供 Agent 调用。
"""
from typing import Annotated

from tools.query_tool.entity_catalog import catalog_summary, get_entity
from tools.platform_api import get_client


def list_platform_entities() -> dict:
    """列出平台中所有可用的数据实体（表/集合）。

    返回实体 id、中文名、别名、支持操作与字段概要。
    导入/查询前应先调用此工具确认目标实体与正确的英文 id。
    """
    client = get_client()
    catalog = catalog_summary()
    details = []
    for row in catalog:
        eid = row["entity"]
        info = client.describe_entity(eid)
        item = {
            "entity": eid,
            "label": row["label"],
            "aliases": row["aliases"],
            "ops": row["ops"],
            "catalog_fields": row["fields"],
        }
        if "error" not in info:
            item["fields"] = info.get("fields", [])
            item["record_count"] = info.get("record_count", 0)
        else:
            item["error"] = info["error"]
            item["fields"] = row["fields"]
            item["record_count"] = 0
        details.append(item)

    return {
        "entities": [r["entity"] for r in catalog],
        "count": len(catalog),
        "details": details,
        "hint": "调用 query/import/export 时 entity 请使用上方 entity 字段的英文 id",
    }


def query_platform_data(
    entity: Annotated[str, "实体英文 id（如 work-orders、production-plans），也可用中文别名"],
    filters: Annotated[
        dict | None, '可选过滤条件，如 {"status": "pending"} 或 {"priority": "high"}'
    ] = None,
    limit: Annotated[int, "返回记录上限，默认 20"] = 20,
) -> dict:
    """查询平台中指定实体的数据。"""
    client = get_client()
    return client.query(entity, filters, limit)


def describe_entity(
    entity: Annotated[str, "实体英文 id 或中文别名"],
) -> dict:
    """查看平台中某个实体的字段结构和样例数据。"""
    client = get_client()
    result = client.describe_entity(entity)
    # 补充目录中的别名与标注字段，方便 Agent 对照
    meta = get_entity(result.get("entity", entity)) if "error" not in result else get_entity(entity)
    if meta and "error" not in result:
        result["label"] = meta.get("label")
        result["aliases"] = meta.get("aliases") or []
        result["ops"] = meta.get("ops") or []
    return result


def get_platform_summary() -> dict:
    """获取平台的概要信息：有哪些实体、各有多少数据。

    适合作为 Agent 了解平台全貌的第一步。
    """
    client = get_client()
    catalog = catalog_summary()
    summary = {}
    total_records = 0
    for row in catalog:
        eid = row["entity"]
        info = client.describe_entity(eid)
        count = info.get("record_count", 0)
        summary[eid] = {
            "label": row["label"],
            "aliases": row["aliases"],
            "record_count": count,
        }
        total_records += count
    return {
        "entity_count": len(catalog),
        "total_records": total_records,
        "breakdown": summary,
    }
