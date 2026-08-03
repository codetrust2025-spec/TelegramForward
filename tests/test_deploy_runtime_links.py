"""Handler sign-in depends on a file the release payload never carries.

config/dashboard_handlers.yaml holds the handler accounts and is gitignored
because it holds secrets, so it is absent from every release unless the
deployer links it in. It was not linked, so from the first release-based deploy
onward every handler login failed while the admin login — which reads .env, and
.env *is* linked — kept working. That asymmetry is why it went unnoticed.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[1] / "scripts" / "deploy_release.py"
SOURCE = DEPLOY.read_text(encoding="utf-8")


def _literal(name: str):
    module = ast.parse(SOURCE)
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == name for t in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in deploy_release.py")


def test_handler_accounts_file_is_linked_as_runtime_state():
    assert "config/dashboard_handlers.yaml" in _literal("RUNTIME_FILE_LINKS")


def test_the_file_is_not_shipped_with_the_release():
    """If it were git-tracked the secrets would be in the repository."""
    gitignore = (DEPLOY.parents[1] / ".gitignore").read_text(encoding="utf-8")
    assert "config/dashboard_handlers.yaml" in gitignore


def test_env_and_handler_file_are_both_treated_as_runtime():
    # .env was linked and handlers were not, which is the whole bug: admin
    # login kept working and hid the handler outage.
    assert ".env" in _literal("RUNTIME_LINKS")
    assert _literal("RUNTIME_FILE_LINKS"), "no runtime files declared"


def test_nested_runtime_files_are_linked_individually():
    """A git-tracked parent directory cannot itself be replaced by a link."""
    for rel in _literal("RUNTIME_FILE_LINKS"):
        assert "/" in rel, f"{rel} belongs in RUNTIME_LINKS, not RUNTIME_FILE_LINKS"

    link_runtime = SOURCE[SOURCE.index("def link_runtime") : SOURCE.index("def health_ok")]
    assert "RUNTIME_FILE_LINKS" in link_runtime
    # The parent must survive; only the file becomes a link.
    assert "os.path.dirname(dest)" in link_runtime
    assert "ln -sfn" in link_runtime


def test_release_verification_fails_when_handlers_are_unreachable():
    verify = SOURCE[SOURCE.index("def verify_release") : SOURCE.index("def verify_live_release")]
    assert "RUNTIME_FILE_LINKS" in verify
    assert "_handler_accounts" in verify
    assert "handler login would fail" in verify


def test_a_missing_runtime_file_is_reported_rather_than_ignored():
    link_runtime = SOURCE[SOURCE.index("def link_runtime") : SOURCE.index("def health_ok")]
    assert "WARNING" in link_runtime, "a silently skipped link is how this shipped"


@pytest.mark.parametrize("secret_path", ["config/dashboard_handlers.yaml"])
def test_runtime_secrets_never_enter_the_repository(secret_path):
    tracked = (DEPLOY.parents[1] / secret_path).exists()
    if tracked:
        pytest.fail(f"{secret_path} must not be committed; it holds credentials")
