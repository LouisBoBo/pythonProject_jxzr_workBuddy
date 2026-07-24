"""
实体目录：从 entities.json 加载平台可操作实体。

加新 API（标准 CRUD）时只需改 entities.json，无需改工具代码。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_CATALOG_PATH = Path(__file__).resolve().parent / "entities.json"


@lru_cache(maxsize=1)
def load_catalog() -> list[dict[str, Any]]:
    """加载实体列表。"""
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("entities", [])


def get_entity_map() -> dict[str, str]:
    """实体 id → REST 资源路径。"""
    return {e["id"]: e.get("path", e["id"]) for e in load_catalog()}


def get_entity(entity_id: str) -> dict[str, Any] | None:
    for e in load_catalog():
        if e["id"] == entity_id:
            return e
    return None


def _alias_terms(entity: dict[str, Any]) -> list[str]:
    """收集可用于匹配的全部说法（label + aliases），去重。"""
    terms: list[str] = []
    label = entity.get("label")
    if label:
        terms.append(str(label))
    for a in entity.get("aliases") or []:
        if a and a not in terms:
            terms.append(str(a))
    return terms


def resolve_entity_id(name: str) -> str | None:
    """将实体 id 或各种中文/英文说法解析为标准 id。

    匹配顺序：
    1. 精确匹配 id / label / aliases（大小写不敏感）
    2. 模糊：名称包含某个别名，或别名包含名称 → 取最长命中，避免短词误伤
    """
    if not name:
        return None
    key = name.strip()
    key_lower = key.lower()

    # 1) 精确匹配
    for e in load_catalog():
        if key == e["id"] or key_lower == e["id"].lower():
            return e["id"]
        for term in _alias_terms(e):
            if key == term or key_lower == term.lower():
                return e["id"]

    # 2) 包含匹配（最长别名优先）
    # - 优先：别名出现在用户说法中（「查一下排程计划」含「排程计划」）
    # - 其次：用户说法是别名的片段且长度≥3（避免「生产」同时命中工单/计划）
    best: tuple[int, str] | None = None  # (score, entity_id)
    for e in load_catalog():
        for term in _alias_terms(e):
            t = term.strip()
            if len(t) < 2:
                continue
            tl = t.lower()
            if tl in key_lower:
                score = len(t) + 100  # 别名⊆用户说法，优先
            elif len(key) >= 3 and key_lower in tl:
                score = len(key)
            else:
                continue
            if best is None or score > best[0]:
                best = (score, e["id"])
    return best[1] if best else None


def list_entity_ids() -> list[str]:
    return [e["id"] for e in load_catalog()]


def catalog_summary() -> list[dict[str, Any]]:
    """供工具返回：id、中文名、别名、支持操作、字段概要。"""
    rows = []
    for e in load_catalog():
        fields = e.get("fields") or []
        rows.append({
            "entity": e["id"],
            "label": e.get("label", e["id"]),
            "aliases": e.get("aliases") or [],
            "ops": e.get("ops") or ["query"],
            "fields": [f["name"] if isinstance(f, dict) else f for f in fields],
        })
    return rows


def build_system_prompt() -> str:
    """根据实体目录生成 Agent 系统提示词。"""
    lines: list[str] = [
        "你是一个 PCB 制造执行系统（MES）的运维助手，帮助用户通过自然语言管理平台数据。",
        "",
        "## 平台实体目录",
        "",
        "调用工具时，entity / target_entity 必须使用下方「实体 id」（英文）。",
        "用户说法不统一很正常：同一实体的别名都指向同一个 id，尽量灵活理解，不要纠结用词。",
        "",
        "### 实体边界（灵活同义，但不要跨实体）",
        "- 「工单 / 生产工单 / 派工单 / WO …」→ `work-orders`",
        "- 「生产计划 / 排产计划 / 排程计划 / 排产 / 排程 …」→ `production-plans`（这些是同一类东西）",
        "- 同义说法都查同一个实体；**不要**把生产计划类问题答成工单，也不要用另一实体数据充数",
        "- 查空或失败时如实说明，勿改查别的实体",
        "",
    ]

    for e in load_catalog():
        label = e.get("label", e["id"])
        aliases = "、".join(e.get("aliases") or [label])
        ops = ", ".join(e.get("ops") or ["query"])
        lines.append(f"### {label}（`{e['id']}`）")
        lines.append(f"- 常见说法（均可）：{aliases}")
        lines.append(f"- 支持操作：{ops}")
        fields = e.get("fields") or []
        if fields:
            field_parts = []
            for f in fields:
                if isinstance(f, dict):
                    field_parts.append(f"{f['name']}（{f.get('label', f['name'])}）")
                else:
                    field_parts.append(str(f))
            lines.append(f"- 字段：{', '.join(field_parts)}")
        lines.append("")

    lines.extend([
        "## 你的核心能力",
        "",
        "### 查看平台数据",
        "示例（说法不同，实体相同）：",
        '- 「查工单 / 看看生产工单」→ query_platform_data(entity="work-orders")',
        '- 「查生产计划 / 排产计划 / 排程计划」→ query_platform_data(entity="production-plans")',
        "- 不确定说法对应哪个实体时，先 list_platform_entities，对照 aliases 选择",
        "- 需要字段结构时调用 describe_entity",
        "",
        "### 文件导入",
        "用户说「把这批数据导入」时：",
        "1. 先 preview_file 预览文件",
        "2. 确认目标实体后，import_file_to_platform，target_entity 填英文 id",
        "3. 告知成功/失败条数",
        "",
        "### 数据导出",
        "用户说「把 XX 导出来」时：",
        "- export_platform_data，entity 填英文 id，可选 format（csv/excel/json）",
        "",
        "### 文件格式转换",
        "- 使用 transform_file 或 preview_file",
        "",
        "## 重要规则",
        "- entity / target_entity 只用实体目录中的英文 id；中文说法先映射到 id",
        "- 回复可用用户原话（如「排程计划」），但工具参数必须是英文 id",
        "- 导入前检查文件存在且格式正确",
        "- 遇到错误时明确告知原因并给出建议",
        "- 用中文回复，简洁专业",
    ])
    return "\n".join(lines)
