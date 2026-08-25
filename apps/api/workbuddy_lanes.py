"""WorkBuddy 车道路由与审核终稿清洗（从 agent_wrapper 抽出，便于单测）。

code_dev / code_review / paste_code 对等互斥：
**优先**显式 ``page_context.workbuddy_lane``（结构化协议）；
仅当缺失时才回退消息内确认标记（兼容旧客户端，可观测）。
"""
from __future__ import annotations

import logging
import re
from typing import Literal, NamedTuple

logger = logging.getLogger(__name__)

LANE_CODE_DEV = "code_dev"
LANE_CODE_REVIEW = "code_review"
LANE_PASTE_CODE = "paste_code"

KNOWN_LANES = frozenset({LANE_CODE_DEV, LANE_CODE_REVIEW, LANE_PASTE_CODE})

LaneSource = Literal["explicit", "marker", "none"]


class LaneResolve(NamedTuple):
    lane: str | None
    source: LaneSource


CODE_DEV_MARKERS = (
    "【写码需求讨论",
    "【写码仓库已确认】",
    ":::cursor_dev_options",
    ":::cursor_dev_propose",
    "【系统强制路由·Cursor 写码】",
)

CODE_REVIEW_MARKERS = (
    "【Git仓库已确认】",
    "【本机工程已确认】",
    "【系统强制路由·公开 Git 全仓审核】",
    "【系统强制路由·本机代码审核】",
)

# 与 cursor_dev.prompts.should_attach_shot_images 对齐的本地兜底
_REDESIGN_SKIP_VISION_RE = re.compile(
    r"重做|重新设计|重新构图|设计感|不要?照抄|不要按旧|不要按截图|"
    r"杂志排版|杂志风|彻底区分|新构图|全新(?:构图|排版|设计|工业)",
    re.I,
)
_STRONG_SHOT_KEEP_VISION_RE = re.compile(
    r"1\s*:\s*1|1：1|按截图复刻|像素级\s*还原|"
    r"(?:照着|仿照).{0,6}(?:做|改)|改成这种|做成这种|改为这种|按这个界面|"
    r"红框|红圈|黄框|蓝框|框选|圈出|标注|框处",
    re.I,
)
# 前端 buildCodingDiscussPrompt 会注入「必须有设计感」等规则，不能拿整段去判 skip vision
_INJECT_LINE_RE = re.compile(
    r"【(?:写码需求讨论|交互铁律|意图规划|产品设计|截图即设计稿|按截图修改|"
    r"任务档位|系统强制路由|本会话已选定|已锁定技术栈|本轮用户原话|"
    r"已锁定技术栈 \+|按截图修改 ·|截图即设计稿 ·)[^】]*】[^\n]*",
    re.I,
)


def user_utterance_for_vision_policy(text: str) -> str:
    """抽出用户原话，避免注入块里的「设计感/禁止照抄」误关视觉。"""
    t = str(text or "")
    matches = list(re.finditer(r"用户说[：:]\s*", t))
    if matches:
        rest = t[matches[-1].end() :]
        cut = re.search(r"\n【|\n:::", rest)
        return (rest[: cut.start()] if cut else rest).strip()
    cleaned = _INJECT_LINE_RE.sub(" ", t)
    cleaned = re.sub(r":::[\\s\\S]*?:::", " ", cleaned)
    return cleaned.strip()


def should_attach_shot_images_for_discuss(text: str) -> bool:
    raw = text or ""
    # 红框/标注/强复刻：整段里出现也必须看图（即使用户原话抽取出错）
    if _STRONG_SHOT_KEEP_VISION_RE.search(raw):
        return True
    t = user_utterance_for_vision_policy(raw)
    if _STRONG_SHOT_KEEP_VISION_RE.search(t):
        return True
    if _REDESIGN_SKIP_VISION_RE.search(t):
        return False
    try:
        from cursor_dev.prompts import should_attach_shot_images

        return should_attach_shot_images(t)
    except Exception:
        return True


IDE_REPORT_MARKERS = (
    "## 🔍 代码审核报告",
    "🔍 代码审核报告",
    "## 代码审核报告",
    "代码审核报告",
)


def normalize_workbuddy_lane(raw: object) -> str | None:
    """校验/归一化显式车道；未知值视为未声明（勿静默当 MES）。"""
    text = str(raw or "").strip()
    if not text:
        return None
    if text in KNOWN_LANES:
        return text
    logger.warning("忽略未知 workbuddy_lane=%r（仅允许 %s）", text, sorted(KNOWN_LANES))
    return None


def resolve_workbuddy_lane_detail(
    message: str = "",
    ctx: dict | None = None,
    *,
    log_marker_fallback: bool = True,
) -> LaneResolve:
    """解析车道，并标明来源（explicit / marker / none）。"""
    ctx = ctx or {}
    explicit = normalize_workbuddy_lane(ctx.get("workbuddy_lane"))
    if explicit:
        return LaneResolve(explicit, "explicit")

    m = message or ""
    has_dev = (
        any(x in m for x in CODE_DEV_MARKERS)
        or bool(ctx.get("cursor_dev_lane"))
        or bool(str(ctx.get("cursor_dev_repo") or "").strip())
    )
    has_review = (
        any(x in m for x in CODE_REVIEW_MARKERS)
        or bool(str(ctx.get("git_repo_url") or "").strip())
        or bool(str(ctx.get("ide_workspace_root") or "").strip())
    )

    lane: str | None = None
    if has_dev and has_review:
        if any(x in m for x in CODE_DEV_MARKERS) and not any(
            x in m for x in ("【Git仓库已确认】", "【本机工程已确认】")
        ):
            lane = LANE_CODE_DEV
        elif any(x in m for x in ("【Git仓库已确认】", "【本机工程已确认】")):
            lane = LANE_CODE_REVIEW
        else:
            lane = None
    elif has_dev:
        lane = LANE_CODE_DEV
    elif has_review:
        lane = LANE_CODE_REVIEW

    if lane is None:
        return LaneResolve(None, "none")

    if log_marker_fallback:
        logger.info(
            "workbuddy_lane 未显式声明，回退确认标记 → %s（请前端传 page_context.workbuddy_lane）",
            lane,
        )
    return LaneResolve(lane, "marker")


def resolve_workbuddy_lane(message: str = "", ctx: dict | None = None) -> str | None:
    """根据本轮显式车道声明 / 确认标记解析意图分支。

    返回 LANE_CODE_DEV | LANE_CODE_REVIEW | LANE_PASTE_CODE | None。
    优先 ``workbuddy_lane``；缺失才认标记。
    """
    return resolve_workbuddy_lane_detail(message, ctx).lane


def is_cursor_dev_coding_lane(message: str = "", ctx: dict | None = None) -> bool:
    """兼容旧调用：是否为写码分支。"""
    return resolve_workbuddy_lane(message, ctx) == LANE_CODE_DEV


def find_ide_report_start(buf: str) -> int:
    best = -1
    for m in IDE_REPORT_MARKERS:
        i = buf.find(m)
        if i >= 0 and (best < 0 or i < best):
            best = i
    return best


def drop_leading_english_aside(buf: str) -> str:
    """丢掉终稿前的英文旁白行，保留从中文/报告标题起的内容。"""
    if not buf:
        return buf
    idx = find_ide_report_start(buf)
    if idx >= 0:
        return buf[idx:]
    lines = buf.splitlines(keepends=True)
    kept: list[str] = []
    started = False
    for line in lines:
        raw = line.strip()
        if not started:
            if not raw:
                continue
            letters = [c for c in raw if c.isalpha()]
            ascii_letters = [c for c in letters if ord(c) < 128]
            if letters and len(ascii_letters) / max(1, len(letters)) > 0.85:
                continue
            if re.match(
                r"^(Now |Let me |I have |Here is |I'll |I will |Compiling |Based on )",
                raw,
                re.I,
            ):
                continue
            started = True
        kept.append(line)
    return "".join(kept) if kept else ""


def sanitize_page_context_lanes(page_context: dict | None) -> dict | None:
    """写入请求上下文前规范化 workbuddy_lane（未知值清空）。"""
    if not page_context or not isinstance(page_context, dict):
        return page_context
    if "workbuddy_lane" not in page_context:
        return page_context
    out = dict(page_context)
    norm = normalize_workbuddy_lane(out.get("workbuddy_lane"))
    if norm:
        out["workbuddy_lane"] = norm
    else:
        out.pop("workbuddy_lane", None)
    return out
