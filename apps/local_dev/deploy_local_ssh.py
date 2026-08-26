"""P1-3 旁路：本机 SSH 部署（仅 DEPLOY_CI_PROVIDER=local_ssh 时启用）。

与 github_actions 路径隔离：不写 GitHub、不经模型、不碰 commit_batch。
确认后在本机 build → ssh/rsync 到预发；状态用进程内 job 供 /deploy/poll 查询。
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from local_dev.deploy_config import (
    DeployConfig,
    effective_ssh_build_steps,
    effective_ssh_rsync_excludes,
    effective_ssh_sync_pairs,
    get_deploy_config,
)

# 主机：IPv4 / 简单域名；不含端口（端口走 DEPLOY_SSH_PORT）
_HOST_RE = re.compile(
    r"^(?:"
    r"(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
    r"|(?:[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]{0,61}[A-Za-z0-9])?)*)"
    r")$"
)
_USER_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")
_REF_RE = re.compile(r"^[A-Za-z0-9._/\-]+$")
_REMOTE_PATH_RE = re.compile(r"^/[\w./\-]+$")
# 远端重启：仅允许安全字符，禁止 ;|& 与环境注入；最终仍 shlex.quote 整句
_RESTART_CMD_RE = re.compile(r"^[A-Za-z0-9_./\-+\s]+$")
_RUN_ID_RE = re.compile(r"^local-[a-f0-9]{12}$")
_SHALLOW_REMOTE = frozenset({"/", "/www", "/www/wwwroot", "/home", "/root", "/var", "/tmp", "/opt"})
_SSH_KEY_ALLOWED_ROOTS = (
    Path.home() / ".ssh",
    Path.home() / ".workbuddy" / "ssh",
)

_JOBS: dict[str, dict[str, Any]] = {}
_JOBS_LOCK = threading.Lock()
_MAX_JOBS = 40
_MAX_CONCURRENT = 1

# 同步时排除敏感/本机专用文件（可被 DEPLOY_SSH_RSYNC_EXCLUDES 覆盖扩展）


def _resolve_setting(name: str, default: str = "") -> str:
    try:
        from settings_store import resolve_setting

        return (resolve_setting(name, default=default) or "").strip()
    except Exception:
        raw = os.getenv(name)
        if raw is None or str(raw).strip() == "":
            return default
        return str(raw).strip()


def local_ssh_settings(cfg: DeployConfig | None = None) -> dict[str, str]:
    """读取本机 SSH 部署专用配置（与 GitHub Secrets 命名独立，避免误用）。"""
    c = cfg or get_deploy_config()
    return {
        "host": (c.ssh_host or _resolve_setting("DEPLOY_SSH_HOST", "")).strip(),
        "user": (c.ssh_user or _resolve_setting("DEPLOY_SSH_USER", "")).strip(),
        "key_path": (c.ssh_key_path or _resolve_setting("DEPLOY_SSH_KEY_PATH", "")).strip(),
        "app_path": (c.ssh_app_path or _resolve_setting("DEPLOY_SSH_APP_PATH", "")).strip(),
        "local_project": (
            c.local_project_path or _resolve_setting("DEPLOY_LOCAL_PROJECT_PATH", "")
        ).strip(),
        "restart_cmd": (
            c.ssh_restart_cmd or _resolve_setting("DEPLOY_SSH_RESTART_CMD", "")
        ).strip(),
        "port": str(c.ssh_port or _resolve_setting("DEPLOY_SSH_PORT", "22") or "22").strip(),
    }


def _looks_like_private_key(path: Path) -> bool:
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:120]
    except OSError:
        return False
    return "BEGIN" in head and "PRIVATE KEY" in head


def _is_git_repo(proj: Path) -> bool:
    git = proj / ".git"
    if git.is_dir() or git.is_file():
        return True
    try:
        r = subprocess.run(
            ["git", "-C", str(proj), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        return r.returncode == 0 and "true" in (r.stdout or "").lower()
    except (OSError, subprocess.TimeoutExpired):
        return False


def validate_local_ssh_settings(
    s: dict[str, str], cfg: DeployConfig | None = None
) -> list[str]:
    """返回缺失/非法项说明；空列表表示可触发。"""
    c = cfg or get_deploy_config()
    sync_pairs = effective_ssh_sync_pairs(c)
    errs: list[str] = []
    if not s.get("host") or not _HOST_RE.match(s["host"]):
        errs.append("DEPLOY_SSH_HOST 无效（须为 IP/域名，勿带端口）")
    if not s.get("user") or not _USER_RE.match(s["user"]):
        errs.append("DEPLOY_SSH_USER 无效")
    key_raw = s.get("key_path") or ""
    if not key_raw:
        errs.append("缺少 DEPLOY_SSH_KEY_PATH（本机私钥路径，如 ~/.ssh/deploy_key）")
    else:
        try:
            key = Path(key_raw).expanduser().resolve()
            if not key.is_file():
                errs.append(f"私钥文件不存在：{key}")
            elif not _looks_like_private_key(key):
                errs.append("DEPLOY_SSH_KEY_PATH 不是私钥文件（须含 BEGIN … PRIVATE KEY）")
            else:
                # 私钥须落在本机允许目录内（防指向任意可读文件）
                allowed = False
                for root in _SSH_KEY_ALLOWED_ROOTS:
                    try:
                        key.relative_to(root.resolve())
                        allowed = True
                        break
                    except ValueError:
                        continue
                if not allowed:
                    errs.append(
                        "DEPLOY_SSH_KEY_PATH 须位于 ~/.ssh 或 ~/.workbuddy/ssh 下"
                    )
                parts = set(key.parts)
                if "etc" in parts or "proc" in parts or "sys" in parts:
                    errs.append("DEPLOY_SSH_KEY_PATH 路径不安全")
        except OSError:
            errs.append("DEPLOY_SSH_KEY_PATH 无法解析")
    app = (s.get("app_path") or "").rstrip("/") or "/"
    if not app or not _REMOTE_PATH_RE.match(app) or ".." in app:
        errs.append("DEPLOY_SSH_APP_PATH 须为绝对路径（如 /var/www/myapp）")
    elif app in _SHALLOW_REMOTE or app.count("/") < 2:
        errs.append("DEPLOY_SSH_APP_PATH 过浅（禁止 /、/www、/www/wwwroot 等，以免 rsync --delete 误伤）")
    proj_raw = s.get("local_project") or ""
    if not proj_raw:
        errs.append("缺少 DEPLOY_LOCAL_PROJECT_PATH（本机业务项目根目录）")
    else:
        try:
            proj = Path(proj_raw).expanduser().resolve()
            if not proj.is_dir():
                errs.append(f"本机项目目录不存在：{proj}")
            elif not _is_git_repo(proj):
                errs.append(f"本机项目不是 git 仓库：{proj}")
            elif c.ssh_sync_pairs:
                roots = {local_rel.split("/")[0] for local_rel, _ in sync_pairs}
                if not any((proj / root).exists() for root in roots):
                    errs.append(
                        "本机项目与 DEPLOY_SSH_SYNC_PAIRS 不匹配（未找到对应顶层目录）"
                    )
            elif not (proj / "frontend").is_dir() or not (proj / "backend").is_dir():
                errs.append(
                    "本机项目须含 frontend/ 与 backend/，或在高级选项配置 DEPLOY_SSH_SYNC_PAIRS"
                )
        except OSError:
            errs.append("DEPLOY_LOCAL_PROJECT_PATH 无法解析")
    port = s.get("port") or "22"
    if not port.isdigit() or not (1 <= int(port) <= 65535):
        errs.append("DEPLOY_SSH_PORT 无效")
    restart = s.get("restart_cmd") or ""
    if restart:
        if "\n" in restart or "\r" in restart:
            errs.append("DEPLOY_SSH_RESTART_CMD 不允许换行")
        elif not _RESTART_CMD_RE.match(restart):
            errs.append(
                "DEPLOY_SSH_RESTART_CMD 含非法字符（仅允许字母数字、空格与 _./-+）"
            )
        elif len(restart) > 240:
            errs.append("DEPLOY_SSH_RESTART_CMD 过长")
    return errs


def _job_snapshot(job: dict[str, Any]) -> dict[str, Any]:
    visit = (job.get("visit_url") or job.get("health_url") or "").strip()
    return {
        "ok": True,
        "provider": "local_ssh",
        "run_id": job.get("run_id"),
        "status": job.get("status"),
        "done": bool(job.get("done")),
        "success": bool(job.get("success")),
        "failed": bool(job.get("failed")),
        "message": job.get("message") or "",
        "log_tail": job.get("log_tail") or "",
        "conclusion": job.get("conclusion") or "",
        "run_url": "",
        "actions_url": "",
        "health_url": job.get("health_url") or "",
        "health_ok": job.get("health_ok"),
        "health_detail": job.get("health_detail") or "",
        "visit_url": visit,
    }


def probe_deploy_health(
    url: str,
    *,
    timeout_sec: float = 20,
    retries: int = 5,
    sleep_fn=time.sleep,
    urlopen_fn=None,
) -> dict[str, Any]:
    """P1-3d：从 WorkBuddy 本机探测预发 URL（须 http/https，走 safe_http）。

    Happy：2xx → ok
    边界：空 URL → skipped；非 2xx / 网络失败 → 重试后失败
    """
    raw = (url or "").strip()
    if not raw:
        return {"ok": True, "skipped": True, "detail": "未配置 DEPLOY_HEALTH_URL，跳过探活"}
    try:
        from safe_http import assert_http_url_allowed, urlopen_limited

        target = assert_http_url_allowed(raw, what="部署探活地址")
    except ValueError as exc:
        return {"ok": False, "skipped": False, "detail": str(exc), "url": raw}

    import urllib.request

    opener = urlopen_fn
    if opener is None:

        def opener(req, timeout=10.0):  # type: ignore[misc]
            # 同主机跳转校验，避免 302 打到 metadata / 内网
            return urlopen_limited(req, timeout=timeout, max_bytes=65536)

    attempts = max(1, int(retries))
    last_err = ""
    for i in range(attempts):
        try:
            req = urllib.request.Request(
                target,
                method="GET",
                headers={"User-Agent": "zr-workbuddy-deploy-health"},
            )
            with opener(req, timeout=float(timeout_sec)) as resp:
                code = int(getattr(resp, "status", None) or resp.getcode() or 0)
            if 200 <= code < 300:
                return {
                    "ok": True,
                    "skipped": False,
                    "url": target,
                    "status_code": code,
                    "detail": f"探活通过 HTTP {code}（第 {i + 1}/{attempts} 次）",
                }
            last_err = f"HTTP {code}"
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)[:200]
        if i + 1 < attempts:
            sleep_fn(min(3.0, 0.8 * (i + 1)))
    return {
        "ok": False,
        "skipped": False,
        "url": target,
        "detail": f"探活失败（{attempts} 次）：{last_err}",
    }


def get_local_ssh_run_status(run_id: str) -> dict[str, Any]:
    rid = (run_id or "").strip()
    if not rid or not _RUN_ID_RE.match(rid):
        return {"ok": False, "error": "无效的本机部署 run_id", "provider": "local_ssh"}
    with _JOBS_LOCK:
        job = _JOBS.get(rid)
        if not job:
            return {
                "ok": False,
                "error": f"未找到本机部署任务 {rid}（可能已重启 API 进程）",
                "provider": "local_ssh",
                "unreachable": False,
            }
        return _job_snapshot(job)


def _count_active_jobs() -> int:
    with _JOBS_LOCK:
        return sum(
            1
            for j in _JOBS.values()
            if not j.get("done") and str(j.get("status") or "") in ("queued", "in_progress")
        )


def _append_log(job: dict[str, Any], line: str) -> None:
    prev = str(job.get("log_tail") or "")
    merged = (prev + "\n" + line).strip()
    if len(merged) > 4000:
        merged = merged[-4000:]
    job["log_tail"] = merged
    job["message"] = line.strip() or job.get("message") or ""


def _run(cmd: list[str], *, cwd: Path | None = None, timeout: float = 600) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise RuntimeError(
            f"命令失败 ({proc.returncode}): {' '.join(cmd[:6])}…\n{out[-1500:]}"
        )
    return out


def _ssh_base(key: Path, port: int, user: str, host: str) -> list[str]:
    return [
        "ssh",
        "-i",
        str(key),
        "-p",
        str(port),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-o",
        "ConnectTimeout=20",
        "-o",
        "PreferredAuthentications=publickey",
        f"{user}@{host}",
    ]


def _rsync_ssh(key: Path, port: int) -> str:
    # rsync -e 需要 shell 字符串；对路径做 quote，防止空格/元字符打断
    return (
        f"ssh -i {shlex.quote(str(key))} -p {int(port)} "
        f"-o IdentitiesOnly=yes -o BatchMode=yes "
        f"-o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "
        f"-o PreferredAuthentications=publickey"
    )


def _prepare_tree(project: Path, ref: str, work_root: Path) -> Path:
    """检出指定 ref 到临时 worktree，避免动用户当前工作区。"""
    if not _REF_RE.match(ref) or ".." in ref:
        raise RuntimeError("非法 git ref")
    _run(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=project, timeout=30)
    dest = work_root / "src"
    _run(
        ["git", "worktree", "add", "--detach", str(dest), ref],
        cwd=project,
        timeout=60,
    )
    return dest


def _rsync_exclude_args(cfg: DeployConfig) -> list[str]:
    out: list[str] = []
    for pat in effective_ssh_rsync_excludes(cfg):
        out.extend(["--exclude", pat])
    return out


def _run_build_cmd(cmd: str, *, cwd: Path, timeout: float = 900) -> str:
    """构建步骤：仅 argv 执行（禁止 shell=True），命令字符已在配置解析时收紧。"""
    from local_dev.deploy_config import _safe_build_cmd

    safe = _safe_build_cmd(cmd)
    if not safe:
        raise RuntimeError(
            "DEPLOY_SSH_BUILD_STEPS 命令非法（仅允许字母数字与 _./-+=@: 空格）"
        )
    try:
        argv = shlex.split(safe, posix=True)
    except ValueError as exc:
        raise RuntimeError(f"构建命令无法解析：{exc}") from exc
    if not argv:
        raise RuntimeError("构建命令为空")
    # 拒绝被拆成独立 token 的 shell 运算符（双保险）
    banned = {";", "|", "&", "&&", "||", ">", ">>", "<", "`"}
    if any(tok in banned for tok in argv):
        raise RuntimeError("构建命令含非法运算符")
    return _run(argv, cwd=cwd, timeout=timeout)


def _path_under(root: Path, candidate: Path) -> Path:
    """resolve 后必须仍在 root 内，防 symlink / .. 逃逸。"""
    root_r = root.resolve()
    cand_r = candidate.resolve()
    try:
        cand_r.relative_to(root_r)
    except ValueError as exc:
        raise RuntimeError(f"路径越界：{candidate} 不在 {root} 内") from exc
    return cand_r


def _copy_tree(src: Path, dest: Path) -> None:
    if not src.exists():
        raise RuntimeError(f"同步源不存在：{src}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest, symlinks=False)
    else:
        shutil.copy2(src, dest)


def _prepare_release(
    src: Path, release: Path, cfg: DeployConfig, log: Callable[[str], None]
) -> None:
    """按配置执行构建步骤，并把待同步目录拷入 release 暂存区。"""
    sync_pairs = effective_ssh_sync_pairs(cfg)
    build_steps = effective_ssh_build_steps(cfg)
    src_root = src.resolve()
    for cwd_rel, cmd in build_steps:
        cwd = src_root if cwd_rel in (".", "") else _path_under(src_root, src / cwd_rel)
        if not cwd.is_dir():
            raise RuntimeError(f"构建目录不存在：{cwd_rel or '.'}")
        log(f"构建 {cwd_rel or '.'} → {cmd}")
        _run_build_cmd(cmd, cwd=cwd, timeout=900)
    for local_rel, _remote_rel in sync_pairs:
        local_path = _path_under(src_root, src / local_rel)
        release_path = release / local_rel
        log(f"打包 {local_rel} …")
        _copy_tree(local_path, release_path)


def _deploy_rsync(
    *,
    release: Path,
    key: Path,
    port: int,
    user: str,
    host: str,
    app: str,
    restart_cmd: str,
    cfg: DeployConfig,
    log: Callable[[str], None],
) -> None:
    if not _REMOTE_PATH_RE.match(app) or ".." in app or app.rstrip("/") in _SHALLOW_REMOTE:
        raise RuntimeError("远端 APP 路径非法")
    remote = f"{user}@{host}"
    ssh = _ssh_base(key, port, user, host)
    sync_pairs = effective_ssh_sync_pairs(cfg)
    remote_dirs = [f"{app}/{remote_rel}".rstrip("/") for _, remote_rel in sync_pairs]
    log("SSH 登录探测 …")
    quoted = " ".join(shlex.quote(p) for p in remote_dirs)
    remote_mkdir = f"mkdir -p -- {quoted} && echo ssh_ok"
    _run(ssh + [remote_mkdir], timeout=40)
    rsh = _rsync_ssh(key, port)
    excludes = _rsync_exclude_args(cfg)
    for local_rel, remote_rel in sync_pairs:
        local_release = release / local_rel
        if not local_release.exists():
            raise RuntimeError(f"release 缺少待同步路径：{local_rel}")
        remote_target = f"{remote}:{app}/{remote_rel}/"
        log(f"rsync {local_rel} → {remote_rel} …")
        cmd = [
            "rsync",
            "-az",
            "--delete",
            "-e",
            rsh,
            *excludes,
        ]
        if local_release.is_dir():
            cmd.append(f"{local_release}/")
        else:
            cmd.append(str(local_release))
        cmd.append(remote_target)
        _run(cmd, timeout=300)
    if restart_cmd:
        if not _RESTART_CMD_RE.match(restart_cmd):
            raise RuntimeError("拒绝执行含非法字符的 DEPLOY_SSH_RESTART_CMD")
        log("执行远端重启 …")
        # 整句 quote，避免 OpenSSH 把多词 argv 拆开导致 -c 只吃到第一个词
        _run(ssh + [f"bash -lc {shlex.quote(restart_cmd)}"], timeout=120)
    else:
        log("未配置 DEPLOY_SSH_RESTART_CMD，已同步文件")


def _execute_job(run_id: str, *, ref: str, environment: str, cfg: DeployConfig) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(run_id)
        if not job:
            return
        job["status"] = "in_progress"
        job["message"] = "本机构建与 SSH 同步进行中…"

    def log(msg: str) -> None:
        with _JOBS_LOCK:
            j = _JOBS.get(run_id)
            if j:
                _append_log(j, msg)

    work_root: Path | None = None
    try:
        if not _REF_RE.match(ref) or ".." in ref:
            raise RuntimeError("非法 git ref")
        s = local_ssh_settings(cfg)
        errs = validate_local_ssh_settings(s, cfg)
        if errs:
            raise RuntimeError("；".join(errs))
        key = Path(s["key_path"]).expanduser().resolve()
        project = Path(s["local_project"]).expanduser().resolve()
        port = int(s["port"])
        app = s["app_path"].rstrip("/")
        work_root = Path(tempfile.mkdtemp(prefix="wb-deploy-"))
        release = work_root / "release"
        release.mkdir()
        log(f"检出 ref={ref}（临时 worktree，不动当前工作区）…")
        src = _prepare_tree(project, ref, work_root)
        _prepare_release(src, release, cfg, log)
        _deploy_rsync(
            release=release,
            key=key,
            port=port,
            user=s["user"],
            host=s["host"],
            app=app,
            restart_cmd=s.get("restart_cmd") or "",
            cfg=cfg,
            log=log,
        )
        health_url = (cfg.health_url or "").strip()
        health_result: dict[str, Any] = {"ok": True, "skipped": True, "detail": ""}
        if health_url:
            log(f"部署后探活 {health_url} …")
            health_result = probe_deploy_health(
                health_url,
                timeout_sec=float(cfg.health_timeout_sec or 20),
                retries=int(cfg.health_retries or 5),
            )
            log(str(health_result.get("detail") or ""))
            if not health_result.get("ok"):
                raise RuntimeError(
                    f"文件已同步，但探活失败：{health_result.get('detail') or '未知错误'}"
                )
        with _JOBS_LOCK:
            j = _JOBS.get(run_id)
            if j:
                j["status"] = "completed"
                j["done"] = True
                j["success"] = True
                j["failed"] = False
                j["conclusion"] = "success"
                j["health_url"] = health_result.get("url") or health_url
                j["health_ok"] = True if not health_result.get("skipped") else None
                j["health_detail"] = health_result.get("detail") or ""
                visit = (health_result.get("url") or health_url or "").strip()
                j["visit_url"] = visit
                base_msg = f"本机 SSH 部署完成 → {s['user']}@{s['host']}:{app}（env={environment}）"
                if visit:
                    base_msg = f"{base_msg}；访问 {visit}"
                if health_result.get("skipped"):
                    j["message"] = base_msg
                else:
                    j["message"] = f"{base_msg}；探活通过"
                j["finished_at"] = time.time()
                if visit:
                    _append_log(j, f"部署成功 · 访问地址 {visit}")
                else:
                    _append_log(j, "部署成功（未配置 DEPLOY_HEALTH_URL，无访问地址）")
    except Exception as exc:  # noqa: BLE001 — 写入 job 终态
        with _JOBS_LOCK:
            j = _JOBS.get(run_id)
            if j:
                j["status"] = "completed"
                j["done"] = True
                j["success"] = False
                j["failed"] = True
                j["conclusion"] = "failure"
                j["message"] = str(exc)[:800]
                if "探活" in str(exc):
                    j["health_ok"] = False
                    j["health_detail"] = str(exc)[:400]
                _append_log(j, f"失败：{exc}")
                j["finished_at"] = time.time()
    finally:
        if work_root and work_root.exists():
            try:
                src_dir = work_root / "src"
                if src_dir.exists():
                    project = Path(local_ssh_settings(cfg)["local_project"]).expanduser().resolve()
                    subprocess.run(
                        ["git", "worktree", "remove", "--force", str(src_dir)],
                        cwd=str(project),
                        capture_output=True,
                        timeout=60,
                        check=False,
                    )
            except Exception:
                pass
            shutil.rmtree(work_root, ignore_errors=True)


def trigger_local_ssh_deploy(
    *,
    ref: str,
    environment: str = "staging",
    cfg: DeployConfig | None = None,
    repo: str = "",
    workflow: str = "",
    **_extra: Any,
) -> dict[str, Any]:
    """启动本机 SSH 部署任务（后台线程）；返回 run_id 供轮询。"""
    c = cfg or get_deploy_config()
    if c.ci_provider != "local_ssh":
        return {
            "ok": False,
            "error": "当前 DEPLOY_CI_PROVIDER 不是 local_ssh",
            "provider": c.ci_provider,
        }
    target_ref = (ref or "").strip()
    if not target_ref or not _REF_RE.match(target_ref) or ".." in target_ref:
        return {"ok": False, "error": "非法或空的 git ref", "provider": "local_ssh"}
    s = local_ssh_settings(c)
    errs = validate_local_ssh_settings(s, c)
    if errs:
        return {"ok": False, "error": "；".join(errs), "provider": "local_ssh"}

    run_id = f"local-{uuid.uuid4().hex[:12]}"
    job = {
        "run_id": run_id,
        "status": "queued",
        "done": False,
        "success": False,
        "failed": False,
        "message": "已排队：本机构建后 SSH 同步",
        "log_tail": "",
        "conclusion": "",
        "ref": target_ref,
        "env": environment,
        "created_at": time.time(),
    }
    with _JOBS_LOCK:
        active = sum(
            1
            for j in _JOBS.values()
            if not j.get("done") and str(j.get("status") or "") in ("queued", "in_progress")
        )
        if active >= _MAX_CONCURRENT:
            return {
                "ok": False,
                "error": "已有本机 SSH 部署在进行中，请等待完成后再触发",
                "provider": "local_ssh",
            }
        if len(_JOBS) >= _MAX_JOBS:
            oldest = sorted(_JOBS.items(), key=lambda kv: kv[1].get("created_at") or 0)
            for k, _ in oldest[: max(1, len(_JOBS) - _MAX_JOBS + 1)]:
                _JOBS.pop(k, None)
        _JOBS[run_id] = job

    t = threading.Thread(
        target=_execute_job,
        kwargs={
            "run_id": run_id,
            "ref": target_ref,
            "environment": environment,
            "cfg": c,
        },
        name=f"deploy-local-ssh-{run_id}",
        daemon=True,
    )
    t.start()
    return {
        "ok": True,
        "provider": "local_ssh",
        "run_id": run_id,
        "run_url": "",
        "actions_url": "",
        "message": (
            f"已启动本机 SSH 部署（{s['user']}@{s['host']}:{s['app_path']}），"
            "请等待构建与同步完成"
        ),
    }


def _clear_jobs_for_tests() -> None:
    with _JOBS_LOCK:
        _JOBS.clear()
