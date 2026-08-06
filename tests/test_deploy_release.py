"""Safety contract for the policy-compliant deployer.

Every test here runs entirely offline against a fake SSH client. None of them
may open a network connection, so the suite can never touch Production.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import deploy_release as dr  # noqa: E402


class FakeSSH:
    """Records commands and replays scripted answers.

    Any command whose prefix is registered in ``fail`` raises, mirroring the
    real ssh() helper's check=True behaviour.
    """

    def __init__(self, answers=None, fail=()):
        self.answers = answers or {}
        self.fail = tuple(fail)
        self.commands: list[str] = []

    def close(self):  # pragma: no cover - parity with paramiko
        pass


def fake_ssh_factory(client: FakeSSH):
    def _ssh(_client, command, *, check=True, timeout=900):
        client.commands.append(command)
        for marker in client.fail:
            if marker in command:
                if check:
                    raise SystemExit(f"Remote command failed: {command}")
                return ""
        for marker, value in client.answers.items():
            if marker in command:
                return value
        return ""
    return _ssh


def ran(client: FakeSSH, fragment: str) -> bool:
    return any(fragment in c for c in client.commands)


# ── local preflight ──────────────────────────────────────────────────────────

def test_dirty_worktree_is_rejected(monkeypatch):
    monkeypatch.setattr(dr, "git", lambda *a: " M scripts/deploy_release.py")
    with pytest.raises(SystemExit, match="dirty"):
        dr.require_deployable_commit("deadbeef")


def test_commit_that_is_not_origin_main_is_rejected(monkeypatch):
    def fake_git(*args):
        if args[0] == "status":
            return ""
        if args[0] == "rev-parse" and args[1] == "origin/main":
            return "a" * 40
        if args[0] == "rev-parse":
            return "b" * 40
        return ""
    monkeypatch.setattr(dr, "git", fake_git)
    with pytest.raises(SystemExit, match="origin/main"):
        dr.require_deployable_commit("b" * 40)


def test_matching_commit_is_accepted(monkeypatch):
    sha = "c" * 40

    def fake_git(*args):
        if args[0] == "status":
            return ""
        return sha
    monkeypatch.setattr(dr, "git", fake_git)
    assert dr.require_deployable_commit(sha) == sha


def test_clean_checkout_excludes_runtime_paths(tmp_path, monkeypatch):
    """Even if a runtime path were committed, it must not ship in a release."""
    repo = tmp_path / "repo"
    (repo / "core").mkdir(parents=True)
    (repo / "server.py").write_text("x", encoding="utf-8")
    (repo / "core" / "app.py").write_text("x", encoding="utf-8")
    for name in ("data", "uploads", "logs"):
        (repo / name).mkdir()
        (repo / name / "secret.txt").write_text("runtime", encoding="utf-8")
    (repo / ".env").write_text("TOKEN=shh", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=repo, check=True,
    )
    monkeypatch.setattr(dr, "REPO", repo)

    source = dr.clean_checkout("HEAD", tmp_path / "ws")

    assert (source / "server.py").exists()
    assert (source / "core" / "app.py").exists()
    for name in (".env", "data", "uploads", "logs"):
        assert not (source / name).exists(), f"{name} leaked into the release"


def test_backup_includes_verified_postgres_dump_inventory_and_checksums(monkeypatch):
    client = FakeSSH()
    monkeypatch.setattr(dr, "ssh", fake_ssh_factory(client))

    target = dr.take_backup(client, "a" * 40)

    assert target.startswith("/var/backups/telegramforward/")
    assert ran(client, "pg_dump -Fc teleautomation")
    assert ran(client, "pg_dump --schema-only teleautomation")
    assert ran(client, "pg_restore --list")
    assert ran(client, "INVENTORY.txt")
    assert ran(client, "sha256sum -c SHA256SUMS")
    assert all("\x00" not in command for command in client.commands)


# ── manifest verification ────────────────────────────────────────────────────

def test_manifest_hash_mismatch_aborts(tmp_path, monkeypatch):
    source = tmp_path / "src"
    (source / "static" / "assets").mkdir(parents=True)
    (source / "scripts").mkdir()
    asset = source / "static" / "assets" / "app-x.js"
    asset.write_text("real bundle", encoding="utf-8")
    (source / "static" / "index.html").write_text("assets/app-x.js", encoding="utf-8")

    monkeypatch.setattr(
        dr, "write_and_verify_manifest",
        dr.write_and_verify_manifest,  # keep the real function under test
    )

    # Stand in for prod_sync_common.write_manifest with a deliberately wrong hash.
    import types
    fake_mod = types.ModuleType("scripts.prod_sync_common")
    fake_mod.write_manifest = lambda git_commit=None: {
        "js": "assets/app-x.js", "css": "assets/app-x.js",
        "js_sha256": "0" * 64, "css_sha256": "0" * 64,
    }
    monkeypatch.setitem(sys.modules, "scripts.prod_sync_common", fake_mod)

    with pytest.raises(SystemExit, match="hash mismatch"):
        dr.write_and_verify_manifest(source, "d" * 40)


# ── switch / rollback contract ───────────────────────────────────────────────

def test_verify_release_reports_missing_confirm_route_and_410(monkeypatch):
    client = FakeSSH(answers={
        "curl": '{"status":"ok"}',
        "bookings/confirm": "0",
        "status=410": "0",
        "sha256sum": "deadbeef",
    })
    monkeypatch.setattr(dr, "ssh", fake_ssh_factory(client))
    problems = dr.verify_release(
        client, "/opt/telegramforward/releases/x",
        {"js": "assets/a.js", "css": "assets/a.css",
         "js_sha256": "abc", "css_sha256": "abc"},
    )
    assert any("bookings/confirm" in p for p in problems)
    assert any("410" in p for p in problems)
    assert any("asset hash mismatch" in p for p in problems)


def test_verify_release_passes_when_everything_matches(monkeypatch):
    client = FakeSSH(answers={
        "curl": '{"status":"ok"}',
        "bookings/confirm": "1",
        "status=410": "1",
        "sha256sum": "abc",
        # Handler accounts must be reachable from the release or every handler
        # login fails; the deployer now refuses to switch without them.
        "dashboard_handlers.yaml": "yes",
        "_handler_accounts": "9",
    })
    monkeypatch.setattr(dr, "ssh", fake_ssh_factory(client))
    assert dr.verify_release(
        client, "/rel",
        {"js": "assets/a.js", "css": "assets/a.css",
         "js_sha256": "abc", "css_sha256": "abc"},
    ) == []


def test_verify_live_release_checks_process_proxy_apis_and_public_assets(monkeypatch):
    commit = "c" * 40
    client = FakeSSH(answers={
        "127.0.0.1:8000/health": '{"status":"ok"}',
        # Handler accounts must be reachable from the release; without them
        # every handler login fails while the admin login keeps working.
        "dashboard_handlers.yaml": "yes",
        "_handler_accounts": "9",
        "bookings/confirm'": "1",
        "status=410": "1",
        "sha256sum /rel/static/assets/a.js": "js-hash",
        "sha256sum /rel/static/assets/a.css": "css-hash",
        "readlink -f /opt/telegramforward/current": "/rel",
        "production.manifest.json": "1",
        "agreed on the date and start time": "1",
        "pm2 pid": "500",
        "sport = :8000": "500",
        "/cwd": "/rel",
        "pgrep -fc": "2",
        "nginx -t": "ok",
        "teleautomation.online/health": '{"status":"ok"}',
        "teleautomation.online/bookings/confirm": "422",
        "teleautomation.online/public/slots/book": "410",
        "teleautomation.online/assets/a.js": "js-hash",
        "teleautomation.online/assets/a.css": "css-hash",
        "curl -sf -m 15 https://teleautomation.online/": (
            '<script src="assets/a.js"></script><link href="assets/a.css">'
        ),
    })
    monkeypatch.setattr(dr, "ssh", fake_ssh_factory(client))

    problems = dr.verify_live_release(
        client,
        "/rel",
        {
            "js": "assets/a.js",
            "css": "assets/a.css",
            "js_sha256": "js-hash",
            "css_sha256": "css-hash",
        },
        commit,
    )

    assert problems == []
    assert ran(client, "sport = :8000"), "the port owner must be checked"
    assert ran(client, "pm2 pid")
    assert ran(client, "nginx -t")
    assert ran(client, "/bookings/confirm")
    assert ran(client, "/public/slots/book")


def test_verify_live_release_reports_critical_runtime_failures(monkeypatch):
    client = FakeSSH(answers={
        "127.0.0.1:8000/health": '{"status":"ok"}',
        # Handler accounts must be reachable from the release; without them
        # every handler login fails while the admin login keeps working.
        "dashboard_handlers.yaml": "yes",
        "_handler_accounts": "9",
        "bookings/confirm'": "1",
        "status=410": "1",
        "sha256sum": "hash",
        "readlink -f": "/wrong",
        "production.manifest.json": "1",
        "agreed on the date and start time": "1",
        "pm2 pid": "",
        "nginx -t": "failed",
        "teleautomation.online/health": "",
        "teleautomation.online/bookings/confirm": "500",
        "teleautomation.online/public/slots/book": "200",
    })
    monkeypatch.setattr(dr, "ssh", fake_ssh_factory(client))

    problems = dr.verify_live_release(
        client,
        "/rel",
        {
            "js": "assets/a.js",
            "css": "assets/a.css",
            "js_sha256": "hash",
            "css_sha256": "hash",
        },
        "d" * 40,
    )

    assert any("current resolves" in problem for problem in problems)
    assert any(
        "port 8000" in problem or "PM2" in problem for problem in problems
    ), "a serving process that is absent or not PM2's must be reported"
    assert any("Nginx" in problem for problem in problems)
    assert any("/bookings/confirm" in problem for problem in problems)
    assert any("legacy booking" in problem for problem in problems)


def test_switch_current_is_a_single_atomic_rename(monkeypatch):
    client = FakeSSH()
    monkeypatch.setattr(dr, "ssh", fake_ssh_factory(client))
    dr.switch_current(client, "/opt/telegramforward/releases/new")
    assert ran(client, "mv -Tf"), "current must move via an atomic rename"
    assert not ran(client, "rm -rf /opt/telegramforward/current")


def test_rollback_repoints_current_to_previous(monkeypatch):
    client = FakeSSH(answers={"curl": '{"status":"ok"}'})
    monkeypatch.setattr(dr, "ssh", fake_ssh_factory(client))
    assert dr.rollback(client, "/opt/telegramforward/releases/prev", "previous-sha") is True
    assert ran(client, "/opt/telegramforward/releases/prev")
    assert ran(client, "mv -Tf")
    assert ran(client, "pm2 stop"), "the old process must be stopped"
    assert ran(client, "pm2 start"), "exactly one process is started"
    assert ran(client, "previous-sha")


def test_marker_is_never_written_before_verification(monkeypatch):
    """The deploy marker must not appear anywhere except after success."""
    source = Path(dr.__file__).read_text(encoding="utf-8")
    body = source.split("switch_current(client, release)")[-1]
    marker = "printf '%s' {q(commit)}"
    assert marker in body, "marker is written before the switch"
    assert body.index("verify_live_release") < body.index(".deploy-commit"), (
        "marker must be written only after post-switch verification"
    )


def test_post_switch_failure_contract_runs_rollback_and_returns_failure():
    source = Path(dr.__file__).read_text(encoding="utf-8")
    body = source.split("switched = False", 1)[1]
    assert "except BaseException" in body
    assert "rollback(client, previous, previous_marker)" in body
    assert "return 1 if recovered else 2" in body


def test_activate_release_rolls_back_and_returns_failure(monkeypatch):
    events = []
    monkeypatch.setattr(dr, "switch_current", lambda *_args: events.append("switch"))
    monkeypatch.setattr(dr, "reload_app", lambda *_args: events.append("reload"))
    monkeypatch.setattr(
        dr,
        "verify_live_release",
        lambda *_args: ["critical verification failure"],
    )
    monkeypatch.setattr(
        dr,
        "rollback",
        lambda *_args: events.append("rollback") or True,
    )

    status = dr.activate_release(
        FakeSSH(),
        release="/new",
        previous="/previous",
        previous_marker="previous-sha",
        manifest={},
        commit="new-sha",
    )

    assert status == 1
    assert events == ["switch", "reload", "rollback"]


def test_activate_release_writes_marker_only_after_live_verification(monkeypatch):
    events = []
    client = FakeSSH()
    monkeypatch.setattr(dr, "switch_current", lambda *_args: events.append("switch"))
    monkeypatch.setattr(dr, "reload_app", lambda *_args: events.append("reload"))
    monkeypatch.setattr(
        dr,
        "verify_live_release",
        lambda *_args: events.append("verify") or [],
    )

    def record_ssh(_client, command, *, check=True, timeout=900):
        events.append("marker" if ".deploy-commit" in command else "ssh")
        return ""

    monkeypatch.setattr(dr, "ssh", record_ssh)

    status = dr.activate_release(
        client,
        release="/new",
        previous="/previous",
        previous_marker="previous-sha",
        manifest={},
        commit="new-sha",
    )

    assert status == 0
    assert events == ["switch", "reload", "verify", "marker"]


def test_existing_release_directory_is_never_overwritten():
    source = Path(dr.__file__).read_text(encoding="utf-8")
    assert "Refusing to overwrite immutable release directory" in source
    assert "rm -rf {q(release)} && mkdir" not in source


def test_previous_release_is_never_deleted(monkeypatch):
    """Rollback depends on the previous release surviving the deploy."""
    source = Path(dr.__file__).read_text(encoding="utf-8")
    assert "rm -rf {q(previous)}" not in source
    assert "retained for rollback" in source


def test_migration_fails_closed_and_checks_completeness(monkeypatch):
    """A partial copy must never become 'current'."""
    client = FakeSSH(
        answers={"test -L": "no"},
        # simulate the completeness probe failing for server.py
        fail=(),
    )
    client.answers["server.py"] = "no"
    monkeypatch.setattr(dr, "ssh", fake_ssh_factory(client))
    with pytest.raises(SystemExit, match="migration incomplete"):
        dr.migrate_legacy_layout(client, "e" * 40)
    assert not ran(client, "mv -Tf"), "current must not be created after a bad copy"


def test_migration_is_skipped_when_current_already_exists(monkeypatch):
    client = FakeSSH(answers={"test -L": "yes"})
    monkeypatch.setattr(dr, "ssh", fake_ssh_factory(client))
    dr.migrate_legacy_layout(client, "f" * 40)
    assert not ran(client, "cp -a"), "must not touch a host already on releases/"
