"""运行摘要 → 纯文本 / 企业微信 Markdown（与前端 automationRunSummary.js 对齐）。"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

URL_RE = re.compile(r"https?://[^\s<>[\]()，。；;]+", re.I)
SOURCE_META_PAREN_RE = re.compile(
    r"[（(][^）)]*(?:接口未返回|检索接口|未返回\s*URL|未返回可直接引用|检索结果未附|检索结果未返回|"
    r"搜索结果未返回|未附可点击链接|未返回可点击链接)[^）)]*[）)]",
    re.I,
)
TRAILING_DATE_SOURCE_RE = re.compile(r"[（(]([^）)]*\d{4}-\d{2}-\d{2}[^）)]*)[）)]\s*$")
LEADING_DATE_BODY_RE = re.compile(r"^\s*[（(]([^）)]*\d{4}-\d{2}-\d{2}[^）)]*)[）)]\s*")
TITLE_DATE_RE = re.compile(r"[（(]([^）)]*\d{4}-\d{2}-\d{2}[^）)]*)[）)]")
META_FOOTER_RE = re.compile(r"\n---+\s*\n+\s*(?:\*\*)?(?:说明|数据说明)(?:\*\*)?[：:][\s\S]*$")
META_INLINE_RE = re.compile(r"\n\s*(?:说明|数据说明)[：:][\s\S]*$")
SOURCE_LINE_RE = re.compile(
    r"(?:^|\n)\s*(?:[-*]\s+)?来源[：:]\s*([\s\S]*?)(?=\n---|\n\s*(?:\*\*)?(?:说明|补充说明|趋势小结|小结|数据缺口|数据说明)[：:]|$)"
)
DETAIL_LINE_RE = re.compile(
    r"(?:^|\n)\s*(?:[-*]\s+)?细分[：:]\s*([\s\S]*?)(?=\n---|\n\s*(?:\*\*)?(?:说明|补充说明|趋势小结|小结|数据缺口|数据说明)[：:]|$)"
)
POINTS_LINE_RE = re.compile(
    r"(?:^|\n)\s*(?:[-*]\s+)?要点[：:]\s*([\s\S]*?)(?=\n\s*(?:[-*]\s+)?(?:来源|细分)[：:]|$)"
)
NEWS_ITEM_RE = re.compile(r"\*\*(\d+)\.\s*([\s\S]*?)\*\*")
PLAIN_NEWS_ITEM_RE = re.compile(r"(?:^|\n)\s*(\d+)\.\s*([^\n]+)")
WECOM_TEXT_SEP = "- - - - - - - - - - - - - - -"
WECOM_TEXT_MAX_BYTES = 2040
WECOM_MD_MAX_BYTES = 4090
REPORT_SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:#{1,3}\s*)?(?:\*\*)?([一二三四五六七八九十]+、[^\n*]+?)(?:\*\*)?\s*(?:\n|$)"
)
NUMBERED_LINE_RE = re.compile(r"(?:^|\n)\s*(\d+)[.、．]\s*")


def strip_markdown_inline(text: str) -> str:
    raw = str(text or "")
    raw = re.sub(r"\*\*([^*]+)\*\*", r"\1", raw)
    raw = re.sub(r"\*([^*]+)\*", r"\1", raw)
    raw = re.sub(r"`([^`]+)`", r"\1", raw)
    raw = re.sub(r"^#{1,6}\s+", "", raw, flags=re.M)
    return re.sub(r"\s+", " ", raw).strip()


def strip_agent_meta(text: str) -> str:
    raw = str(text or "")
    raw = META_FOOTER_RE.sub("", raw)
    raw = META_INLINE_RE.sub("", raw)
    raw = re.sub(r"^#+\s*昨日生产运营日报[^\n]*\n+", "", raw, flags=re.I | re.M)
    raw = re.sub(r"^>\s[^\n]*\n+", "", raw, flags=re.M)
    raw = re.sub(
        r"^(?:[^\n]*(?:所有数据已取齐|交叉核对|以下为昨日生产运营日报)[^\n]*\n+)*",
        "",
        raw,
        flags=re.I,
    )
    return raw.strip()


def _is_production_daily_report(text: str, automation_name: str = "") -> bool:
    name = str(automation_name or "")
    if re.search(r"生产运营日报|生产日报|昨日生产", name):
        return True
    raw = str(text or "")
    return bool(
        re.search(r"\*\*1\.\s*工单概况\*\*", raw)
        or re.search(r"^1\.\s*工单概况", raw, re.M)
        or re.search(r"一、工单概况", raw)
    )


def _sanitize_source(source: str) -> str:
    raw = str(source or "")
    raw = URL_RE.sub("", raw)
    raw = SOURCE_META_PAREN_RE.sub("", raw)
    raw = re.sub(r"[（(]\s*[）)]", "", raw)
    raw = re.sub(r"\s{2,}", " ", raw)
    raw = re.sub(r"[，,、；;]\s*$", "", raw)
    raw = re.sub(r"[。．]?\s*无原文链接[。．]?", "", raw)
    return raw.strip()


def _extract_trailing_source_meta(text: str) -> tuple[str, str]:
    raw = str(text or "").strip()
    m = TRAILING_DATE_SOURCE_RE.search(raw)
    if not m:
        return raw, ""
    cleaned = raw[: m.start()].rstrip("，,、").strip()
    return cleaned, m.group(1).strip()


def _extract_date_from_title(title: str) -> str:
    matches = list(TITLE_DATE_RE.finditer(str(title or "")))
    if not matches:
        return ""
    return matches[-1].group(1).strip()


def _extract_leading_date_from_body(body: str) -> tuple[str, str]:
    raw = str(body or "")
    m = LEADING_DATE_BODY_RE.match(raw)
    if not m:
        return "", raw
    return m.group(1).strip(), raw[m.end() :]


def _finalize_source(source: str, title: str, lead_date: str) -> str:
    value = str(source or "").strip()
    if not value and lead_date:
        value = lead_date
    if not value:
        value = _extract_date_from_title(title)
    return _sanitize_source(value)


def _strip_item_footer(text: str) -> str:
    raw = str(text or "")
    raw = re.sub(r"\n---[\s\S]*$", "", raw)
    raw = re.sub(r"\n\s*\*\*(?:说明|补充说明|趋势小结|小结)[：:][\s\S]*$", "", raw)
    return raw.strip()


def _parse_news_item_body(body: str) -> tuple[str, str, str, str]:
    raw = _strip_block(_strip_item_footer(body))
    points = ""
    source = ""
    source_label = "来源"
    pm = POINTS_LINE_RE.search(raw)
    dm = DETAIL_LINE_RE.search(raw)
    sm = SOURCE_LINE_RE.search(raw)
    if pm:
        points = re.sub(r"\n+", " ", pm.group(1)).strip()
    if dm:
        source = re.sub(r"\n+", " ", dm.group(1)).strip()
        source_label = "细分"
    elif sm:
        source = re.sub(r"\n+", " ", sm.group(1)).strip()
        source_label = "来源"
    meta = dm or sm
    if not points and meta:
        before = raw[: meta.start()].strip()
        if before:
            points = re.sub(r"\n+", " ", before).strip()
    if not points and not source and raw:
        points = re.sub(r"\n+", " ", raw).strip()
    if points and not source:
        points, trailing = _extract_trailing_source_meta(points)
        if trailing:
            source = trailing
            source_label = "细分"
    urls = URL_RE.findall(source or raw)
    link = urls[0].rstrip(".,;:!?)") if urls else ""
    return points, _sanitize_source(source), link, source_label


def _parse_news_item_fields(title: str, body: str) -> tuple[str, str, str, str]:
    lead_date, rest = _extract_leading_date_from_body(body)
    points, source, link, source_label = _parse_news_item_body(rest)
    return points, _finalize_source(source, title, lead_date), link, source_label


def _strip_block(text: str) -> str:
    raw = str(text or "")
    raw = re.sub(r"\*\*([^*]+)\*\*", r"\1", raw)
    raw = re.sub(r"\*([^*]+)\*", r"\1", raw)
    raw = re.sub(r"`([^`]+)`", r"\1", raw)
    raw = re.sub(r"^#{1,6}\s+", "", raw, flags=re.M)
    raw = re.sub(r"^---+$", "", raw, flags=re.M)
    raw = re.sub(r"^[-*]\s+", "", raw, flags=re.M)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def _split_numbered_lines(text: str) -> list[dict[str, Any]]:
    raw = str(text or "").strip()
    matches = list(NUMBERED_LINE_RE.finditer(raw))
    if not matches:
        return []
    items: list[dict[str, Any]] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = strip_markdown_inline(raw[start:end]).strip()
        if body:
            items.append({"index": int(m.group(1)), "text": body})
    return items


def _parse_news_items_bold(text: str) -> list[dict[str, Any]]:
    cleaned = strip_agent_meta(text)
    matches = list(NEWS_ITEM_RE.finditer(cleaned))
    if not matches:
        return []
    items: list[dict[str, Any]] = []
    for i, m in enumerate(matches):
        index = int(m.group(1))
        title = strip_markdown_inline(m.group(2))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
        body = cleaned[start:end]
        points, source, link, source_label = _parse_news_item_fields(title, body)
        items.append(
            {
                "index": index,
                "title": title,
                "points": points,
                "source": source,
                "source_label": source_label,
                "link": link,
            }
        )
    return items


def _parse_plain_news_items(text: str) -> list[dict[str, Any]]:
    """Agent 常输出 `1. 标题`（无 **），需单独识别。"""
    cleaned = strip_agent_meta(text)
    matches = list(PLAIN_NEWS_ITEM_RE.finditer(cleaned))
    if not matches or int(matches[0].group(1)) != 1:
        return []
    items: list[dict[str, Any]] = []
    for i, m in enumerate(matches):
        index = int(m.group(1))
        title = strip_markdown_inline(m.group(2))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
        body = cleaned[start:end]
        points, source, link, source_label = _parse_news_item_fields(title, body)
        items.append(
            {
                "index": index,
                "title": title,
                "points": points,
                "source": source,
                "source_label": source_label,
                "link": link,
            }
        )
    return items


def _parse_news_items(text: str) -> list[dict[str, Any]]:
    items = _parse_news_items_bold(text)
    if items:
        return items
    return _parse_plain_news_items(text)


def _find_first_news_index(raw: str) -> int:
    cleaned = strip_agent_meta(raw)
    m = re.search(r"(?:^|\n)\s*1\.\s+", cleaned)
    if m:
        return m.start()
    idx = raw.find("**1.")
    return idx if idx >= 0 else -1


def _news_intro(raw: str) -> str:
    idx = _find_first_news_index(raw)
    if idx > 0:
        return _strip_block(strip_agent_meta(raw[:idx]))
    return ""


def _parse_report_sections(text: str) -> dict[str, Any] | None:
    cleaned = _strip_block(strip_agent_meta(text))
    if not re.search(r"[一二三四五六七八九十]+、", cleaned):
        return None
    matches = list(REPORT_SECTION_RE.finditer(cleaned))
    if not matches:
        return None
    first_idx = matches[0].start() or 0
    intro = strip_markdown_inline(cleaned[:first_idx]).strip()
    sections: list[dict[str, Any]] = []
    for i, m in enumerate(matches):
        title = strip_markdown_inline(m.group(1)).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
        body = cleaned[start:end].strip()
        numbered = _split_numbered_lines(body)
        if numbered:
            sections.append({"title": title, "type": "numbered", "items": numbered})
            continue
        bullets = [
            strip_markdown_inline(p).strip()
            for p in re.split(r"\n\s*[-*]\s+", body.lstrip("-* ").strip())
            if strip_markdown_inline(p).strip()
        ]
        if bullets:
            sections.append(
                {
                    "title": title,
                    "type": "bullets",
                    "items": [{"index": j + 1, "text": t} for j, t in enumerate(bullets)],
                }
            )
            continue
        para = strip_markdown_inline(body).strip()
        if para:
            sections.append({"title": title, "type": "text", "items": [{"index": 1, "text": para}]})
    if not sections:
        return None
    return {"intro": intro, "sections": sections}


def _banner_title(kind: str, automation_name: str, summary: str = "") -> str:
    if kind == "news" and _is_production_daily_report(summary, automation_name):
        return "生产日报"
    if kind == "news":
        return "今日精选"
    if kind == "report":
        return "本周简报"
    name = str(automation_name or "").strip()
    return name or "任务摘要"


def parse_run_summary(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {"kind": "empty"}
    items = _parse_news_items(raw)
    if items:
        return {"kind": "news", "intro": _news_intro(raw), "items": items}
    report = _parse_report_sections(raw)
    if report:
        return {"kind": "report", "intro": report["intro"], "sections": report["sections"]}
    paragraphs = [p.strip() for p in _strip_block(strip_agent_meta(raw)).split("\n\n") if p.strip()]
    return {"kind": "plain", "paragraphs": paragraphs}


def format_plain_text(summary: str, automation_name: str = "") -> str:
    parsed = parse_run_summary(summary)
    if parsed["kind"] == "empty":
        return ""
    lines: list[str] = []
    banner = _banner_title(parsed["kind"], automation_name, summary)
    lines.extend([f"📰 {banner} 📰", ""])
    if parsed["kind"] == "news":
        if parsed.get("intro"):
            lines.extend([parsed["intro"], ""])
        for item in parsed.get("items") or []:
            lines.append(f"{item['index']}. {item['title']}")
            if item.get("points"):
                lines.append(f"要点：{item['points']}")
            if item.get("link"):
                lines.append(f"来源：{item['link']}")
            elif item.get("source"):
                lines.append(f"来源：{item['source']}")
            lines.append("")
    elif parsed["kind"] == "report":
        if parsed.get("intro"):
            lines.extend([parsed["intro"], ""])
        for sec in parsed.get("sections") or []:
            lines.append(sec["title"])
            if sec["type"] == "numbered":
                for row in sec["items"]:
                    lines.append(f"{row['index']}、{row['text']}")
            elif sec["type"] == "bullets":
                for row in sec["items"]:
                    lines.append(f"• {row['text']}")
            else:
                text = sec["items"][0]["text"] if sec.get("items") else ""
                if text:
                    lines.append(text)
            lines.append("")
    else:
        for para in parsed.get("paragraphs") or []:
            lines.extend([para, ""])
    return "\n".join(lines).strip()


def _escape_wecom_md(text: str) -> str:
    return str(text or "").replace("<", "&lt;").strip()


def _md_join(*parts: str) -> str:
    """企微 Markdown 段落间须空一行才分段。"""
    return "\n\n".join(p for p in parts if p and str(p).strip())


def _format_news_item_text(item: dict[str, Any]) -> list[str]:
    label = str(item.get("source_label") or "来源")
    lines = [f"{item['index']}. {item['title']}", ""]
    if item.get("points"):
        lines.extend([f"要点：{item['points']}", ""])
    if item.get("link"):
        lines.extend([f"{label}：{item['link']}", ""])
    elif item.get("source"):
        lines.extend([f"{label}：{item['source']}", ""])
    return lines


def _format_news_item_md(item: dict[str, Any]) -> str:
    label = str(item.get("source_label") or "来源")
    chunks: list[str] = [f"**{item['index']}. {_escape_wecom_md(item['title'])}**"]
    if item.get("points"):
        chunks.append(f"要点：{_escape_wecom_md(item['points'])}")
    if item.get("link"):
        chunks.append(f"[{label}]({item['link']})")
    elif item.get("source"):
        chunks.append(f"{label}：{_escape_wecom_md(item['source'])}")
    return _md_join(*chunks)


def _truncate_bytes(text: str, max_bytes: int, note: str) -> str:
    content = str(text or "").strip()
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes:
        return content
    budget = max_bytes - len(note.encode("utf-8"))
    return encoded[: max(0, budget)].decode("utf-8", errors="ignore").rstrip() + note


def format_wecom_text(
    summary: str,
    automation_name: str = "",
    *,
    started_at: int | None = None,
) -> str:
    """企微 text 单条消息（换行可靠；上限约 2040 字节）。"""
    parsed = parse_run_summary(summary)
    if parsed["kind"] == "empty":
        return ""
    banner = _banner_title(parsed["kind"], automation_name, summary)
    ts = ""
    if started_at:
        ts = datetime.fromtimestamp(int(started_at)).strftime("%Y-%m-%d %H:%M")
    lines: list[str] = [f"📰 {banner}"]
    if ts:
        lines.append(f"{ts} · ZR WorkBuddy 自动推送")
    lines.append("")

    if parsed["kind"] == "news":
        if parsed.get("intro"):
            lines.extend([parsed["intro"], "", WECOM_TEXT_SEP, ""])
        items = parsed.get("items") or []
        for i, item in enumerate(items):
            lines.extend(_format_news_item_text(item))
            if i < len(items) - 1:
                lines.extend([WECOM_TEXT_SEP, ""])
    elif parsed["kind"] == "report":
        if parsed.get("intro"):
            lines.extend([parsed["intro"], "", WECOM_TEXT_SEP, ""])
        for si, sec in enumerate(parsed.get("sections") or []):
            lines.extend([sec["title"], ""])
            if sec["type"] == "numbered":
                for row in sec["items"]:
                    lines.extend([f"{row['index']}、{row['text']}", ""])
            elif sec["type"] == "bullets":
                for row in sec["items"]:
                    lines.extend([f"• {row['text']}", ""])
            else:
                text = sec["items"][0]["text"] if sec.get("items") else ""
                if text:
                    lines.extend([text, ""])
            if si < len(parsed.get("sections") or []) - 1:
                lines.extend([WECOM_TEXT_SEP, ""])
    else:
        for pi, para in enumerate(parsed.get("paragraphs") or []):
            lines.extend([para, ""])
            if pi < len(parsed.get("paragraphs") or []) - 1:
                lines.extend([WECOM_TEXT_SEP, ""])

    lines.extend([WECOM_TEXT_SEP, "", "由 ZR WorkBuddy 自动生成"])
    return "\n".join(lines).strip()


def format_wecom_markdown(
    summary: str,
    automation_name: str = "",
    *,
    started_at: int | None = None,
) -> str:
    parsed = parse_run_summary(summary)
    if parsed["kind"] == "empty":
        return ""
    banner = _banner_title(parsed["kind"], automation_name, summary)
    ts = ""
    if started_at:
        ts = datetime.fromtimestamp(int(started_at)).strftime("%Y-%m-%d %H:%M")
    header = f"## 📰 {_escape_wecom_md(banner)}"
    if ts:
        header += f"\n> {ts} · ZR WorkBuddy 自动推送"

    blocks: list[str] = [header]

    if parsed["kind"] == "news":
        if parsed.get("intro"):
            blocks.append(_escape_wecom_md(parsed["intro"]))
            blocks.append(WECOM_TEXT_SEP)
        items = parsed.get("items") or []
        for i, item in enumerate(items):
            blocks.append(_format_news_item_md(item))
            if i < len(items) - 1:
                blocks.append(WECOM_TEXT_SEP)
    elif parsed["kind"] == "report":
        if parsed.get("intro"):
            blocks.append(_escape_wecom_md(parsed["intro"]))
            blocks.append(WECOM_TEXT_SEP)
        for sec in parsed.get("sections") or []:
            sec_parts: list[str] = [f"**{_escape_wecom_md(sec['title'])}**"]
            if sec["type"] == "numbered":
                for row in sec["items"]:
                    sec_parts.append(f"{row['index']}、{_escape_wecom_md(row['text'])}")
            elif sec["type"] == "bullets":
                for row in sec["items"]:
                    sec_parts.append(f"• {_escape_wecom_md(row['text'])}")
            else:
                text = sec["items"][0]["text"] if sec.get("items") else ""
                if text:
                    sec_parts.append(_escape_wecom_md(text))
            blocks.append(_md_join(*sec_parts))
    else:
        for para in parsed.get("paragraphs") or []:
            blocks.append(_escape_wecom_md(para))

    blocks.extend([WECOM_TEXT_SEP, "由 ZR WorkBuddy 自动生成"])
    content = _md_join(*blocks)
    note = "\n\n…（内容过长已截断，完整版见 WorkBuddy 运行记录）"
    return _truncate_bytes(content, WECOM_MD_MAX_BYTES, note)


def format_wecom_push(
    summary: str,
    automation_name: str = "",
    *,
    started_at: int | None = None,
) -> tuple[str, str]:
    """生成单条企微推送：(msgtype, content)。短内容 text，长内容 markdown（4096）。"""
    text = format_wecom_text(summary, automation_name, started_at=started_at)
    if not text:
        return "", ""
    note = "\n\n…（内容过长已截断，完整版见 WorkBuddy 运行记录）"
    if len(text.encode("utf-8")) <= WECOM_TEXT_MAX_BYTES:
        return "text", text
    md = format_wecom_markdown(summary, automation_name, started_at=started_at)
    if md:
        return "markdown", md
    return "text", _truncate_bytes(text, WECOM_TEXT_MAX_BYTES, note)
