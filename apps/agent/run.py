#!/usr/bin/env python3
"""
简化版 WorkBuddy — 启动入口。

用法:
    python run.py              # 交互式命令行
    python run.py demo         # 运行演示流程（无 LLM 需要时用 Mock）
    python run.py agent "导入 data/orders.csv 到订单系统"  # 单次调用
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()


def demo():
    """本地演示：仅使用 MockClient，不调用 LLM。"""
    from tools.platform_api import get_client
    from tools.file_ops import import_file_to_platform, export_platform_data, preview_file
    from tools.query_tool.platform_query import list_platform_entities, get_platform_summary

    get_client()

    print("=" * 60)
    print("  简化版 WorkBuddy — 本地演示（Mock 模式）")
    print("=" * 60)
    print()

    # 1. 平台概况
    print("1. 平台当前数据概况：")
    summary = get_platform_summary()
    for entity, info in summary["breakdown"].items():
        count = info["record_count"] if isinstance(info, dict) else info
        label = info.get("label", entity) if isinstance(info, dict) else entity
        print(f"   - {label}（{entity}）: {count} 条记录")
    print()

    # 2. 列出实体详情
    print("2. 可用实体及字段：")
    entities = list_platform_entities()
    for d in entities["details"]:
        print(f"   {d['entity']}: {d['fields']}  ({d['record_count']} 条)")
    print()

    # 3. 创建测试文件并导入
    print("3. 创建测试数据文件并导入到平台...")

    test_dir = os.path.join(os.path.dirname(__file__), "test_data")
    os.makedirs(test_dir, exist_ok=True)

    import pandas as pd

    # 创建测试 CSV
    test_csv = os.path.join(test_dir, "new_orders.csv")
    df = pd.DataFrame([
        {"order_no": "WO-T001", "product_name": "PCB-8L", "plan_quantity": 150, "status": "pending"},
        {"order_no": "WO-T002", "product_name": "PCB-4L", "plan_quantity": 300, "status": "in_progress"},
        {"order_no": "WO-T003", "product_name": "FPC-2L", "plan_quantity": 800, "status": "pending"},
    ])
    df.to_csv(test_csv, index=False, encoding="utf-8-sig")

    result = import_file_to_platform(test_csv, "work-orders")
    print(f"   导入结果: {result['status']}, 导入了 {result['rows_imported']} 条记录")
    print(f"   文件列: {result['columns']}")
    print()

    # 4. 预览文件
    print("4. 文件预览功能演示：")
    preview = preview_file(test_csv)
    print(f"   文件: {preview['file']}, 共 {preview['total_rows']} 行")
    for row in preview["preview"]:
        print(f"     {row}")
    print()

    # 5. 导出数据
    print("5. 导出数据到本地文件：")
    export_result = export_platform_data("work-orders", output_format="xlsx")
    print(f"   导出到: {export_result['file']}")
    print(f"   共 {export_result['rows']} 条记录")
    print()

    # 6. 导入后的平台状态
    print("6. 导入后平台数据：")
    summary = get_platform_summary()
    for entity, info in summary["breakdown"].items():
        count = info["record_count"] if isinstance(info, dict) else info
        label = info.get("label", entity) if isinstance(info, dict) else entity
        print(f"   - {label}（{entity}）: {count} 条记录")
    print()
    print("=" * 60)
    print("  演示完成！以上流程完全由 MockClient 驱动，无需真实平台。")
    print("  接下来可以：")
    print("  1. 配置 .env 中的 SILICONFLOW_API_KEY 后运行 python run.py agent")
    print("  2. 配置 PLATFORM_API_KEY 连接真实平台后运行全功能 Agent")
    print("=" * 60)


def agent_mode(prompt: str = ""):
    """Agent 模式：单次自然语言调用。"""
    from agents.agent import create_agent

    agent = create_agent()
    config = {"configurable": {"thread_id": "single-shot"}}

    if prompt:
        print(f"> {prompt}")
        print("处理中...", flush=True)
        result = agent.invoke(
            {"messages": [{"role": "user", "content": prompt}]},
            config=config,
        )
        print(f"\n{result['messages'][-1].content}")
    else:
        from agents.agent import run_cli
        run_cli()


def main():
    if len(sys.argv) < 2:
        # 默认演示模式
        demo()
        return

    cmd = sys.argv[1]

    if cmd == "demo":
        demo()
    elif cmd == "agent":
        prompt = sys.argv[2] if len(sys.argv) > 2 else ""
        agent_mode(prompt)
    elif cmd == "cli":
        agent_mode()
    else:
        print(f"未知命令: {cmd}")
        print("用法: python run.py [demo|agent|cli]")
        sys.exit(1)


if __name__ == "__main__":
    main()
