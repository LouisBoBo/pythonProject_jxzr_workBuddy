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
    summarize_platform_data,
    analyze_platform_brief,
    describe_entity,
    get_platform_summary,
    list_query_metrics,
    query_metric,
)
from tools.query_tool.analysis_chart import render_analysis_chart
from tools.query_tool.analysis_dashboard import render_analysis_dashboard
from tools.query_tool.analysis_demo import list_analysis_demos, run_analysis_demo
from tools.query_tool.ops_playbook import list_ops_scenes, run_ops_scene
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
from tools.schema_tool.schema_diff import compare_schema_vs_catalog
from tools.schema_tool.profile_readiness import (
    inspect_mes_profile,
    refresh_mes_profile_from_runtime,
)
from tools.query_tool.dev_preflight import mes_change_preflight
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

try:
    from bundle_root import resolve_agent_root

    AGENT_ROOT = resolve_agent_root()
except Exception:  # noqa: BLE001 — 兜底源码布局
    AGENT_ROOT = Path(__file__).resolve().parents[1]
# 相对 FilesystemBackend root 的 POSIX 路径（须以 / 开头的虚拟路径）
SKILL_SOURCES = ["/skills/"]

SYSTEM_PROMPT = build_system_prompt()

TOOLS = [
    list_platform_entities,
    get_platform_summary,
    describe_entity,
    query_platform_data,
    summarize_platform_data,
    analyze_platform_brief,
    list_query_metrics,
    query_metric,
    render_analysis_chart,
    render_analysis_dashboard,
    list_analysis_demos,
    run_analysis_demo,
    list_ops_scenes,
    run_ops_scene,
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
    compare_schema_vs_catalog,
    inspect_mes_profile,
    refresh_mes_profile_from_runtime,
    mes_change_preflight,
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
    """根据配置构建 LLM 实例（OpenAI 兼容协议：任意供应商）。"""
    api_key = (Config.LLM_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError(
            "请设置对话模型 API Key（可在「系统配置」填写，或配置 LLM_API_KEY / DEEPSEEK_API_KEY）"
        )
    kwargs: dict = {
        "model": Config.MODEL_NAME,
        "api_key": api_key,
        "timeout": 120,
        "max_retries": 3,
    }
    base = (Config.LLM_BASE_URL or "").strip().rstrip("/")
    if base:
        kwargs["base_url"] = base
    return ChatOpenAI(**kwargs)


def _build_backend() -> FilesystemBackend:
    """Skills / 文件系统工具的后端。

    virtual_mode=True：路径限制在 apps/agent 内，避免 Agent 读到仓库根 .env。
    """
    return FilesystemBackend(root_dir=str(AGENT_ROOT), virtual_mode=True)


_PASTE_CODE_ANALYZE_PROMPT = """
【粘贴代码分析 — 对话读码，不是正式审核】
- 仅当用户自己粘贴了源码（markdown 代码围栏）且只是问这段有什么问题时：走 Skill「paste-code-analyze」。
- 【多轮】先判断意图再答：
  · 续写且带【已生成片段】：严格从片段末尾接着写；禁止「上文应已覆盖」；片段未出现的条目必须补全；最终=片段+续写。
  · 续写但带【完整重答指令】/几乎无正文：对【用户原任务】从头完整回答，禁止跳号、禁止假设已写过。
  · 补充原任务：合并补充后再答。
  · 新问题：按新问题答，勿强行续写旧半截。
  · 兑现「来吧/要完整版」：立刻交付完整代码。
- 写/改代码是正常对话能力。
- 仅当「消息里已有用户粘贴源码块、且用户只是问这段有什么问题」时：
  **禁止**调 request_ide_review / request_ide_read_files / request_git_review /
  request_git_list_source_files / request_git_read_batch；
  **禁止**输出「代码审核报告」壳。
- 若用户要审本机/已选工程（见【本机工程已确认】或 page_context.ide_workspace_root），
  **必须**走 ide-code-review / request_ide_review，本段粘贴禁令不适用。
- 若用户要审公开 Git 仓（见【Git仓库已确认】或 page_context.git_repo_url），
  **必须**走 git-code-review（list→read_batch），本段粘贴禁令不适用。全文中文。
- 若 workbuddy_lane=code_dev / 【写码需求讨论】：走写码分支，本段与审核段均不适用。
"""

_SCREENSHOT_PROMPT = """
【截图理解】
- 用户可在输入框粘贴或上传截图。系统会先用视觉模型生成【截图理解】文字块再交给你。
- 请结合【截图理解】与用户意图处理：排错、改 UI、写码讨论、MES 答疑等。
- 不要声称自己直接看到了像素；依据【截图理解】中的文字描述作答。
- 若用户说「改成这种 / 1:1 / 复刻 / 照着做 / 跟截图一样 / 按这个效果」等（不要求必须说「1:1」）且带【截图理解】：把截图当**视觉设计规格**（布局位置、图表类型、色块背景优先于纯数字文案），走写码讨论；质量优先于速度；
  禁止开放题问技术栈/仓库/「截图里有什么」；propose 禁止臆造截图没有的模块，禁止写成 Element 白卡片 KPI 模板。
- 若用户是「按截图改某处 / 图上这个按钮…」：按局部修改处理，不要默认整页复刻；若上下文其实要整页一样，再按视觉对齐。
- 若意图仍不清楚（例如只有截图、或话很短）：先用 1～2 个选择题反问确认目标
  （做成跟截图一样 / 按图改一部分 / 解释报错 / 查 MES / 审核代码），不要臆测后直接开干。
- 截图本身不改变车道：仍按用户确认的意图走 MES / 贴码 / 审核 / 写码。
"""

_CURSOR_DEV_CODING_PROMPT = """
【写码 · workbuddy_lane=code_dev — 与审核互斥】
- **必须**走 Skill「cursor-dev-chat」：短正文 + :::cursor_dev_options / :::cursor_dev_propose。
- 默认 target=local：本机沙箱 + **Cursor SDK Local Agent**（不经 DeepSeek 工具环）。
- 仅用户明确要 GitHub 时用 target=github（Cursor Cloud）。
- 业务页/看板同时启用 Skill「ui-product-design」。
- **禁止** request_git_* / request_ide_*；禁止 read_file 本机绝对路径；路径只写入 propose.workspace。
"""

# 审核详规在 Skills（git-code-review / ide-code-review / code-review），系统提示只保留路由。
_REVIEW_LANE_BRIEF = """
【代码审核 · workbuddy_lane=code_review — 与写码互斥】
- 公开 Git：Skill「git-code-review」→ request_git_list_source_files → request_git_read_batch(按序) → 终稿「## 🔍 代码审核报告」。
- 本机 IDE：Skill「ide-code-review」→ request_ide_list_source_files → request_ide_read_batch(按序) → 同上终稿。
- 方法论：Skill「code-review」(Viprasol) + gate-90；分批过程**禁止**向用户输出正文；末批后禁止再取码。
- **禁止** request_git_review 抽样结案；**禁止** :::cursor_dev_*。
"""


def create_agent(model=None, checkpointer=None):
    """创建 Deep Agent 实例（含 Skills + 自定义 Middleware）。

    Args:
        model: LLM 实例，不传则根据配置自动构建
        checkpointer: LangGraph checkpointer。
            API 流式必须传 AsyncSqliteSaver；不传则用内存 InMemorySaver（CLI/单测）。
    """
    if model is None:
        model = build_model()
    if checkpointer is None:
        from langgraph.checkpoint.memory import InMemorySaver

        checkpointer = InMemorySaver()

    tools = list(TOOLS)
    # 写码 / 审核两条对等路由说明（按意图分叉，无优先级）
    system_prompt = (
        build_system_prompt()
        + _CURSOR_DEV_CODING_PROMPT
        + _PASTE_CODE_ANALYZE_PROMPT
        + _SCREENSHOT_PROMPT
    )
    if Config.IDE_REVIEW_ENABLED:
        from tools.ide_review import (
            request_ide_list_source_files,
            request_ide_read_batch,
            request_ide_read_files,
            request_ide_review,
        )

        tools.append(request_ide_list_source_files)
        tools.append(request_ide_read_batch)
        tools.append(request_ide_review)
        tools.append(request_ide_read_files)
        system_prompt = system_prompt + _REVIEW_LANE_BRIEF

    # 可选只读 SQL（默认关）
    if Config.READONLY_SQL_ENABLED:
        from tools.query_tool.readonly_sql import readonly_sql

        tools.append(readonly_sql)

    # 公开 Git 仓审核与 VS Code Bridge 解耦：桌面默认不开 IDE_REVIEW 也能审公开仓
    from tools.ide_review import (
        request_git_list_source_files,
        request_git_read_batch,
        request_git_review,
    )

    tools.append(request_git_list_source_files)
    tools.append(request_git_read_batch)
    tools.append(request_git_review)
    if not Config.IDE_REVIEW_ENABLED:
        system_prompt = system_prompt + _REVIEW_LANE_BRIEF

    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        backend=_build_backend(),
        skills=SKILL_SOURCES,
        middleware=build_custom_middleware(),
        # 按 thread_id 持久化多轮消息；否则每轮只见本句用户输入
        checkpointer=checkpointer,
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
