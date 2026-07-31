"""Offline contract tests for the isolated deterministic deployer."""
from __future__ import annotations

import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import deploy_prod_v2 as deploy


def clean_capture(command: list[str], *, cwd: Path | None = None) -> str:
    command_key = tuple(command)
    responses = {
        ("git", "status", "--porcelain"): "",
        ("git", "rev-parse", "--abbrev-ref", "HEAD"): "main",
        ("git", "rev-parse", "HEAD"): "a" * 40,
        ("git", "rev-parse", "origin/main"): "a" * 40,
    }
    return responses[command_key]


class DeployGateTests(unittest.TestCase):
    def test_dirty_tree_is_rejected(self) -> None:
        with patch.object(deploy, "run"), patch.object(deploy, "capture", return_value=" M server.py"):
            with self.assertRaisesRegex(deploy.DeployError, "working tree is not clean"):
                deploy.require_clean_main()

    def test_wrong_branch_is_rejected(self) -> None:
        def capture(command: list[str], *, cwd: Path | None = None) -> str:
            if command == ["git", "status", "--porcelain"]:
                return ""
            if command == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
                return "codex/production-recovery-20260731"
            raise AssertionError(command)

        with patch.object(deploy, "run"), patch.object(deploy, "capture", side_effect=capture):
            with self.assertRaisesRegex(deploy.DeployError, "checkout main"):
                deploy.require_clean_main()

    def test_origin_mismatch_is_rejected(self) -> None:
        def capture(command: list[str], *, cwd: Path | None = None) -> str:
            if command == ["git", "rev-parse", "HEAD"]:
                return "a" * 40
            if command == ["git", "rev-parse", "origin/main"]:
                return "b" * 40
            return clean_capture(command, cwd=cwd)

        with patch.object(deploy, "run"), patch.object(deploy, "capture", side_effect=capture):
            with self.assertRaisesRegex(deploy.DeployError, "does not exactly equal origin/main"):
                deploy.require_clean_main()

    def test_missing_lockfiles_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(deploy, "REPO", Path(directory)):
            with self.assertRaisesRegex(deploy.DeployError, "requirements.lock"):
                deploy.require_reproducible_inputs()

    def test_clean_main_returns_the_exact_deploy_commit(self) -> None:
        with patch.object(deploy, "run") as run, patch.object(deploy, "capture", side_effect=clean_capture):
            self.assertEqual(deploy.require_clean_main(), "a" * 40)
        run.assert_called_once_with(["git", "fetch", "--prune", "origin", "main"], timeout=120)

    def test_clean_checkout_is_detached_at_requested_commit(self) -> None:
        commit = "a" * 40
        def capture(command: list[str], *, cwd: Path | None = None) -> str:
            if command == ["git", "rev-parse", "HEAD"]:
                return commit
            if command == ["git", "status", "--porcelain"]:
                return ""
            raise AssertionError(command)

        with tempfile.TemporaryDirectory() as directory, patch.object(deploy, "run") as run, patch.object(
            deploy, "capture", side_effect=capture
        ):
            source = deploy.clean_checkout(commit, Path(directory))
        self.assertEqual(source.name, "source")
        self.assertIn(unittest.mock.call(["git", "checkout", "--detach", commit], cwd=source), run.call_args_list)


class DeployPayloadTests(unittest.TestCase):
    def test_runtime_paths_and_secrets_never_enter_a_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            for relative in (
                "server.py",
                "static/index.html",
                ".env",
                "data/state.json",
                "uploads/proof.png",
                "logs/app.log",
                "sessions/account.session",
                "cache/value",
                ".git/HEAD",
            ):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("test", encoding="utf-8")
            archive_path = Path(directory) / "release.tar.gz"
            deploy.release_archive(source, archive_path)
            with tarfile.open(archive_path) as archive:
                names = archive.getnames()
        self.assertIn("server.py", names)
        self.assertIn("static/index.html", names)
        self.assertFalse(any(name == ".env" or name.startswith(("data/", "uploads/", "logs/", "sessions/", "cache/", ".git/")) for name in names))

    def test_failed_build_stops_before_manifest_or_upload(self) -> None:
        def fail_tests(command: list[str], **_: object) -> str:
            if command[-2:] == ["pytest", "-q"]:
                raise deploy.DeployError("tests failed")
            return ""

        with tempfile.TemporaryDirectory() as directory, patch.object(deploy, "run", side_effect=fail_tests), patch.object(
            deploy, "validate_manifest"
        ) as validate_manifest:
            with self.assertRaisesRegex(deploy.DeployError, "tests failed"):
                deploy.run_quality_gates(Path(directory))
        validate_manifest.assert_not_called()

    def test_failed_upload_closes_sftp_connection(self) -> None:
        class Sftp:
            closed = False

            def mkdir(self, path: str) -> None:
                return None

            def put(self, local: str, remote: str) -> None:
                raise OSError("network failure")

            def close(self) -> None:
                self.closed = True

        class Client:
            def __init__(self) -> None:
                self.sftp = Sftp()

            def open_sftp(self) -> Sftp:
                return self.sftp

        client = Client()
        with self.assertRaisesRegex(OSError, "network failure"):
            deploy.upload(client, Path("payload.tar.gz"), "payload.tar.gz")
        self.assertTrue(client.sftp.closed)


class DeployRollbackContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.script = deploy.remote_script("a" * 40, "payload.tar.gz", "b" * 64, "operator", "a" * 40)

    def test_remote_release_uses_protected_runtime_paths(self) -> None:
        for path in ("$SHARED/.env", "$SHARED/data", "$SHARED/uploads", "$SHARED/sessions", "$SHARED/logs", "$SHARED/cache"):
            self.assertIn(path, self.script)
        self.assertIn("umask 027", self.script)
        self.assertIn("Shared runtime paths are not writable", self.script)

    def test_health_failure_restores_previous_release(self) -> None:
        self.assertIn("health_check_failed", self.script)
        self.assertIn('ln -s "$previous" "$ROOT/.rollback-next"', self.script)
        self.assertIn('mv -Tf "$ROOT/.rollback-next" "$ROOT/current"', self.script)
        self.assertIn('startOrReload "$PM2_CONFIG"', self.script)
        self.assertIn('rollback.log', self.script)

    def test_release_switch_and_records_are_atomic_and_auditable(self) -> None:
        self.assertIn('test -f "$previous/RELEASE.json"', self.script)
        self.assertIn('ln -s "$RELEASE" "$ROOT/.next"', self.script)
        self.assertIn('mv -Tf "$ROOT/.next" "$ROOT/current"', self.script)
        self.assertIn('"$SHARED/deployments/current.json"', self.script)
        self.assertIn('"$RELEASE_ID" "$COMMIT" "$HASH" "$OPERATOR"', self.script)

    def test_obsolete_release_cleanup_is_not_performed(self) -> None:
        self.assertNotIn('rm -rf "$RELEASES/', self.script)
        self.assertIn('rm -rf "$STAGING"', self.script)


if __name__ == "__main__":
    unittest.main()
