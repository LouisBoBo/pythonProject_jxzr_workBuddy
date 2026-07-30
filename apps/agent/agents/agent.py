"""
简化版 WorkBuddy — Deep Agent 主程序。

基于 Deep Agents harness：
- Tools：平台查询 / 文件导入导出
- Skills：按需加载的领域剧本（apps/agent/skills/）
- Middleware：横切逻辑（审计、守卫等，apps/agent/middleware/）
"""
from pathlib import Path

from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from config import Config
from middleware import build_custom_middleware
from tools.query_tool.entity_catalog import build_system_prompt
from tools.file_ops import import_file_to_platform, export_platform_data, transform_file, preview_file
from tools.write_audit_query import query_write_audit
from tools.query_tool.platform_query import (
    list_platform_entities,
    query_platform_data,
    describe_entity,
    get_platform_summary,
)
from tools.schema_tool.schema_query import (
    list_schema_domains,
    list_schema_tables,
    describe_schema_table,
    analyze_schema_capabilities,
    rebuild_schema_index,
)
from tools.schema_tool.business_scenarios import (
    list_business_scenarios,
    get_scenario_table_pack,
)
from tools.schema_tool.schema_report import export_schema_survey_report
from tools.schema_tool.capability_map import (
    list_platform_capabilities,
    describe_platform_capability,
    list_platform_glossary,
)
from tools.api_log_tool.api_health import (
    build_api_catalog,
    list_api_catalog,
    query_api_call_log,
    summarize_api_doc_vs_logs,
    rank_problematic_apis,
    inspect_api_path,
    probe_api_catalog,
    render_api_health_report,
    import_external_api_logs,
    analyze_api_errors_from_logs,
)

# apps/agent
AGENT_ROOT = Path(__file__).resolve().parents[1]
# 相对 FilesystemBackend root 的 POSIX 路径（须以 / 开头的虚拟路径）
SKILL_SOURCES = ["/skills/"]

SYSTEM_PROMPT = build_system_prompt()

TOOLS = [
    list_platform_entities,
    get_platform_summary,
    describe_entity,
    query_platform_data,
    import_file_to_platform,
    export_platform_data,
    transform_file,
    preview_file,
    query_write_audit,
    # 表结构文档分析（只读本地 docs，不影响 ERP 查/导）
    list_schema_domains,
    list_schema_tables,
    describe_schema_table,
    analyze_schema_capabilities,
    rebuild_schema_index,
    list_business_scenarios,
    get_scenario_table_pack,
    export_schema_survey_report,
    list_platform_capabilities,
    describe_platform_capability,
    list_platform_glossary,
    # API：文档接口测试一律默认沙箱探活再分析；live 仅明确要生产只读时
    build_api_catalog,
    list_api_catalog,
    query_api_call_log,
    summarize_api_doc_vs_logs,
    rank_problematic_apis,
    inspect_api_path,
    probe_api_catalog,
    render_api_health_report,
    import_external_api_logs,
    analyze_api_errors_from_logs,
]


def build_model():
    """根据配置构建 LLM 实例。支持硅基流动 / DeepSeek / OpenAI。"""
    provider = Config.LLM_PROVIDER

    if provider == "siliconflow":
        if not Config.SILICONFLOW_API_KEY:
            raise RuntimeError("请设置 SILICONFLOW_API_KEY 环境变量")
        return ChatOpenAI(
            model=Config.MODEL_NAME,
            api_key=Config.SILICONFLOW_API_KEY,
            base_url=Config.SILICONFLOW_BASE_URL,
            timeout=120,
            max_retries=3,
        )

    if provider == "deepseek":
        if not Config.DEEPSEEK_API_KEY:
            raise RuntimeError("请设置 DEEPSEEK_API_KEY 环境变量")
        return ChatOpenAI(
            model=Config.MODEL_NAME,
            api_key=Config.DEEPSEEK_API_KEY,
            base_url=Config.DEEPSEEK_BASE_URL,
            timeout=120,
            max_retries=3,
        )

    if provider == "openai":
        return ChatOpenAI(model=Config.MODEL_NAME)

    raise ValueError(f"不支持的 LLM provider: {provider}")


def _build_backend() -> FilesystemBackend:
    """Skills / 文件系统工具的后端。

    virtual_mode=True：路径限制在 apps/agent 内，避免 Agent 读到仓库根 .env。
    """
    return FilesystemBackend(root_dir=str(AGENT_ROOT), virtual_mode=True)


_IDE_REVIEW_PROMPT = """
【本机 IDE / 代码审核 — 硬约束】
- 禁止 read_file/grep/glob 读本机绝对路径。
- 已选工程或「审核代码」：禁止再追问，立刻 request_ide_review。
- file_contents 不足则 request_ide_read_files；并按 gate-90 补拉依赖/配置
  （pom.xml、package.json、requirements.txt、application*.yml/properties、appsettings.json、go.mod 等存在者）。
- Bridge 离线 → request_git_review；selected-not-open ≠ 离线。
- 方法论：Viprasol（/skills/code-review/references/viprasol-skill.md）+
  公司门禁（/skills/code-review/references/workbuddy-gate-90.md）：
  必扫依赖/配置/日志脱敏；鉴权缺失与数据损坏竞态可上调 P0；
  P0/P1 必须含可粘贴修复 + 验证（复现与通过标准）；总览条数=正文条数。
- 禁止自造检查清单替代上述两份 reference。
- 【语言】用户可见全文必须中文（含报告前过渡句、处理过程旁白）。
  禁止输出英文句子，例如 "Now I have all files…" / "Let me compile the report"。
  可保留：代码、路径、CVE/CWE、命令、专有名词缩写。
  正确示例：「源码已齐，开始汇总审核报告。」

【终稿】
## 🔍 代码审核报告
工作区 / 审核范围(含未覆盖) / 引擎(Bridge+Viprasol+gate-90) / 结论 / 重点
### 📊 问题总览（数量自洽）
### 🔴 P0（触发+修复代码+验证）
### 🟠 P1（同上）
### 🟡 P2
### ✅ 质量较好的部分
### 🎯 优先修复建议
### 🔎 验证清单（可选）
"""


def create_agent(model=None):
    """创建 Deep Agent 实例（含 Skills + 自定义 Middleware）。

    Args:
        model: LLM 实例，不传则根据配置自动构建
    """
    if model is None:
        model = build_model()

    tools = list(TOOLS)
    system_prompt = build_system_prompt()
    # 仅特性开关打开时追加；模块级 TOOLS 保持不变，默认现网行为一致
    if Config.IDE_REVIEW_ENABLED:
        from tools.ide_review import (
            request_git_review,
            request_ide_read_files,
            request_ide_review,
        )

        tools.append(request_ide_review)
        tools.append(request_ide_read_files)
        tools.append(request_git_review)
        system_prompt = system_prompt + _IDE_REVIEW_PROMPT

    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        backend=_build_backend(),
        skills=SKILL_SOURCES,
        middleware=build_custom_middleware(),
        # 危险写操作已由 MesWriteConfirmMiddleware + REQUIRE_WRITE_CONFIRM 管控（默认开启）
        # 勿在此重复开 interrupt_on，除非另行接入 LangGraph resume 审批流。
    )


def run_cli():
    """命令行交互模式。"""
    print("=" * 60)
    print("  简化版 WorkBuddy — 平台运维助手")
    print("=" * 60)
    print(f"  {Config.summary().replace(chr(10), chr(10) + '  ')}")
    print(f"  Skills: {AGENT_ROOT / 'skills'}")
    print(f"  Middleware: {[m.name for m in build_custom_middleware()]}")
    print()
    print("  输入命令或自然语言操作，输入 quit/exit 退出")
    print("-" * 60)

    agent = create_agent()
    thread_id = "cli-session-001"
    config = {
        "configurable": {"thread_id": thread_id},
        "recursion_limit": Config.AGENT_RECURSION_LIMIT,
    }

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        print("处理中...", flush=True)
        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config,
            )
            reply = result["messages"][-1].content
            print(f"\n{reply}")
        except Exception as e:
            print(f"\n[错误] {e}")
