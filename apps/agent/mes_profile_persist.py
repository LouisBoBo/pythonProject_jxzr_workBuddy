"""MES 资料包持久化（OpenAPI / entities 合并写入，供 API 路由与本机写码自动同步复用）。"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_path(path: str) -> str:
    s = str(path or "").strip().replace("\\", "/")
    if not s.startswith("/"):
        s = "/" + s
    return s.rstrip("/") or "/"


def merge_entities(
    existing: list[dict[str, Any]],
    generated: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """合并实体目录：新增/更新来自 OpenAPI 的项，保留旧目录中未出现在新文档里的实体。"""
    by_id: dict[str, dict[str, Any]] = {}
    by_path: dict[str, dict[str, Any]] = {}
    for item in existing or []:
        if not isinstance(item, dict):
            continue
        eid = str(item.get("id") or "").strip()
        if eid:
            by_id[eid] = item
        p = _normalize_path(str(item.get("path") or ""))
        if p != "/":
            by_path[p] = item

    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    added: list[str] = []
    updated: list[str] = []

    for gen in generated or []:
        if not isinstance(gen, dict):
            continue
        gid = str(gen.get("id") or "").strip()
        if not gid:
            continue
        gpath = _normalize_path(str(gen.get("path") or ""))
        old = by_id.get(gid) or (by_path.get(gpath) if gpath != "/" else None)

        if old:
            out = dict(old)
            for key in ("path", "paging", "list_keys", "fields", "columns", "ops"):
                if gen.get(key) and not out.get(key):
                    out[key] = gen[key]
            old_aliases = {
                str(x).strip()
                for x in (out.get("aliases") or [])
                if str(x).strip()
            }
            new_aliases = {
                str(x).strip()
                for x in (gen.get("aliases") or [])
                if str(x).strip()
            }
            for label in (out.get("label"), gen.get("label")):
                if label and str(label).strip():
                    old_aliases.add(str(label).strip())
            out["aliases"] = sorted(old_aliases | new_aliases)
            if gen.get("label") and not str(out.get("label") or "").strip():
                out["label"] = gen["label"]
            merged.append(out)
            eid = str(out.get("id") or gid).strip()
            updated.append(eid)
            seen_ids.add(eid)
        else:
            merged.append(dict(gen))
            added.append(gid)
            seen_ids.add(gid)

    preserved: list[str] = []
    for old in existing or []:
        if not isinstance(old, dict):
            continue
        oid = str(old.get("id") or "").strip()
        if oid and oid not in seen_ids:
            merged.append(dict(old))
            preserved.append(oid)
            seen_ids.add(oid)

    stats = {
        "added": added,
        "updated": updated,
        "preserved": preserved,
        "total": len(merged),
    }
    return merged, stats


def _merge_meta(
    old_meta: dict[str, Any] | None,
    new_meta: dict[str, Any],
    *,
    source_url: str = "",
    sync_note: str = "",
    preserve_runtime: bool = False,
) -> dict[str, Any]:
    meta = dict(old_meta or {})
    for key, val in new_meta.items():
        if key in {"entity_count", "generated_from", "api_title", "note"}:
            meta[key] = val
        elif key in {"api_base", "path_prefix", "login_paths", "login_required_fields"}:
            if preserve_runtime and meta.get(key):
                continue
            if val and not meta.get(key):
                meta[key] = val
            elif val:
                meta[key] = val
    if source_url:
        if not (preserve_runtime and meta.get("source_url")):
            meta["source_url"] = source_url
    if sync_note:
        meta["auto_sync_note"] = sync_note
    meta["auto_sync_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta["entity_count"] = new_meta.get("entity_count") or meta.get("entity_count")
    return meta


def persist_openapi_text(
    profile_id: str,
    text: str,
    *,
    source_url: str = "",
    merge_existing: bool = True,
    reload_agent: bool = True,
    sync_note: str = "",
    preserve_runtime: bool = False,
) -> dict[str, Any]:
    """写入 openapi.json，并按需合并写入 entities.json。"""
    from mes_profile import (
        ENTITIES_FILENAME,
        OPENAPI_FILENAME,
        ensure_profile_dir,
        profile_status,
    )
    from tools.query_tool.openapi_to_entities import (
        enrich_entity_aliases,
        generate_entities_from_openapi_text,
    )

    generated = generate_entities_from_openapi_text(text)
    new_entities = generated.get("entities") or []
    if not new_entities:
        raise ValueError("接口文档未解析到任何可查列表接口，已跳过资料包更新")

    new_meta = dict(generated.get("meta") or {})
    if source_url:
        from mes_profile import origin_from_docs_url
        from safe_http import assert_http_url_allowed, same_http_origin

        new_meta["source_url"] = source_url
        origin = origin_from_docs_url(source_url)
        if origin:
            try:
                origin = assert_http_url_allowed(origin, what="接口文档主机")
            except ValueError:
                origin = ""
        doc_base = str(new_meta.get("api_base") or "")
        if origin:
            if doc_base and not same_http_origin(doc_base, origin):
                new_meta["api_base"] = origin
            elif not doc_base:
                new_meta["api_base"] = origin

    root = ensure_profile_dir(profile_id)
    entities_path = root / ENTITIES_FILENAME
    old_payload: dict[str, Any] = {}
    if merge_existing and entities_path.is_file():
        try:
            loaded = json.loads(entities_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                old_payload = loaded
        except Exception:
            old_payload = {}

    old_entities = old_payload.get("entities") if isinstance(old_payload.get("entities"), list) else []
    if merge_existing and old_entities:
        entities, merge_stats = merge_entities(old_entities, new_entities)
    else:
        entities = list(new_entities)
        merge_stats = {
            "added": [str(e.get("id") or "") for e in entities if e.get("id")],
            "updated": [],
            "preserved": [],
            "total": len(entities),
        }

    entities = [enrich_entity_aliases(dict(e)) for e in entities]

    meta = _merge_meta(
        old_payload.get("meta") if isinstance(old_payload.get("meta"), dict) else None,
        {**new_meta, "entity_count": len(entities)},
        source_url=source_url,
        sync_note=sync_note,
        preserve_runtime=preserve_runtime,
    )

    try:
        parsed = json.loads(text)
        openapi_text = json.dumps(parsed, ensure_ascii=False, indent=2) + "\n"
    except json.JSONDecodeError:
        openapi_text = text

    (root / OPENAPI_FILENAME).write_text(openapi_text, encoding="utf-8")
    entities_dest = root / ENTITIES_FILENAME
    payload = json.dumps({"entities": entities, "meta": meta}, ensure_ascii=False, indent=2) + "\n"
    tmp = entities_dest.with_name(f".{ENTITIES_FILENAME}.tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(entities_dest)
    finally:
        if tmp.is_file():
            try:
                tmp.unlink()
            except OSError:
                pass

    if reload_agent:
        _reload_after_profile_change()

    logger.info(
        "mes openapi persisted profile=%s entities=%s added=%s preserved=%s source=%s",
        profile_id,
        len(entities),
        len(merge_stats.get("added") or []),
        len(merge_stats.get("preserved") or []),
        source_url or "inline",
    )
    return {
        "ok": True,
        "entity_count": len(entities),
        "entity_ids": [e.get("id") for e in entities],
        "merge": merge_stats,
        "meta": meta,
        "profile_dir": str(root),
        **profile_status(),
    }


def persist_schema_text(
    profile_id: str,
    text: str,
    *,
    reload_agent: bool = True,
) -> dict[str, Any]:
    from mes_profile import SCHEMA_FILENAME, ensure_profile_dir, profile_status

    if not str(text or "").strip():
        raise ValueError("表结构内容为空")
    root = ensure_profile_dir(profile_id)
    dest = root / SCHEMA_FILENAME
    dest.write_text(text, encoding="utf-8")
    if reload_agent:
        _reload_after_profile_change()
    return {"ok": True, "saved": str(dest), **profile_status()}


def _reload_after_profile_change() -> None:
    from mes_profile import invalidate_mes_data_caches

    invalidate_mes_data_caches()
    try:
        from agent_wrapper import AgentRunner

        AgentRunner().reset_agent()
    except Exception as exc:  # noqa: BLE001
        logger.warning("资料包变更后 reset_agent 失败: %s", exc)
