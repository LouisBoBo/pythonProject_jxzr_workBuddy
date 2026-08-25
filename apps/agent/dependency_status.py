"""外部依赖就绪摘要与降级提示文案（无网络、无 LLM）。

供启动自检、系统配置页、降级演练冒烟共用。
说明见 docs/桌面与部署/外部依赖降级演练手册.md
"""
from __future__ import annotations

from typing import Any

# 与 agents.agent.build_model / local_dev 文案对齐（改文案须同步单测）
LLM_KEY_MISSING = (
    "请设置对话模型 API Key（可在「系统配置」填写，或配置 LLM_API_KEY / DEEPSEEK_API_KEY）"
)
VISION_KEY_MISSING_HINT = "请到「系统配置」填写视觉模型 API Key（VISION_API_KEY / 智谱 Key）"
PLATFORM_UNREACHABLE = "无法连接 MES 接口，请检查接口文档主机是否可达。"
PLATFORM_URL_MISSING = "未配置 MES 接口地址。请先在「系统配置 → MES 接入」导入接口文档。"
MES_CATALOG_MISSING = "当前未配置可查对象，请先在系统配置接入 MES。"


def llm_configured() -> bool:
    from config import Config

    return bool((getattr(Config, "LLM_API_KEY", "") or "").strip())


def vision_configured() -> bool:
    try:
        from tools.vision_describe import vision_enabled

        return bool(vision_enabled())
    except Exception:
        from config import Config

        return bool((getattr(Config, "VISION_API_KEY", "") or "").strip())


def platform_base_configured() -> bool:
    from config import Config

    return bool((getattr(Config, "PLATFORM_BASE_URL", "") or "").strip())


def cursor_api_configured() -> bool:
    try:
        from settings_store import resolve_setting

        return bool((resolve_setting("CURSOR_API_KEY", "") or "").strip())
    except Exception:
        import os

        return bool((os.getenv("CURSOR_API_KEY") or "").strip())


def summarize_dependencies() -> dict[str, Any]:
    """当前进程可见的依赖就绪（不探活远端）。"""
    llm_ok = llm_configured()
    vision_ok = vision_configured()
    platform_ok = platform_base_configured()
    cursor_ok = cursor_api_configured()

    degrade: list[dict[str, str]] = []
    if not llm_ok:
        degrade.append(
            {
                "id": "llm",
                "severity": "critical",
                "message": LLM_KEY_MISSING,
                "impact": "对话 / 本机写码讨论不可用",
            }
        )
    if not vision_ok:
        degrade.append(
            {
                "id": "vision",
                "severity": "degraded",
                "message": f"截图理解降级：未配置视觉模型。{VISION_KEY_MISSING_HINT}",
                "impact": "可贴图但无【截图理解】；主模型仍可纯文本对话",
            }
        )
    if not platform_ok:
        degrade.append(
            {
                "id": "platform_url",
                "severity": "critical",
                "message": PLATFORM_URL_MISSING,
                "impact": "查数 / 摸底连不上现场 API",
            }
        )
    if not cursor_ok:
        degrade.append(
            {
                "id": "cursor_cloud",
                "severity": "optional",
                "message": "未配置 CURSOR_API_KEY：GitHub Cloud 写码不可用；本机写码仍可走 Local Agent",
                "impact": "仅 cursor_dev（target=github）受影响",
            }
        )

    critical_ok = llm_ok and platform_ok
    return {
        "llm_configured": llm_ok,
        "vision_configured": vision_ok,
        "platform_base_configured": platform_ok,
        "cursor_api_configured": cursor_ok,
        "critical_ready": critical_ok,
        "degrade": degrade,
        "hints": {
            "llm_missing": LLM_KEY_MISSING,
            "vision_missing": VISION_KEY_MISSING_HINT,
            "platform_unreachable": PLATFORM_UNREACHABLE,
            "platform_url_missing": PLATFORM_URL_MISSING,
            "mes_catalog_missing": MES_CATALOG_MISSING,
        },
    }
