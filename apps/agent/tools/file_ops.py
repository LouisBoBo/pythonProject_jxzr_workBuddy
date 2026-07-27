"""
文件操作工具集：CSV / Excel / JSON 读写、数据校验与格式转换。
"""
import csv
import json
import os
from datetime import datetime
from typing import Annotated, Literal

import pandas as pd

from config import Config
from tools.platform_api import get_client


def import_file_to_platform(
    file_path: Annotated[str, "本地文件的绝对路径（如 /Users/xxx/data/orders.csv）"],
    target_entity: Annotated[str, "平台目标实体英文 id（如 work-orders、production-plans）"],
    file_type: Annotated[
        Literal["csv", "excel", "json"] | None,
        "文件类型；不传则按扩展名自动判断",
    ] = None,
    sheet_name: Annotated[str, "Excel 工作表名，默认 Sheet1"] = "Sheet1",
) -> dict:
    """从本地文件读取数据，导入到平台指定实体中。

    支持 CSV、Excel(.xlsx/.xls) 和 JSON 格式。
    Agent 应该先调用 list_platform_entities 确认目标实体存在。
    """
    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}

    try:
        # 自动推断文件类型
        if file_type is None:
            ext = os.path.splitext(file_path)[1].lower()
            type_map = {".csv": "csv", ".xlsx": "excel", ".xls": "excel", ".json": "json"}
            file_type = type_map.get(ext)
            if not file_type:
                return {"error": f"无法识别的文件类型: {ext}，支持的格式: csv, xlsx, xls, json"}

        # 读取文件
        if file_type == "csv":
            df = pd.read_csv(file_path, encoding="utf-8")
        elif file_type == "excel":
            df = pd.read_excel(file_path, sheet_name=sheet_name)
        elif file_type == "json":
            df = pd.read_json(file_path)

        row_count = len(df)
        if row_count == 0:
            return {"error": "文件为空，没有可导入的数据"}
        if row_count > Config.MAX_IMPORT_ROWS:
            return {"error": f"数据量过大（{row_count} 行），上限 {Config.MAX_IMPORT_ROWS} 行"}

        # 数据清洗：处理 NaN 和类型转换
        df = df.where(pd.notna(df), None)

        # 检查字段兼容性
        client = get_client()
        entity_info = client.describe_entity(target_entity)
        if "error" in entity_info:
            return {"warning": f"目标实体 '{target_entity}' 可能不存在，将尝试自动创建"}

        # 转换为字典列表并导入
        records = df.to_dict(orient="records")
        result = client.import_data(target_entity, records)

        return {
            "status": result.get("status", "unknown"),
            "file": os.path.basename(file_path),
            "rows_read": row_count,
            "rows_imported": result.get("imported", 0),
            "target_entity": target_entity,
            "columns": list(df.columns),
        }

    except UnicodeDecodeError:
        # 尝试 GBK 编码
        try:
            df = pd.read_csv(file_path, encoding="gbk")
            records = df.where(pd.notna(df), None).to_dict(orient="records")
            result = get_client().import_data(target_entity, records)
            return {
                "status": result.get("status", "ok"),
                "file": os.path.basename(file_path),
                "rows_imported": len(records),
                "target_entity": target_entity,
            }
        except Exception as e2:
            return {"error": f"文件编码错误，尝试了 UTF-8 和 GBK 均失败: {e2}"}
    except Exception as e:
        return {"error": f"导入失败: {str(e)}"}


def export_platform_data(
    entity: Annotated[str, "平台实体英文 id 或中文别名"],
    output_format: Annotated[
        Literal["csv", "excel", "json"], "导出格式：csv / excel / json"
    ] = "csv",
    filters: Annotated[dict | None, '可选过滤条件，如 {"status": "生产中"}'] = None,
    output_dir: Annotated[str | None, "输出目录；默认使用配置的 EXPORT_DIR"] = None,
) -> dict:
    """从平台导出指定实体的数据到本地文件。"""
    client = get_client()

    # 获取数据
    data = client.export_data(entity, filters)
    if isinstance(data, dict) and "error" in data:
        return data
    if not data:
        return {"error": f"实体 '{entity}' 没有数据可导出"}

    # 确定输出目录
    out_dir = output_dir or Config.EXPORT_DIR
    os.makedirs(out_dir, exist_ok=True)

    # 生成文件名：格式别名 excel 统一输出为 .xlsx 扩展名
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "xlsx" if output_format in ("excel", "xlsx") else output_format
    filename = f"{entity}_{ts}.{ext}"
    file_path = os.path.join(out_dir, filename)

    # 写入文件
    df = pd.DataFrame(data)

    if output_format == "csv":
        df.to_csv(file_path, index=False, encoding="utf-8-sig")
    elif output_format in ("excel", "xlsx"):
        df.to_excel(file_path, index=False, sheet_name=entity[:31], engine="openpyxl")
    elif output_format == "json":
        df.to_json(file_path, orient="records", force_ascii=False, indent=2)

    return {
        "status": "ok",
        "file": file_path,
        "format": output_format,
        "rows": len(data),
        "columns": list(df.columns),
    }


def transform_file(
    file_path: Annotated[str, "输入文件路径"],
    output_format: Annotated[Literal["csv", "excel", "json"], "输出格式：csv / excel / json"],
    column_map: Annotated[
        dict[str, str] | None,
        '字段名映射，如 {"客户名": "customer", "产量": "quantity"}',
    ] = None,
    filter_condition: Annotated[
        str | None, 'pandas 查询表达式，如 "quantity > 100"'
    ] = None,
    sort_by: Annotated[str | None, "排序字段名"] = None,
) -> dict:
    """读取一个文件，进行格式转换、字段映射、筛选和排序，输出为新文件。"""
    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}

    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        elif ext == ".csv":
            df = pd.read_csv(file_path)
        elif ext == ".json":
            df = pd.read_json(file_path)
        else:
            return {"error": f"不支持的文件类型: {ext}"}

        # 字段映射
        if column_map:
            df = df.rename(columns=column_map)

        # 条件筛选
        if filter_condition:
            try:
                df = df.query(filter_condition)
            except Exception as e:
                return {"error": f"筛选条件执行失败: {e}"}

        # 排序
        if sort_by:
            if sort_by in df.columns:
                df = df.sort_values(by=sort_by)
            else:
                return {"error": f"排序字段 '{sort_by}' 不存在，可用字段: {list(df.columns)}"}

        # 输出：格式别名 excel 统一输出为 .xlsx 扩展名
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.splitext(os.path.basename(file_path))[0]
        ext = "xlsx" if output_format in ("excel", "xlsx") else output_format
        out_path = os.path.join(os.path.dirname(file_path) or ".", f"{base}_transformed_{ts}.{ext}")

        if output_format == "csv":
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
        elif output_format in ("excel", "xlsx"):
            df.to_excel(out_path, index=False, engine="openpyxl")
        elif output_format == "json":
            df.to_json(out_path, orient="records", force_ascii=False, indent=2)

        return {
            "status": "ok",
            "input": os.path.basename(file_path),
            "output": out_path,
            "rows_after_transform": len(df),
            "columns": list(df.columns),
        }
    except Exception as e:
        return {"error": f"转换失败: {str(e)}"}


def preview_file(
    file_path: Annotated[str, "文件路径"],
    rows: Annotated[int, "预览行数，默认 5"] = 5,
) -> dict:
    """预览文件的前 N 行内容，帮助确认数据格式是否正确。"""
    if not os.path.exists(file_path):
        return {"error": f"文件不存在: {file_path}"}

    try:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
        elif ext == ".csv":
            df = pd.read_csv(file_path)
        elif ext == ".json":
            df = pd.read_json(file_path)
        else:
            return {"error": f"不支持的文件类型: {ext}"}

        total = len(df)
        preview_df = df.head(rows).where(pd.notna(df.head(rows)), None)

        return {
            "file": os.path.basename(file_path),
            "total_rows": total,
            "total_columns": len(df.columns),
            "columns": list(df.columns),
            "preview": preview_df.to_dict(orient="records"),
        }
    except Exception as e:
        return {"error": f"预览失败: {str(e)}"}
