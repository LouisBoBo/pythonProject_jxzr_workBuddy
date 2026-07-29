"""
配置中心：统一管理 LLM 和平台连接配置。

环境变量从仓库根目录 .env 加载（monorepo 约定）。
"""
import os
import platform
from pathlib import Path
from dotenv import load_dotenv

# apps/agent/config.py → 仓库根
REPO_ROOT = Path(__file__).resolve().parents[2]
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


class Config:
    # --- 路径 ---
    REPO_ROOT = REPO_ROOT
    # 多实例 HA：挂载同一卷时设置 DATA_DIR=/shared/mes-data
    DATA_DIR = Path(os.getenv("DATA_DIR") or (REPO_ROOT / "data")).expanduser().resolve()

    # --- LLM 配置 ---
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")

    SILICONFLOW_API_KEY = os.getenv("SILICONFLOW_API_KEY", "")
    SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"

    MODEL_NAME = os.getenv("MODEL_NAME") or os.getenv("MAIN_MODEL", "deepseek-chat")

    LLM_PROVIDER = os.getenv("LLM_PROVIDER") or (
        "deepseek" if DEEPSEEK_API_KEY else "siliconflow"
    )

    # --- 平台连接配置 ---
    PLATFORM_BASE_URL = os.getenv("PLATFORM_BASE_URL", "http://localhost:8000")
    USE_ERP = os.getenv("USE_ERP", "").lower() in ("true", "1", "yes")

    ERP_USERNAME = os.getenv("ERP_USERNAME", "")
    ERP_PASSWORD = os.getenv("ERP_PASSWORD", "")
    ERP_ENTERPRISE_CODE = os.getenv("ERP_ENTERPRISE_CODE", "")

    # --- Agent 配置 ---
    MAX_IMPORT_ROWS = int(os.getenv("MAX_IMPORT_ROWS", "10000"))
    EXPORT_DIR = os.getenv("EXPORT_DIR") or _default_export_dir()
    EXPORT_TO_DESKTOP = os.getenv("EXPORT_TO_DESKTOP", "true").lower() in ("true", "1", "yes")
    # LangGraph 默认 recursion_limit=25；文档全量探活 + Skills 易触顶
    AGENT_RECURSION_LIMIT = max(25, int(os.getenv("AGENT_RECURSION_LIMIT", "100")))

    @classmethod
    def summary(cls) -> str:
        lines = [
            f"LLM: {cls.MODEL_NAME} via {cls.LLM_PROVIDER}",
            f"Platform: {cls.PLATFORM_BASE_URL}",
        ]
        if cls.ERP_USERNAME:
            lines.append(f"ERP Login: {cls.ERP_USERNAME}")
        lines.append(f"Max import rows: {cls.MAX_IMPORT_ROWS}")
        return "\n".join(lines)
