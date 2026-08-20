"""分析演示编排：配置驱动的多步剧本（简报→看板→清单）。

设计约束：
- 仅由明确别名触发（如「演示·PCB早会」），不改写普通查数/日报/看板行为
- 步骤声明式；换厂靠资料包 demos/{id}.json 或 analysis.json 覆盖，禁止写死实体 id
- 单步失败隔离；optional 步失败不拖垮整场
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

_BUILTIN_DIR = Path(__file__).resolve().parent / "demo_playbooks"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if not path.is_file() or path.stat().st_size <= 0:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _profile_demos_dir() -> Path | None:
    try:
        from mes_profile import profile_dir

        pdir = profile_dir()
    except Exception:
        return None
    if pdir is None:
        return None
    d = Path(pdir) / "demos"
    return d if d.is_dir() else None


def _demo_overlays_from_analysis() -> dict[str, dict[str, Any]]:
    """analysis.json.analysis_demos：{ id: { enabled, ... } }。"""
    try:
        from tools.query_tool.analysis_config import load_analysis_config

        raw = load_analysis_config().get("analysis_demos")
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            out[str(k).strip()] = v
    return out


def _merge_playbook(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, val in overlay.items():
        if key.startswith("_"):
            continue
        if key == "steps" and isinstance(val, list):
            out["steps"] = [s for s in val if isinstance(s, dict)]
        elif key == "aliases" and isinstance(val, list):
            out["aliases"] = [str(a).strip() for a in val if str(a).strip()]
        elif key == "enabled":
            out["enabled"] = bool(val)
        elif key in ("id", "label", "definition", "reply_hint") and val is not None:
            out[key] = str(val).strip() if key != "definition" else str(val)
    return out


def load_demo_playbooks() -> dict[str, dict[str, Any]]:
    """内置 ← 资料包 demos/*.json ← analysis.json.analysis_demos。"""
    by_id: dict[str, dict[str, Any]] = {}

    if _BUILTIN_DIR.is_dir():
        for path in sorted(_BUILTIN_DIR.glob("*.json")):
            data = _read_json(path)
            if not data:
                continue
            pid = str(data.get("id") or path.stem).strip()
            if not pid:
                continue
            item = dict(data)
            item["id"] = pid
            item.setdefault("enabled", True)
            item.setdefault("aliases", [])
            item.setdefault("steps", [])
            item["_source"] = f"builtin:{path.name}"
            by_id[pid] = item

    pdir = _profile_demos_dir()
    if pdir is not None:
        for path in sorted(pdir.glob("*.json")):
            data = _read_json(path)
            if not data:
                continue
            pid = str(data.get("id") or path.stem).strip()
            if not pid:
                continue
            if pid in by_id:
                by_id[pid] = _merge_playbook(by_id[pid], data)
                by_id[pid]["_source"] = f"profile:demos/{path.name}"
            else:
                item = dict(data)
                item["id"] = pid
                item.setdefault("enabled", True)
                item["_source"] = f"profile:demos/{path.name}"
                by_id[pid] = item

    for pid, ov in _demo_overlays_from_analysis().items():
        if pid in by_id:
            by_id[pid] = _merge_playbook(by_id[pid], ov)
            by_id[pid]["_source"] = (by_id[pid].get("_source") or "") + "+analysis"
        elif ov.get("enabled") is False:
            # 仅用于关闭未知 id 时忽略
            continue

    return by_id


def find_demo_playbook(name: str) -> dict[str, Any] | None:
    raw = str(name or "").strip()
    if not raw:
        return None
    pack = load_demo_playbooks()
    # 旧 id 兼容
    if raw.lower() in {"pcb-morning", "analysis-demo-pcb-morning"}:
        spec = pack.get("pcb-ops-board")
        if spec and spec.get("enabled", True):
            return spec
    low = raw.lower().replace("·", "").replace(" ", "")
    for pid, spec in pack.items():
        if not spec.get("enabled", True):
            continue
        if pid.lower() == raw.lower() or pid.lower().replace("-", "") == low.replace("-", ""):
            return spec
        label = str(spec.get("label") or "").strip()
        if label and (label == raw or label.replace("·", "") == raw.replace("·", "")):
            return spec
        for alias in spec.get("aliases") or []:
            a = str(alias).strip()
            if not a:
                continue
            if a == raw:
                return spec
            if a.lower().replace("·", "").replace(" ", "") == low:
                return spec
    return None


def list_analysis_demos() -> dict[str, Any]:
    """列出当前可用的分析演示剧本（已禁用的仍列出但 marked）。"""
    items: list[dict[str, Any]] = []
    for pid, spec in load_demo_playbooks().items():
        items.append(
            {
                "id": pid,
                "label": spec.get("label") or pid,
                "enabled": bool(spec.get("enabled", True)),
                "aliases": list(spec.get("aliases") or [])[:12],
                "definition": str(spec.get("definition") or "")[:240],
                "source": spec.get("_source"),
            }
        )
    return {
        "count": len(items),
        "demos": items,
        "hint": (
            "用户说「打开PCB运营看板」时调用 run_analysis_demo；"
            "普通指标/单图/值班简报勿误用。换厂可在资料包 demos/ 覆盖。"
        ),
    }


def _extract_brief_md(scene_out: dict[str, Any]) -> str:
    if not isinstance(scene_out, dict):
        return ""
    for key in ("markdown_report", "markdown"):
        v = scene_out.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    result = scene_out.get("result")
    if isinstance(result, dict):
        for key in ("markdown_report", "markdown"):
            v = result.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return ""


def _run_step(step: dict[str, Any], *, user_intent: str) -> dict[str, Any]:
    kind = str(step.get("kind") or "").strip().lower()
    sid = str(step.get("id") or kind or "step")
    optional = bool(step.get("optional"))
    base: dict[str, Any] = {
        "id": sid,
        "kind": kind,
        "optional": optional,
    }

    try:
        if kind == "ops_scene":
            from tools.query_tool.ops_playbook import run_ops_scene

            scene = str(step.get("scene") or "").strip()
            if not scene:
                return {**base, "status": "gap", "reason": "未配置 scene"}
            limit = step.get("limit")
            kwargs: dict[str, Any] = {"scene": scene}
            if limit is not None:
                try:
                    kwargs["limit"] = max(1, min(int(limit), 50))
                except (TypeError, ValueError):
                    pass
            out = run_ops_scene(**kwargs)
            if isinstance(out, dict) and out.get("error"):
                return {
                    **base,
                    "status": "gap",
                    "reason": str(out.get("error")),
                    "scene": scene,
                    "result": out,
                }
            return {
                **base,
                "status": "ok",
                "scene": scene,
                "result": out,
                "markdown_excerpt": _extract_brief_md(out if isinstance(out, dict) else {})[
                    :4000
                ],
            }

        if kind == "dashboard":
            from tools.query_tool.analysis_dashboard import render_analysis_dashboard

            tid = str(step.get("template_id") or "auto").strip() or "auto"
            max_cards = step.get("max_cards", 4)
            try:
                mc = max(1, min(int(max_cards or 4), 8))
            except (TypeError, ValueError):
                mc = 4
            out = render_analysis_dashboard(
                template_id=tid,
                user_intent=user_intent or "早会演示看板",
                max_cards=mc,
            )
            if isinstance(out, dict) and out.get("error") and not out.get("charts"):
                return {
                    **base,
                    "status": "gap",
                    "reason": str(out.get("error")),
                    "result": out,
                }
            return {
                **base,
                "status": "ok",
                "result": out,
                "template_id": (out or {}).get("template_id") if isinstance(out, dict) else tid,
                "chart_count": (out or {}).get("chart_count") if isinstance(out, dict) else 0,
                "gap_count": (out or {}).get("gap_count") if isinstance(out, dict) else 0,
            }

        if kind == "metric":
            from tools.query_tool.platform_query import query_metric

            name = str(step.get("metric") or step.get("name") or "").strip()
            if not name:
                return {**base, "status": "gap", "reason": "未配置 metric"}
            limit = 10
            try:
                if step.get("limit") is not None:
                    limit = max(1, min(int(step["limit"]), 50))
            except (TypeError, ValueError):
                pass
            out = query_metric(name, limit=limit)
            if isinstance(out, dict) and out.get("error"):
                return {
                    **base,
                    "status": "gap",
                    "reason": str(out.get("error")),
                    "metric": name,
                    "result": out,
                }
            return {**base, "status": "ok", "metric": name, "result": out}

        return {**base, "status": "gap", "reason": f"未知步骤 kind={kind!r}"}
    except Exception as e:  # noqa: BLE001 — 单步隔离
        return {
            **base,
            "status": "gap",
            "reason": f"{type(e).__name__}: {e}",
        }


def run_analysis_demo(
    playbook: Annotated[
        str,
        "看板编排 id 或别名，如 pcb-ops-board / 打开PCB运营看板",
    ] = "pcb-ops-board",
    user_intent: Annotated[str, "用户原话，传给看板选型"] = "",
) -> dict[str, Any]:
    """按资料包可覆盖的剧本打开运营看板（简报+多图+急单样例）。不改变单图/指标默认行为。"""
    spec = find_demo_playbook(playbook)
    if not spec:
        listed = list_analysis_demos()
        return {
            "error": f"未知或已禁用的分析看板编排：{playbook!r}",
            "available": listed.get("demos") or [],
            "hint": listed.get("hint"),
        }
    if not spec.get("enabled", True):
        return {
            "error": f"演示「{spec.get('id')}」已在资料包中禁用",
            "hint": "在 analysis.json 的 analysis_demos 设 enabled:true，或删除禁用项。",
        }

    steps_in = [s for s in (spec.get("steps") or []) if isinstance(s, dict)]
    if not steps_in:
        return {"error": "演示剧本没有 steps", "playbook": spec.get("id")}

    intent = (user_intent or "").strip() or str(spec.get("label") or playbook)
    step_results: list[dict[str, Any]] = []
    charts: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    brief_parts: list[str] = []
    urgent_preview: dict[str, Any] | None = None
    template_id = ""
    board_label = str(spec.get("label") or spec.get("id"))
    board_kpis: list[dict[str, Any]] = []
    board_skin = "ops_dark"
    board_presentation = True

    for step in steps_in:
        one = _run_step(step, user_intent=intent)
        step_results.append(
            {
                "id": one.get("id"),
                "kind": one.get("kind"),
                "status": one.get("status"),
                "reason": one.get("reason"),
                "scene": one.get("scene"),
                "metric": one.get("metric"),
                "chart_count": one.get("chart_count"),
                "gap_count": one.get("gap_count"),
            }
        )
        if one.get("status") != "ok":
            if not one.get("optional", True):
                gaps.append(
                    {
                        "id": one.get("id"),
                        "title": one.get("id"),
                        "status": "gap",
                        "reason": one.get("reason") or "步骤失败",
                    }
                )
            continue

        kind = one.get("kind")
        result = one.get("result") if isinstance(one.get("result"), dict) else {}

        if kind == "ops_scene":
            md = one.get("markdown_excerpt") or _extract_brief_md(result)
            if md:
                brief_parts.append(md)
            # 急单步：带上精简展示，避免整包 records 撑爆上下文
            if str(one.get("scene") or "") == "urgent-backlog" or one.get("id") == "urgent":
                rows = result.get("result") if isinstance(result.get("result"), dict) else result
                display = None
                if isinstance(rows, dict):
                    display = rows.get("display_rows") or rows.get("markdown_table")
                    urgent_preview = {
                        "scene": one.get("scene"),
                        "definition": result.get("definition") or rows.get("definition"),
                        "total": rows.get("total"),
                        "returned": rows.get("returned"),
                        "display_rows": (display[:8] if isinstance(display, list) else None),
                        "markdown_table": (
                            display if isinstance(display, str) else rows.get("markdown_table")
                        ),
                        "summary": result.get("summary"),
                    }

        if kind == "dashboard" and isinstance(result, dict):
            template_id = str(result.get("template_id") or "")
            board_label = str(result.get("label") or board_label)
            if isinstance(result.get("kpis"), list):
                board_kpis = [k for k in result["kpis"] if isinstance(k, dict)]
            if result.get("skin"):
                board_skin = str(result.get("skin") or board_skin)
            board_presentation = bool(result.get("presentation", True))
            for ch in result.get("charts") or []:
                if isinstance(ch, dict) and ch.get("chart_option"):
                    charts.append(ch)
            for g in result.get("gaps") or []:
                if isinstance(g, dict):
                    gaps.append(g)
            if result.get("markdown_report"):
                brief_parts.append(str(result["markdown_report"]))

    ok_steps = sum(1 for s in step_results if s.get("status") == "ok")
    if ok_steps == 0:
        return {
            "error": "演示剧本各步骤均未成功（请检查 MES 接入与资料包）",
            "playbook_id": spec.get("id"),
            "steps": step_results,
            "gaps": gaps,
            "hint": "可先 list_platform_entities / inspect_mes_profile；勿编造数据。",
        }

    lines = [
        f"## {spec.get('label') or spec.get('id')}",
        "",
        f"- 剧本：`{spec.get('id')}`（{spec.get('_source') or ''}）",
        f"- 步骤成功：{ok_steps}/{len(step_results)}；出图：{len(charts)}；缺口：{len(gaps)}",
        "",
    ]
    for s in step_results:
        if s.get("status") == "ok":
            extra = ""
            if s.get("chart_count") is not None:
                extra = f"（图 {s.get('chart_count')} / 缺口 {s.get('gap_count')}）"
            lines.append(f"- ✅ **{s.get('id')}** {s.get('kind')}{extra}")
        else:
            lines.append(f"- ⚠ **{s.get('id')}**：{s.get('reason') or '跳过'}")

    first = charts[0] if charts else None
    display_label = (
        board_label
        or str(spec.get("label") or "")
        or str(spec.get("id") or "运营看板")
    )
    return {
        "ok": True,
        "demo": True,
        "playbook_id": spec.get("id"),
        "label": display_label,
        "template_id": template_id,
        "source": spec.get("_source"),
        "presentation": board_presentation,
        "skin": board_skin,
        "kpis": board_kpis,
        "steps": step_results,
        "charts": charts,
        "gaps": gaps,
        "chart_count": len(charts),
        "gap_count": len(gaps),
        "brief_markdown": "\n\n".join(brief_parts)[:8000] if brief_parts else "",
        "urgent_preview": urgent_preview,
        # 兼容 SSE 看板 / 单图
        "chart_option": (first or {}).get("chart_option"),
        "title": display_label,
        "chart_type": (first or {}).get("chart_type"),
        "definition": str(spec.get("definition") or "")[:400],
        "caveats": [
            "本结果为运营看板编排；页内汇总勿当全库。",
            "缺口项未编造 KPI。",
        ],
        "layout": (first or {}).get("layout") or {},
        "markdown_report": "\n".join(lines).replace(
            f"## {spec.get('label') or spec.get('id')}",
            f"## {display_label}",
            1,
        ),
        "reply_hint": str(spec.get("reply_hint") or "")
        + " 优先展示运营大屏 KPI+多图；可提示点击图下钻；禁止编造未出现的数。",
    }
