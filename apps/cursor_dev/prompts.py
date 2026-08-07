"""写码会话系统 Prompt 拼装。"""
from __future__ import annotations


def build_first_turn_prompt(
    *,
    user_message: str,
    repo: str,
    work_branch: str,
    base_ref: str = "",
    create_pr: bool = False,
) -> str:
    """一用户一分支：所有改动落在固定工作分支，禁止按功能开新分支。"""
    base = (base_ref or "").strip() or "仓库默认分支（通常 main）"
    if create_pr:
        pr_rule = (
            "本轮用户要求创建 PR：完成后开 PR 指向默认分支（main），标题写清变更摘要。"
            "优先用平台能力开 PR；工作分支必须仍是上述固定分支名。"
        )
    else:
        pr_rule = (
            "【禁止开 PR · 用户未勾选】硬性约束：\n"
            "- 不要创建 Pull Request，不要调用 ManagePullRequest / create_pull_request。\n"
            "- 不要执行 `gh pr create`、`hub pull-request` 或任何等价开 PR 命令。\n"
            "- 不要因为工具要求 `cursor/` 前缀分支就改分支名或强行开 PR。\n"
            "- 只把代码 push 到固定工作分支；合入 main 由用户稍后手动处理。\n"
            "- 结束摘要不要写「已创建 PR」；可写分支名与 commit，并提示用户自行合 main。"
        )
    return (
        "你是代码实现 Agent，在用户的同一聊天会话中协作改仓库。\n"
        "每一轮只做当前要求。正文只输出一遍完整摘要，不要重复粘贴同一段「已完成本轮需求」。\n"
        f"目标仓库：{repo}\n"
        f"【固定工作分支 · 一人一支】必须使用分支 `{work_branch}`：\n"
        f"- 若远端已有 `{work_branch}`：checkout 该分支并在其上继续提交（基于该分支最新 tip）。\n"
        f"- 若尚不存在：从 `{base}` 创建分支 `{work_branch}`，之后所有提交都在该分支。\n"
        "- 严禁再新建带功能名/随机后缀的分支（例如 dev/workbuddy-erp-login-xxxx、feat/首页-xxx）。\n"
        "- 同一用户后续需求（登录、首页、报表…）全部累积在这一条工作分支上。\n"
        f"{pr_rule}\n"
        "首轮需求：\n"
        f"{user_message.strip()}\n"
        "验收：能补测则补；无权限的依赖不要伪造；不要修改与需求无关的配置密钥。"
    )


def build_followup_prompt(
    *,
    user_message: str,
    repo: str,
    work_branch: str,
    prior_assistant: str = "",
    create_pr: bool = False,
) -> str:
    prior = (prior_assistant or "").strip()
    prior_block = f"上一轮助手摘要（供续聊上下文）：\n{prior[:4000]}\n\n" if prior else ""
    if create_pr:
        pr_rule = "本轮用户要求开 PR：完成后开 PR；工作分支仍用固定分支。"
    else:
        pr_rule = (
            "【禁止开 PR · 用户未勾选】不要 ManagePullRequest / `gh pr create` / 任何开 PR；"
            "只推固定工作分支；摘要勿宣称已开 PR；不要重复粘贴同一段完成摘要。"
        )
    return (
        "你是代码实现 Agent，继续在同一仓库、同一用户工作分支上改代码。\n"
        f"目标仓库：{repo}\n"
        f"【固定工作分支】继续使用 `{work_branch}`，禁止新开其它功能分支。\n"
        f"{pr_rule}\n"
        f"{prior_block}"
        "本轮用户补充：\n"
        f"{user_message.strip()}\n"
        "验收：只做本轮要求；能补测则补。"
    )
