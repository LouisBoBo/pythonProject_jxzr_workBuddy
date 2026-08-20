"""枚举字段中文展示。"""
from __future__ import annotations

from tools.query_tool.query_present import display_rows, summarize_records
from tools.query_tool.value_labels import label_enum_value


def test_label_status_matches_list_ui():
    assert label_enum_value("status", "pending") == "待开工"
    assert label_enum_value("status", "in_progress") == "进行中"
    assert label_enum_value("status", "cancelled") == "已取消"
    assert label_enum_value("priority", "urgent") == "紧急"
    assert label_enum_value("priority", "normal") == "普通"


def test_summarize_records_uses_chinese_status():
    records = [
        {"status": "pending"},
        {"status": "pending"},
        {"status": "in_progress"},
    ]
    groups = summarize_records(records, "status")
    values = {g["value"] for g in groups}
    assert "待开工" in values
    assert "进行中" in values
    assert "pending" not in values
    assert "in_progress" not in values


def test_display_rows_translates_status_column():
    rows = display_rows(
        [{"status": "in_progress", "order_no": "WO-1"}],
        ["order_no", "status"],
        {"order_no": "工单号", "status": "状态"},
    )
    assert rows[0]["状态"] == "进行中"
    assert rows[0]["工单号"] == "WO-1"
