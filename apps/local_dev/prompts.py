"""本机沙箱写码提示词。"""
from __future__ import annotations

import re


SYSTEM_PROMPT = """你是本机写码执行助手。你只能通过工具在**沙箱工作区**内读写文件，不能访问沙箱外路径。

规则：
1. **工具参数**里的 path：只用相对沙箱根的路径，禁止绝对路径，禁止用 `..` 逃逸沙箱。
2. 禁止读写 `.env`、证书、私钥等敏感文件。
3. **开工前必须先调用 `set_plan`**：用 4～12 条**给最终用户看的中文短句**（说清楚「做什么结果」），例如「增加设备看板后端接口」「接上左侧菜单入口」。禁止写 schemas、router、main.py、API 模块等开发黑话；不要在正文里再罗列「第一步/第二步」。
4. 每开始做某一步前调用 `update_plan_step(index, "running")`，该步完成后立刻 `update_plan_step(index, "done")`（index 从 0 起）。
5. **调用工具改文件时：正文保持空白或最多一句**；进度只走 `update_plan_step`，不要每轮重复「现在创建/追加某某」。
6. 先 list/read 了解结构，再最小必要改动；新项目可创建合理目录与入口文件。
7. **前端 import 路径（P0 · 写错会直接 Vite 红屏）**：
   - 源码里的 `from '../…'` / `from '../../…'` **可以且必须**按真实目录深度书写；这与规则 1（工具 path 禁止 `..`）无关。
   - 计算方式：从**当前文件所在目录**走到目标文件，每一级父目录写一层 `../`。
   - 例：`frontend/src/views/kanban/Foo.vue` → `frontend/src/api/bar.js` 必须是 `../../api/bar`，**禁止**写成 `../api/bar`（会解析到 `src/views/api`，目标不存在）。
   - 若仓库已有页面使用 `@/api/...` 或 `@/views/...`，新建页优先照抄别名，避免手算相对层数。
   - 写完 import 后：用 list_dir/read_file 确认目标文件在沙箱内真实存在；不要假设「api 一定在 views 上一级」。
8. **全部工具结束后**，再用简短中文总结改了哪些文件与如何验收；不要声称已改宿主机其它目录。
9. 工具结果 ok=false 时换思路，不要死循环同一失败路径。
"""


def build_user_prompt(*, requirement: str, workspace_hint: str, empty_target: bool) -> str:
    mode = "空目录新项目：请从零生成可运行的最小实现" if empty_target else "已有工程（已拷入沙箱）：请在现有结构上增量修改"
    return (
        f"【目标模式】{mode}\n"
        f"【用户确认的本机目录（仅同步目标，勿当可读绝对路径）】{workspace_hint}\n\n"
        f"【需求】\n{requirement.strip()}\n\n"
        f"请先 set_plan，再按步 update_plan_step 并改文件。\n"
    )


_STEP_LINE_RE = re.compile(
    r"^\s*(?:第\s*[一二三四五六七八九十百零〇\d]+\s*步|[（(]?\d+[）)]?[.、．])\s*[：:．.]?\s*(.+?)\s*$"
)


def parse_plan_steps_from_text(text: str) -> list[str]:
    """从「第一步：…」类正文兜底解析计划（模型未调 set_plan 时）。"""
    out: list[str] = []
    for line in str(text or "").splitlines():
        m = _STEP_LINE_RE.match(line.strip())
        if not m:
            continue
        title = m.group(1).strip()
        if title and title not in out:
            out.append(title[:80])
        if len(out) >= 12:
            break
    return out


TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "set_plan",
            "description": "开工前提交本轮进度步骤（给用户看的中文短句）。前端会显示每步状态。",
            "parameters": {
                "type": "object",
                "properties": {
                    "steps": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "4～12 条用户可读短句，如「增加设备看板页面」；勿写 schemas/router/文件名黑话；勿带「第N步」前缀",
                    }
                },
                "required": ["steps"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_plan_step",
            "description": "更新某一步状态：开始执行用 running，完成用 done",
            "parameters": {
                "type": "object",
                "properties": {
                    "index": {
                        "type": "integer",
                        "description": "步骤下标，从 0 开始",
                    },
                    "state": {
                        "type": "string",
                        "enum": ["running", "done", "error"],
                    },
                },
                "required": ["index", "state"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "列出沙箱内某相对目录的条目",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "相对路径，默认 .",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取沙箱内相对路径文本文件",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "写入/覆盖沙箱内相对路径文本文件",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mkdir",
            "description": "在沙箱内创建目录（可多层）",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
]
