"""写码会话系统 Prompt 拼装。"""
from __future__ import annotations

import re
from typing import Iterable

# 强视觉对齐：效果要跟截图一样（不要求用户必须说「1:1」）
_STRONG_SHOT_RE = re.compile(
    r"1\s*:\s*1|1：1|按截图复刻|像素级\s*还原|真正\s*1\s*:\s*1|"
    r"(?:照着|仿照).{0,8}(?:做|改|还原)|改成这种|做成这种|改为这种|按这个界面|"
    r"跟(?:着)?(?:截图|这个|图)一样|和(?:截图|这个|图里|图上)一样|"
    r"做成图里|改成图上|做成这样|调成这种|长这样|"
    r"按这个效果|效果跟.{0,10}一样|按图(?:还原|实现|做)|照图|"
    r"还原成|设计稿|效果图|"
    r"(?:按|参考)(?:这个|此|该)?(?:界面|页面|设计稿|效果图|UI\s*稿)",
    re.I,
)
# 弱截图残留（旧 propose /【截图理解】/「按截图位置」）；可被「重做」盖过
_UI_SHOT_RE = re.compile(
    r"【截图理解】|1\s*:\s*1|1：1|复刻|照着做|仿照|按截图|改成这种|做成这种|按这个界面|"
    r"视觉布局（按截图|五卡布局与截图|与截图一致|"
    r"跟(?:截图|图)一样|按这个效果|设计稿|效果图",
    re.I,
)
# 按截图做「局部修改」（不是整页复刻）
_GUIDED_EDIT_RE = re.compile(
    r"(?:按|根据|参考|对照)截图.{0,16}(?:改|调|修|换|动)|"
    r"截图里.{0,20}(?:改|调|修|做成|换成)|"
    r"图上.{0,16}(?:按钮|颜色|布局|顶栏|侧栏|表单|Logo|logo|间距).{0,10}(?:改|调|修)|"
    r"把.{0,24}(?:改成|换成|调成).{0,16}(?:截图|图里|图上)|"
    r"(?:只改|仅改|先改).{0,16}(?:截图|图里|图上)|"
    r"【用户意图·按图修改】",
    re.I,
)
# 用户要重新设计（高于弱截图残留）。避免裸「全新/重写」误伤非 UI 需求。
_REDESIGN_RE = re.compile(
    r"重做|重新设计|重新构图|换个布局|换布局|"
    r"(?:页面|界面|概览|看板|仪表盘|首页).{0,12}重写|"
    r"重写.{0,12}(?:页面|界面|概览|看板|仪表盘|首页)|"
    r"更好看|设计感|有设计感|"
    r"不要?照抄|别照抄|不要?像首页|不要?雷同|不要?套模板|"
    r"不要按旧|不要按截图|非按截图|不要五卡|非五卡|"
    r"全新(?:构图|排版|设计|工业)|杂志排版|杂志风|彻底区分|新排版|新构图",
    re.I,
)

_REDESIGN_BANNER_MARK = "【本轮最高指令 · 重新设计"
_REDESIGN_BANNER_RE = re.compile(
    r"^【本轮最高指令 · 重新设计[^\n]*】\n(?:- [^\n]*\n)*\n*",
)

# 纯布局/滚动/溢出：缩小探索面
_CSS_LAYOUT_RE = re.compile(
    r"overflow(?:-x|-y)?|100vw|100vh|max-width\s*:\s*100|"
    r"滚动条?|横向滚动|横向溢出|超出屏幕|X\s*方向|视口宽度|撑破|"
    r"视口固定|页面固定|整体滚动|框架滚动|"
    r"侧边栏.*滚动|菜单.*滚动|内容区.*滚动|"
    r"仅.*样式|纯\s*CSS|只改\s*(样式|CSS|布局)|"
    r"不[改动变].{0,6}(视觉|配色|图表|表格数据|卡片)|"
    r"布局壳|css[_\s-]?only|layout[_\s-]?shell|"
    r"自适应.*宽度|完整展示|无横向|"
    r"【任务档位\s*[:：]\s*css_layout】",
    re.I,
)

_HEAVY_FEATURE_RE = re.compile(
    r"新接口|数据库|迁移|登录鉴权|权限模型|重构整个|从零|新建项目|CRUD|后端API",
    re.I,
)

_PATH_RE = re.compile(
    r"(?:^|[\s`'\"(（:：、，,])((?:[\w.-]+/)+[\w.-]+\.(?:vue|tsx?|jsx?|css|scss|sass|less|html))",
    re.I,
)

_TIER_TAG_RE = re.compile(
    r"【任务档位\s*[:：]\s*(css_layout|ui_visual|default)】",
    re.I,
)

# 通用交付物结构（不写死业务名）；词干宜短，避免吞掉整句
_DELIVERABLE_RE = re.compile(
    r"((?:[\u4e00-\u9fff]{2,10})|(?:[A-Za-z][A-Za-z0-9_-]{1,24}))(?:界面|页面|模块|功能|视图|看板)",
)
_NEW_DELIVERABLE_ACTION_RE = re.compile(
    r"(?:新(?:界面|页面|模块|功能)|(?:开发|实现|新增|做|写|搭建|建设).{0,20}(?:模块|界面|页面|功能))",
    re.I,
)
_CONFIRMED_REQ_RE = re.compile(
    r"验收|【任务档位|视觉布局|改动点\s*[:：]|本轮范围|页面身份|禁止照抄",
    re.I,
)

# 页面/界面产品设计（非纯滚动壳）
_PAGE_UI_DESIGN_RE = re.compile(
    r"界面|页面|概览|看板|仪表盘|首页|视图|重写|更好看|设计感|美观|"
    r"配色|视觉|不要?照抄|不要?像首页|产品设计|ui[-_\s]?product|"
    r"【任务档位\s*[:：]\s*ui_visual】",
    re.I,
)


def wants_ui_redesign(text: str) -> bool:
    """用户要重做/有设计感（非视觉对齐复刻）。"""
    return bool(_REDESIGN_RE.search(text or ""))


def classify_ui_visual_intent(text: str, *, has_images: bool = False) -> str:
    """截图相关视觉意图（灵活，不唯「1:1」关键词）。

    返回：
    - full_match：效果要跟截图一样（质量优先）
    - guided_edit：按截图改一部分 / 参照修改
    - redesign：重新设计（旧图非布局合同）
    - none：无 UI 视觉对齐意图
    """
    t = text or ""
    # 「不要复刻 / 禁止复刻」不是视觉对齐
    negated_replica = bool(
        re.search(r"(?:不(?:要|必|用)?|别|非|禁止|勿).{0,6}复刻", t)
    )
    match = bool(_STRONG_SHOT_RE.search(t))
    if not match and not negated_replica and re.search(r"复刻", t):
        match = True
    guided = bool(_GUIDED_EDIT_RE.search(t))
    redesign = wants_ui_redesign(t)

    # 明文视觉对齐优先于「重做/更好看」残留词
    if match:
        return "full_match"
    if redesign:
        return "redesign"
    if guided:
        return "guided_edit"
    # 有图 + 写/改界面动作，但没说整页复刻 → 按参照修改，勿默认整页 1:1 赶工/也不要完全忽略图
    if has_images and _PAGE_UI_DESIGN_RE.search(t) and re.search(
        r"改|调|修|换|做|写|实现|开发|新增|参考", t
    ):
        return "guided_edit"
    if has_images and _UI_SHOT_RE.search(t):
        return "guided_edit"
    return "none"


def looks_like_ui_shot_fidelity(text: str, *, has_images: bool = False) -> bool:
    """是否应按截图做视觉落地（整页对齐或按图局部改）。"""
    return classify_ui_visual_intent(text, has_images=has_images) in {
        "full_match",
        "guided_edit",
    }


def should_attach_shot_images(text: str) -> bool:
    """重做时不要把旧截图原图/视觉规格塞给 Cloud（否则必抄布局）。"""
    return classify_ui_visual_intent(text, has_images=True) != "redesign"


def normalize_cloud_ui_message(message: str) -> str:
    """开工前净化需求：重做时撕掉截图布局合同，并钉死最高指令（幂等）。"""
    text = (message or "").strip()
    if not text:
        return text
    # 已带 banner：先剥掉再净化，避免 API + build_* 双重叠加
    if text.startswith(_REDESIGN_BANNER_MARK):
        text = _REDESIGN_BANNER_RE.sub("", text).strip()
    if classify_ui_visual_intent(text, has_images=True) != "redesign":
        return text
    cleaned = text
    cleaned = re.sub(r"【截图理解】[\s\S]*?(?=\n【|\n## |\Z)", "\n", cleaned)
    cleaned = re.sub(
        r"(?:^|\n)#{1,3}\s*[^\n]*(?:按截图位置|按截图)[^\n]*\n(?:[-*].*\n?)*",
        "\n",
        cleaned,
    )
    for pat in (
        r"[^\n]*按截图位置[^\n]*\n?",
        r"[^\n]*五卡布局与截图[^\n]*\n?",
        r"[^\n]*与截图一致[^\n]*\n?",
        r"[^\n]*布局以截图为准[^\n]*\n?",
    ):
        cleaned = re.sub(pat, "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if not cleaned:
        cleaned = text
    banner = (
        f"{_REDESIGN_BANNER_MARK} · 盖过下文一切旧规格】\n"
        "- 必须全新构图；禁止旧截图五卡骨架、禁止照抄首页/生产看板。\n"
        "- 只保留业务字段与接口；布局/视觉签名必须新做。\n"
        "- 若下文仍出现「按截图位置 / 与截图一致 / 五卡」→ 一律视为过期，忽略。\n\n"
    )
    return banner + cleaned


def classify_task_tier(user_message: str, *, has_images: bool = False) -> str:
    """任务档位：css_layout | ui_visual | default。用于收窄探索，不换模型。"""
    text = user_message or ""
    tagged = _TIER_TAG_RE.search(text)
    if tagged:
        return tagged.group(1).lower()
    shot = looks_like_ui_shot_fidelity(text, has_images=has_images)
    if _CSS_LAYOUT_RE.search(text) and not _HEAVY_FEATURE_RE.search(text):
        if shot:
            return "ui_visual"
        return "css_layout"
    if shot:
        return "ui_visual"
    # 重做/设计感：视觉质量优先探索，但不走截图 1:1 硬锁（见 _ui_fidelity_rules）
    if wants_ui_redesign(text):
        return "ui_visual"
    return "default"


def extract_deliverable_phrases(text: str, *, limit: int = 8) -> list[str]:
    """从用户原文抽取交付物短语（通用，不维护业务词典）。"""
    out: list[str] = []
    seen: set[str] = set()
    action_prefix = re.compile(r"^(?:开发|实现|新增|搭建|建设|做|写|系统)+")
    for m in _DELIVERABLE_RE.finditer(text or ""):
        full = (m.group(0) or "").strip()
        stem = (m.group(1) or "").strip()
        # 去掉词干前的动作/系统等前缀，保留真正对象名
        stem2 = action_prefix.sub("", stem).strip() or stem
        if len(stem2) >= 6 and action_prefix.search(stem):
            stem2 = stem2[-4:] if len(stem2) > 4 else stem2
        suffix = full[len(stem) :] if full.startswith(stem) else full[-2:]
        phrase = f"{stem2}{suffix}" if stem2 and not stem2.endswith(suffix) else (stem2 or full)
        for p in (phrase, stem2, full):
            if len(p) < 2 or p in seen:
                continue
            if p in {"系统", "开发", "实现", "功能", "模块", "界面", "页面"}:
                continue
            seen.add(p)
            out.append(p)
            if len(out) >= limit:
                return out
    return out


def looks_like_unscoped_new_deliverable(message: str) -> bool:
    """短句新交付、且不像已确认摘要 → 须先澄清，勿直接并进旧 job。"""
    msg = (message or "").strip()
    if not msg:
        return False
    if _CONFIRMED_REQ_RE.search(msg):
        return False
    if len(msg) >= 72 and msg.count("\n") >= 2:
        return False
    if _CSS_LAYOUT_RE.search(msg) and not _NEW_DELIVERABLE_ACTION_RE.search(msg):
        return False
    return bool(_NEW_DELIVERABLE_ACTION_RE.search(msg))


def extract_page_search_hints(text: str, *, limit: int = 8) -> list[str]:
    """从需求原文动态提取检索词（通用），供 glob/rg 与锚点探测。"""
    out: list[str] = []
    seen: set[str] = set()

    def _add(h: str) -> None:
        s = str(h or "").strip()
        if len(s) < 2 or s in seen:
            return
        seen.add(s)
        out.append(s)

    for p in extract_deliverable_phrases(text, limit=limit):
        _add(p)
        for suffix in ("界面", "页面", "模块", "功能", "视图", "看板"):
            if p.endswith(suffix) and len(p) > len(suffix):
                _add(p[: -len(suffix)])
                break
    for m in re.finditer(r"\b([A-Z][a-zA-Z0-9]{2,40})\b", text or ""):
        _add(m.group(1))
    for m in re.finditer(r"[「\"'`]([^」\"'`]{2,40})[」\"'`]", text or ""):
        _add(m.group(1))
    return out[:limit]

def extract_file_anchors_from_text(text: str, *, limit: int = 12) -> list[str]:
    """从需求正文抠相对路径，供 Cloud 优先打开。"""
    out: list[str] = []
    seen: set[str] = set()
    for m in _PATH_RE.finditer(text or ""):
        p = (m.group(1) or "").replace("\\", "/").strip().lstrip("./")
        if not p or p in seen:
            continue
        seen.add(p)
        out.append(p)
        if len(out) >= limit:
            break
    return out


def merge_file_anchors(*groups: Iterable[str] | None, limit: int = 12) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for group in groups:
        if not group:
            continue
        for raw in group:
            p = str(raw or "").replace("\\", "/").strip().lstrip("./")
            if not p or p in seen:
                continue
            seen.add(p)
            out.append(p)
            if len(out) >= limit:
                return out
    return out


def _ui_fidelity_rules(user_message: str, *, has_images: bool = False) -> str:
    """按视觉意图注入约束：整页对齐 / 按图局部改 / 重做。"""
    text = user_message or ""
    intent = classify_ui_visual_intent(text, has_images=has_images)
    if intent == "redesign":
        return (
            "【旧截图/旧稿仅供参考 · 非视觉对齐】用户要求重做/有设计感：\n"
            "- 可保留业务字段与模块清单（指标名、表列、接口字段）。\n"
            "- **禁止**把「顶行双 gauge + 中左右卡 + 底表明细」等旧截图/旧 propose 骨架原样落地。\n"
            "- 正文里若出现「按截图位置 / 与截图一致 / 五卡布局与截图」：视为过期规格，以重新构图为准。\n"
            "- 截图/旧页只作信息参考，不是布局合同。\n"
        )
    if intent == "none":
        return ""
    if intent == "guided_edit":
        base = (
            "【按截图修改 · 对准意图】用户是参照截图改界面，不一定要整页像素复刻：\n"
            "- 先抓住用户点名的改动点（颜色/按钮/顶栏/某块布局等），把这部分对照截图做对。\n"
            "- 未点名的区域保持现有实现，禁止借机整页重做或臆造模块。\n"
            "- 若用户其实要「整页跟截图一样」的效果（即使没说 1:1），按整页视觉对齐处理。\n"
            "- 涉及替换的 Logo/主视觉：优先从截图裁剪入库，禁止无关占位图交差。\n"
            "- 结束摘要写清：改了哪几处、与截图是否对齐、未动哪些区域。\n"
        )
        if has_images:
            base += (
                "- 【原图优先】已附带截图；与【截图理解】冲突时以原图为准。\n"
            )
        return base
    # full_match
    base = (
        "【截图视觉还原 · 硬约束】用户真实意图是效果跟截图一样"
        "（可能说 1:1/复刻/改成这种/跟截图一样/按这个效果等）：\n"
        "- **质量优先于速度**：宁可多改几轮，也不允许「大概像」交差；"
        "完成标准是肉眼对照截图高度一致，不是「几分钟搞定」。\n"
        "- 以布局位置、比例、图表类型、色块/背景为最高优先级；"
        "数字文案正确但视觉做成通用后台模板 = 不合格。\n"
        "- 禁止臆造截图中未出现的模块（例如无中生有的底部双柱图、明细表格）。\n"
        "- 禁止把「整卡色块背景（绿/粉/橙）+ 特色图表（仪表盘/半透明浮层）」"
        "改写成默认 Element Plus 白底 el-card KPI 行。\n"
        "- 可沿用仓库技术栈与 ECharts 等库，但样式必须贴近截图；"
        "需要自定义 CSS/卡片背景时请自定义，不要用「与现有风格一致」当借口简化视觉。\n"
        "- **禁止偷懒资源**：不得用无关 Unsplash/Lorem 图、纯 CSS 文字假 Logo "
        "冒充截图中的品牌标、设备合成图、插画主视觉；应从截图裁剪导出到 "
        "`frontend/src/assets/`（或等价静态目录）再引用，或按像素重绘等价 SVG/PNG。\n"
        "- 对照清单（提交前自检）：分区比例、背景渐变/主色、顶栏与页脚原文、"
        "表单字段顺序与占位、勾选项、主按钮色与圆角、主视觉位置与内容。\n"
        "- 结束摘要必须列「仍未对齐截图的差距」；若差距仍大须继续改，"
        "不要谎称「与截图一致」或「1:1 完成」。\n"
    )
    if has_images:
        base += (
            "- 【原图优先】本轮 prompt 已附带原始截图（images）。请直接看图对照色值、圆角、"
            "渐变、图表线型/点样式与间距；【截图理解】文字仅辅助，与原图冲突时以原图为准。\n"
        )
    base += (
        "- 【强视觉对齐】先落静态视觉（布局+资源+样式），再接已有业务逻辑；"
        "视觉未对齐前不要急着 commit 收工。\n"
    )
    return base


def _ui_product_design_rules(user_message: str, *, tier: str = "default") -> str:
    """页面/仪表盘产品设计：禁止照抄首页与通用 Admin 模板（Skill ui-product-design）。"""
    if (tier or "").strip().lower() == "css_layout":
        return ""
    text = user_message or ""
    if (tier or "").strip().lower() != "ui_visual" and not _PAGE_UI_DESIGN_RE.search(text):
        return ""
    base = (
        "【产品设计 · Skill ui-product-design · 硬约束】\n"
        "- 一页一身份：业务页必须有可辨认的视觉签名（主色/主图元/首屏构图至少一项与其它页不同）。\n"
        "- **禁止照抄**：不得把 Home/首页（或其它已有业务页）的布局骨架复制到本页再改标题；"
        "须独立视图组件；可复用的只有布局壳、侧栏、主题 token。\n"
        "- 信息层级：首屏突出 1 个主指标或 1 组主关系；禁止同权卡片墙、同亮度数字平铺。\n"
        "- 图表叙事：仪表/柱状/折线须服务本页语义；禁止两个完全相同的半圆 gauge 复制粘贴。\n"
        "- 深色工业风克制：强调色 ≤2；禁止霓虹描边堆砌、紫色辉光、多层阴影、圆角胶囊标签墙。\n"
        "- 沿用技术栈 ≠ 沿用烂布局：可用 Vue/Element/ECharts，但样式须按本页规格自定义。\n"
        "- 结束摘要写清本页与首页差异点；若实际是复制首页布局 = 不合格。\n"
    )
    if wants_ui_redesign(text) and classify_ui_visual_intent(text) != "full_match":
        base += (
            "- 【重做优先】本轮是重新设计：须给出与旧页/旧截图明显不同的新构图；"
            "保留数据字段即可，布局与视觉签名必须新做。\n"
        )
    return base


def _speed_scope_rules(
    tier: str,
    file_anchors: list[str] | None = None,
    page_hints: list[str] | None = None,
    *,
    redesign: bool = False,
    strong_replica: bool = False,
) -> str:
    """按档位收窄搜索/改动面；1:1 强复刻时关闭赶工话术，质量优先。"""
    anchors = [str(a).strip() for a in (file_anchors or []) if str(a).strip()]
    hints = [str(h).strip() for h in (page_hints or []) if str(h).strip()]
    anchor_block = ""
    if anchors:
        listed = "\n".join(f"  - `{p}`" for p in anchors[:12])
        anchor_block = (
            "【优先打开的文件锚点】（存在则先读；页面级锚点优先于 App/Layout）：\n"
            f"{listed}\n"
        )
    hint_block = ""
    if hints:
        q = " ".join(f"`*{h}*`" for h in hints[:8])
        hint_block = (
            "【页面定位】先用 glob/rg 按这些关键词找目标页，禁止从仓库根目录漫游：\n"
            f"  {q}\n"
        )

    if tier == "css_layout":
        return (
            "【任务档位：css_layout · 硬加速 · 保质】\n"
            "- 本轮只修溢出/滚动/宽度自适应（如 overflow-x、100% 宽、grid/flex 压缩、"
            "表格内部横滚、ECharts resize）。\n"
            "- 【步数预算】目标 ≤6 次工具调用落地：①关键词定位页面 ②读目标 vue/css "
            "③最小样式改动 ④必要时同页 chart resize ⑤提交推送。禁止通读 README/后端/测试。\n"
            "- 只改目标页及其局部样式；禁止重构路由/业务组件；禁止改配色、图表 option、"
            "表格列定义与文案（除非需求明文要求）。\n"
            "- 整页用 overflow-x:hidden 时，多列表格只允许表格容器内部横滚。\n"
            "- 改对应即可 commit；不要为「再确认一遍」重复打开无关文件。\n"
            f"{hint_block}"
            f"{anchor_block}"
        )
    if tier == "ui_visual":
        if redesign:
            return (
                "【任务档位：ui_visual · 重新设计】\n"
                "- 产品设计质量优先：新构图、信息层级、视觉签名；"
                "探索顺序：目标页 → 布局壳 → 主题 token；禁止照搬旧页 DOM。\n"
                f"{hint_block}"
                f"{anchor_block}"
            )
        if strong_replica:
            return (
                "【任务档位：ui_visual · 1:1 质量优先】\n"
                "- **禁止赶工**：不要为省时间用占位图/假 Logo/白卡片模板；"
                "对照原图做到分区比例、主视觉、配色与控件样式对齐。\n"
                "- 允许充分迭代：裁剪/导出截图资源 → 落目标页样式 → 对照原图微调 → "
                "差距仍大则继续改；不要第一步就 commit 收工。\n"
                "- 探索顺序：目标页 → 静态资源目录 → 布局壳/全局样式；"
                "仍禁止无目的地通读后端与无关历史大文件。\n"
                f"{hint_block}"
                f"{anchor_block}"
            )
        return (
            "【任务档位：ui_visual · 视觉还原】\n"
            "- 视觉还原质量优先；探索顺序：目标页 → 布局壳 → 图表样式；"
            "禁止遍历后端/脚本/无关历史大文件。\n"
            f"{hint_block}"
            f"{anchor_block}"
        )
    mild = (
        "【效率】优先打开需求点名的文件与同目录邻近文件；"
        "不要重构无关模块；能小改就不要大挪。\n"
    )
    return mild + hint_block + anchor_block


def build_first_turn_prompt(
    *,
    user_message: str,
    repo: str,
    work_branch: str,
    base_ref: str = "",
    create_pr: bool = False,
    has_images: bool = False,
    file_anchors: list[str] | None = None,
    task_tier: str | None = None,
    page_hints: list[str] | None = None,
    repo_index_block: str = "",
) -> str:
    """一用户一分支：所有改动落在固定工作分支，禁止按功能开新分支。"""
    raw_msg = (user_message or "").strip()
    user_message = normalize_cloud_ui_message(raw_msg)
    visual_intent = classify_ui_visual_intent(raw_msg, has_images=bool(has_images))
    effective_images = bool(has_images) and visual_intent != "redesign"
    redesign = visual_intent == "redesign"
    strong_replica = visual_intent == "full_match"
    base = (base_ref or "").strip() or "仓库默认分支（通常 main）"
    if create_pr:
        pr_rule = (
            "本轮用户要求创建 PR：完成后开 PR 指向默认分支（main），标题写清变更摘要。"
            "优先用平台能力开 PR；工作分支必须仍是上述固定分支名。"
        )
    else:
        pr_rule = (
            "【禁止开 PR · 用户未勾选】硬性约束：\n"
            "- 不要创建 Pull Request，不要调用 ManagePullRequest / create_pull_request。\n"
            "- 不要执行 `gh pr create`、`hub pull-request` 或任何等价开 PR 命令。\n"
            "- 不要因为工具要求 `cursor/` 前缀分支就改分支名或强行开 PR。\n"
            "- 只把代码 push 到固定工作分支；合入 main 由用户稍后手动处理。\n"
            "- 结束摘要不要写「已创建 PR」；可写分支名与 commit，并提示用户自行合 main。"
            "- 结束摘要禁止写「ERP 已上线 / 本机已可见 / 界面已部署」；"
            "须写明：仅工作分支有代码，本机/ERP 需合入后 pull 并重启才可见。"
        )
    tier = (task_tier or "").strip().lower() or classify_task_tier(
        raw_msg, has_images=effective_images
    )
    hints = list(page_hints or []) or extract_page_search_hints(user_message)
    anchors = merge_file_anchors(
        file_anchors,
        extract_file_anchors_from_text(user_message),
    )
    ui_rules = _ui_fidelity_rules(raw_msg, has_images=effective_images)
    design_rules = _ui_product_design_rules(raw_msg, tier=tier)
    speed_rules = _speed_scope_rules(
        tier, anchors, hints, redesign=redesign, strong_replica=strong_replica
    )
    index_block = (repo_index_block or "").strip()
    index_part = f"{index_block}\n" if index_block else ""
    return (
        "你是代码实现 Agent，在用户的同一聊天会话中协作改仓库。\n"
        "每一轮只做当前要求。正文只输出一遍完整摘要，不要重复粘贴同一段「已完成本轮需求」。\n"
        f"目标仓库：{repo}\n"
        f"【固定工作分支 · 一人一支】必须使用分支 `{work_branch}`：\n"
        f"- 若远端已有 `{work_branch}`：checkout 该分支并在其上继续提交（基于该分支最新 tip）。\n"
        f"- 若尚不存在：从 `{base}` 创建分支 `{work_branch}`，之后所有提交都在该分支。\n"
        "- 严禁再新建带功能名/随机后缀的分支（例如 dev/workbuddy-erp-login-xxxx、feat/首页-xxx）。\n"
        "- 同一用户后续需求（登录、首页、报表…）全部累积在这一条工作分支上。\n"
        f"{pr_rule}\n"
        f"{index_part}"
        f"{speed_rules}"
        f"{ui_rules}"
        f"{design_rules}"
        "首轮需求：\n"
        f"{user_message}\n"
        "验收：css_layout 无需补测套件；无权限的依赖不要伪造；不要修改与需求无关的配置密钥。"
        "落地声明（摘要必须含）：仅推到工作分支；未合入 main；未部署 ERP/本机演示环境。"
        + (
            " 视觉对齐以对照截图为准，未对齐前不要宣称完成。"
            if strong_replica
            else (
                " 按图修改时只对准用户点名的改动点，勿整页盲复刻。"
                if visual_intent == "guided_edit"
                else ""
            )
        )
    )


def build_followup_prompt(
    *,
    user_message: str,
    repo: str,
    work_branch: str,
    prior_assistant: str = "",
    create_pr: bool = False,
    has_images: bool = False,
    file_anchors: list[str] | None = None,
    task_tier: str | None = None,
    page_hints: list[str] | None = None,
    repo_index_block: str = "",
) -> str:
    raw_msg = (user_message or "").strip()
    user_message = normalize_cloud_ui_message(raw_msg)
    visual_intent = classify_ui_visual_intent(raw_msg, has_images=bool(has_images))
    effective_images = bool(has_images) and visual_intent != "redesign"
    redesign = visual_intent == "redesign"
    strong_replica = visual_intent == "full_match"
    prior = (prior_assistant or "").strip()
    if redesign and prior:
        prior_block = (
            "上一轮助手摘要（仅供字段/路径参考；布局指令以本轮重做为准，可忽略旧五卡/截图骨架）：\n"
            f"{prior[:2000]}\n\n"
        )
    else:
        prior_block = f"上一轮助手摘要（供续聊上下文）：\n{prior[:4000]}\n\n" if prior else ""
    if create_pr:
        pr_rule = "本轮用户要求开 PR：完成后开 PR；工作分支仍用固定分支。"
    else:
        pr_rule = (
            "【禁止开 PR · 用户未勾选】不要 ManagePullRequest / `gh pr create` / 任何开 PR；"
            "只推固定工作分支；摘要勿宣称已开 PR；不要重复粘贴同一段完成摘要。"
        )
    tier = (task_tier or "").strip().lower() or classify_task_tier(
        raw_msg, has_images=effective_images
    )
    hints = list(page_hints or []) or extract_page_search_hints(
        f"{user_message}\n{prior}"
    )
    anchors = merge_file_anchors(
        file_anchors,
        extract_file_anchors_from_text(user_message),
        extract_file_anchors_from_text(prior),
    )
    ui_rules = _ui_fidelity_rules(raw_msg, has_images=effective_images)
    design_rules = _ui_product_design_rules(raw_msg, tier=tier)
    speed_rules = _speed_scope_rules(
        tier, anchors, hints, redesign=redesign, strong_replica=strong_replica
    )
    index_block = (repo_index_block or "").strip()
    index_part = f"{index_block}\n" if index_block else ""
    return (
        "你是代码实现 Agent，继续在同一仓库、同一用户工作分支上改代码。\n"
        f"目标仓库：{repo}\n"
        f"【固定工作分支】继续使用 `{work_branch}`，禁止新开其它功能分支。\n"
        f"{pr_rule}\n"
        f"{index_part}"
        f"{speed_rules}"
        f"{ui_rules}"
        f"{design_rules}"
        f"{prior_block}"
        "本轮用户补充：\n"
        f"{user_message}\n"
        "验收：只做本轮要求；css_layout 无需补测套件。"
        + (
            " 视觉对齐继续对照截图补齐差距，未对齐前不要宣称完成。"
            if strong_replica
            else (
                " 按图修改只补用户点名的点，勿借机整页复刻。"
                if visual_intent == "guided_edit"
                else ""
            )
        )
    )
