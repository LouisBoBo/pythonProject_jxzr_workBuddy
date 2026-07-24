"""
配置中心 — Agent API 服务配置。
复用 apps/agent 的 Config，数据目录统一落在仓库根 data/。
"""
import os
import sys
from pathlib import Path

# 仓库根：apps/api/routes_config.py → parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_PATH = REPO_ROOT / "apps" / "agent"
if str(AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(AGENT_PATH))

from config import Config as AgentConfig  # noqa: E402

# 服务端口
SERVER_PORT = int(os.getenv("MES_SERVER_PORT", "8765"))

# 统一数据目录（历史 / 上传 / 转换 / 导出）
DATA_DIR = REPO_ROOT / "data"
HISTORY_DIR = str(DATA_DIR / "history")
UPLOAD_DIR = str(DATA_DIR / "uploads")
CONVERT_DIR = str(DATA_DIR / "converted")
EXPORTS_DIR = str(DATA_DIR / "exports")

MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
