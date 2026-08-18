"""实体守卫纯规则（无 LangChain 依赖，可供冒烟脚本直接引用）。

对照**当前资料包**可查对象目录，不写死某一套 MES 的实体 id。
"""
from __future__ import annotations

from typing import Any

GUARD_TOOLS = frozenset(
    {
        "query_platform_data",
        "summarize_platform_data",
        "describe_entity",
        "export_platform_data",
        "import_file_to_platform",
    }
)


def _terms(entity: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    label = str(entity.get("label") or "").strip()
    if len(label) >= 2:
        terms.append(label)
    for a in entity.get("aliases") or []:
        t = str(a or "").strip()
        if len(t) >= 2 and t not in terms:
            terms.append(t)
    eid = str(entity.get("id") or "").strip()
    if eid and eid not in terms:
        terms.append(eid)
        spaced = eid.replace("-", " ").replace("_", " ")
        if spaced != eid and spaced not in terms:
            terms.append(spaced)
    return terms


def _hit(entity: dict[str, Any], user_text: str) -> tuple[int, str]:
    """用户原文命中该实体别名的最长分数。"""
    if not user_text:
        return 0, ""
    text_l = user_text.lower()
    best = (0, "")
    for t in _terms(entity):
        tl = t.lower()
        if t in user_text or tl in text_l:
            score = len(t)
            if score > best[0]:
                best = (score, t)
    return best


def _load_catalog() -> list[dict[str, Any]]:
    try:
        from tools.query_tool.entity_catalog import load_catalog

        return list(load_catalog() or [])
    except Exception:
        return []


def guard_mismatch_tip(entity: str, user_text: str) -> str | None:
    """若所选实体与用户说法明显冲突，提示改用目录里更匹配的 id。

    只依据当前 catalog 的 label/aliases；目录没有的 id 不会被当成「标准答案」。
    """
    if not entity or not user_text:
        return None
    catalog = _load_catalog()
    if not catalog:
        return None

    chosen_key = entity.strip()
    chosen_l = chosen_key.lower()
    chosen_rec: dict[str, Any] | None = None
    ranked: list[tuple[int, str, str, str]] = []  # score, eid, term, eid

    for rec in catalog:
        eid = str(rec.get("id") or "")
        if not eid:
            continue
        if eid == chosen_key or eid.lower() == chosen_l:
            chosen_rec = rec
        score, term = _hit(rec, user_text)
        if score:
            ranked.append((score, eid, term, eid))

    if not ranked:
        return None

    ranked.sort(key=lambda x: x[0], reverse=True)
    best_score, best_id, best_term, _ = ranked[0]
    if len(ranked) > 1 and ranked[1][0] == best_score and ranked[1][1] != best_id:
        return None  # 并列命中，不拦
    if best_id.lower() == chosen_l:
        return None

    chosen_score = 0
    if chosen_rec:
        chosen_score, _ = _hit(chosen_rec, user_text)
    if chosen_score > 0:
        return None  # 所选实体别名也出现在用户话里，可能是并列查询

    if best_score < 2:
        return None

    return (
        f"实体守卫：用户说法更像「{best_term}」（`{best_id}`），"
        f"但工具参数用了 `{chosen_key}`。"
        f"请改用 entity='{best_id}' 后重试，不要用其它对象数据充数。"
        "实体 id 以当前资料包目录为准。"
    )
