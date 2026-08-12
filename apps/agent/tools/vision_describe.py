"""截图/图片理解：调用视觉模型，把图转成主模型可读的文字上下文。

主对话模型（DeepSeek 等）多为纯文本；同事贴截图时先走本模块，再注入用户消息。
默认对接智谱 GLM-4V（OpenAI 兼容）；也可用 VISION_* 指向任意兼容端点。

「1:1 / 复刻 / 照着做」类意图会走更长的 UI 视觉规格提示，避免只抄文案丢掉色块与图表类型。
"""
from __future__ import annotations

import base64
import logging
import mimetypes
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

_UI_REPLICA_HINT_RE = re.compile(
    r"1\s*:\s*1|1：1|复刻|照着|仿照|按这个|按截图|改成这种|改为这种|做成这种|"
    r"像素级\s*还原|界面效果|跟(?:截图|这个|图)一样|按这个效果|做成这样|"
    r"设计稿|效果图|按图|照图|【用户意图·视觉对齐】",
    re.I,
)
_UI_REDESIGN_HINT_RE = re.compile(
    r"重做|重新设计|重新构图|设计感|不要?照抄|不要按旧|不要按截图|"
    r"杂志排版|彻底区分|新构图|全新(?:构图|排版|设计)",
    re.I,
)

_DEFAULT_PROMPT = (
    "请用中文描述这张截图，供同事排查与答疑。按条理写清楚：\n"
    "1) 画面类型（登录页/列表/表单/报错弹窗/终端等）\n"
    "2) 主要可见文案（标题、按钮、错误信息原文）\n"
    "3) 关键布局与控件\n"
    "4) 若有报错或异常高亮，逐条抄出\n"
    "不要臆造图中没有的内容；控制在 800 字内。"
)

_UI_REPLICA_PROMPT = (
    "这是需要 1:1 / 复刻的前端界面截图。请输出「可交给前端实现」的中文视觉规格，"
    "不要只抄数字 KPI。务必覆盖：\n"
    "1) 整体构图：左右/上下分区、背景色或渐变、主视觉（插画/设备图等）位置\n"
    "2) 顶栏/侧栏/页脚：Logo 文案、公司名、导航或版权原文\n"
    "3) 主内容区模块：每个区块的位置（左/右/上/下）、用途、关键可见文案\n"
    "4) 表单/控件：字段标签、占位符、下拉、勾选项、主按钮文案与大致样式（色/圆角/宽度）\n"
    "5) 图表与色块：类型（仪表盘/折线/柱状/色块底卡等）、主色倾向；"
    "明确是否为深色底、色块 KPI（禁止笼统写成「普通白卡片后台」）\n"
    "6) 叠层/装饰：半透明浮层、阴影、分割线等醒目元素\n"
    "禁止臆造截图中未出现的表格、双柱图或额外菜单。"
    "控制在 1200 字内，分条书写。"
)


def is_image_path(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTS


def is_ui_replica_hint(text: str | None) -> bool:
    """用户话术是否像「按截图复刻 UI」。重做意图不走长视觉规格。"""
    t = str(text or "")
    if re.search(r"(?:不(?:要|必|用)?|别|非|禁止|勿).{0,6}复刻", t):
        # 否定复刻 → 不当视觉对齐
        if _UI_REDESIGN_HINT_RE.search(t):
            return False
    if _UI_REDESIGN_HINT_RE.search(t) and not re.search(
        r"1\s*:\s*1|1：1|按截图复刻|改成这种|做成这种|跟(?:截图|图)一样", t, re.I
    ):
        return False
    return bool(_UI_REPLICA_HINT_RE.search(t))

def _api_key() -> str:
    try:
        from config import Config

        key = (getattr(Config, "VISION_API_KEY", None) or "").strip()
        if key:
            return key
    except Exception:
        pass
    try:
        from settings_store import resolve_setting

        return (
            resolve_setting("VISION_API_KEY", "")
            or resolve_setting("ZHIPU_API_KEY", "")
        )
    except Exception:
        pass
    return (
        os.getenv("VISION_API_KEY", "").strip()
        or os.getenv("ZHIPU_API_KEY", "").strip()
    )


def _base_url() -> str:
    try:
        from config import Config

        raw = (getattr(Config, "VISION_BASE_URL", None) or "").strip()
        if raw:
            return raw.rstrip("/") + "/"
    except Exception:
        pass
    try:
        from settings_store import resolve_setting

        raw = (
            resolve_setting("VISION_BASE_URL", "")
            or resolve_setting("ZHIPU_BASE_URL", "")
        )
        if raw:
            return raw.rstrip("/") + "/"
    except Exception:
        pass
    raw = (
        os.getenv("VISION_BASE_URL", "").strip()
        or os.getenv("ZHIPU_BASE_URL", "").strip()
        or "https://open.bigmodel.cn/api/paas/v4/"
    )
    return raw.rstrip("/") + "/"


def _model() -> str:
    try:
        from config import Config

        m = (getattr(Config, "VISION_MODEL", None) or "").strip()
        if m:
            return m
    except Exception:
        pass
    try:
        from settings_store import resolve_setting

        m = resolve_setting("VISION_MODEL", "")
        if m:
            return m
    except Exception:
        pass
    return (os.getenv("VISION_MODEL", "").strip() or "glm-4v-flash")


def vision_enabled() -> bool:
    flag = os.getenv("VISION_ENABLED", "").strip().lower()
    if flag in ("0", "false", "no", "off"):
        return False
    return bool(_api_key())


def _max_images() -> int:
    try:
        return max(1, min(5, int(os.getenv("VISION_MAX_IMAGES", "3"))))
    except ValueError:
        return 3


def _max_bytes() -> int:
    try:
        return max(100_000, int(os.getenv("VISION_MAX_BYTES", str(8 * 1024 * 1024))))
    except ValueError:
        return 8 * 1024 * 1024


def _mime_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if guessed and guessed.startswith("image/"):
        return guessed
    ext = path.suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
    }.get(ext, "image/png")


def _prompt_for_hint(user_hint: str = "") -> str:
    if is_ui_replica_hint(user_hint):
        return _UI_REPLICA_PROMPT
    return _DEFAULT_PROMPT


def describe_image(path: str | Path, *, user_hint: str = "") -> str:
    """描述单张本地图片；失败时返回简短说明（不抛）。仅允许 data/uploads 下文件。"""
    from tools.upload_paths import resolve_under_uploads

    safe = resolve_under_uploads(
        str(path),
        allowed_suffixes=IMAGE_EXTS,
    )
    if safe is None:
        return f"（拒绝读取非上传目录图片：{Path(path).name}）"
    p = safe
    if not p.is_file():
        return f"（图片不存在：{p.name}）"
    if not is_image_path(p):
        return f"（非图片文件：{p.name}）"
    size = p.stat().st_size
    if size > _max_bytes():
        return f"（图片过大已跳过：{p.name}，{size} bytes）"
    if not vision_enabled():
        return (
            f"（已收到截图 {p.name}，但未配置视觉模型。"
            "请到「系统配置」填写视觉模型 API Key（VISION_API_KEY / 智谱 Key）。）"
        )

    try:
        raw = p.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        data_url = f"data:{_mime_for(p)};base64,{b64}"
        prompt = _prompt_for_hint(user_hint)
        hint = (user_hint or "").strip()
        if hint:
            prompt += f"\n\n用户同时说了：{hint[:600]}"

        from openai import OpenAI

        client = OpenAI(api_key=_api_key(), base_url=_base_url())
        # 智谱多模态对 max_tokens 较敏感，省略以免 1210
        resp = client.chat.completions.create(
            model=_model(),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_url}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            temperature=0.15,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            return f"（视觉模型未返回内容：{p.name}）"
        # 硬顶：模型偶发超长，避免撑爆下游上下文
        if len(text) > 1500:
            text = text[:1480].rstrip() + "…"
        return text
    except Exception as exc:
        logger.warning("vision describe failed for %s: %s", p, exc)
        return f"（看图失败 {p.name}：{exc}）"


def build_image_context_block(
    file_paths: list[str] | None,
    *,
    user_hint: str = "",
) -> str:
    """从附件路径中挑出图片，生成注入主模型的【截图理解】块。"""
    if not file_paths:
        return ""
    from tools.upload_paths import resolve_under_uploads

    images: list[str] = []
    for p in file_paths:
        if not is_image_path(p):
            continue
        safe = resolve_under_uploads(str(p), allowed_suffixes=IMAGE_EXTS)
        if safe is not None:
            images.append(str(safe))
    if not images:
        return ""
    images = images[: _max_images()]
    parts: list[str] = []
    for i, path in enumerate(images, 1):
        name = Path(path).name
        desc = describe_image(path, user_hint=user_hint)
        parts.append(f"### 截图 {i}（{name}）\n{desc}")
    body = "\n\n".join(parts)
    ui_note = ""
    if is_ui_replica_hint(user_hint):
        ui_note = (
            "\n\n【给写码 Agent】以上是视觉规格：实现时以布局/图表类型/色块为准；"
            "禁止把彩色仪表盘改成通用 Element 白卡片 KPI；"
            "禁止增加截图中未出现的表格/双柱等模块。"
        )
    return (
        "【截图理解】以下由视觉模型根据用户粘贴/上传的截图生成，"
        "请结合用户意图使用（改 UI、排错、写码、答疑等），勿声称自己「看到了图」以外的细节：\n\n"
        f"{body}{ui_note}"
    )


def append_image_context(
    message: str,
    file_paths: list[str] | None,
    *,
    max_block_chars: int = 6000,
) -> str:
    """把截图理解块追加到用户消息后。"""
    block = build_image_context_block(file_paths, user_hint=message or "")
    if not block:
        return message or ""
    if len(block) > max_block_chars:
        block = block[: max_block_chars - 20].rstrip() + "\n…(截图理解已截断)"
    base = (message or "").strip()
    if not base:
        return block
    return f"{base}\n\n{block}"
