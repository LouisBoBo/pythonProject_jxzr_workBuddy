"""自定义自动化指令：AI 基于骨架扩写（不曲解意图）。"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

PROMPT_SKELETON = """【目标】（一句话：要产出什么）
【数据来源】MES 查数 / 联网检索 / 本仓库 git
【查数或检索步骤】
1. …
2. …
【输出格式】
- 共几条；每条含标题、要点；（新闻类须保留来源链接）
- 查不到的数据整段省略，禁止编造
【禁止】Markdown 表格、工具名、写码/提交/部署"""

_REWRITE_SYSTEM = """你是 ZR WorkBuddy 自动化任务「执行指令」改写助手。
用户会给出草稿意图；你要在理解意图后，按指令骨架扩写成更清晰、更易被执行 Agent 理解的中文指令。

硬性要求：
1. 不曲解、不增减业务目标；用户没提的指标/步骤不要擅自添加为「必须做」。
2. 可补充结构与可执行表述（目标、数据来源、步骤、输出格式、禁止项），使 LLM 更容易一次完成。
3. 必须采用下列骨架区块（可按意图删改条目，但保留【目标】【数据来源】【输出格式】；步骤/禁止按需）：
【目标】…
【数据来源】…
【查数或检索步骤】…
【输出格式】…
【禁止】…
4. 不要写调度时间、工作目录、企微/飞书配置（界面另配）。
5. 禁止引导写码、Git 提交、部署等需人工确认的操作。
6. 只输出改写后的指令正文，不要前言、后记或 Markdown 代码围栏。
"""


def _load_llm_client():
    import sys
    from pathlib import Path

    agent_root = Path(__file__).resolve().parents[1] / "agent"
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    from config import Config  # type: ignore

    try:
        Config.reload_runtime()
    except Exception:
        pass
    api_key = (Config.LLM_API_KEY or "").strip()
    if not api_key:
        raise RuntimeError("未配置对话模型 API Key（系统配置 → LLM_API_KEY）")
    from openai import OpenAI

    kwargs: dict[str, Any] = {"api_key": api_key}
    base = (Config.LLM_BASE_URL or "").strip().rstrip("/")
    if base:
        kwargs["base_url"] = base
    client = OpenAI(**kwargs)
    from llm_model_guard import assert_llm_model_allowed

    model = assert_llm_model_allowed(Config.MODEL_NAME or "deepseek-chat")
    return client, model


def _strip_fences(text: str) -> str:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:\w+)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def rewrite_automation_prompt(
    draft: str,
    *,
    task_name: str = "",
) -> str:
    """将用户草稿扩写为结构化执行指令。"""
    text = str(draft or "").strip()
    if not text:
        raise ValueError("请先填写几句任务意图，再使用 AI 改写")
    if len(text) > 8000:
        text = text[:8000]

    name = str(task_name or "").strip()[:120]
    user_parts = [
        f"【任务名称】{name}" if name else "",
        "【指令骨架参考】",
        PROMPT_SKELETON,
        "",
        "【用户草稿】",
        text,
        "",
        "请输出改写后的完整执行指令：",
    ]
    user_msg = "\n".join(p for p in user_parts if p is not None)

    client, model = _load_llm_client()
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            max_tokens=2048,
            timeout=45.0,
            messages=[
                {"role": "system", "content": _REWRITE_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("automation prompt rewrite failed: %s", type(exc).__name__)
        raise RuntimeError("AI 改写失败，请稍后重试") from exc

    choice = (resp.choices or [None])[0]
    content = ""
    if choice is not None:
        msg = getattr(choice, "message", None)
        content = getattr(msg, "content", None) or ""
    out = _strip_fences(str(content))
    if not out:
        raise RuntimeError("AI 未返回有效指令，请重试或手工完善")
    if len(out) > 8000:
        out = out[:8000]
    return out
