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
"""

_REVIEW_FINDING_ITEM = """
每条问题（P0/P1/P2）必须按下列四段写满，缺一不可；文件路径用完整相对路径：
#### Px-n: 简短标题
- **文件**：`path/to/File.ext`（行号若可知）
- **问题描述**：错在哪、为何危险、触发条件（禁止只写文件名）
- **问题代码**：
```语言
（从 file_contents 原样摘录的问题片段，含足够上下文）
```
- **修复建议**：怎么改、注意点（可验证）
- **修复代码**：
```语言
（可直接粘贴替换的修复示例，禁止空话）
```
"""

_GIT_REVIEW_PROMPT = """
【公开 Git 仓库审核 — 硬约束】
- 触发：【Git仓库已确认】或 page_context.git_repo_url（公开 https:// 地址）。
- **必须**走 Skill「git-code-review」，流程对齐本机 IDE 全仓审：
  1) request_git_list_source_files → 记下 total / batch_count
  2) i=0..batch_count-1：request_git_read_batch(batch_index=i) → **静默**记下问题 → 立刻下一批
  3) 全部完成后，**仅此时**输出一份完整「🔍 代码审核报告」
- **禁止**只用 request_git_review 抽样几份文件就结案（那是降级抽样，不是全仓）。
- **禁止** request_ide_review / request_ide_list_source_files / request_ide_read_batch / request_ide_read_files。
- **禁止** SSH（git@ / ssh://）、URL 内嵌 Token；一期仅公开 HTTPS。
- 【输出纪律】分批过程中禁止向用户输出任何正文；进度由系统过程区展示。输出区只允许终稿。
- 终稿第一行必须是「## 🔍 代码审核报告」；禁止英文过渡句。
- 审核范围=全部功能/业务源码（工具已排除配置/锁文件/样式/文档）。禁止只审 1～2 批就结案。
- 方法论：Viprasol + gate-90。全文中文。
""" + _REVIEW_FINDING_ITEM + """
【终稿】（全部批次完成后）
## 🔍 代码审核报告
仓库 / 审核范围(N 文件 M 批) / 引擎 / 结论
### 📊 问题总览（合并各批；条数必须与正文一致）
| 级别 | 数量 | 摘要 |
| P0 | … | … |
| P1 | … | … |
| P2 | … | … |
### 🔴 P0
（按上列四段逐条展开）
### 🟠 P1
（同上）
### 🟡 P2
（同上；P2 也须有问题代码+修复代码，可更短）
### 🎯 优先修复建议
（按 P0→P1 列出落地顺序）
"""

_IDE_REVIEW_PROMPT = """
【本机 IDE / 全仓代码审核 — 硬约束】
- 禁止 read_file/grep/glob 读本机绝对路径。
- 用户已选工程或说「审核代码」（且无 Git 仓库确认）：禁止再追问。
- 若消息含【Git仓库已确认】或 page_context.git_repo_url：本段不适用，走 git-code-review。
- **正确流程**（仅本机工程）：
  1) request_ide_list_source_files → 记下 total / batch_count（已自动只要功能源码）
  2) i=0..batch_count-1：request_ide_read_batch(batch_index=i) → **静默**记下问题 → 立刻下一批
  3) 全部完成后，**仅此时**输出一份完整「🔍 代码审核报告」
- 【输出纪律】分批过程中禁止向用户输出任何正文（含「共 N 个文件」「第 N 批纪要」）；
  进度由系统过程区展示。输出区只允许终稿报告。
- 终稿必须以「## 🔍 代码审核报告」作为输出区第一行；
  **禁止**任何英文过渡句（如 Now I have… / Let me compile… / Here is the report…）。
  正确：直接从报告标题写起。
- 审核范围=业务/功能代码。不要审配置/锁文件/样式/文档/uni_modules/locale/static 等。
- 禁止只审 1～2 批就结案。
- Bridge 离线且同机不可读、且用户给的是本机路径 → request_git_review(local_path=…)。
- 方法论：Viprasol + gate-90。用户可见全文中文。
""" + _REVIEW_FINDING_ITEM + """
【终稿】（全部批次完成后）
## 🔍 代码审核报告
工作区 / 审核范围(N 文件 M 批) / 引擎 / 结论
### 📊 问题总览（合并各批；条数必须与正文一致）
| 级别 | 数量 | 摘要 |
| P0 | … | … |
| P1 | … | … |
| P2 | … | … |
### 🔴 P0
（按上列四段逐条展开）
### 🟠 P1
（同上）
### 🟡 P2
（同上；P2 也须有问题代码+修复代码，可更短）
### 🎯 优先修复建议
（按 P0→P1 列出落地顺序）
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
    # 先钉死互斥总路由，再分别挂贴码 / Git / IDE 三条车道说明（互不交叉）
    system_prompt = build_system_prompt() + _PASTE_CODE_ANALYZE_PROMPT
    if Config.IDE_REVIEW_ENABLED:
        from tools.ide_review import (
            request_git_list_source_files,
            request_git_read_batch,
            request_git_review,
            request_ide_list_source_files,
            request_ide_read_batch,
            request_ide_read_files,
            request_ide_review,
        )

        tools.append(request_ide_list_source_files)
        tools.append(request_ide_read_batch)
        tools.append(request_ide_review)
        tools.append(request_ide_read_files)
        tools.append(request_git_list_source_files)
        tools.append(request_git_read_batch)
        tools.append(request_git_review)
        system_prompt = system_prompt + _GIT_REVIEW_PROMPT + _IDE_REVIEW_PROMPT

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
