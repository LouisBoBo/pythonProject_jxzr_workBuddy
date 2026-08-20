"""
业务场景 → 相关表包（只读本地字典）。

预置常见实施摸底场景；种子表 + 文档内关联关系做有限跳数扩展。
不连 ERP，不改 entities.json / WRITE_TOOLS。
"""
from __future__ import annotations

import json
from typing import Annotated, Any

from tools.schema_tool.mes_schema_parser import build_index, find_table_full
from tools.schema_tool.schema_infer import match_tables_for_stage

# 预置场景：种子表须存在于当前字典；缺失表在运行时自动跳过并记入 missing。
# 资料包可放 business_scenarios.json 按 id 覆盖/停用，换 MES 不必改代码。
_BUILTIN_SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "mo-to-warehouse",
        "title": "工单从下达到入库/仓储",
        "aliases": [
            "工单到入库",
            "下达入库",
            "生产入库",
            "工单仓储",
            "从工单到仓库",
            "工单下达入库",
        ],
        "description": "从主数据、工单下达、车间过站/包装，到仓储领料与货位相关表。",
        "stages": [
            {
                "name": "基础主数据",
                "tables": ["TBL_BD_ITEM", "TBL_BD_PROCESS", "TBL_BD_WC", "TBL_BD_CUSTOMER"],
            },
            {
                "name": "工单下达",
                "tables": ["TBL_MO", "TBL_MO_BARCODE_PROD_LINK", "TBL_MO_OUTS"],
            },
            {
                "name": "车间执行",
                "tables": ["TBL_SFC_WS_LOG", "TBL_SFC_RECIPE_LOT", "TBL_SFC_RECIPE_PRODUCT"],
            },
            {
                "name": "包装",
                "tables": [
                    "TBL_SFC_PACKAGE",
                    "TBL_SFC_PACKAGE_LOG",
                    "TBL_SFC_PACKAGE_RULE",
                    "TBL_SFC_PACKAGE_RULE_LINK",
                ],
            },
            {
                "name": "仓储与领料",
                "tables": [
                    "TBL_WMS_WAREHOUSE",
                    "TBL_WMS_AREA",
                    "TBL_WMS_LOCATION",
                    "TBL_WMS_PICKING_LOG",
                    "TBL_WMS_PICKING_LOG_DTL",
                    "TBL_WMS_LINE_RECORD",
                    "TBL_WMS_ITEM_BARCODE",
                ],
            },
        ],
    },
    {
        "id": "srm-receiving",
        "title": "采购收料到入库",
        "aliases": ["采购收料", "SRM收货", "供应商收货", "采购入库"],
        "description": "采购单、收货单与条码，再到仓库主数据/条码相关表。",
        "stages": [
            {
                "name": "主数据",
                "tables": ["TBL_BD_ITEM", "TBL_BD_SUPPLIER"],
            },
            {
                "name": "采购与交付",
                "tables": ["TBL_SRM_PO", "TBL_SRM_PO_DETAIL", "TBL_SRM_PO_DELIVERY"],
            },
            {
                "name": "收货",
                "tables": [
                    "TBL_SRM_RECEIVING",
                    "TBL_SRM_RECEIVING_DTL",
                    "TBL_SRM_RECEIVING_BARCODE",
                ],
            },
            {
                "name": "仓储衔接",
                "tables": [
                    "TBL_WMS_WAREHOUSE",
                    "TBL_WMS_ITEM_BARCODE",
                    "TBL_WMS_ITEM_PACKING_BARCODE",
                    "TBL_WMS_PRINT_LOG",
                ],
            },
        ],
    },
    {
        "id": "quality-ipqc",
        "title": "品质检验（IPQC/化验/客诉）",
        "aliases": ["品质", "IPQC", "检验", "化验", "客诉", "质量管理"],
        "description": "首件检验、药水化验、客诉相关表包。",
        "stages": [
            {
                "name": "检验",
                "tables": ["TBL_QM_INSPECT_RECORD", "TBL_QM_INSPECTION_RECORD_ITEM"],
            },
            {
                "name": "化验",
                "tables": ["TBL_QM_ASSAY_LOG", "TBL_QM_ASSAY_LOG_ITEM", "TBL_QM_MEDICINE_TANK"],
            },
            {
                "name": "物性送检",
                "tables": ["TBL_QM_PL_LOG", "TBL_QM_PL_LOG_ITEM"],
            },
            {
                "name": "客诉",
                "tables": ["TBL_QM_COMPLAINT", "TBL_QM_COMPLAINT_IMAGE", "TBL_QM_CC_EXCEPTION"],
            },
        ],
    },
    {
        "id": "oqc-shipment",
        "title": "出货报告（OQC）",
        "aliases": ["出货", "OQC", "出货报告", "出货检验"],
        "description": "出货报告生成与类型、物料关联。",
        "stages": [
            {
                "name": "出货报告",
                "tables": [
                    "TBL_OQC_SHIPMENT_REPORT",
                    "TBL_OQC_SHIPMENT_REPORT_TYPE",
                    "TBL_OQC_SHIPMENT_GENERATE",
                    "TBL_OQC_SHIPMENT_GENERATE_LOG",
                    "TBL_OQC_SHIPMENT_ITEM_LINK",
                ],
            },
            {
                "name": "相关主数据",
                "tables": ["TBL_BD_ITEM", "TBL_BD_CUSTOMER"],
            },
        ],
    },
    {
        "id": "eam-maintain-repair",
        "title": "设备点检保养与维修",
        "aliases": ["点检", "保养", "维修", "EAM", "设备维保"],
        "description": "保养任务、维修工单与物料/图片关联。",
        "stages": [
            {
                "name": "保养任务",
                "tables": [
                    "TBL_EAM_MAINTAIN_TASK",
                    "TBL_EAM_MAINTAIN_TASK_ITEM",
                    "TBL_EAM_MAINTAIN_TASK_ITEM_IMG",
                    "TBL_EAM_MAINTAIN_TASK_CHANGE_LOG",
                    "TBL_EAM_FREQUENCY",
                    "TBL_EAM_PM_TEMP_WC_LINK",
                ],
            },
            {
                "name": "维修",
                "tables": [
                    "TBL_EAM_REPAIR",
                    "TBL_EAM_REPAIR_MAN",
                    "TBL_EAM_REPAIR_MATERIAL",
                    "TBL_EAM_REPAIR_IMG",
                    "TBL_EAM_ERROR_CODE",
                ],
            },
            {
                "name": "设备主数据",
                "tables": ["TBL_BD_WC"],
            },
        ],
    },
    {
        "id": "spc-control",
        "title": "SPC 统计过程控制",
        "aliases": ["SPC", "过程控制", "控制图"],
        "description": "控制特性、规则与实时数据相关表。",
        "stages": [
            {
                "name": "控制特性",
                "tables": [
                    "TBL_SPC_CONTROL_CHARACTERISTIC",
                    "TBL_SPC_CONTROL_CHARACTERISTIC_LIMIT",
                    "TBL_SPC_CONTROL_CHARACTERISTIC_ITEM_LINK",
                    "TBL_SPC_CONTROL_CHARACTERISTIC_RULE_LINK",
                ],
            },
            {
                "name": "规则与数据",
                "tables": ["TBL_SPC_RULE_OF_DISSENT", "TBL_SPC_DATA_REAL"],
            },
        ],
    },
    {
        "id": "pcb-process-quality",
        "title": "PCB 工序与品质（AOI/过站/Lot）",
        "aliases": [
            "AOI",
            "SPI",
            "FQC",
            "过孔",
            "电镀",
            "防焊",
            "成型",
            "拼板",
            "Lot",
            "工序在制",
            "过站",
            "报废",
            "PCB品质",
            "pcb process",
        ],
        "description": "PCB 常见工序执行、检测不良与批次相关表；文档无种子表时按中文/英文关键字匹配。",
        "stages": [
            {
                "name": "工序与过站",
                "tables": ["TBL_BD_PROCESS", "TBL_SFC_WS_LOG", "TBL_SFC_RECIPE_LOT"],
            },
            {
                "name": "检测与品质",
                "tables": ["TBL_QC_AOI", "TBL_QC_SPI", "TBL_QC_FQC", "TBL_QC_SCRAP"],
            },
            {
                "name": "批次与拼板",
                "tables": ["TBL_SFC_LOT", "TBL_SFC_PANEL", "TBL_SFC_PACKAGE"],
            },
        ],
    },
]

# 阶段关键字：当前文档没有 TBL_* 时按表名/中文匹配。资料包 business_scenarios.json 仍可整段覆盖。
_STAGE_KEYWORDS: dict[str, dict[str, list[str]]] = {
    "mo-to-warehouse": {
        "基础主数据": ["物料", "工序", "工作中心", "客户", "item", "process", "customer"],
        "工单下达": ["工单", "制造订单", "派工", "work_order", "workorder"],
        "车间执行": ["过站", "车间", "配方", "报工", "sfc"],
        "包装": ["包装", "package"],
        "仓储与领料": ["仓储", "仓库", "库存", "入库", "出库", "领料", "货位", "wms"],
    },
    "srm-receiving": {
        "主数据": ["物料", "供应商", "supplier", "item"],
        "采购与交付": ["采购", "采购单", "purchase", "po"],
        "收货": ["收货", "收料", "receiving"],
        "仓储衔接": ["仓储", "仓库", "库存", "条码", "wms"],
    },
    "quality-ipqc": {
        "检验": ["检验", "质检", "ipqc", "inspect", "quality"],
        "化验": ["化验", "assay", "药水"],
        "物性送检": ["物性", "送检"],
        "客诉": ["客诉", "complaint", "投诉"],
    },
    "oqc-shipment": {
        "出货报告": ["出货", "oqc", "shipment", "发货"],
        "相关主数据": ["物料", "客户", "item", "customer"],
    },
    "eam-maintain-repair": {
        "保养任务": ["保养", "点检", "维保", "maintain", "inspection", "pm"],
        "维修": ["维修", "repair", "故障"],
        "设备主数据": ["设备", "工作中心", "equipment", "device"],
    },
    "spc-control": {
        "控制特性": ["spc", "控制图", "控制特性"],
        "规则与数据": ["spc", "过程控制"],
    },
    "pcb-process-quality": {
        "工序与过站": ["工序", "过站", "电镀", "防焊", "成型", "过孔", "sfc", "process", "wip"],
        "检测与品质": ["AOI", "SPI", "FQC", "报废", "不良", "检验", "aoi", "scrap", "defect"],
        "批次与拼板": ["Lot", "拼板", "Panel", "条码", "lot", "panel", "package"],
    },
}


def load_business_scenarios() -> list[dict[str, Any]]:
    scenes = [s for s in _BUILTIN_SCENARIOS if isinstance(s, dict) and s.get("id")]
    try:
        from mes_profile import profile_dir

        pdir = profile_dir()
        candidate = (pdir / "business_scenarios.json") if pdir is not None else None
    except Exception:
        candidate = None
    if candidate is None or not candidate.is_file() or candidate.stat().st_size <= 0:
        return scenes
    try:
        extra = json.loads(candidate.read_text(encoding="utf-8") or "{}")
    except Exception:
        return scenes
    if not isinstance(extra, dict):
        return scenes
    by_id = {str(s["id"]): s for s in scenes}
    for s in extra.get("scenarios") or []:
        if not isinstance(s, dict) or not s.get("id"):
            continue
        sid = str(s["id"])
        if s.get("disabled"):
            by_id.pop(sid, None)
            continue
        by_id[sid] = s
    return list(by_id.values())


def list_business_scenarios() -> dict[str, Any]:
    """列出预置的业务场景表包（实施摸底用）。

    用户问「有哪些业务场景」「工单到入库相关表」前可先看清单。
    """
    pack = load_business_scenarios()
    try:
        known = _index_lookup()
        schema_ok = True
    except Exception:
        known = {}
        schema_ok = False
    scenarios = []
    for s in pack:
        found = 0
        if known:
            found = _scenario_table_count(s, known)
        scenarios.append(
            {
                "id": s["id"],
                "title": s["title"],
                "aliases": s.get("aliases") or [],
                "description": s.get("description") or "",
                "stage_count": len(s.get("stages") or []),
                "tables_found": found,
                "bindable": bool(schema_ok and found > 0),
            }
        )
    return {
        "count": len(scenarios),
        "scenarios": scenarios,
        "note": (
            "预置场景按当前表结构匹配（精确表名或中文/关键字），不是写死某一套 TBL_ 前缀。"
            "资料包可放 business_scenarios.json 覆盖。非实时流程引擎，仅用于摸底对齐。"
        ),
    }


def _match_scenario(query: str) -> dict[str, Any] | None:
    q = (query or "").strip()
    if not q:
        return None
    q_l = q.lower()
    pack = load_business_scenarios()
    # exact id
    for s in pack:
        if s["id"] == q or s["id"].lower() == q_l:
            return s
    # title / alias contains
    for s in pack:
        if q in s["title"] or s["title"] in q:
            return s
        for a in s.get("aliases") or []:
            if q in a or a in q:
                return s
    # keyword score
    best: tuple[int, dict[str, Any] | None] = (0, None)
    for s in pack:
        blob = (s["title"] + " " + " ".join(s.get("aliases") or []) + " " + (s.get("description") or "")).lower()
        score = 0
        for tok in [q_l, *q.replace("到", " ").replace("/", " ").split()]:
            tok = tok.strip().lower()
            if len(tok) >= 2 and tok in blob:
                score += 2 if tok in (s["id"],) or tok in s["title"].lower() else 1
        if score > best[0]:
            best = (score, s)
    return best[1] if best[0] > 0 else None


def _index_lookup() -> dict[str, dict[str, Any]]:
    index = build_index()
    return {t["table"]: t for t in (index.get("tables") or []) if t.get("table")}


def _stage_keywords(scenario_id: str, stage: dict[str, Any]) -> list[str]:
    if stage.get("keywords"):
        return [str(x) for x in stage["keywords"] if str(x).strip()]
    by_stage = _STAGE_KEYWORDS.get(str(scenario_id) or "") or {}
    return list(by_stage.get(str(stage.get("name") or ""), []) or [])


def _resolve_stage_tables(
    scenario_id: str,
    stage: dict[str, Any],
    known: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    exact = [str(t) for t in (stage.get("tables") or []) if t]
    keywords = _stage_keywords(scenario_id, stage)
    return match_tables_for_stage(known, exact_names=exact, keywords=keywords, limit=8)


def _scenario_table_count(scenario: dict[str, Any], known: dict[str, dict[str, Any]]) -> int:
    names: set[str] = set()
    sid = str(scenario.get("id") or "")
    for stage in scenario.get("stages") or []:
        hits, _unused = _resolve_stage_tables(sid, stage, known)
        names.update(hits)
    return len(names)


def _expand_relations(
    seed_tables: list[str],
    known: dict[str, dict[str, Any]],
    max_hops: int = 1,
    max_extra: int = 20,
) -> list[dict[str, Any]]:
    """从种子表出发，按文档「关联关系」扩展 1 跳（默认可控）。"""
    visited = set(seed_tables)
    extras: list[dict[str, Any]] = []
    frontier = list(seed_tables)

    for _hop in range(max(0, max_hops)):
        nxt: list[str] = []
        for tname in frontier:
            if len(extras) >= max_extra:
                return extras
            full = find_table_full(tname)
            if not full:
                continue
            for rel in full.get("relations") or []:
                for peer in (rel.get("from_table"), rel.get("to_table")):
                    if not peer or peer in visited:
                        continue
                    if peer not in known:
                        continue
                    visited.add(peer)
                    meta = known[peer]
                    extras.append(
                        {
                            "table": peer,
                            "label": meta.get("label"),
                            "domain": meta.get("domain"),
                            "meaning": (meta.get("meaning") or "")[:100],
                            "via": f"{rel.get('from_table')}.{rel.get('from_field')} = {rel.get('to_table')}.{rel.get('to_field')}",
                            "from_seed": tname,
                        }
                    )
                    nxt.append(peer)
                    if len(extras) >= max_extra:
                        return extras
        frontier = nxt
        if not frontier:
            break
    return extras


def get_scenario_table_pack(
    scenario: Annotated[
        str,
        "场景 id（如 mo-to-warehouse）或中文说法（如 工单到入库、品质、出货）",
    ],
    expand_relations: Annotated[
        bool, "是否按字典关联关系向外扩跳（默认开）"
    ] = True,
    max_relation_hops: Annotated[int, "关联扩展跳数，默认 1，最大 2"] = 1,
) -> dict[str, Any]:
    """按业务场景串出主表 + 阶段表包（可选关联扩展）。

    适用：「工单从下达到入库相关表」「采购收料表包」「品质检验涉及哪些表」。
    """
    matched = _match_scenario(scenario)
    if not matched:
        return {
            "error": f"未匹配到场景: {scenario}",
            "hint": "先调用 list_business_scenarios 查看 id / 别名",
            "available": [{"id": s["id"], "title": s["title"]} for s in load_business_scenarios()],
        }

    try:
        known = _index_lookup()
    except Exception as e:
        return {"error": str(e)}

    hops = max(0, min(int(max_relation_hops or 1), 2))
    stages_out: list[dict[str, Any]] = []
    all_seed: list[str] = []
    unused_seeds: list[str] = []
    path_lines: list[str] = []
    sid = str(matched.get("id") or "")

    for stage in matched.get("stages") or []:
        hit_names, unused = _resolve_stage_tables(sid, stage, known)
        unused_seeds.extend(unused)
        rows = []
        for tname in hit_names:
            meta = known.get(tname) or {}
            rows.append(
                {
                    "table": tname,
                    "label": meta.get("label"),
                    "domain": meta.get("domain"),
                    "meaning": (meta.get("meaning") or "")[:120],
                    "field_count": meta.get("field_count"),
                }
            )
            all_seed.append(tname)
        stages_out.append({"name": stage.get("name"), "tables": rows, "table_count": len(rows)})
        if rows:
            labels = " → ".join(f"{r['label']}({r['table']})" for r in rows[:4])
            if len(rows) > 4:
                labels += f" …共{len(rows)}张"
            path_lines.append(f"{stage.get('name')}: {labels}")

    related: list[dict[str, Any]] = []
    if expand_relations and all_seed:
        related = _expand_relations(all_seed, known, max_hops=hops, max_extra=20)

    return {
        "scenario_id": matched["id"],
        "title": matched["title"],
        "description": matched.get("description"),
        "path_summary": " ｜ ".join(path_lines),
        "stages": stages_out,
        "seed_table_count": len(set(all_seed)),
        "related_by_schema": related,
        "related_count": len(related),
        "unused_builtin_seeds": unused_seeds[:20],
        "missing_in_doc": unused_seeds[:20] if not all_seed else [],
        "note": (
            "依据当前资料包表结构。预置 TBL_* 种子仅作加速；"
            "换平台后按表名/中文关键字匹配，不必改代码。"
            "关联扩展来自字典「关联关系」，不是运行时流程日志。"
            "不等于已对接 query_platform_data。"
        ),
    }
