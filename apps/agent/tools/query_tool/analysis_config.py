"""资料包驱动的分析配置：分组字段、简报口径、可选行业指标包。

换平台时只改 mes_profiles/{id}/ 下配置，不改产品代码。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 通用默认：不绑定任何客户实体 id
_DEFAULT_GROUP_BY_LABELS = ["状态", "优先级", "产线", "工序", "线体"]
_DEFAULT_BRIEF_METRIC_IDS = [
    "wip",
    "unfinished",
    "urgent-unfinished",
    "completed-today",
]
_DEFAULT_METRIC_PACKS: list[str] = []  # 行业包默认不加载，由资料包声明


def load_analysis_config() -> dict[str, Any]:
    """合并：内置默认 ← profile.json.analysis ← analysis.json。"""
    cfg: dict[str, Any] = {
        "group_by_labels": list(_DEFAULT_GROUP_BY_LABELS),
        "brief_metric_ids": list(_DEFAULT_BRIEF_METRIC_IDS),
        "metric_packs": list(_DEFAULT_METRIC_PACKS),
        "brief_metric_limit": 4,
        "dashboard_template": "pcb_ops",
        "value_labels": {},
        "analysis_demos": {},
        "source": "defaults",
    }
    try:
        from mes_profile import profile_dir

        pdir = profile_dir()
    except Exception:
        pdir = None
    if pdir is None:
        return cfg

    # profile.json 内嵌 analysis / metric_packs
    meta_path = pdir / "profile.json"
    if meta_path.is_file() and meta_path.stat().st_size > 0:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        if isinstance(meta, dict):
            if isinstance(meta.get("metric_packs"), list):
                cfg["metric_packs"] = [
                    str(x).strip() for x in meta["metric_packs"] if str(x).strip()
                ]
                cfg["source"] = "profile.json"
            nested = meta.get("analysis")
            if isinstance(nested, dict):
                _merge_analysis_dict(cfg, nested)
                cfg["source"] = "profile.json"

    analysis_path = pdir / "analysis.json"
    if analysis_path.is_file() and analysis_path.stat().st_size > 0:
        try:
            extra = json.loads(analysis_path.read_text(encoding="utf-8"))
        except Exception:
            extra = {}
        if isinstance(extra, dict):
            _merge_analysis_dict(cfg, extra)
            if isinstance(extra.get("metric_packs"), list):
                cfg["metric_packs"] = [
                    str(x).strip() for x in extra["metric_packs"] if str(x).strip()
                ]
            cfg["source"] = "analysis.json"
    return cfg


def _merge_analysis_dict(cfg: dict[str, Any], extra: dict[str, Any]) -> None:
    if isinstance(extra.get("group_by_labels"), list) and extra["group_by_labels"]:
        cfg["group_by_labels"] = [
            str(x).strip() for x in extra["group_by_labels"] if str(x).strip()
        ]
    if isinstance(extra.get("brief_metric_ids"), list) and extra["brief_metric_ids"]:
        cfg["brief_metric_ids"] = [
            str(x).strip() for x in extra["brief_metric_ids"] if str(x).strip()
        ]
    if extra.get("brief_metric_limit") is not None:
        try:
            cfg["brief_metric_limit"] = max(1, min(int(extra["brief_metric_limit"]), 12))
        except (TypeError, ValueError):
            pass
    if extra.get("dashboard_template"):
        raw = str(extra.get("dashboard_template") or "").strip()
        safe = "".join(c for c in raw if c.isalnum() or c in "-_")
        if safe:
            cfg["dashboard_template"] = safe
    # 枚举展示名：按字段角色合并（status/priority…），资料包覆盖内置
    vl = extra.get("value_labels")
    if isinstance(vl, dict):
        bucket: dict[str, dict[str, str]] = cfg.setdefault("value_labels", {})
        for role, mapping in vl.items():
            if not isinstance(mapping, dict):
                continue
            key = str(role).strip().lower()
            role_map = bucket.setdefault(key, {})
            for raw_v, label in mapping.items():
                if raw_v is None or label is None:
                    continue
                role_map[str(raw_v).strip()] = str(label).strip()
    # 分析演示剧本覆盖（enabled / aliases / steps 由 analysis_demo 合并）
    demos = extra.get("analysis_demos")
    if isinstance(demos, dict):
        bucket: dict[str, Any] = cfg.setdefault("analysis_demos", {})
        for did, ov in demos.items():
            if isinstance(ov, dict):
                bucket[str(did).strip()] = dict(ov)


def packs_dir() -> Path:
    return Path(__file__).resolve().parent / "metric_packs"
