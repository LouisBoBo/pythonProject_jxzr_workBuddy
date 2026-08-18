"""指标口径：通用模板绑定当前资料包实体/字段/真实枚举，不写死某一套 MES。"""
from __future__ import annotations

import itertools
import json
from datetime import date
from pathlib import Path
from typing import Any

from tools.query_tool.entity_catalog import load_catalog
from tools.query_tool.query_present import _fold_field, resolve_group_by

_DEFAULT_PATH = Path(__file__).resolve().parent / "metrics_default.json"
_MAX_FILTER_SETS = 8


def load_metrics_pack() -> dict[str, Any]:
    """内置模板 + 资料包 metrics.json（按 id 覆盖）。"""
    data = _read_json(_DEFAULT_PATH) or {"version": 1, "metrics": []}
    metrics = [m for m in (data.get("metrics") or []) if isinstance(m, dict) and m.get("id")]
    overlay_path = None
    try:
        from mes_profile import resolve_metrics_path

        overlay_path, _src = resolve_metrics_path()
    except Exception:
        overlay_path = None
    if overlay_path:
        extra = _read_json(Path(overlay_path)) or {}
        by_id = {str(m["id"]): m for m in metrics}
        for m in extra.get("metrics") or []:
            if not isinstance(m, dict) or not m.get("id"):
                continue
            if m.get("disabled"):
                by_id.pop(str(m["id"]), None)
                continue
            by_id[str(m["id"])] = m
        metrics = list(by_id.values())
        data = dict(extra) if extra else dict(data)
    data["metrics"] = metrics
    return data


def find_metric(name: str, pack: dict[str, Any] | None = None) -> dict[str, Any] | None:
    raw = (name or "").strip()
    if not raw:
        return None
    pack = pack or load_metrics_pack()
    key = raw.lower()
    for m in pack.get("metrics") or []:
        if str(m.get("id") or "").lower() == key:
            return m
        if str(m.get("label") or "").strip() == raw:
            return m
        for a in m.get("aliases") or []:
            if str(a).strip() == raw or str(a).strip().lower() == key:
                return m
    best: tuple[int, dict[str, Any]] | None = None
    for m in pack.get("metrics") or []:
        for a in [m.get("label"), *(m.get("aliases") or [])]:
            t = str(a or "").strip()
            if len(t) >= 2 and (t in raw or t.lower() in key):
                if best is None or len(t) > best[0]:
                    best = (len(t), m)
    return best[1] if best else None


def bind_metric(
    metric: dict[str, Any],
    *,
    catalog: list[dict[str, Any]] | None = None,
    available_fields: list[str] | None = None,
    observed: dict[str, list[str]] | None = None,
    filter_fields: list[str] | None = None,
    today: str | None = None,
) -> dict[str, Any]:
    """把口径绑到当前目录。失败时 error 说明缺什么，不编造实体。"""
    cats = catalog if catalog is not None else load_catalog()
    eid = _resolve_entity(metric.get("entity_hints") or [], cats)
    if not eid:
        return {
            "error": "当前资料包没有与该口径匹配的可查对象。",
            "metric": metric.get("id"),
            "label": metric.get("label"),
            "entity_hints": metric.get("entity_hints") or [],
            "hint": "换平台后请确认目录别名，或在资料包 metrics.json 覆盖 entity_hints。",
        }
    rec = next((e for e in cats if e.get("id") == eid), {}) or {}
    fields = list(available_fields or [])
    if not fields:
        fields = _fields_from_entity(rec)
    labels = {}
    for item in list(rec.get("columns") or []) + list(rec.get("fields") or []):
        if isinstance(item, dict) and item.get("name"):
            labels[str(item["name"])] = str(item.get("label") or item["name"])
    filterable = list(filter_fields) if filter_fields is not None else [
        str(f["name"] if isinstance(f, dict) else f)
        for f in (rec.get("fields") or [])
        if (f.get("name") if isinstance(f, dict) else f)
    ]
    clauses_out: list[dict[str, Any]] = []
    caveats: list[str] = []
    for clause in metric.get("clauses") or []:
        if not isinstance(clause, dict):
            continue
        bound = _bind_clause(
            clause,
            fields=fields,
            labels=labels,
            observed=observed or {},
            filterable=filterable,
            today=today or date.today().isoformat(),
        )
        if bound.get("skip"):
            caveats.append(str(bound.get("caveat") or "该条件无法下发给接口，已跳过。"))
            continue
        if bound.get("error"):
            return {
                "error": bound["error"],
                "metric": metric.get("id"),
                "label": metric.get("label"),
                "entity": eid,
                "available_fields": fields,
            }
        clauses_out.append(bound)
    if not clauses_out:
        return {
            "error": "口径无法绑定到当前接口的可筛选字段。",
            "metric": metric.get("id"),
            "entity": eid,
            "caveats": caveats,
        }
    sets = _filter_sets(clauses_out)
    return {
        "id": metric.get("id"),
        "label": metric.get("label"),
        "definition": metric.get("definition") or "",
        "entity": eid,
        "entity_label": rec.get("label") or eid,
        "clauses": clauses_out,
        "filter_sets": sets,
        "caveats": caveats,
    }


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _resolve_entity(hints: list[Any], catalog: list[dict[str, Any]]) -> str | None:
    if not catalog:
        return None
    best: tuple[int, str] | None = None
    for hint in hints:
        h = str(hint or "").strip()
        if not h:
            continue
        hl = h.lower()
        for e in catalog:
            eid = str(e.get("id") or "")
            terms = [eid, eid.replace("-", " "), str(e.get("label") or "")]
            terms.extend(str(a) for a in (e.get("aliases") or []))
            for t in terms:
                tl = str(t).strip()
                if len(tl) < 2:
                    continue
                tll = tl.lower()
                if hl == tll or hl == eid.lower():
                    score = len(tl) + 200
                elif hl in tll or tll in hl:
                    score = min(len(h), len(tl)) + 50
                else:
                    continue
                if best is None or score > best[0]:
                    best = (score, eid)
    return best[1] if best else None


def _fields_from_entity(rec: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("columns", "fields"):
        for item in rec.get(key) or []:
            n = item.get("name") if isinstance(item, dict) else item
            s = str(n or "").strip()
            if s and s not in names:
                names.append(s)
    return names


def _pick_field(role: str, hints: list[Any], fields: list[str], labels: dict[str, str]) -> str | None:
    for h in hints:
        name = str(h or "").strip()
        if not name:
            continue
        if name in fields:
            return name
        folded = _fold_field(name)
        for f in fields:
            if _fold_field(f) == folded:
                return f
        got = resolve_group_by(name, fields, labels)
        if got:
            return got
    if role == "status":
        return resolve_group_by("状态", fields, labels)
    if role == "priority":
        return resolve_group_by("优先级", fields, labels)
    if role == "date":
        for f in fields:
            n = _fold_field(f)
            if any(tok in n for tok in ("end_date", "finish", "complete", "closed_at")):
                return f
        for f in fields:
            n = _fold_field(f)
            if "date" in n or n.endswith("_at"):
                return f
    return None


def _norm_val(v: Any) -> str:
    return str(v).strip().lower()


def _match_values(hints: list[Any], observed: list[str]) -> list[str]:
    if not hints:
        return []
    if observed:
        obs_map = {_norm_val(v): str(v) for v in observed if v not in (None, "")}
        out: list[str] = []
        for h in hints:
            key = _norm_val(h)
            if key in obs_map and obs_map[key] not in out:
                out.append(obs_map[key])
        return out
    # 尚无样例时，只用 ASCII 枚举试探，避免把中文口径值直接打给接口
    out = []
    for h in hints:
        s = str(h).strip()
        if s and s.isascii() and s.replace("_", "").isalnum() and s not in out:
            out.append(s)
    return out


def _bind_clause(
    clause: dict[str, Any],
    *,
    fields: list[str],
    labels: dict[str, str],
    observed: dict[str, list[str]],
    filterable: list[str],
    today: str,
) -> dict[str, Any]:
    role = str(clause.get("field_role") or "status")
    hints = list(clause.get("field_hints") or [])
    field = _pick_field(role, hints, fields, labels)
    if not field:
        return {"error": f"当前对象没有可绑定的{role}字段（hints={hints}）。"}
    if filterable and field not in filterable and role != "date":
        # 仍允许用该字段：不少平台 query 参数名与返回列同名但不在 OpenAPI parameters 里
        pass
    if role == "date" or clause.get("relative") == "today":
        if filterable and field not in filterable:
            return {
                "skip": True,
                "caveat": f"接口未声明日期筛选参数 `{field}`，未能限定当日，仅按其它条件查询。",
            }
        return {"field": field, "values": [today], "role": "date"}
    observed_for_field = list(observed.get(field) or [])
    include = _match_values(list(clause.get("include_values") or []), observed_for_field)
    exclude = {_norm_val(v) for v in (clause.get("exclude_values") or [])}
    if not include and observed_for_field and exclude:
        include = [v for v in observed_for_field if _norm_val(v) not in exclude]
    elif include and exclude:
        include = [v for v in include if _norm_val(v) not in exclude]
    if not include:
        return {
            "error": (
                f"字段 `{field}` 的实际取值与口径枚举对不上。"
                f"观察到：{observed_for_field or '（无样例）'}。"
            )
        }
    return {"field": field, "values": include, "role": role}


def _filter_sets(clauses: list[dict[str, Any]]) -> list[dict[str, str]]:
    if not clauses:
        return []
    axes = [c["values"] for c in clauses]
    names = [c["field"] for c in clauses]
    out: list[dict[str, str]] = []
    for combo in itertools.product(*axes):
        item = {names[i]: str(combo[i]) for i in range(len(names))}
        out.append(item)
        if len(out) >= _MAX_FILTER_SETS:
            break
    return out
