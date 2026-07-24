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
from tools.query_tool.platform_query import (
    list_platform_entities,
    query_platform_data,
    describe_entity,
    get_platform_summary,
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
        )

    if provider == "deepseek":
        if not Config.DEEPSEEK_API_KEY:
            raise RuntimeError("请设置 DEEPSEEK_API_KEY 环境变量")
        return ChatOpenAI(
            model=Config.MODEL_NAME,
            api_key=Config.DEEPSEEK_API_KEY,
            base_url=Config.DEEPSEEK_BASE_URL,
        )

    if provider == "openai":
        return ChatOpenAI(model=Config.MODEL_NAME)

    raise ValueError(f"不支持的 LLM provider: {provider}")


def _build_backend() -> FilesystemBackend:
    """Skills / 文件系统工具的后端。

    virtual_mode=True：路径限制在 apps/agent 内，避免 Agent 读到仓库根 .env。
    """
    return FilesystemBackend(root_dir=str(AGENT_ROOT), virtual_mode=True)


def create_agent(model=None):
    """创建 Deep Agent 实例（含 Skills + 自定义 Middleware）。

    Args:
        model: LLM 实例，不传则根据配置自动构建
    """
    if model is None:
        model = build_model()

    return create_deep_agent(
        model=model,
        tools=TOOLS,
        system_prompt=build_system_prompt(),
        backend=_build_backend(),
        skills=SKILL_SOURCES,
        middleware=build_custom_middleware(),
        # 危险写操作可开人工确认，例如：
        # interrupt_on={"import_file_to_platform": True},
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
    config = {"configurable": {"thread_id": thread_id}}

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
