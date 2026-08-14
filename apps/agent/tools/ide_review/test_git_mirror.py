"""Git HTTPS 镜像前缀校验单测。"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from tools.ide_review.git_review import (
    _clone_url_candidates,
    _is_github_https_repo,
    _sanitize_mirror_prefix,
)


class GitMirrorTests(unittest.TestCase):
    def test_github_host_exact(self) -> None:
        self.assertTrue(
            _is_github_https_repo("https://github.com/org/repo.git")
        )
        self.assertFalse(
            _is_github_https_repo("https://github.com.evil.com/org/repo.git")
        )
        self.assertFalse(
            _is_github_https_repo("https://gitee.com/org/repo.git")
        )

    def test_reject_insecure_and_ssrf_prefixes(self) -> None:
        self.assertIsNone(_sanitize_mirror_prefix("http://evil.com/"))
        self.assertIsNone(_sanitize_mirror_prefix("https://127.0.0.1/"))
        self.assertIsNone(_sanitize_mirror_prefix("https://localhost/"))
        self.assertIsNone(_sanitize_mirror_prefix("https://192.168.1.1/proxy/"))
        self.assertIsNone(_sanitize_mirror_prefix("https://user:pass@evil.com/"))
        self.assertEqual(
            _sanitize_mirror_prefix("https://ghfast.top"),
            "https://ghfast.top/",
        )

    def test_custom_mirror_and_off(self) -> None:
        url = "https://github.com/a/b.git"
        with mock.patch.dict(os.environ, {"IDE_GIT_HTTPS_MIRROR": "off"}, clear=False):
            with mock.patch(
                "tools.ide_review.git_review._resolve_git_setting",
                side_effect=lambda k, d="": os.environ.get(k, d) or d,
            ):
                self.assertEqual(_clone_url_candidates(url), [url])

        with mock.patch(
            "tools.ide_review.git_review._resolve_git_setting",
            side_effect=lambda k, d="": (
                "https://ghfast.top/,http://bad/,https://127.0.0.1/"
                if k == "IDE_GIT_HTTPS_MIRROR"
                else ("0" if k == "IDE_GIT_MIRROR_FIRST" else d)
            ),
        ):
            cands = _clone_url_candidates(url)
            self.assertEqual(cands[0], url)
            self.assertIn("https://ghfast.top/" + url, cands)
            self.assertTrue(all("127.0.0.1" not in c for c in cands))
            self.assertTrue(all(not c.startswith("http://bad") for c in cands))


if __name__ == "__main__":
    unittest.main()
