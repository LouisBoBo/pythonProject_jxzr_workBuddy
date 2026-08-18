"""运维值班 playbook：场景清单 + 标准链（绑定当前资料包，不写死某一套 MES）。"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from tools.query_tool.entity_catalog import load_catalog
from tools.query_tool.metrics_pack import _resolve_entity
from tools.query_tool.query_present import resolve_group_by, summarize_records

_DEFAULT_PATH = Path(__file__).resolve().parent / "ops_scenes_default.json"


def load_ops_scenes() -> dict[str, Any]:
    data = _read_json(_DEFAULT_PATH) or {"version": 1, "scenes": []}
    scenes = [s for s in (data.get("scenes") or []) if isinstance(s, dict) and s.get("id")]
    overlay_path = None
    try:
        from mes_profile import profile_dir

        pdir = profile_dir()
        if pdir is not None:
            candidate = pdir / "ops_scenes.json"
            if candidate.is_file() and candidate.stat().st_size > 0:
                overlay_path = candidate
    except Exception:
        overlay_path = None
    if overlay_path:
        extra = _read_json(overlay_path) or {}
        by_id = {str(s["id"]): s for s in scenes}
        for s in extra.get("scenes") or []:
            if not isinstance(s, dict) or not s.get("id"):
                continue
            if s.get("disabled"):
                by_id.pop(str(s["id"]), None)
                continue
            by_id[str(s["id"])] = s
        scenes = list(by_id.values())
        data = dict(extra) if extra else dict(data)
    data["scenes"] = scenes
    return data


def find_ops_scene(name: str, pack: dict[str, Any] | None = None) -> dict[str, Any] | None:
    raw = (name or "").strip()
    if not raw:
        return None
    pack = pack or load_ops_scenes()
    key = raw.lower()
    for s in pack.get("scenes") or []:
        if str(s.get("id") or "").lower() == key:
            return s
        if str(s.get("label") or "").strip() == raw:
            return s
        for a in s.get("aliases") or []:
            if str(a).strip() == raw or str(a).strip().lower() == key:
                return s
    # 包含匹配：最长别名优先
    best: tuple[int, dict[str, Any]] | None = None
    for s in pack.get("scenes") or []:
        for a in [s.get("label"), *(s.get("aliases") or [])]:
            t = str(a or "").strip()
            if len(t) >= 2 and (t in raw or t.lower() in key):
                if best is None or len(t) > best[0]:
                    best = (len(t), s)
    return best[1] if best else None


def list_ops_scenes() -> dict[str, Any]:
    """列出运维值班场景（≥8）：紧急堆积、在制、探活、写审计等。"""
    pack = load_ops_scenes()
    catalog = load_catalog()
    items = []
    for s in pack.get("scenes") or []:
        bindable = True
        reason = None
        kind = str(s.get("kind") or "")
        if kind in ("metric_chain", "summarize", "export") and not catalog:
            bindable = False
            reason = "当前无可查对象目录"
        elif kind in ("summarize", "export"):
            eid = _resolve_entity(list(s.get("entity_hints") or []), catalog)
            if not eid:
                bindable = False
                reason = "目录中无匹配实体别名"
        items.append(
            {
                "id": s.get("id"),
                "label": s.get("label"),
                "aliases": s.get("aliases") or [],
                "kind": kind,
                "definition": s.get("definition") or "",
                "exportable": bool(s.get("exportable")),
                "bindable": bindable,
                "reason": reason,
            }
        )
    return {
        "count": len(items),
        "scenes": items,
        "hint": (
            "值班话术用 run_ops_scene(scene=场景id或中文)。"
            "写状态/导入须确认卡；接口探活默认沙箱。换平台后目录会变。"
        ),
    }


def run_ops_scene(
    scene: Annotated[str, "场景 id 或中文说法，如 urgent-backlog / 紧急工单 / 谁导入了 / 接口通不通"],
    export: Annotated[bool, "是否在查清单后导出文件（仅 exportable 场景）"] = False,
    output_format: Annotated[
        Literal["csv", "excel", "json"], "导出格式，默认 csv"
    ] = "csv",
    limit: Annotated[int, "清单条数上限，默认 20"] = 20,
) -> dict[str, Any]:
    """执行一条运维值班标准链：查询→汇总→可选导出；或审计/探活指引。"""
    spec = find_ops_scene(scene)
    if not spec:
        pack = load_ops_scenes()
        return {
            "error": f"未知运维场景：{scene!r}",
            "available": [
                {"id": s.get("id"), "label": s.get("label"), "aliases": s.get("aliases") or []}
                for s in pack.get("scenes") or []
            ],
            "hint": "先 list_ops_scenes。",
        }
    kind = str(spec.get("kind") or "")
    if kind == "metric_chain":
        return _run_metric_chain(spec, export=export, output_format=output_format, limit=limit)
    if kind == "summarize":
        return _run_summarize(spec, limit=limit)
    if kind == "export":
        return _run_export(spec, output_format=output_format)
    if kind == "write_audit":
        return _run_write_audit(spec)
    if kind == "api_health":
        return _run_api_health(spec)
    if kind == "guidance":
        return _run_guidance(spec)
    if kind == "diagnose":
        return _run_diagnose(spec)
    if kind == "daily_brief":
        return _run_daily_brief(spec, limit=limit)
    return {"error": f"不支持的场景类型：{kind}", "scene": spec.get("id")}


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _run_metric_chain(
    spec: dict[str, Any],
    *,
    export: bool,
    output_format: str,
    limit: int,
) -> dict[str, Any]:
    from tools.query_tool.platform_query import query_metric

    metric_name = str(spec.get("metric") or "")
    result = query_metric(metric_name, limit=limit)
    out: dict[str, Any] = {
        "scene": spec.get("id"),
        "label": spec.get("label"),
        "definition": spec.get("definition") or "",
        "step": "query_metric",
        "result": result,
    }
    if isinstance(result, dict) and "error" in result:
        out["reply_hint"] = "口径绑定失败时如实说明，不要套用其它 MES 的实体/状态。"
        return out

    records = result.get("records") if isinstance(result, dict) else None
    groups = None
    group_by = spec.get("summarize_group_by")
    if group_by and isinstance(records, list) and records:
        keys: list[str] = []
        for rec in records:
            if isinstance(rec, dict):
                for k in rec.keys():
                    if str(k) not in keys:
                        keys.append(str(k))
        field = resolve_group_by(str(group_by), keys, {})
        if field:
            groups = summarize_records(records, field)
            out["summary"] = {
                "group_by": field,
                "group_by_label": group_by,
                "groups": groups,
            }

    if export and spec.get("exportable") and isinstance(records, list) and records:
        exported = _export_records(
            records,
            entity=str(result.get("entity") or "export"),
            label=str(result.get("label") or result.get("entity") or "export"),
            output_format=output_format,
        )
        out["export"] = exported

    out["reply_hint"] = (
        f"先复述场景「{spec.get('label')}」与口径 definition；"
        "用 result 的 markdown_table / display_rows 展示清单；"
        "有 summary.groups 则给出分组表；有 export.file 须报绝对路径与 rows。"
        "禁止未确认就改状态；需要写变更时说明须走确认卡。"
    )
    return out


def _run_summarize(spec: dict[str, Any], *, limit: int) -> dict[str, Any]:
    from tools.query_tool.platform_query import summarize_platform_data

    catalog = load_catalog()
    eid = _resolve_entity(list(spec.get("entity_hints") or []), catalog)
    if not eid:
        return {
            "scene": spec.get("id"),
            "error": "当前目录没有与该场景匹配的可查对象。",
            "entity_hints": spec.get("entity_hints") or [],
        }
    result = summarize_platform_data(
        eid, group_by=str(spec.get("group_by") or "状态"), limit=limit
    )
    return {
        "scene": spec.get("id"),
        "label": spec.get("label"),
        "definition": spec.get("definition") or "",
        "result": result,
        "reply_hint": "展示 groups；说明 entity 与 group_by；不要编造未出现的分组。",
    }


def _run_export(spec: dict[str, Any], *, output_format: str) -> dict[str, Any]:
    from tools.file_ops import export_platform_data

    catalog = load_catalog()
    eid = _resolve_entity(list(spec.get("entity_hints") or []), catalog)
    if not eid:
        return {
            "scene": spec.get("id"),
            "error": "当前目录没有与该场景匹配的可查对象。",
            "entity_hints": spec.get("entity_hints") or [],
        }
    result = export_platform_data(eid, output_format=output_format)
    return {
        "scene": spec.get("id"),
        "label": spec.get("label"),
        "definition": spec.get("definition") or "",
        "result": result,
        "reply_hint": "必须给出 file 绝对路径与 rows；不要编造。",
    }


def _run_write_audit(spec: dict[str, Any]) -> dict[str, Any]:
    from tools.write_audit_query import query_write_audit

    event = str(spec.get("audit_event") or "write_confirmed")
    result = query_write_audit(event=event)  # type: ignore[arg-type]
    return {
        "scene": spec.get("id"),
        "label": spec.get("label"),
        "definition": spec.get("definition") or "",
        "result": result,
        "reply_hint": (
            "用表格列出时间、操作人、文件、目标实体、行数；说明默认近 30 天窗口；"
            "数据来自助手审计而非 ERP。写失败场景可提示：重试须重新走确认卡。"
        ),
    }


def _run_api_health(spec: dict[str, Any]) -> dict[str, Any]:
    mes = _mes_query_readiness()
    return {
        "scene": spec.get("id"),
        "label": spec.get("label"),
        "definition": spec.get("definition") or "",
        "kind": "api_health",
        "mes_query_readiness": mes,
        "rules": [
            "文档/Swagger 探活默认 mode=sandbox，禁止因「测试」自动改 live",
            "仅当用户明确要求打生产/真实出站只读时才用 live",
            "「MES 查数通不通」≠「OpenAPI 沙箱探活」：前者用 query；后者走 analyze-api-health 六步",
            "外部网关日志用 import_external_api_logs → analyze_api_errors_from_logs，勿与沙箱结论混写",
        ],
        "next_tools": [
            "build_api_catalog(docs_url=用户原样 URL)",
            "list_api_catalog",
            "probe_api_catalog()  # 默认 sandbox，limit=0",
            "summarize_api_doc_vs_logs → rank_problematic_apis → render_api_health_report",
        ],
        "reply_hint": (
            "先说明两条线：① MES 查数就绪见 mes_query_readiness；② 文档探活须用户给 docs URL 后走沙箱。"
            "不要默认打生产；不要泄露密钥。"
        ),
    }


def _run_guidance(spec: dict[str, Any]) -> dict[str, Any]:
    sid = str(spec.get("id") or "")
    bullets: list[str]
    if sid == "login-mes-auth-help":
        mes = _mes_query_readiness()
        recent = _recent_erp_auth_errors()
        bullets = [
            "WorkBuddy 登录（登录页账号）与 MES 接口账号是两套，互不替代。",
            "查数 401/未授权：到「系统配置 → MES 接入」检查接口账号/密码/企业编码（若文档要求），保存后新开对话再查一条。",
            "不要把 WorkBuddy 会话 token 发给 MES；也不要在对话里回显密码。",
            f"当前 MES 接口账号：{'已配置' if mes.get('has_mes_credentials') else '未配置'}；"
            f"可查对象：{mes.get('entity_count', 0)} 个；"
            f"API 根地址：{'已配置' if mes.get('has_api_base') else '未配置'}。",
        ]
        if recent.get("count"):
            bullets.append(
                f"近 {recent.get('lookback_days')} 天助手出站日志里有 {recent['count']} 条鉴权失败（HTTP 401/403），"
                "多为 token 过期或 MES 账号失效，优先刷新 MES 接口凭据。"
            )
            sample = recent.get("sample") or []
            if sample:
                bullets.append("最近一次失败：" + str(sample[0]))
        return {
            "scene": sid,
            "label": spec.get("label"),
            "definition": spec.get("definition") or "",
            "kind": "guidance",
            "bullets": bullets,
            "recent_auth_errors": recent,
            "reply_hint": "按 bullets 引导；可引用 recent_auth_errors 的 path/status，禁止回显密码或 token。",
        }
    else:
        bullets = [
            "请到「系统配置 → MES 接入」填写平台名称。",
            "上传/导入接口文档（OpenAPI），生成可查对象目录。",
            "填写 MES 接口账号/密码（及企业编码，若文档要求）。",
            "保存后新开对话，先 list_platform_entities 再查数。",
        ]
    return {
        "scene": sid,
        "label": spec.get("label"),
        "definition": spec.get("definition") or "",
        "kind": "guidance",
        "bullets": bullets,
        "reply_hint": "按 bullets 用中文简洁引导；不要编造已接通。",
    }


def _run_diagnose(spec: dict[str, Any]) -> dict[str, Any]:
    """值班故障树：只读本地就绪状态 + 出站日志，不改 MES、不默写。"""
    mes = _mes_query_readiness()
    auth = _recent_erp_auth_errors()
    fails = _recent_erp_failures()
    branches: list[dict[str, Any]] = []

    def add(bid: str, *, likely: bool, title: str, action: str, next_scene: str | None = None) -> None:
        branches.append(
            {
                "id": bid,
                "likely": likely,
                "title": title,
                "action": action,
                "next_scene": next_scene,
            }
        )

    if not mes.get("catalog_ready"):
        add(
            "catalog-empty",
            likely=True,
            title="无可查对象目录",
            action="到系统配置导入当前 MES 的接口文档，生成可查对象后再查。",
            next_scene="catalog-empty-help",
        )
    if not mes.get("has_mes_credentials") or not mes.get("has_api_base"):
        add(
            "mes-auth-config",
            likely=True,
            title="MES 接口账号或地址未配齐",
            action="WorkBuddy 登录不能代替 MES 接口账号。到系统配置补账号/密码/地址后新开对话。",
            next_scene="login-mes-auth-help",
        )
    if auth.get("count"):
        add(
            "http-401",
            likely=True,
            title="近期出站调用鉴权失败（401/403）",
            action="刷新 MES access_token 或重录接口账号。不要把密码贴进对话。",
            next_scene="login-mes-auth-help",
        )
    conn = [x for x in (fails.get("sample") or []) if x.get("kind") == "connect"]
    if conn:
        add(
            "connect",
            likely=True,
            title="连不上 MES（超时/拒绝）",
            action="核对 API 根地址与网络；这不是实体 id 写错。",
        )
    notfound = [x for x in (fails.get("sample") or []) if x.get("kind") == "not_found"]
    if notfound:
        add(
            "http-404",
            likely=True,
            title="路径 404",
            action="用当前目录的 path，不要沿用另一套 MES 的 /api/v1 或实体 id。",
        )
    add(
        "wrong-entity",
        likely=not branches,
        title="可能问错对象",
        action="先 list_platform_entities，对照 aliases；不要拿别的对象充数。",
    )
    add(
        "empty-ok",
        likely=False,
        title="接口通但就是 0 条",
        action="如实报空；检查 filters 是否下发、口径是否绑上当前目录枚举。",
    )
    likely = [b for b in branches if b.get("likely")]
    return {
        "scene": spec.get("id"),
        "label": spec.get("label"),
        "definition": spec.get("definition") or "",
        "kind": "diagnose",
        "mes_query_readiness": mes,
        "recent_auth_errors": auth,
        "recent_failures": {"count": fails.get("count"), "sample": (fails.get("sample") or [])[:5]},
        "likely": likely,
        "branches": branches,
        "reply_hint": (
            "按 likely 分支给中文结论，一次只推一条最可能原因。"
            "禁止回显密码；禁止默写；探活仍默认沙箱。"
        ),
    }


def _run_daily_brief(spec: dict[str, Any], *, limit: int) -> dict[str, Any]:
    """值班简报：只跑当前目录能绑定的口径，绑不上就跳过。"""
    from tools.query_tool.platform_query import list_query_metrics, query_metric

    listed = list_query_metrics()
    rows: list[dict[str, Any]] = []
    queried = 0
    cap = 4
    page_limit = max(3, min(int(limit or 8), 20))
    for m in listed.get("metrics") or []:
        item: dict[str, Any] = {
            "id": m.get("id"),
            "label": m.get("label"),
            "definition": m.get("definition") or "",
            "bindable": bool(m.get("bindable")),
            "entity": m.get("entity"),
        }
        if not m.get("bindable"):
            item["skipped"] = m.get("reason") or "当前目录绑不上"
            rows.append(item)
            continue
        if queried >= cap:
            item["skipped"] = "简报最多抽 4 个已绑定口径，其余见 list_query_metrics"
            rows.append(item)
            continue
        try:
            out = query_metric(str(m.get("id") or ""), limit=page_limit)
        except Exception as e:
            item["error"] = str(e)[:200]
            rows.append(item)
            queried += 1
            continue
        queried += 1
        item["total"] = out.get("total")
        item["returned"] = out.get("returned")
        item["error"] = out.get("error")
        item["caveats"] = out.get("caveats")
        rows.append(item)
    return {
        "scene": spec.get("id"),
        "label": spec.get("label"),
        "definition": spec.get("definition") or "",
        "kind": "daily_brief",
        "metrics": rows,
        "reply_hint": (
            "用中文简报列出各口径条数与定义；绑不上的如实跳过。"
            "不要编造；不要默写；不要套其它 MES 的实体 id。"
        ),
    }


def _recent_erp_auth_errors(*, lookback_days: int = 7, limit: int = 50) -> dict[str, Any]:
    """助手出站日志里近期 401/403（不含 token/密码）。"""
    days = max(1, min(int(lookback_days or 7), 30))
    since_ts = datetime.now().timestamp() - days * 86400
    try:
        from tools.api_log_tool.call_store import query_api_calls

        page = query_api_calls(
            ok=False,
            source="erp",
            since_ts=since_ts,
            offset=0,
            limit=max(1, min(int(limit or 50), 50)),
        )
    except Exception:
        return {"count": 0, "lookback_days": days, "sample": []}
    sample: list[dict[str, Any]] = []
    count = 0
    for row in page.get("items") or []:
        if not isinstance(row, dict):
            continue
        try:
            status = int(row.get("status") or 0)
        except (TypeError, ValueError):
            continue
        if status not in (401, 403):
            continue
        count += 1
        if len(sample) >= 3:
            continue
        sample.append(_safe_fail_row(row, kind="auth", status=status))
    return {"count": count, "lookback_days": days, "sample": sample}


def _recent_erp_failures(*, lookback_days: int = 7, limit: int = 50) -> dict[str, Any]:
    """近期出站失败（分类：auth / not_found / connect / other），不含密钥。"""
    days = max(1, min(int(lookback_days or 7), 30))
    since_ts = datetime.now().timestamp() - days * 86400
    try:
        from tools.api_log_tool.call_store import query_api_calls

        page = query_api_calls(
            ok=False,
            source="erp",
            since_ts=since_ts,
            offset=0,
            limit=max(1, min(int(limit or 50), 50)),
        )
    except Exception:
        return {"count": 0, "lookback_days": days, "sample": []}
    sample: list[dict[str, Any]] = []
    count = 0
    for row in page.get("items") or []:
        if not isinstance(row, dict):
            continue
        count += 1
        if len(sample) >= 8:
            continue
        kind = _classify_fail(row)
        try:
            status = int(row.get("status") or 0)
        except (TypeError, ValueError):
            status = 0
        sample.append(_safe_fail_row(row, kind=kind, status=status))
    return {"count": count, "lookback_days": days, "sample": sample}


def _classify_fail(row: dict[str, Any]) -> str:
    try:
        status = int(row.get("status") or 0)
    except (TypeError, ValueError):
        status = 0
    if status in (401, 403):
        return "auth"
    if status == 404:
        return "not_found"
    err = str(row.get("error") or "").lower()
    if any(x in err for x in ("refused", "timeout", "timed out", "unreachable", "failed to establish")):
        return "connect"
    if status:
        return "other"
    return "connect" if err else "other"


def _safe_fail_row(row: dict[str, Any], *, kind: str, status: int) -> dict[str, Any]:
    when = ""
    try:
        when = datetime.fromtimestamp(float(row.get("ts") or 0)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        when = ""
    path = str(row.get("path") or row.get("path_key") or "")
    path_safe = path.split("?")[0] if path else path
    err = str(row.get("error") or "")[:120]
    return {
        "time": when,
        "method": str(row.get("method") or "GET").upper(),
        "path": path_safe,
        "status": status or None,
        "kind": kind,
        "error": err,
    }


def _mes_query_readiness() -> dict[str, Any]:
    has_user = False
    has_pass = False
    api_base = ""
    try:
        from settings_store import resolve_setting

        has_user = bool((resolve_setting("MES_API_USERNAME", "") or "").strip())
        has_pass = bool((resolve_setting("MES_API_PASSWORD", "") or "").strip())
    except Exception:
        try:
            from config import Config

            has_user = bool((Config.ERP_USERNAME or "").strip())
            has_pass = bool((Config.ERP_PASSWORD or "").strip())
        except Exception:
            pass
    try:
        from mes_profile import resolve_mes_api_base

        api_base = (resolve_mes_api_base() or "").strip()
    except Exception:
        api_base = ""
    catalog = load_catalog()
    return {
        "has_mes_credentials": bool(has_user and has_pass),
        "has_api_base": bool(api_base),
        "entity_count": len(catalog),
        "catalog_ready": len(catalog) > 0,
    }


def _export_records(
    records: list[dict[str, Any]],
    *,
    entity: str,
    label: str,
    output_format: str,
) -> dict[str, Any]:
    import pandas as pd

    from config import Config

    if not records:
        return {"error": "没有可导出的记录"}
    out_dir = Config.EXPORT_DIR
    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in entity) or "export"
    ext = "xlsx" if output_format in ("excel", "xlsx") else output_format
    path = os.path.join(out_dir, f"{safe}_ops_{ts}.{ext}")
    df = pd.DataFrame(records)
    sheet = (label or entity)[:31] or "data"
    if output_format == "csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
    elif output_format in ("excel", "xlsx"):
        df.to_excel(path, index=False, sheet_name=sheet, engine="openpyxl")
    else:
        df.to_json(path, orient="records", force_ascii=False, indent=2)
    return {
        "status": "ok",
        "file": path,
        "format": output_format,
        "rows": len(records),
        "hint": "请把绝对路径 file 和行数 rows 告诉用户。",
    }
