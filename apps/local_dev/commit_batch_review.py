"""提交批审：commit-batch-review Skill 执行器（commit_batch API 专用，不经审码车道）。"""
from __future__ import annotations

import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any

_SKILL_DIR = Path(__file__).resolve().parents[1] / "agent" / "skills" / "commit-batch-review"
_MAX_FILES = 40
_MAX_CHARS_PER_FILE = 12_000
_logger = logging.getLogger("local_dev.commit_batch_review")


def _norm_rel(rel: str) -> str:
    r = (rel or "").replace("\\", "/").strip()
    while r.startswith("./"):
        r = r[2:]
    return r.lstrip("/")


def _estimate_tokens(text: str) -> int:
    """中英混合粗估：约 2 字符 ≈ 1 token（偏保守，便于对账量级）。"""
    n = len(text or "")
    return max(1, (n + 1) // 2) if n else 0


def _resolve_model_name(model: Any = None) -> str:
    """优先读 ChatOpenAI.model_name / model；否则 Config.MODEL_NAME。"""
    if model is not None:
        for attr in ("model_name", "model"):
            val = getattr(model, attr, None)
            if val and str(val).strip():
                return str(val).strip()
    try:
        from config import Config

        name = (getattr(Config, "MODEL_NAME", None) or "").strip()
        if name:
            return name
    except Exception:
        pass
    return "unknown"


def _usage_from_response(resp: Any) -> dict[str, int]:
    """从 LangChain AIMessage 提取官方用量（有则用，无则空）。"""
    out: dict[str, int] = {}
    meta = getattr(resp, "usage_metadata", None)
    if isinstance(meta, dict):
        for src, dst in (
            ("input_tokens", "prompt_tokens"),
            ("output_tokens", "completion_tokens"),
            ("total_tokens", "total_tokens"),
        ):
            if meta.get(src) is not None:
                try:
                    out[dst] = int(meta[src])
                except (TypeError, ValueError):
                    pass
    rm = getattr(resp, "response_metadata", None)
    if isinstance(rm, dict):
        tu = rm.get("token_usage") or rm.get("usage") or {}
        if isinstance(tu, dict):
            for src, dst in (
                ("prompt_tokens", "prompt_tokens"),
                ("completion_tokens", "completion_tokens"),
                ("total_tokens", "total_tokens"),
                ("input_tokens", "prompt_tokens"),
                ("output_tokens", "completion_tokens"),
            ):
                if dst not in out and tu.get(src) is not None:
                    try:
                        out[dst] = int(tu[src])
                    except (TypeError, ValueError):
                        pass
    if out.get("prompt_tokens") is not None and out.get("completion_tokens") is not None:
        out.setdefault(
            "total_tokens",
            int(out["prompt_tokens"]) + int(out["completion_tokens"]),
        )
    return out


def _build_llm_usage(
    *,
    model_name: str,
    system: str,
    user: str,
    output_text: str,
    resp: Any = None,
    elapsed_ms: int = 0,
    file_count: int = 0,
) -> dict[str, Any]:
    est_in = _estimate_tokens(system) + _estimate_tokens(user)
    est_out = _estimate_tokens(output_text)
    official = _usage_from_response(resp) if resp is not None else {}
    usage: dict[str, Any] = {
        "model": model_name,
        "file_count": file_count,
        "prompt_chars": len(system) + len(user),
        "completion_chars": len(output_text or ""),
        "estimated_prompt_tokens": est_in,
        "estimated_completion_tokens": est_out,
        "estimated_total_tokens": est_in + est_out,
        "elapsed_ms": elapsed_ms,
        "source": "api" if official else "estimate",
    }
    if official:
        usage["prompt_tokens"] = official.get("prompt_tokens")
        usage["completion_tokens"] = official.get("completion_tokens")
        usage["total_tokens"] = official.get("total_tokens")
    return usage


def _log_llm_usage(usage: dict[str, Any]) -> None:
    model = usage.get("model") or "unknown"
    src = usage.get("source") or "estimate"
    if src == "api" and usage.get("total_tokens") is not None:
        tok = (
            f"api prompt={usage.get('prompt_tokens')} "
            f"completion={usage.get('completion_tokens')} "
            f"total={usage.get('total_tokens')}"
        )
    else:
        tok = (
            f"est prompt≈{usage.get('estimated_prompt_tokens')} "
            f"completion≈{usage.get('estimated_completion_tokens')} "
            f"total≈{usage.get('estimated_total_tokens')}"
        )
    msg = (
        f"[commit-batch-review] model={model} files={usage.get('file_count')} "
        f"chars_in={usage.get('prompt_chars')} chars_out={usage.get('completion_chars')} "
        f"{tok} elapsed_ms={usage.get('elapsed_ms')} source={src}"
    )
    _logger.info(msg)
    print(msg, flush=True)


def load_skill_bundle() -> str:
    parts: list[str] = []
    skill_md = _SKILL_DIR / "SKILL.md"
    if skill_md.is_file():
        parts.append(skill_md.read_text(encoding="utf-8"))
    for name in ("checklist.md", "output-schema.md"):
        p = _SKILL_DIR / "references" / name
        if p.is_file():
            parts.append(p.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


def _read_batch_contents(root: Path, synced: list[str]) -> list[dict[str, str]]:
    agent_root = Path(__file__).resolve().parents[1] / "agent"
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    from tools.ide_review.local_files import read_workspace_files

    paths = [_norm_rel(p) for p in synced if _norm_rel(p)][: _MAX_FILES]
    if not paths:
        return []
    packed = read_workspace_files(root, paths)
    out: list[dict[str, str]] = []
    for item in packed.get("file_contents") or []:
        if not isinstance(item, dict):
            continue
        path = _norm_rel(str(item.get("path") or ""))
        body = str(item.get("content") or "")
        if not path:
            continue
        if len(body) > _MAX_CHARS_PER_FILE:
            body = body[:_MAX_CHARS_PER_FILE] + "\n…(截断)"
        out.append({"path": path, "content": body})
    return out


def _extract_json(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.I)
    if fence:
        raw = fence.group(1).strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(raw[start : end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _normalize_skill_result(
    data: dict[str, Any],
    *,
    synced: list[str],
    llm_usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings_in = data.get("findings") if isinstance(data.get("findings"), list) else []
    findings: list[dict[str, Any]] = []
    for f in findings_in:
        if not isinstance(f, dict):
            continue
        sev = str(f.get("severity") or "P2").upper()
        if sev not in {"P0", "P1", "P2"}:
            sev = "P2"
        blocking = bool(f.get("blocking"))
        if sev in {"P0", "P1"}:
            blocking = True
        findings.append(
            {
                "severity": sev,
                "path": _norm_rel(str(f.get("path") or "")),
                "rule": str(f.get("rule") or "commit-batch-review")[:80],
                "message": str(f.get("message") or "")[:300],
                "blocking": blocking,
            }
        )

    scans_in = data.get("file_scans") if isinstance(data.get("file_scans"), list) else []
    file_scans: list[dict[str, Any]] = []
    for s in scans_in:
        if not isinstance(s, dict):
            continue
        file_scans.append(
            {
                "path": _norm_rel(str(s.get("path") or "")),
                "status": "blocked" if str(s.get("status") or "").lower() == "blocked" else "pass",
                "steps": [str(x)[:200] for x in (s.get("steps") or []) if str(x).strip()][:8],
                "issues": [str(x)[:200] for x in (s.get("issues") or []) if str(x).strip()][:8],
            }
        )

    seen_paths = {s["path"] for s in file_scans if s.get("path")}
    for rel in synced:
        if rel not in seen_paths:
            file_scans.append({"path": rel, "status": "pass", "steps": ["已纳入本批范围"], "issues": []})

    blocking = [f for f in findings if f.get("blocking") or f.get("severity") in {"P0", "P1"}]
    warnings = [f for f in findings if f not in blocking]
    verdict = str(data.get("verdict") or "").lower()
    if not verdict:
        verdict = "blocked" if blocking else ("warn" if warnings else "pass")

    summary = str(data.get("summary") or "").strip()
    if not summary:
        if blocking:
            summary = f"提交批审：{len(blocking)} 条阻断、{len(warnings)} 条警告 —— 禁止提交"
        elif warnings:
            summary = f"提交批审：无阻断，{len(warnings)} 条警告 —— 确认后可提交"
        else:
            summary = "提交批审：未发现阻断或警告 —— 可提交"

    steps = data.get("process_steps") if isinstance(data.get("process_steps"), list) else []
    process_steps = [str(x).strip() for x in steps if str(x).strip()][:20]

    out: dict[str, Any] = {
        "ok": True,
        "provider": "commit-batch-review-skill",
        "review_method": "commit-batch-review Skill（gate-90 本批版；非全量审码车道）",
        "files_reviewed": len(synced),
        "findings": findings[:50],
        "file_scans": file_scans[:80],
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "can_commit": not blocking,
        "summary": summary,
        "verdict": verdict,
        "process_steps": process_steps,
        "checks": [
            "Skill：commit-batch-review（提交批审专用）",
            "检查面：敏感路径 / 注入·RCE / 密钥 / 认证 / 正确性（本批）",
            "P0/P1 阻断；P2 警告",
        ],
        "scope_label": f"提交批审 Skill · 本批 {len(synced)} 个文件（非全仓审码）",
    }
    if isinstance(llm_usage, dict) and llm_usage:
        out["llm_usage"] = llm_usage
    return out


def run_commit_batch_skill_review(
    workspace: Path | str,
    synced_files: list[str],
) -> dict[str, Any] | None:
    """调用 LLM + commit-batch-review Skill；失败返回 None（由 commit_gate 降级）。"""
    root = Path(workspace).expanduser().resolve()
    synced = [_norm_rel(str(p)) for p in (synced_files or []) if str(p).strip()]
    synced = list(dict.fromkeys(synced))[:_MAX_FILES]
    if not synced:
        return _normalize_skill_result(
            {
                "verdict": "pass",
                "summary": "提交批审：无待审文件",
                "process_steps": ["① 本批无文件需审"],
                "findings": [],
                "file_scans": [],
            },
            synced=synced,
        )

    contents = _read_batch_contents(root, synced)
    if not contents:
        return None

    bundle = load_skill_bundle()
    if not bundle.strip():
        return None

    agent_root = Path(__file__).resolve().parents[1] / "agent"
    if str(agent_root) not in sys.path:
        sys.path.insert(0, str(agent_root))
    try:
        from agents.agent import build_model
        from langchain_core.messages import HumanMessage, SystemMessage
    except Exception:
        return None

    try:
        model = build_model()
    except Exception:
        return None

    model_name = _resolve_model_name(model)
    files_blob = json.dumps(contents, ensure_ascii=False)
    system = (
        bundle
        + "\n\n你是提交批审引擎。严格按 output-schema 只输出一个 JSON 对象，不要 Markdown 报告。"
    )
    user = (
        f"工作区：{root}\n本批文件数：{len(synced)}\n"
        f"文件与内容（JSON）：\n{files_blob}\n\n"
        "请完成提交批审并只输出 JSON。"
    )
    t0 = time.monotonic()
    try:
        resp = model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        text = str(getattr(resp, "content", None) or resp)
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - t0) * 1000)
        fail_usage = _build_llm_usage(
            model_name=model_name,
            system=system,
            user=user,
            output_text="",
            elapsed_ms=elapsed_ms,
            file_count=len(contents),
        )
        fail_usage["error"] = f"{type(exc).__name__}: {exc}"[:200]
        _log_llm_usage(fail_usage)
        return None
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    usage = _build_llm_usage(
        model_name=model_name,
        system=system,
        user=user,
        output_text=text,
        resp=resp,
        elapsed_ms=elapsed_ms,
        file_count=len(contents),
    )
    _log_llm_usage(usage)

    parsed = _extract_json(text)
    if not parsed:
        return None
    return _normalize_skill_result(parsed, synced=synced, llm_usage=usage)
