"""当前资料包分层就绪自检。换平台后按新配置重学表结构/接口，缺什么就说什么。

只读本地配置与目录，不打 MES。A/B 分层返回，避免把可查对象当成表结构能力。
"""
from __future__ import annotations

from typing import Annotated, Any

_SURVEY_RE = ("表结构", "能干什么", "有哪些模块", "摸底", "相关表", "能力地图", "场景表")
_QUERY_RE = ("查", "导出", "多少", "列表", "在制", "未完工", "紧急", "汇总")
_OPS_RE = ("谁导入", "401", "接口通不通", "值班", "探活", "查不到")


def _credential_flags() -> dict[str, Any]:
    """只返回是否已填，永不带回账号/密码原文。"""
    try:
        from settings_store import resolve_setting

        user = bool((resolve_setting("MES_API_USERNAME", "") or "").strip())
        pwd = bool((resolve_setting("MES_API_PASSWORD", "") or "").strip())
        ent = bool((resolve_setting("MES_API_ENTERPRISE_CODE", "") or "").strip())
    except Exception:
        user = pwd = ent = False
    return {
        "mes_api_username": user,
        "mes_api_password": pwd,
        "mes_enterprise_code": ent,
        "query_auth_ready": bool(user and pwd),
    }


def _intent_kind(text: str) -> str:
    raw = text or ""
    if any(k in raw for k in ("换平台", "配好了吗", "能不能用", "资料包")):
        return "switch"
    if any(k in raw for k in _OPS_RE):
        return "ops"
    if any(k in raw for k in _SURVEY_RE):
        return "survey"
    if any(k in raw for k in _QUERY_RE):
        return "query"
    return "unknown"


def format_mes_context_block() -> str:
    """每轮对话注入：当前平台身份 + 缺什么。不编造、不含密钥。"""
    try:
        from mes_profile import profile_status

        status = profile_status()
    except Exception:
        return (
            "【当前 MES 配置】未读取到资料包。涉及 MES 时不要编造，请用户到「系统配置 → MES 接入」配置。"
        )
    pid = str(status.get("active_profile_id") or "").strip()
    ui = status.get("ui") or {}
    schema_ok = bool(ui.get("schema_uploaded"))
    openapi_ok = bool(ui.get("openapi_imported"))
    n_ent = int(ui.get("entity_count") or 0)
    cred = _credential_flags()
    if not pid:
        return (
            "【当前 MES 配置】尚未指定平台名称。问 MES 表结构/查数/接口时禁止用上一套系统的记忆作答，"
            "请用户到「系统配置 → MES 接入」填写平台名称并上传表结构与接口文档。"
        )
    bits = [
        f"【当前 MES 配置】平台：{pid}",
        "表结构：" + ("已上传" if schema_ok else "未上传（摸底不可用，不要编模块清单）"),
        "接口文档："
        + (
            f"已导入，可查对象 {n_ent} 个"
            if openapi_ok and n_ent
            else "未导入或目录为空（查数不可用，不要编实体/条数）"
        ),
        "MES 接口账号："
        + ("已填" if cred.get("query_auth_ready") else "未填（查真实数据前请到系统配置补账号密码，与 WorkBuddy 登录不是同一套）"),
        "规则：只根据当前配置与本轮工具结果回答；会话里出现过但当前目录没有的实体/表名视为未知；"
        "已知则做下一步，未知则列出缺失项请用户补齐，禁止编造。",
    ]
    return "\n".join(bits)


def inspect_mes_profile(
    user_intent: Annotated[
        str | None,
        "用户原话，可选。用于判断本问是摸底/查数/运维，从而列出挡住本问的缺失项",
    ] = None,
) -> dict[str, Any]:
    """按最新资料包重学：表结构、接口目录、平台信息。返回已知/缺失；缺的不要编。

    适用：换了平台、资料包配好了吗、以及任何 MES 摸底/查数前的对齐。
    会清缓存后重读当前配置，不打 MES 业务接口、不改仓库。
    """
    try:
        from mes_profile import invalidate_mes_data_caches, profile_status

        invalidate_mes_data_caches()
        status = profile_status()
    except Exception as e:
        return {
            "error": f"{type(e).__name__}：未能读取资料包",
            "hint": "请先在「系统配置 → MES 接入」配置资料包。",
        }

    pid = str(status.get("active_profile_id") or "")
    cred = _credential_flags()
    next_steps: list[str] = []
    missing: list[dict[str, str]] = []
    if not status.get("configured"):
        next_steps.append("到系统配置填写平台名称，上传表结构 .md 与接口文档。")
        missing.append(
            {
                "item": "平台名称",
                "why": "未配置 MES 资料包",
                "action": "系统配置 → MES 接入 → 填写平台名称",
            }
        )

    schema_layer = _schema_layer(status, next_steps)
    query_layer = _query_layer(status, next_steps)
    query_layer["query_auth_ready"] = cred["query_auth_ready"]
    query_layer["credentials"] = {
        "username_set": cred["mes_api_username"],
        "password_set": cred["mes_api_password"],
        "enterprise_code_set": cred["mes_enterprise_code"],
    }
    ops_layer = _ops_layer(query_layer, next_steps)

    if schema_layer.get("capability_overlay_stale"):
        next_steps.append(
            "资料包 capability_map.json 的代表表对不上当前文档，可删除该文件以按表结构域自动生成能力地图。"
        )
    if schema_layer.get("table_count") == 0 and status.get("configured"):
        missing.append(
            {
                "item": "表结构文档",
                "why": "未上传或未能解析 schema.md",
                "action": "系统配置 → MES 接入 → 上传表结构（.md）",
            }
        )
    if query_layer.get("entity_count") == 0 and status.get("configured"):
        missing.append(
            {
                "item": "接口文档",
                "why": "未导入 OpenAPI 或未生成可查对象",
                "action": "系统配置 → MES 接入 → 导入接口文档（/docs 或 openapi.json）",
            }
        )
    if query_layer.get("entity_count") and not cred["query_auth_ready"]:
        missing.append(
            {
                "item": "MES 接口账号",
                "why": "未填写 MES 接口账号或密码（与 WorkBuddy 登录无关）",
                "action": "系统配置 → MES 接入 → 填写 MES 接口账号/密码",
            }
        )

    ready_survey = bool(schema_layer.get("table_count"))
    ready_query_catalog = bool(query_layer.get("entity_count"))
    ready_query_live = bool(ready_query_catalog and cred["query_auth_ready"])
    kind = _intent_kind(user_intent or "")
    blocked = False
    if kind == "survey" and not ready_survey:
        blocked = True
    if kind == "query" and not ready_query_catalog:
        blocked = True
    if kind == "query" and ready_query_catalog and not cred["query_auth_ready"]:
        blocked = True
    if kind == "ops" and not status.get("configured"):
        blocked = True

    known = {
        "platform": pid or None,
        "schema_tables": schema_layer.get("table_count") or 0,
        "schema_domains": schema_layer.get("domain_count") or 0,
        "api_entities": [e.get("entity") for e in (query_layer.get("entities") or []) if e.get("entity")],
        "api_entity_count": query_layer.get("entity_count") or 0,
        "path_prefix": query_layer.get("path_prefix") or "",
        "api_base": query_layer.get("api_base") or "",
        "bindable_metrics": [
            m.get("id") for m in (query_layer.get("metrics") or []) if m.get("bindable")
        ],
    }
    next_tool = ""
    if not blocked:
        if kind == "survey" and ready_survey:
            next_tool = "list_platform_capabilities"
        elif kind == "query" and ready_query_live:
            next_tool = "list_platform_entities 或 query_platform_data（entity 必须来自当前目录）"
        elif kind == "ops" and status.get("configured"):
            next_tool = "run_ops_scene 或 list_ops_scenes"
        elif kind in ("switch", "unknown"):
            next_tool = "按用户下一问在摸底/查数中选一层继续"

    ready = bool(status.get("configured") and ready_survey and ready_query_catalog)
    return {
        "profile_id": pid,
        "configured": bool(status.get("configured")),
        "ready_for_survey": ready_survey,
        "ready_for_query": ready_query_catalog,
        "ready_for_live_query": ready_query_live,
        "ready": ready,
        "intent_kind": kind if user_intent else None,
        "can_answer_now": (not blocked) if user_intent else ready,
        "known": known,
        "missing": missing,
        "A_schema": schema_layer,
        "B_query": query_layer,
        "C_ops": ops_layer,
        "next_steps": next_steps[:8],
        "next_tool": next_tool,
        "reply_gate": {
            "may_survey": ready_survey,
            "may_query_catalog": ready_query_catalog,
            "may_query_live": ready_query_live,
            "must_not_invent": [
                "未上传表结构时不要列举 MES 模块或表名",
                "当前目录没有的实体不要查询或编造条数",
                "会话里出现过但 known.api_entities 没有的 id 视为未知",
                "缺 MES 接口账号时不要假装已查到真数",
            ],
        },
        "hint": (
            "先看 missing：有挡住本问的项就原样告诉用户去系统配置补，不要编造。"
            "没有挡住则用 known 做 next_tool。"
            "摸底只看 A_schema；查数只看 B_query。WorkBuddy 登录 ≠ MES 接口账号。"
        ),
    }


def _schema_layer(status: dict[str, Any], next_steps: list[str]) -> dict[str, Any]:
    schema = status.get("schema") or {}
    table_count = 0
    domain_count = 0
    map_source = "empty"
    cap_count = 0
    backed = 0
    scenarios: list[dict[str, Any]] = []
    try:
        from tools.schema_tool.mes_schema_parser import build_index

        index = build_index()
        table_count = int(index.get("table_count") or 0)
        domain_count = int(index.get("domain_count") or 0)
    except Exception as e:
        if status.get("configured"):
            next_steps.append(f"表结构未能解析（{type(e).__name__}），请检查上传的 .md。")
    try:
        from tools.schema_tool.capability_map import list_platform_capabilities

        caps = list_platform_capabilities()
        map_source = str(caps.get("map_source") or "empty")
        cap_count = int(caps.get("capability_count") or 0)
        backed = len((caps.get("summary") or {}).get("schema_backed") or [])
    except Exception:
        pass
    try:
        from tools.schema_tool.business_scenarios import list_business_scenarios

        pack = list_business_scenarios()
        scenarios = [
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "tables_found": s.get("tables_found") or 0,
                "bindable": bool(s.get("bindable")),
            }
            for s in (pack.get("scenarios") or [])
        ]
    except Exception:
        scenarios = []
    if status.get("configured") and not table_count:
        next_steps.append("上传表结构 .md 后才能摸底（能力地图/场景表包）。")
    cap_info = status.get("capability_map") or {}
    overlay_stale = bool(
        cap_info.get("exists") and cap_info.get("size") and backed == 0 and cap_count
    )
    return {
        "schema_uploaded": bool((status.get("ui") or {}).get("schema_uploaded") or schema.get("exists")),
        "table_count": table_count,
        "domain_count": domain_count,
        "map_source": map_source,
        "capability_count": cap_count,
        "capabilities_backed": backed,
        "capability_overlay_stale": overlay_stale,
        "scenarios": scenarios,
        "bindable_scenarios": sum(1 for s in scenarios if s.get("bindable")),
    }


def _query_layer(status: dict[str, Any], next_steps: list[str]) -> dict[str, Any]:
    entity_count = int((status.get("ui") or {}).get("entity_count") or 0)
    entities: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    try:
        from tools.query_tool.entity_catalog import catalog_summary

        summary_rows = catalog_summary()
        entities = [
            {"entity": r.get("entity"), "label": r.get("label")}
            for r in summary_rows[:20]
        ]
        entity_count = max(entity_count, len(summary_rows))
    except Exception:
        entities = []
    try:
        from tools.query_tool.platform_query import list_query_metrics

        metrics = [
            {
                "id": m.get("id"),
                "label": m.get("label"),
                "bindable": bool(m.get("bindable")),
                "entity": m.get("entity"),
                "reason": m.get("reason"),
            }
            for m in (list_query_metrics().get("metrics") or [])
        ]
    except Exception:
        metrics = []
    if status.get("configured") and entity_count == 0:
        next_steps.append("导入接口文档（OpenAPI）以生成可查对象，才能查数/导出。")
    bindable_metrics = [m for m in metrics if m.get("bindable")]
    if entity_count and not bindable_metrics:
        next_steps.append(
            "可查对象已有，但在制/紧急未完工等口径未绑上：目录别名可能不含工单类对象，"
            "可在资料包 metrics.json 覆盖 entity_hints。"
        )
    return {
        "openapi_imported": bool((status.get("ui") or {}).get("openapi_imported")),
        "entity_count": entity_count,
        "entities": entities,
        "metrics": metrics,
        "bindable_metrics": len(bindable_metrics),
        "api_base": ((status.get("runtime") or {}).get("api_base") or ""),
        "path_prefix": ((status.get("runtime") or {}).get("path_prefix") or ""),
    }


def _ops_layer(query_layer: dict[str, Any], next_steps: list[str]) -> dict[str, Any]:
    scenes: list[dict[str, Any]] = []
    try:
        from tools.query_tool.ops_playbook import list_ops_scenes

        scenes = [
            {
                "id": s.get("id"),
                "label": s.get("label"),
                "bindable": s.get("bindable", True),
                "reason": s.get("reason"),
            }
            for s in (list_ops_scenes().get("scenes") or [])
        ]
    except Exception:
        scenes = []
    bindable = sum(1 for s in scenes if s.get("bindable"))
    return {
        "scene_count": len(scenes),
        "bindable_scenes": bindable,
        "scenes": scenes,
        "note": "探活默认沙箱；写操作仍须确认卡。场景随当前目录绑定，不写死某一套 MES。",
    }
