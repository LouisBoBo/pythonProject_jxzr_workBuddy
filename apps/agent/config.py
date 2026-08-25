"""
配置中心：统一管理 LLM 和平台连接配置。

环境变量从仓库根目录 .env 加载（monorepo 约定）。
旋钮分层与 settings 覆盖：docs/桌面与部署/配置旋钮分层与接手指南.md
"""
import os
import platform
from pathlib import Path
from dotenv import load_dotenv

from bundle_root import resolve_repo_root

# 仓库根（源码 / 桌面冻结 / WORKBUDDY_REPO_ROOT）
REPO_ROOT = resolve_repo_root()
load_dotenv(REPO_ROOT / ".env")
# 兼容：若仍把 .env 放在 apps/agent 下也能读到
load_dotenv(Path(__file__).resolve().parent / ".env")


def _default_export_dir() -> str:
    """默认导出目录：优先返回用户桌面，区分 Windows / macOS / Linux。"""
    if os.getenv("EXPORT_TO_DESKTOP", "true").lower() in ("false", "0", "no"):
        return str(REPO_ROOT / "data" / "exports")

    system = platform.system()
    home = Path.home()

    if system == "Windows":
        desktop = home / "Desktop"
    elif system == "Darwin":
        desktop = home / "Desktop"
    else:
        desktop = home / "Desktop"

    return str(desktop)


def _resolve(key: str, default: str = "") -> str:
    """UI settings.json 覆盖优先，否则环境变量。"""
    try:
        from settings_store import resolve_setting

        return resolve_setting(key, default=default)
    except Exception:
        val = os.getenv(key)
        if val is not None and str(val).strip() != "":
            return str(val).strip()
        return default


def _normalize_openai_base(url: str) -> str:
    """OpenAI 兼容 Base URL，去掉末尾斜杠；无 /v1 时不强制追加（由调用方决定）。"""
    return (url or "").strip().rstrip("/")


def _effective_llm_api_key() -> str:
    return (
        _resolve("LLM_API_KEY", "")
        or _resolve("DEEPSEEK_API_KEY", "")
        or _resolve("SILICONFLOW_API_KEY", "")
    )


def _effective_llm_base_url() -> str:
    """通用 Base URL：LLM_BASE_URL > 旧 DEEPSEEK_BASE_URL > 按旧 Key 推断。"""
    explicit = _normalize_openai_base(_resolve("LLM_BASE_URL", ""))
    if explicit:
        return explicit
    if _resolve("LLM_API_KEY", ""):
        # 用户显式配了通用 Key，不再默认 DeepSeek；可空（走官方 OpenAI）
        return ""
    ds_key = _resolve("DEEPSEEK_API_KEY", "")
    sf_key = _resolve("SILICONFLOW_API_KEY", "")
    ds_base = _normalize_openai_base(
        _resolve("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    if ds_key:
        if ds_base and not ds_base.endswith("/v1"):
            return f"{ds_base}/v1"
        return ds_base or "https://api.deepseek.com/v1"
    if sf_key:
        return "https://api.siliconflow.cn/v1"
    if ds_base:
        return ds_base if ds_base.endswith("/v1") else f"{ds_base}/v1"
    return ""


def _effective_vision_api_key() -> str:
    return _resolve("VISION_API_KEY", "") or _resolve("ZHIPU_API_KEY", "")


def _effective_vision_base_url() -> str:
    return (
        _resolve("VISION_BASE_URL", "")
        or _resolve("ZHIPU_BASE_URL", "")
        or "https://open.bigmodel.cn/api/paas/v4/"
    ).strip().rstrip("/") + "/"


def _effective_vision_model() -> str:
    return _resolve("VISION_MODEL", "") or "glm-4v-flash"


class Config:
    # --- 路径 ---
    REPO_ROOT = REPO_ROOT
    # 多实例 HA：挂载同一卷时设置 DATA_DIR=/shared/mes-data
    DATA_DIR = Path(os.getenv("DATA_DIR") or (REPO_ROOT / "data")).expanduser().resolve()

    # --- LLM 配置（通用 OpenAI 兼容；界面优先写 LLM_*）---
    LLM_API_KEY = _effective_llm_api_key()
    LLM_BASE_URL = _effective_llm_base_url()
    DEEPSEEK_API_KEY = _resolve("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = _normalize_openai_base(
        _resolve("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    )
    SILICONFLOW_API_KEY = _resolve("SILICONFLOW_API_KEY", "")
    SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"

    MODEL_NAME = (
        _resolve("MODEL_NAME", "")
        or _resolve("MAIN_MODEL", "")
        or "deepseek-chat"
    )
    LLM_PROVIDER = _resolve("LLM_PROVIDER", "") or "openai_compatible"

    # --- 平台连接配置（UI settings 可覆盖，供桌面同事配置）---
    PLATFORM_BASE_URL = _resolve("PLATFORM_BASE_URL", "http://localhost:8000")
    USE_ERP = os.getenv("USE_ERP", "").lower() in ("true", "1", "yes")

    ERP_USERNAME = _resolve("MES_API_USERNAME", "") or os.getenv("ERP_USERNAME", "")
    ERP_PASSWORD = _resolve("MES_API_PASSWORD", "") or os.getenv("ERP_PASSWORD", "")
    ERP_ENTERPRISE_CODE = (
        _resolve("MES_API_ENTERPRISE_CODE", "") or os.getenv("ERP_ENTERPRISE_CODE", "")
    )

    # --- Agent 配置 ---
    MAX_IMPORT_ROWS = int(os.getenv("MAX_IMPORT_ROWS", "10000"))
    EXPORT_DIR = os.getenv("EXPORT_DIR") or _default_export_dir()
    EXPORT_TO_DESKTOP = os.getenv("EXPORT_TO_DESKTOP", "true").lower() in ("true", "1", "yes")
    # LangGraph 默认 recursion_limit=25；全仓分批审核（每批工具+纪要）易上百步
    AGENT_RECURSION_LIMIT = max(25, int(os.getenv("AGENT_RECURSION_LIMIT", "500")))

    # --- 会话上下文（checkpointer + 历史回填）---
    # 空 = DATA_DIR/agent_checkpoints.sqlite
    AGENT_CHECKPOINT_PATH = os.getenv("AGENT_CHECKPOINT_PATH", "").strip()
    # 进入模型的消息条数上限（含回填与裁剪）；0 = 不裁剪
    CONTEXT_MAX_MESSAGES = max(0, int(os.getenv("CONTEXT_MAX_MESSAGES", "40")))
    # 单条历史回填最大字符；0 = 不截断
    CONTEXT_MAX_CHARS_PER_MSG = max(0, int(os.getenv("CONTEXT_MAX_CHARS_PER_MSG", "12000")))
    # 系统提示词实体目录用紧凑一行式（省 token；字段细节走 describe_entity）
    SYSTEM_PROMPT_COMPACT_CATALOG = os.getenv(
        "SYSTEM_PROMPT_COMPACT_CATALOG", "true"
    ).lower() in ("true", "1", "yes")

    # --- IDE 代码审核（M0 POC，默认关闭，不影响现网工具集）---
    IDE_REVIEW_ENABLED = os.getenv("IDE_REVIEW_ENABLED", "").lower() in (
        "1",
        "true",
        "yes",
    )

    # --- 只读 SQL（默认关；须 DSN + 表白名单）---
    READONLY_SQL_ENABLED = (
        _resolve("READONLY_SQL_ENABLED", "") or os.getenv("READONLY_SQL_ENABLED", "")
    ).lower() in ("1", "true", "yes")
    READONLY_SQL_DSN = _resolve("READONLY_SQL_DSN", "") or os.getenv("READONLY_SQL_DSN", "")
    READONLY_SQL_TABLE_WHITELIST = (
        _resolve("READONLY_SQL_TABLE_WHITELIST", "")
        or os.getenv("READONLY_SQL_TABLE_WHITELIST", "")
    )

    # --- 截图理解（主模型多为纯文本时，先走视觉模型再注入）---
    # 优先 VISION_*，兼容 ZHIPU_*
    VISION_API_KEY = _effective_vision_api_key()
    VISION_BASE_URL = _effective_vision_base_url()
    VISION_MODEL = _effective_vision_model()

    @classmethod
    def reload_runtime(cls) -> None:
        """从 settings.json + 环境变量刷新可热更新字段（保存界面配置后调用）。"""
        try:
            from settings_store import invalidate_cache

            invalidate_cache()
        except Exception:
            pass
        cls.LLM_API_KEY = _effective_llm_api_key()
        cls.LLM_BASE_URL = _effective_llm_base_url()
        cls.DEEPSEEK_API_KEY = _resolve("DEEPSEEK_API_KEY", "")
        cls.DEEPSEEK_BASE_URL = _normalize_openai_base(
            _resolve("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        )
        cls.SILICONFLOW_API_KEY = _resolve("SILICONFLOW_API_KEY", "")
        cls.MODEL_NAME = (
            _resolve("MODEL_NAME", "")
            or _resolve("MAIN_MODEL", "")
            or "deepseek-chat"
        )
        cls.LLM_PROVIDER = _resolve("LLM_PROVIDER", "") or "openai_compatible"
        cls.VISION_API_KEY = _effective_vision_api_key()
        cls.VISION_BASE_URL = _effective_vision_base_url()
        cls.VISION_MODEL = _effective_vision_model()
        cls.PLATFORM_BASE_URL = _resolve("PLATFORM_BASE_URL", "http://localhost:8000")
        cls.ERP_USERNAME = _resolve("MES_API_USERNAME", "") or os.getenv("ERP_USERNAME", "")
        cls.ERP_PASSWORD = _resolve("MES_API_PASSWORD", "") or os.getenv("ERP_PASSWORD", "")
        cls.ERP_ENTERPRISE_CODE = (
            _resolve("MES_API_ENTERPRISE_CODE", "") or os.getenv("ERP_ENTERPRISE_CODE", "")
        )
        cls.READONLY_SQL_ENABLED = (
            _resolve("READONLY_SQL_ENABLED", "") or os.getenv("READONLY_SQL_ENABLED", "")
        ).lower() in ("1", "true", "yes")
        cls.READONLY_SQL_DSN = (
            _resolve("READONLY_SQL_DSN", "") or os.getenv("READONLY_SQL_DSN", "")
        )
        cls.READONLY_SQL_TABLE_WHITELIST = (
            _resolve("READONLY_SQL_TABLE_WHITELIST", "")
            or os.getenv("READONLY_SQL_TABLE_WHITELIST", "")
        )

    @classmethod
    def summary(cls) -> str:
        lines = [
            f"LLM: {cls.MODEL_NAME} @ {cls.LLM_BASE_URL or 'default'}",
            f"Platform: {cls.PLATFORM_BASE_URL}",
        ]
        if cls.ERP_USERNAME:
            lines.append(f"ERP Login: {cls.ERP_USERNAME}")
        lines.append(f"Max import rows: {cls.MAX_IMPORT_ROWS}")
        return "\n".join(lines)
