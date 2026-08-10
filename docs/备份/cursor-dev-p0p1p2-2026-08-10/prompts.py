"""写码会话系统 Prompt 拼装。"""
from __future__ import annotations

import re
from typing import Iterable

# 强视觉复刻（有这些才升 ui_visual；单提「仪表盘」不算）
_UI_SHOT_RE = re.compile(
    r"【截图理解】|1\s*:\s*1|1：1|复刻|照着做|仿照|按截图|改成这种|做成这种|按这个界面",
    re.I,
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

# 从需求抠「页面名」→ 供 glob/rg 与锚点探测（中英）
_PAGE_HINT_PATTERNS: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(r"生产看板|生产看板页", re.I), ["生产看板", "ProductionBoard", "ProductionKanban", "ProdBoard", "Board"]),
    (re.compile(r"看板管理|看板页|看板", re.I), ["看板", "Kanban", "Board", "Dashboard"]),
    (re.compile(r"工作台|首页|仪表盘(?!卡片)", re.I), ["Home", "Dashboard", "Workbench", "Index"]),
    (re.compile(r"登录页|登录", re.I), ["Login", "SignIn"]),
]


def classify_task_tier(user_message: str, *, has_images: bool = False) -> str:
    """任务档位：css_layout | ui_visual | default。用于收窄探索，不换模型。"""
    text = user_message or ""
    tagged = _TIER_TAG_RE.search(text)
    if tagged:
        return tagged.group(1).lower()
    # 布局/溢出类优先于「提到仪表盘」的软视觉词，避免误升档拖慢
    if _CSS_LAYOUT_RE.search(text) and not _HEAVY_FEATURE_RE.search(text):
        # 仅当明确复刻/带原图时才盖过 css_layout
        if has_images or _UI_SHOT_RE.search(text):
            return "ui_visual"
        return "css_layout"
    if has_images or _UI_SHOT_RE.search(text):
        return "ui_visual"
    return "default"


def extract_page_search_hints(text: str, *, limit: int = 8) -> list[str]:
    """从需求提取页面关键词，供 Cloud rg/glob 与布局探测。"""
    out: list[str] = []
    seen: set[str] = set()
    for pat, hints in _PAGE_HINT_PATTERNS:
        if not pat.search(text or ""):
            continue
        for h in hints:
            if h in seen:
                continue
            seen.add(h)
            out.append(h)
            if len(out) >= limit:
                return out
    return out


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
    """截图复刻场景：防止 Cloud 按「Element 白卡片模板」交差。"""
    if not _UI_SHOT_RE.search(user_message or "") and not has_images:
        return ""
    base = (
        "【截图视觉还原 · 硬约束】本需求含界面截图理解或 1:1/复刻意图：\n"
        "- 以布局位置、图表类型、色块/背景为最高优先级；"
        "数字文案正确但视觉做成通用后台模板 = 不合格。\n"
        "- 禁止臆造截图中未出现的模块（例如无中生有的底部双柱图、明细表格）。\n"
        "- 禁止把「整卡色块背景（绿/粉/橙）+ 特色图表（仪表盘/半透明浮层）」"
        "改写成默认 Element Plus 白底 el-card KPI 行。\n"
        "- 可沿用仓库技术栈与 ECharts 等库，但样式必须贴近截图；"
        "需要自定义 CSS/卡片背景时请自定义，不要用「与现有风格一致」当借口简化视觉。\n"
        "- 结束摘要如实写还原差距；不要谎称「与截图一致」若实际是白卡片模板。\n"
    )
    if has_images:
        base += (
            "- 【原图优先】本轮 prompt 已附带原始截图（images）。请直接看图对照色值、圆角、"
            "渐变、图表线型/点样式与间距；【截图理解】文字仅辅助，与原图冲突时以原图为准。\n"
        )
    return base


def _speed_scope_rules(
    tier: str,
    file_anchors: list[str] | None = None,
    page_hints: list[str] | None = None,
) -> str:
    """按档位收窄搜索/改动面；质量硬约束仍由 fidelity / 需求正文负责。"""
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
        return (
            "【任务档位：ui_visual · 加速探索】\n"
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
) -> str:
    """一用户一分支：所有改动落在固定工作分支，禁止按功能开新分支。"""
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
        )
    tier = (task_tier or "").strip().lower() or classify_task_tier(
        user_message, has_images=has_images
    )
    hints = list(page_hints or []) or extract_page_search_hints(user_message)
    anchors = merge_file_anchors(
        file_anchors,
        extract_file_anchors_from_text(user_message),
    )
    ui_rules = _ui_fidelity_rules(user_message, has_images=has_images)
    speed_rules = _speed_scope_rules(tier, anchors, hints)
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
        f"{speed_rules}"
        f"{ui_rules}"
        "首轮需求：\n"
        f"{user_message.strip()}\n"
        "验收：css_layout 无需补测套件；无权限的依赖不要伪造；不要修改与需求无关的配置密钥。"
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
) -> str:
    prior = (prior_assistant or "").strip()
    prior_block = f"上一轮助手摘要（供续聊上下文）：\n{prior[:4000]}\n\n" if prior else ""
    if create_pr:
        pr_rule = "本轮用户要求开 PR：完成后开 PR；工作分支仍用固定分支。"
    else:
        pr_rule = (
            "【禁止开 PR · 用户未勾选】不要 ManagePullRequest / `gh pr create` / 任何开 PR；"
            "只推固定工作分支；摘要勿宣称已开 PR；不要重复粘贴同一段完成摘要。"
        )
    tier = (task_tier or "").strip().lower() or classify_task_tier(
        user_message, has_images=has_images
    )
    hints = list(page_hints or []) or extract_page_search_hints(
        f"{user_message}\n{prior}"
    )
    anchors = merge_file_anchors(
        file_anchors,
        extract_file_anchors_from_text(user_message),
        extract_file_anchors_from_text(prior),
    )
    ui_rules = _ui_fidelity_rules(user_message, has_images=has_images)
    speed_rules = _speed_scope_rules(tier, anchors, hints)
    return (
        "你是代码实现 Agent，继续在同一仓库、同一用户工作分支上改代码。\n"
        f"目标仓库：{repo}\n"
        f"【固定工作分支】继续使用 `{work_branch}`，禁止新开其它功能分支。\n"
        f"{pr_rule}\n"
        f"{speed_rules}"
        f"{ui_rules}"
        f"{prior_block}"
        "本轮用户补充：\n"
        f"{user_message.strip()}\n"
        "验收：只做本轮要求；css_layout 无需补测套件。"
    )
