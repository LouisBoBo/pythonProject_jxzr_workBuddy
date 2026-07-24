"""
Agent 包装器 — 将 apps/agent 的 Agent 封装为服务端可调用接口。
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENT_PATH = REPO_ROOT / "apps" / "agent"
if str(AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(AGENT_PATH))

from agents.agent import create_agent, build_model  # noqa: E402


class AgentRunner:
    """单例 Agent 运行器，避免每次请求重新创建 Deep Agent。"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._agent = None
            cls._instance._model = None
        return cls._instance

    @property
    def agent(self):
        if self._agent is None:
            self._model = build_model()
            self._agent = create_agent(model=self._model)
        return self._agent

    def _build_message(self, message: str, file_paths: list[str] | None = None) -> str:
        """将用户输入与文件路径合并为最终发送给 Agent 的 prompt。"""
        if not file_paths:
            return message
        file_note = "\n".join([f"[附件路径]: {p}" for p in file_paths])
        return f"{message}\n\n用户已上传以下文件，请按需读取或导入：\n{file_note}"

    def chat(self, message: str, thread_id: str = "default", file_paths: list[str] | None = None) -> str:
        """同步调用 Agent，返回完整回复文本。"""
        final_message = self._build_message(message, file_paths)
        result = self.agent.invoke(
            {"messages": [{"role": "user", "content": final_message}]},
            config={"configurable": {"thread_id": thread_id}},
        )
        return result["messages"][-1].content

    async def stream_chat(self, message: str, thread_id: str = "default", file_paths: list[str] | None = None):
        """异步流式调用 Agent，逐 token yield。"""
        final_message = self._build_message(message, file_paths)
        async for event in self.agent.astream_events(
            {"messages": [{"role": "user", "content": final_message}]},
            config={"configurable": {"thread_id": thread_id}},
            version="v2",
        ):
            kind = event.get("event", "")
            if kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and chunk.content:
                    yield chunk.content
