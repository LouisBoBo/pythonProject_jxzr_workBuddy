"""前端加字段/加列时必须走完的数据链路（不写死某一套 MES）。"""
from __future__ import annotations

import re

_CSS_ONLY_RE = re.compile(r"【任务档位\s*[:：]\s*css_layout】", re.I)
_DATA_FEATURE_RE = re.compile(
    r"加一列|新增一列|加列|加字段|新增字段|表单加|列表加|"
    r"数据库|落库|补列|ALTER|迁移|"
    r"读写|CRUD|状态流转|开工|完工",
    re.I,
)

DATA_STACK_CHAIN_RULES = """
【完整链路 · 列表/表单新字段硬性】用户要「加一列 / 加字段 / 页面展示新业务数据」时，禁止只改前端：
1. **库表**：模型增加字段；已有库要补列（ALTER/迁移），不能只改新库。
2. **接口**：列表/详情/创建/更新的 schema 与返回值都带该字段；OpenAPI 用中文说明。
3. **写入**：业务动作（保存、开工、完工、编辑）要赋值；禁止只展示空列。
4. **前端**：列表、表单、详情同一字段；空值有约定（如 —）。
5. **旧数据必须回填**：列表里已开工/已完成却时间全空，视为未完成。演示库用同表计划日回填（开始 08:00、结束 18:00）。禁止以「无依据」跳过，只让待开工保持空。
6. **验收摘要必须写清**：库是否有列、接口 JSON 是否有字段、回填了几行、页面何时有值/何时为空。
纯 CSS/滚动壳（css_layout）或纯视觉复刻不套本条。
""".strip()


def looks_like_data_ui_change(text: str) -> bool:
    raw = text or ""
    if _CSS_ONLY_RE.search(raw):
        return False
    return bool(_DATA_FEATURE_RE.search(raw))
