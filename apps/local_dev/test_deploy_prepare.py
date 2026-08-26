"""P1-3 部署配置 / 准备 / 确认单测（mock CI，无真网）。"""
from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from local_dev import deploy_confirm as deploy_confirm_mod
from local_dev.deploy_config import (
    DeployConfig,
    _parse_build_steps,
    _parse_sync_pairs,
    default_deploy_env,
    effective_ssh_build_steps,
    effective_ssh_sync_pairs,
    env_allowed,
    get_deploy_config,
)
from local_dev.deploy_confirm import confirm_deploy
from local_dev.deploy_github import parse_github_repo, trigger_workflow_dispatch
from local_dev.deploy_prepare import prepare_deploy


def _cfg(**kwargs) -> DeployConfig:
    base = dict(
        enabled=False,
        env_whitelist=("staging",),
        allow_production=False,
        ci_provider="github_actions",
        github_workflow="deploy-staging.yml",
        github_repo="acme/app",
        require_pushed_ref=True,
        confirm_timeout_sec=600,
        poll_timeout_sec=1800,
    )
    base.update(kwargs)
    return DeployConfig(**base)


@contextmanager
def _isolated_settings():
    """单测专用 DATA_DIR，避免改写开发者本机 data/settings.json。"""
    from settings_store import invalidate_cache

    prev = os.environ.get("DATA_DIR")
    td = tempfile.mkdtemp(prefix="wb-deploy-test-")
    os.environ["DATA_DIR"] = td
    invalidate_cache()
    try:
        yield td
    finally:
        invalidate_cache()
        if prev is None:
            os.environ.pop("DATA_DIR", None)
        else:
            os.environ["DATA_DIR"] = prev
        invalidate_cache()


class DeployConfigTests(unittest.TestCase):
    def test_default_disabled(self):
        from settings_store import invalidate_cache, update_settings

        with _isolated_settings():
            with patch.dict(os.environ, {}, clear=False):
                for k in list(os.environ):
                    if k.startswith("DEPLOY_"):
                        os.environ.pop(k, None)
                update_settings({"DEPLOY_ENABLED": ""})
                invalidate_cache()
                cfg = get_deploy_config()
                self.assertFalse(cfg.enabled)
                self.assertIn("staging", cfg.env_whitelist)
                self.assertFalse(cfg.allow_production)

    def test_settings_overlay_beats_env(self):
        """系统配置覆盖 .env（与写码车道同一解析顺序）。"""
        from settings_store import invalidate_cache, update_settings

        with _isolated_settings():
            with patch.dict(os.environ, {"DEPLOY_ENABLED": "0"}, clear=False):
                invalidate_cache()
                update_settings({"DEPLOY_ENABLED": "1"})
                cfg = get_deploy_config()
                self.assertTrue(cfg.enabled)

    def test_parse_sync_and_build_steps(self):
        pairs = _parse_sync_pairs("dist:public,api:api")
        self.assertEqual(pairs, (("dist", "public"), ("api", "api")))
        steps = _parse_build_steps("web:npm ci\nweb:npm run build")
        self.assertEqual(steps, (("web", "npm ci"), ("web", "npm run build")))

    def test_reject_injection_in_build_and_sync(self):
        self.assertEqual(_parse_build_steps("frontend:npm ci; curl evil.com"), ())
        self.assertEqual(_parse_build_steps(".:bash -c evil"), ())
        self.assertEqual(_parse_sync_pairs("../etc:passwd"), ())
        self.assertEqual(_parse_sync_pairs("ok:/etc/passwd"), ())
        self.assertEqual(_parse_sync_pairs("a/../../b:c"), ())
        from local_dev.deploy_config import _parse_rsync_excludes

        self.assertEqual(_parse_rsync_excludes(".env\n--exclude-from=/etc/passwd"), (".env",))
        self.assertNotIn("--exclude-from=/etc/passwd", _parse_rsync_excludes("--exclude-from=/tmp/x"))

    def test_default_deploy_env_from_whitelist(self):
        cfg = _cfg(env_whitelist=("uat", "staging"))
        self.assertEqual(default_deploy_env(cfg), "uat")
        custom = _cfg(ssh_sync_pairs=(("dist", "dist"),))
        self.assertEqual(effective_ssh_sync_pairs(custom), (("dist", "dist"),))
        self.assertEqual(effective_ssh_build_steps(custom), ())

    def test_production_stripped_unless_allowed(self):
        with _isolated_settings():
            with patch.dict(
                os.environ,
                {
                    "DEPLOY_ENABLED": "0",
                    "DEPLOY_ENV_WHITELIST": "staging,production",
                    "DEPLOY_ALLOW_PRODUCTION": "0",
                },
                clear=False,
            ):
                from settings_store import invalidate_cache, update_settings

                invalidate_cache()
                update_settings(
                    {
                        "DEPLOY_ENV_WHITELIST": "",
                        "DEPLOY_ALLOW_PRODUCTION": "",
                    }
                )
                invalidate_cache()
                cfg = get_deploy_config()
                self.assertNotIn("production", cfg.env_whitelist)
                self.assertFalse(env_allowed("production", cfg))
                self.assertTrue(env_allowed("预发", cfg))


class DeployPrepareTests(unittest.TestCase):
    def test_disabled_never_ready(self):
        with patch("local_dev.deploy_prepare.github_deploy_token", return_value="tok"):
            out = prepare_deploy(message="部署到预发", cfg=_cfg(enabled=False))
        self.assertTrue(out["ok"])
        self.assertFalse(out["enabled"])
        self.assertFalse(out["ready_for_confirm"])
        self.assertFalse(out["can_trigger_ci"])

    def test_ready_with_token_can_trigger_flag(self):
        with patch("local_dev.deploy_prepare.github_deploy_token", return_value="tok"):
            out = prepare_deploy(
                message="部署到预发",
                env="staging",
                ref="hebo",
                cfg=_cfg(enabled=True),
            )
        self.assertTrue(out["ready_for_confirm"])
        self.assertTrue(out["can_trigger_ci"])

    def test_ready_without_token_cannot_trigger(self):
        with patch("local_dev.deploy_prepare.github_deploy_token", return_value=""):
            out = prepare_deploy(
                message="部署到预发",
                env="staging",
                ref="hebo",
                cfg=_cfg(enabled=True),
            )
        self.assertTrue(out["ready_for_confirm"])
        self.assertFalse(out["can_trigger_ci"])

    def test_guess_env_production_blocked(self):
        with patch("local_dev.deploy_prepare.github_deploy_token", return_value="tok"):
            out = prepare_deploy(message="部署到生产", cfg=_cfg(enabled=True))
        self.assertFalse(out["ready_for_confirm"])


class DeployGithubTests(unittest.TestCase):
    def test_parse_repo(self):
        self.assertEqual(parse_github_repo("acme/app"), ("acme", "app"))
        self.assertEqual(parse_github_repo("https://github.com/acme/app.git"), ("acme", "app"))
        self.assertIsNone(parse_github_repo("../evil"))

    def test_trigger_mock_ok(self):
        calls = []

        def fake_req(url, method="GET", body=None, timeout=30.0):
            calls.append((url, method, body))
            if method == "POST":
                return 204, None
            return 200, {
                "workflow_runs": [
                    {
                        "id": 99,
                        "html_url": "https://github.com/acme/app/actions/runs/99",
                        "status": "queued",
                    }
                ]
            }

        with patch("local_dev.deploy_github.time.sleep", return_value=None):
            out = trigger_workflow_dispatch(
                repo="acme/app",
                workflow="deploy-staging.yml",
                ref="hebo",
                environment="staging",
                request_json=fake_req,
            )
        self.assertTrue(out["ok"])
        self.assertEqual(out["run_id"], "99")
        self.assertEqual(out["run_url"], "https://github.com/acme/app/actions/runs/99")
        self.assertTrue(any(c[1] == "POST" for c in calls))
        post_body = next(c[2] for c in calls if c[1] == "POST")
        self.assertEqual(post_body.get("inputs", {}).get("environment"), "staging")

    def test_trigger_without_env_input(self):
        calls = []

        def fake_req(url, method="GET", body=None, timeout=30.0):
            calls.append((url, method, body))
            if method == "POST":
                return 204, None
            return 200, {"workflow_runs": []}

        with patch("local_dev.deploy_github.time.sleep", return_value=None):
            out = trigger_workflow_dispatch(
                repo="acme/app",
                workflow="deploy-staging.yml",
                ref="main",
                environment="staging",
                workflow_env_input="none",
                request_json=fake_req,
            )
        self.assertTrue(out["ok"])
        post_body = next(c[2] for c in calls if c[1] == "POST")
        self.assertNotIn("inputs", post_body)

    def test_poll_run_success(self):
        from local_dev.deploy_github import get_workflow_run_status

        def fake_req(url, method="GET", body=None, timeout=30.0):
            return 200, {
                "id": 99,
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://github.com/acme/app/actions/runs/99",
            }

        out = get_workflow_run_status(repo="acme/app", run_id="99", request_json=fake_req)
        self.assertTrue(out["ok"])
        self.assertTrue(out["done"])
        self.assertTrue(out["success"])

    def test_poll_unreachable(self):
        from local_dev.deploy_github import get_workflow_run_status

        def fake_req(url, method="GET", body=None, timeout=30.0):
            raise RuntimeError("network down")

        out = get_workflow_run_status(repo="acme/app", run_id="99", request_json=fake_req)
        self.assertFalse(out["ok"])
        self.assertTrue(out.get("unreachable"))


class DeployConfirmTests(unittest.TestCase):
    def setUp(self):
        deploy_confirm_mod._RECENT.clear()

    def test_cancel(self):
        out = confirm_deploy(decision="cancel")
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "cancelled")

    def test_confirm_triggers_mock(self):
        with patch("local_dev.deploy_confirm.github_deploy_token", return_value="tok"), patch(
            "local_dev.deploy_prepare.github_deploy_token", return_value="tok"
        ):
            out = confirm_deploy(
                decision="confirm",
                message="部署到预发",
                env="staging",
                ref="hebo",
                user_id="u1",
                cfg=_cfg(enabled=True),
                trigger_fn=lambda **kw: {
                    "ok": True,
                    "message": "triggered",
                    "run_url": "https://example.com/run",
                    "actions_url": "https://example.com/actions",
                },
            )
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "triggered")

    def test_confirm_idempotent(self):
        with patch("local_dev.deploy_confirm.github_deploy_token", return_value="tok"), patch(
            "local_dev.deploy_prepare.github_deploy_token", return_value="tok"
        ):
            cfg = _cfg(enabled=True)
            kwargs = dict(
                decision="confirm",
                env="staging",
                ref="hebo",
                user_id="u1",
                cfg=cfg,
                trigger_fn=lambda **kw: {"ok": True, "message": "ok"},
            )
            self.assertTrue(confirm_deploy(**kwargs)["ok"])
            dup = confirm_deploy(**kwargs)
            self.assertFalse(dup["ok"])
            self.assertEqual(dup.get("status"), "duplicate")

    def test_confirm_disabled(self):
        out = confirm_deploy(
            decision="confirm",
            env="staging",
            ref="hebo",
            cfg=_cfg(enabled=False),
            trigger_fn=lambda **kw: {"ok": True},
        )
        self.assertFalse(out["ok"])


class DeployLocalSshPrepareTests(unittest.TestCase):
    def test_github_path_unchanged_when_provider_default(self):
        """默认 github_actions：仍须 workflow+repo；缺 token 仍 ready 但不可 trigger。"""
        with patch("local_dev.deploy_prepare.github_deploy_token", return_value=""):
            out = prepare_deploy(
                message="部署到预发",
                env="staging",
                ref="hebo",
                cfg=_cfg(enabled=True, ci_provider="github_actions"),
            )
        self.assertTrue(out["ready_for_confirm"])
        self.assertFalse(out["can_trigger_ci"])
        self.assertEqual(out["ci_provider"], "github_actions")

    def test_local_ssh_ready_without_github_token(self):
        ssh_ok = {
            "host": "175.178.238.31",
            "user": "root",
            "key_path": "/tmp/fake_key",
            "app_path": "/www/wwwroot/zr-aicoding",
            "local_project": "/tmp/fake_proj",
            "restart_cmd": "",
            "port": "22",
        }
        with (
            patch("local_dev.deploy_prepare.github_deploy_token", return_value=""),
            patch("local_dev.deploy_local_ssh.local_ssh_settings", return_value=ssh_ok),
            patch("local_dev.deploy_local_ssh.validate_local_ssh_settings", return_value=[]),
        ):
            out = prepare_deploy(
                message="部署到预发",
                env="staging",
                ref="hebo",
                cfg=_cfg(
                    enabled=True,
                    ci_provider="local_ssh",
                    github_workflow="",
                    github_repo="",
                    ssh_host="175.178.238.31",
                    ssh_user="root",
                    ssh_key_path="~/.ssh/tc_staging_deploy",
                    ssh_app_path="/www/wwwroot/zr-aicoding",
                    local_project_path="/tmp/proj",
                ),
            )
        self.assertTrue(out["ready_for_confirm"])
        self.assertTrue(out["can_trigger_ci"])
        self.assertEqual(out["ci_provider"], "local_ssh")
        self.assertIn("本机 SSH", out["summary"])

    def test_local_ssh_not_ready_when_settings_invalid(self):
        with (
            patch("local_dev.deploy_prepare.github_deploy_token", return_value=""),
            patch(
                "local_dev.deploy_local_ssh.local_ssh_settings",
                return_value={
                    "host": "",
                    "user": "",
                    "key_path": "",
                    "app_path": "",
                    "local_project": "",
                    "restart_cmd": "",
                    "port": "22",
                },
            ),
            patch(
                "local_dev.deploy_local_ssh.validate_local_ssh_settings",
                return_value=["缺少 DEPLOY_SSH_HOST"],
            ),
        ):
            out = prepare_deploy(
                message="部署到预发",
                cfg=_cfg(enabled=True, ci_provider="local_ssh", github_workflow="", github_repo=""),
            )
        self.assertFalse(out["ready_for_confirm"])
        self.assertFalse(out["can_trigger_ci"])


class DeployLocalSshConfirmTests(unittest.TestCase):
    def setUp(self):
        deploy_confirm_mod._RECENT.clear()

    def test_confirm_local_ssh_does_not_require_github_token(self):
        called = {}

        def fake_trigger(**kw):
            called.update(kw)
            return {
                "ok": True,
                "provider": "local_ssh",
                "run_id": "local-abc",
                "message": "started",
            }

        with patch("local_dev.deploy_prepare.github_deploy_token", return_value=""):
            # prepare 内会校验 SSH；mock 掉
            with (
                patch("local_dev.deploy_local_ssh.local_ssh_settings") as ls,
                patch("local_dev.deploy_local_ssh.validate_local_ssh_settings", return_value=[]),
            ):
                ls.return_value = {
                    "host": "1.2.3.4",
                    "user": "root",
                    "key_path": "/k",
                    "app_path": "/app",
                    "local_project": "/p",
                    "restart_cmd": "",
                    "port": "22",
                }
                out = confirm_deploy(
                    decision="confirm",
                    env="staging",
                    ref="hebo",
                    user_id="u1",
                    cfg=_cfg(
                        enabled=True,
                        ci_provider="local_ssh",
                        github_repo="",
                        github_workflow="",
                        ssh_host="1.2.3.4",
                        ssh_app_path="/app",
                    ),
                    trigger_fn=fake_trigger,
                )
        self.assertTrue(out["ok"])
        self.assertEqual(out["status"], "triggered")
        self.assertEqual(out["ci"]["run_id"], "local-abc")
        self.assertEqual(called.get("ref"), "hebo")


class DeployLocalSshValidateTests(unittest.TestCase):
    def test_validate_rejects_bad_host(self):
        from local_dev.deploy_local_ssh import validate_local_ssh_settings

        errs = validate_local_ssh_settings(
            {
                "host": "bad host;rm",
                "user": "root",
                "key_path": "/no/such/key",
                "app_path": "/www/app",
                "local_project": "/no/proj",
                "restart_cmd": "",
                "port": "22",
            }
        )
        self.assertTrue(any("HOST" in e for e in errs))

    def test_validate_rejects_host_with_port(self):
        from local_dev.deploy_local_ssh import validate_local_ssh_settings

        errs = validate_local_ssh_settings(
            {
                "host": "175.178.238.31:22",
                "user": "root",
                "key_path": "/tmp/x",
                "app_path": "/www/wwwroot/zr-aicoding",
                "local_project": "/tmp/p",
                "restart_cmd": "",
                "port": "22",
            }
        )
        self.assertTrue(any("HOST" in e for e in errs))

    def test_validate_rejects_shallow_app_path(self):
        from local_dev.deploy_local_ssh import validate_local_ssh_settings

        errs = validate_local_ssh_settings(
            {
                "host": "175.178.238.31",
                "user": "root",
                "key_path": "/tmp/x",
                "app_path": "/www/wwwroot",
                "local_project": "/tmp/p",
                "restart_cmd": "",
                "port": "22",
            }
        )
        self.assertTrue(any("过浅" in e for e in errs))

    def test_validate_rejects_evil_restart_cmd(self):
        from local_dev.deploy_local_ssh import validate_local_ssh_settings

        errs = validate_local_ssh_settings(
            {
                "host": "175.178.238.31",
                "user": "root",
                "key_path": "/tmp/x",
                "app_path": "/www/wwwroot/zr-aicoding",
                "local_project": "/tmp/p",
                "restart_cmd": "bash /x.sh; curl http://evil",
                "port": "22",
            }
        )
        self.assertTrue(any("RESTART" in e for e in errs))

    def test_validate_accepts_safe_restart_cmd(self):
        from local_dev.deploy_local_ssh import validate_local_ssh_settings

        # 其它项故意无效，只断言 restart 本身不单独报错
        errs = validate_local_ssh_settings(
            {
                "host": "175.178.238.31",
                "user": "root",
                "key_path": "/tmp/x",
                "app_path": "/www/wwwroot/zr-aicoding",
                "local_project": "/tmp/p",
                "restart_cmd": "bash /www/wwwroot/zr-aicoding/start-api.sh",
                "port": "22",
            }
        )
        self.assertFalse(any("RESTART" in e for e in errs))

    def test_poll_unknown_run(self):
        from local_dev.deploy_local_ssh import _clear_jobs_for_tests, get_local_ssh_run_status

        _clear_jobs_for_tests()
        out = get_local_ssh_run_status("local-aaaaaaaaaaaa")
        self.assertFalse(out["ok"])
        self.assertIn("未找到", out.get("error") or "")

    def test_poll_rejects_malformed_run_id(self):
        from local_dev.deploy_local_ssh import get_local_ssh_run_status

        out = get_local_ssh_run_status("local-../../../etc")
        self.assertFalse(out["ok"])
        self.assertIn("无效", out.get("error") or "")

    def test_trigger_rejects_dotdot_ref(self):
        from local_dev.deploy_local_ssh import trigger_local_ssh_deploy

        out = trigger_local_ssh_deploy(
            ref="foo/../bar",
            environment="staging",
            cfg=_cfg(enabled=True, ci_provider="local_ssh"),
        )
        self.assertFalse(out["ok"])
        self.assertIn("非法", out.get("error") or "")

    def test_backend_excludes_env(self):
        from local_dev.deploy_config import DEFAULT_SSH_RSYNC_EXCLUDES, effective_ssh_rsync_excludes

        self.assertIn(".env", DEFAULT_SSH_RSYNC_EXCLUDES)
        self.assertIn(".env.*", DEFAULT_SSH_RSYNC_EXCLUDES)
        self.assertIn("*.pem", effective_ssh_rsync_excludes(_cfg()))

    def test_validate_rejects_env_inject_restart(self):
        from local_dev.deploy_local_ssh import validate_local_ssh_settings

        errs = validate_local_ssh_settings(
            {
                "host": "175.178.238.31",
                "user": "root",
                "key_path": "/tmp/x",
                "app_path": "/www/wwwroot/zr-aicoding",
                "local_project": "/tmp/p",
                "restart_cmd": "LD_PRELOAD=/tmp/x.so systemctl restart x",
                "port": "22",
            }
        )
        self.assertTrue(any("RESTART" in e for e in errs))

    def test_validate_rejects_key_outside_ssh_home(self):
        from local_dev.deploy_local_ssh import validate_local_ssh_settings
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            key = Path(td) / "id_rsa"
            key.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nx\n-----END OPENSSH PRIVATE KEY-----\n")
            errs = validate_local_ssh_settings(
                {
                    "host": "175.178.238.31",
                    "user": "root",
                    "key_path": str(key),
                    "app_path": "/www/wwwroot/zr-aicoding",
                    "local_project": "/tmp/p",
                    "restart_cmd": "",
                    "port": "22",
                }
            )
            self.assertTrue(any("ssh" in e.lower() for e in errs))

    def test_validate_accepts_systemctl_restart(self):
        from local_dev.deploy_local_ssh import validate_local_ssh_settings

        errs = validate_local_ssh_settings(
            {
                "host": "175.178.238.31",
                "user": "root",
                "key_path": "/tmp/x",
                "app_path": "/www/wwwroot/zr-aicoding",
                "local_project": "/tmp/p",
                "restart_cmd": "systemctl restart zr-aicoding-api",
                "port": "22",
            }
        )
        self.assertFalse(any("RESTART" in e for e in errs))


class DeployHealthProbeTests(unittest.TestCase):
    def test_skip_when_empty(self):
        from local_dev.deploy_local_ssh import probe_deploy_health

        out = probe_deploy_health("")
        self.assertTrue(out["ok"])
        self.assertTrue(out["skipped"])

    def test_reject_bad_url(self):
        from local_dev.deploy_local_ssh import probe_deploy_health

        out = probe_deploy_health("file:///etc/passwd")
        self.assertFalse(out["ok"])

    def test_success_2xx(self):
        from local_dev.deploy_local_ssh import probe_deploy_health

        class Resp:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def getcode(self):
                return 200

        def fake_open(req, timeout=10.0):
            return Resp()

        out = probe_deploy_health(
            "http://175.178.238.31:8090/",
            retries=1,
            sleep_fn=lambda _s: None,
            urlopen_fn=fake_open,
        )
        self.assertTrue(out["ok"])
        self.assertFalse(out["skipped"])
        self.assertEqual(out.get("status_code"), 200)

    def test_fail_after_retries(self):
        from local_dev.deploy_local_ssh import probe_deploy_health

        class Resp:
            status = 503

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def getcode(self):
                return 503

        calls = {"n": 0}

        def fake_open(req, timeout=10.0):
            calls["n"] += 1
            return Resp()

        out = probe_deploy_health(
            "http://175.178.238.31:8090/",
            retries=3,
            sleep_fn=lambda _s: None,
            urlopen_fn=fake_open,
        )
        self.assertFalse(out["ok"])
        self.assertEqual(calls["n"], 3)


if __name__ == "__main__":
    unittest.main()
