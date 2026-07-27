"""写操作工具清单（M2）：须经人工确认才可改平台数据。"""
from __future__ import annotations

# 仅列入会改写 ERP/平台的工具；查询与本地导出不在此列
WRITE_TOOLS: frozenset[str] = frozenset(
    {
        "import_file_to_platform",
    }
)

WRITE_CONFIRM_MARKER = "__write_confirm__"
