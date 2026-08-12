"""同步后确保目标工程开发服务可用，并返回本机预览地址。

已在监听则复用（不杀进程）；未跑则在目标目录启动。预览失败不影响写码成功。
"""
from __future__ import annotations

import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .config import LocalDevConfig, get_config

Progress = Callable[[str], None]


def _progress(cb: Progress | None, text: str) -> None:
    if cb:
        try:
            cb(text)
        except Exception:
            pass


def _port_listening(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.8):
            return True
    except OSError:
        return False


def _http_ok(url: str, timeout: float = 1.5) -> bool:
    """仅 2xx 视为健康；4xx（如未登录页 401）不算可复用服务。"""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            code = getattr(resp, "status", None) or resp.getcode()
            return 200 <= int(code) < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def _any_http_ok(urls: list[str], timeout: float = 1.5) -> bool:
    return any(_http_ok(u, timeout=timeout) for u in urls)


def _listener_pids(port: int) -> list[int]:
    try:
        out = subprocess.check_output(
            ["lsof", f"-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return []
    pids: list[int] = []
    for line in out.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))
    return pids


def _pid_cwd(pid: int) -> Path | None:
    """尽量解析进程 cwd（macOS/Linux）；失败返回 None。"""
    try:
        out = subprocess.check_output(
            ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return None
    for line in out.splitlines():
        if line.startswith("n"):
            try:
                return Path(line[1:]).resolve()
            except OSError:
                return None
    return None


def _read_managed_pid(pid_path: Path) -> int | None:
    try:
        raw = pid_path.read_text(encoding="utf-8").strip()
        return int(raw) if raw.isdigit() else None
    except (OSError, ValueError):
        return None


def _safe_kill_port_for_workspace(
    port: int,
    workspace: Path,
    *,
    managed_pid_path: Path | None = None,
) -> tuple[bool, str]:
    """仅结束「本工程相关」占用端口的进程，避免误杀其它服务。

    允许杀掉的条件（满足其一）：
    1. pid 与 `.dev-logs/*.pid` 记录一致（本工具先前启动）
    2. 进程 cwd 位于目标 workspace 之下
    """
    workspace = workspace.resolve()
    pids = _listener_pids(port)
    if not pids:
        return True, ""
    managed = _read_managed_pid(managed_pid_path) if managed_pid_path else None
    killable: list[int] = []
    skipped: list[int] = []
    for pid in pids:
        if managed is not None and pid == managed:
            killable.append(pid)
            continue
        cwd = _pid_cwd(pid)
        if cwd is not None:
            try:
                cwd.relative_to(workspace)
                killable.append(pid)
                continue
            except ValueError:
                pass
        skipped.append(pid)
    if killable:
        _kill_pids(killable)
    if skipped and _port_listening(port):
        return False, (
            f"端口 {port} 被其它进程占用（pid={','.join(map(str, skipped))}），"
            f"且不属于本工程，未强杀；请手动释放或改端口后重试"
        )
    return True, ""


def _kill_pids(pids: list[int]) -> None:
    for pid in pids:
        try:
            subprocess.run(["kill", "-TERM", str(pid)], check=False, capture_output=True)
        except OSError:
            pass
    time.sleep(0.8)
    for pid in pids:
        try:
            subprocess.run(["kill", "-KILL", str(pid)], check=False, capture_output=True)
        except OSError:
            pass
    time.sleep(0.5)


def _tail_log(path: Path, lines: int = 40) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    parts = text.splitlines()
    return "\n".join(parts[-lines:])


def _startup_error_from_log(log_path: Path) -> str:
    tail = _tail_log(log_path, 60)
    if not tail:
        return ""
    for key in ("ImportError", "ModuleNotFoundError", "SyntaxError", "Address already in use", "Error"):
        if key in tail:
            # 取最后一行含关键字
            for line in reversed(tail.splitlines()):
                if key in line:
                    return line.strip()[:240]
    return ""


def _read_text(path: Path, limit: int = 80_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def _parse_ports_from_vite(vite_path: Path, cfg: LocalDevConfig) -> tuple[int, int]:
    fe = cfg.preview_fe_port
    be = cfg.preview_be_port
    text = _read_text(vite_path)
    if not text:
        return fe, be
    m = re.search(r"\bport\s*:\s*(\d{2,5})\b", text)
    if m:
        fe = int(m.group(1))
    m = re.search(
        r"target\s*:\s*['\"]https?://(?:127\.0\.0\.1|localhost):(\d{2,5})",
        text,
        re.I,
    )
    if m:
        be = int(m.group(1))
    return fe, be


def detect_project_layout(workspace: Path) -> dict[str, Any]:
    """识别 frontend/backend 或根目录 Vite。"""
    root = Path(workspace)
    fe_pkg = root / "frontend" / "package.json"
    be_dir = root / "backend"
    root_pkg = root / "package.json"
    vite_candidates = [
        root / "frontend" / "vite.config.js",
        root / "frontend" / "vite.config.ts",
        root / "frontend" / "vite.config.mjs",
        root / "vite.config.js",
        root / "vite.config.ts",
        root / "vite.config.mjs",
    ]
    vite = next((p for p in vite_candidates if p.is_file()), None)

    has_fe = fe_pkg.is_file()
    has_be = be_dir.is_dir() and (
        (be_dir / "app" / "main.py").is_file()
        or (be_dir / "requirements.txt").is_file()
        or (be_dir / "pyproject.toml").is_file()
    )
    root_vite = (root / "package.json").is_file() and any(
        (root / name).is_file()
        for name in ("vite.config.js", "vite.config.ts", "vite.config.mjs")
    )

    if has_fe and has_be:
        mode = "fullstack"
    elif has_fe or root_vite:
        mode = "frontend_only"
    else:
        mode = "unknown"

    fe_dir = root / "frontend" if has_fe else (root if root_vite else None)
    return {
        "mode": mode,
        "frontend_dir": fe_dir,
        "backend_dir": be_dir if has_be else None,
        "vite_config": vite,
        "frontend_pkg": fe_pkg if has_fe else (root_pkg if root_vite else None),
    }


def _side_result(
    *,
    action: str,
    port: int | None = None,
    error: str = "",
) -> dict[str, Any]:
    return {"action": action, "port": port, "error": error or ""}


def _need_npm_install(synced: list[str], fe_rel_prefix: str) -> bool:
    keys = ("package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock")
    for rel in synced:
        n = str(rel).replace("\\", "/")
        base = Path(n).name
        if base not in keys:
            continue
        if fe_rel_prefix:
            if n == base or n.startswith(fe_rel_prefix):
                return True
        else:
            return True
    return False


def _need_pip_install(synced: list[str]) -> bool:
    for rel in synced:
        n = str(rel).replace("\\", "/")
        if n.endswith("requirements.txt") or n.endswith("pyproject.toml"):
            if "backend/" in n or n in {"requirements.txt", "pyproject.toml"}:
                return True
    return False


def _run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, f"超时（>{timeout}s）"
    except FileNotFoundError as e:
        return False, str(e)
    except OSError as e:
        return False, str(e)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        return False, err[:500] or f"exit {proc.returncode}"
    return True, ""


def _start_detached(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path,
    pid_path: Path,
) -> tuple[bool, str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(log_path, "ab") as logf:
            proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                stdout=logf,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        pid_path.write_text(str(proc.pid), encoding="utf-8")
        return True, ""
    except OSError as e:
        return False, str(e)


def _wait_http(
    urls: list[str],
    timeout_sec: int,
    *,
    label: str,
    on_progress: Progress | None,
    should_cancel: Callable[[], bool] | None = None,
) -> bool:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if should_cancel and should_cancel():
            raise RuntimeError("任务已取消")
        for url in urls:
            if _http_ok(url):
                return True
        _progress(on_progress, f"等待{label}就绪…")
        time.sleep(1.0)
    return False


def ensure_dev_preview(
    workspace: Path,
    synced_files: list[str] | None = None,
    *,
    cfg: LocalDevConfig | None = None,
    on_progress: Progress | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """确保预览可用。返回 ok / preview_url / backend_url / frontend / backend / notes。"""
    cfg = cfg or get_config()
    synced = list(synced_files or [])
    root = Path(workspace).resolve()
    empty_side = _side_result(action="skipped")
    result: dict[str, Any] = {
        "ok": False,
        "preview_url": "",
        "backend_url": "",
        "frontend": dict(empty_side),
        "backend": dict(empty_side),
        "notes": "",
    }

    def _check_cancel() -> None:
        if should_cancel and should_cancel():
            raise RuntimeError("任务已取消")

    if not cfg.preview_enabled:
        result["notes"] = "预览已关闭（LOCAL_DEV_PREVIEW_ENABLED）"
        return result

    if not root.is_dir():
        result["notes"] = "目标目录无效，无法启动预览"
        return result

    layout = detect_project_layout(root)
    mode = layout["mode"]
    if mode == "unknown":
        result["notes"] = "未识别可自动启动的前后端（需 frontend+Vite 或 backend/uvicorn 结构），请手动启动"
        result["frontend"] = _side_result(action="skipped", error=result["notes"])
        result["backend"] = _side_result(action="skipped", error=result["notes"])
        return result

    vite_path = layout.get("vite_config")
    fe_port, be_port = cfg.preview_fe_port, cfg.preview_be_port
    if vite_path:
        fe_port, be_port = _parse_ports_from_vite(Path(vite_path), cfg)

    log_dir = root / ".dev-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    fe_dir: Path | None = layout.get("frontend_dir")
    be_dir: Path | None = layout.get("backend_dir")
    notes: list[str] = []

    _check_cancel()

    # --- 按需装依赖 ---
    if fe_dir and _need_npm_install(synced, "frontend/" if (root / "frontend").is_dir() else ""):
        _progress(on_progress, "检测到依赖清单变更，正在 npm install…")
        ok, err = _run_cmd(
            ["npm", "install"],
            cwd=fe_dir,
            timeout=cfg.preview_install_timeout_sec,
        )
        _check_cancel()
        if not ok:
            notes.append(f"npm install 失败：{err}")
        else:
            notes.append("已执行 npm install")

    if be_dir and _need_pip_install(synced):
        venv_pip = be_dir / ".venv" / "bin" / "pip"
        req = be_dir / "requirements.txt"
        if not venv_pip.is_file():
            notes.append("后端依赖有变更但缺少 backend/.venv，未自动建环境")
        elif req.is_file():
            _progress(on_progress, "检测到 requirements 变更，正在 pip install…")
            ok, err = _run_cmd(
                [str(venv_pip), "install", "-r", str(req), "-q"],
                cwd=be_dir,
                timeout=cfg.preview_install_timeout_sec,
            )
            _check_cancel()
            if not ok:
                notes.append(f"pip install 失败：{err}")
            else:
                notes.append("已执行 pip install")

    # --- 后端 ---
    if mode == "fullstack" and be_dir:
        be_urls = [
            f"http://127.0.0.1:{be_port}/api/health",
            f"http://127.0.0.1:{be_port}/docs",
            f"http://127.0.0.1:{be_port}/openapi.json",
        ]
        be_healthy = _port_listening(be_port) and _any_http_ok(be_urls)
        if be_healthy:
            result["backend"] = _side_result(action="reused", port=be_port)
            _progress(on_progress, f"后端已在 :{be_port}，复用热重载")
        else:
            port_blocked = False
            if _port_listening(be_port):
                _progress(on_progress, f"后端 :{be_port} 无响应，尝试安全重启…")
                freed, reason = _safe_kill_port_for_workspace(
                    be_port,
                    root,
                    managed_pid_path=log_dir / "backend.pid",
                )
                if freed:
                    notes.append(f"后端端口 {be_port} 曾占用但健康检查失败，已重启本工程相关进程")
                else:
                    port_blocked = True
                    result["backend"] = _side_result(action="skipped", port=be_port, error=reason)
                    notes.append(reason)
            if not port_blocked:
                uvicorn_bin = be_dir / ".venv" / "bin" / "uvicorn"
                if not uvicorn_bin.is_file():
                    result["backend"] = _side_result(
                        action="skipped",
                        port=be_port,
                        error="缺少 backend/.venv（uvicorn），请先创建虚拟环境",
                    )
                    notes.append(result["backend"]["error"])
                else:
                    _check_cancel()
                    _progress(on_progress, f"启动后端 uvicorn :{be_port}…")
                    ok, err = _start_detached(
                        [
                            str(uvicorn_bin),
                            "app.main:app",
                            "--reload",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(be_port),
                        ],
                        cwd=be_dir,
                        log_path=log_dir / "backend.log",
                        pid_path=log_dir / "backend.pid",
                    )
                    if not ok:
                        result["backend"] = _side_result(action="skipped", port=be_port, error=err)
                        notes.append(f"后端启动失败：{err}")
                    else:
                        ready = _wait_http(
                            be_urls,
                            cfg.preview_start_timeout_sec,
                            label="后端",
                            on_progress=on_progress,
                            should_cancel=should_cancel,
                        )
                        if ready:
                            result["backend"] = _side_result(action="started", port=be_port)
                        else:
                            detail = _startup_error_from_log(log_dir / "backend.log") or (
                                "已启动但健康检查超时，请查看 .dev-logs/backend.log"
                            )
                            result["backend"] = _side_result(
                                action="skipped",
                                port=be_port,
                                error=detail,
                            )
                            notes.append(f"后端未就绪：{detail}")
        if result["backend"].get("action") in {"reused", "started"} and result["backend"].get("port"):
            result["backend_url"] = f"http://127.0.0.1:{result['backend']['port']}"
    else:
        result["backend"] = _side_result(action="skipped")

    # --- 前端 ---
    if fe_dir:
        # 若无 node_modules 且未因同步触发 install，仍需装一次才能启动
        if not (fe_dir / "node_modules").is_dir():
            if not any("npm install" in n for n in notes):
                _progress(on_progress, "缺少 node_modules，正在 npm install…")
                ok, err = _run_cmd(
                    ["npm", "install"],
                    cwd=fe_dir,
                    timeout=cfg.preview_install_timeout_sec,
                )
                _check_cancel()
                if not ok:
                    notes.append(f"npm install 失败：{err}")

        fe_urls = [
            f"http://127.0.0.1:{fe_port}/",
            f"http://localhost:{fe_port}/",
        ]
        fe_healthy = _port_listening(fe_port) and _any_http_ok(fe_urls)
        if fe_healthy:
            result["frontend"] = _side_result(action="reused", port=fe_port)
            _progress(on_progress, f"前端已在 :{fe_port}，复用 HMR")
        else:
            port_blocked = False
            if _port_listening(fe_port):
                _progress(on_progress, f"前端 :{fe_port} 无响应，尝试安全重启…")
                freed, reason = _safe_kill_port_for_workspace(
                    fe_port,
                    root,
                    managed_pid_path=log_dir / "frontend.pid",
                )
                if freed:
                    notes.append(f"前端端口 {fe_port} 曾占用但健康检查失败，已重启本工程相关进程")
                else:
                    port_blocked = True
                    result["frontend"] = _side_result(action="skipped", port=fe_port, error=reason)
                    notes.append(reason)
            if not port_blocked:
                if not (fe_dir / "node_modules").is_dir():
                    result["frontend"] = _side_result(
                        action="skipped",
                        port=fe_port,
                        error="缺少 node_modules，无法启动前端",
                    )
                    notes.append(result["frontend"]["error"])
                else:
                    _check_cancel()
                    _progress(on_progress, f"启动前端 Vite :{fe_port}…")
                    ok, err = _start_detached(
                        [
                            "npm",
                            "run",
                            "dev",
                            "--",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(fe_port),
                        ],
                        cwd=fe_dir,
                        log_path=log_dir / "frontend.log",
                        pid_path=log_dir / "frontend.pid",
                    )
                    if not ok:
                        result["frontend"] = _side_result(action="skipped", port=fe_port, error=err)
                        notes.append(f"前端启动失败：{err}")
                    else:
                        ready = _wait_http(
                            fe_urls,
                            cfg.preview_start_timeout_sec,
                            label="前端",
                            on_progress=on_progress,
                            should_cancel=should_cancel,
                        )
                        if ready:
                            result["frontend"] = _side_result(action="started", port=fe_port)
                        else:
                            detail = _startup_error_from_log(log_dir / "frontend.log") or (
                                "已启动但页面检查超时，请查看 .dev-logs/frontend.log"
                            )
                            result["frontend"] = _side_result(
                                action="skipped",
                                port=fe_port,
                                error=detail,
                            )
                            notes.append(f"前端未就绪：{detail}")

        if result["frontend"].get("action") in {"reused", "started"} and result["frontend"].get("port"):
            result["preview_url"] = f"http://127.0.0.1:{result['frontend']['port']}/"
    else:
        result["frontend"] = _side_result(action="skipped", error="无前端目录")

    # 仅后端时用 docs 作弱预览
    if not result["preview_url"] and result.get("backend_url"):
        result["preview_url"] = result["backend_url"] + "/docs"
        notes.append("无前端预览，已回退到后端 /docs")

    fe_ok = result["frontend"].get("action") in {"reused", "started"}
    be_ok = result["backend"].get("action") in {"reused", "started"}
    if mode == "fullstack":
        # 双端工程：前后端都健康才算预览真正可用（否则登录会卡住）
        result["ok"] = bool(result["preview_url"]) and fe_ok and be_ok
        if fe_ok and not be_ok:
            notes.append("前端已开但后端不可用，登录会失败")
    else:
        result["ok"] = bool(result["preview_url"]) and (fe_ok or be_ok)

    if result["ok"] and not notes:
        actions = []
        if result["frontend"].get("action") == "reused":
            actions.append("前端已复用")
        elif result["frontend"].get("action") == "started":
            actions.append("前端已启动")
        if result["backend"].get("action") == "reused":
            actions.append("后端已复用")
        elif result["backend"].get("action") == "started":
            actions.append("后端已启动")
        result["notes"] = "；".join(actions) or "预览就绪"
    else:
        result["notes"] = "；".join(notes) if notes else ("预览就绪" if result["ok"] else "预览未就绪")

    return result
