"""Deployment must verify the process that owns the port, not PM2's record."""
import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "deploy_release", Path(__file__).resolve().parents[1] / "scripts" / "deploy_release.py"
)
deploy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(deploy)

RELEASE = "/opt/telegramforward/releases/abc123"


class FakeSSH:
    """Answers the shell probes deploy_release makes, by substring match."""

    def __init__(self, port_owner="500", pm2="500", cwd=RELEASE, procs="2",
                 owner_sequence=None):
        self.port_owner = port_owner
        self.owner_sequence = list(owner_sequence or [])
        self.pm2 = pm2
        self.cwd = cwd
        self.procs = procs
        self.killed = []

    def __call__(self, _client, command, check=True):
        if "sport = :8000" in command:
            if self.owner_sequence:
                return self.owner_sequence.pop(0)
            return self.port_owner
        if "pm2 pid" in command:
            return self.pm2
        if "/cwd" in command:
            return self.cwd
        if "pgrep -fc" in command:
            return self.procs
        if "pgrep -f" in command:
            return ""
        if command.startswith("kill "):
            self.killed.append(command)
            return ""
        return ""


@pytest.fixture(autouse=True)
def patch_ssh(monkeypatch):
    def install(fake):
        monkeypatch.setattr(deploy, "ssh", fake)
        monkeypatch.setattr(deploy, "log", lambda *_a, **_k: None)
        return fake
    return install


def test_healthy_deployment_reports_no_problems(patch_ssh):
    patch_ssh(FakeSSH(port_owner="500", pm2="500", cwd=RELEASE, procs="2"))
    assert deploy.verify_serving_process(None, RELEASE) == []


def test_pm2_pid_not_owning_the_port_is_a_failure(patch_ssh):
    """The exact production defect: PM2 reports a crash-looping child while an
    orphan from the previous release keeps serving."""
    patch_ssh(FakeSSH(port_owner="256707", pm2="523383", cwd=RELEASE))
    problems = deploy.verify_serving_process(None, RELEASE)
    assert any("owns port 8000" in p for p in problems)


def test_serving_from_the_wrong_release_is_a_failure(patch_ssh):
    patch_ssh(FakeSSH(cwd="/opt/telegramforward/releases/stale999"))
    problems = deploy.verify_serving_process(None, RELEASE)
    assert any("not /opt/telegramforward/releases/abc123" in p for p in problems)


def test_nothing_listening_is_a_failure(patch_ssh):
    patch_ssh(FakeSSH(port_owner=""))
    problems = deploy.verify_serving_process(None, RELEASE)
    # The wait is exhausted first, so the message says so.
    assert len(problems) == 1
    assert "nothing is listening on port 8000" in problems[0]


def test_a_changing_pid_is_detected_as_a_respawn_loop(patch_ssh):
    patch_ssh(FakeSSH(owner_sequence=["500", "501"], pm2="500", cwd=RELEASE))
    problems = deploy.verify_serving_process(None, RELEASE)
    assert any("respawn loop" in p for p in problems)


def test_extra_app_processes_are_reported(patch_ssh):
    patch_ssh(FakeSSH(procs="7"))
    problems = deploy.verify_serving_process(None, RELEASE)
    assert any("app processes are running" in p for p in problems)


def test_reload_drains_the_port_before_starting(patch_ssh):
    fake = patch_ssh(FakeSSH(owner_sequence=["256707", "", "", ""], procs="2"))
    deploy.reload_app(None)
    assert fake.killed, "a process holding the port must be terminated"
    assert any("-TERM" in cmd for cmd in fake.killed)


def test_reload_refuses_to_start_while_the_port_is_still_held(patch_ssh):
    patch_ssh(FakeSSH(port_owner="256707"))
    with pytest.raises(SystemExit, match="still held"):
        deploy.reload_app(None)


class SettlingSSH(FakeSSH):
    """A start that takes a few seconds to bind and be noticed by PM2."""

    def __init__(self, *, settle_after=2, **kwargs):
        super().__init__(**kwargs)
        self.settle_after = settle_after
        self.probes = 0
        self.sleeps = 0

    def __call__(self, _client, command, check=True):
        if "sport = :8000" in command:
            self.probes += 1
            return "" if self.probes <= self.settle_after else self.port_owner
        if command.startswith("sleep "):
            self.sleeps += 1
            return ""
        return super().__call__(_client, command, check)


def test_verification_waits_for_the_process_to_settle(patch_ssh):
    """A release that binds a moment later must not be rolled back."""
    fake = patch_ssh(SettlingSSH(port_owner="600", pm2="600", cwd=RELEASE,
                                 procs="2", settle_after=2))
    assert deploy.verify_serving_process(None, RELEASE) == []
    assert fake.sleeps > 0, "it should have waited rather than failed immediately"


def test_a_fast_start_is_not_delayed(patch_ssh):
    fake = patch_ssh(SettlingSSH(port_owner="600", pm2="600", cwd=RELEASE,
                                 procs="2", settle_after=0))
    owner = deploy.wait_until_settled(None)
    assert owner == "600"
    assert fake.sleeps == 0, "no waiting when it is already steady"


def test_a_process_that_never_binds_still_fails(patch_ssh):
    patch_ssh(SettlingSSH(port_owner="600", pm2="600", cwd=RELEASE,
                          settle_after=999))
    problems = deploy.verify_serving_process(None, RELEASE)
    assert any("nothing is listening" in p for p in problems)
    assert any("settle" in p for p in problems)


def test_settling_waits_for_pm2_to_agree_with_the_port(patch_ssh):
    """Binding alone is not enough — PM2 must be reporting the same pid."""
    fake = patch_ssh(FakeSSH(port_owner="600", pm2="599", cwd=RELEASE))
    owner = deploy.wait_until_settled(None, attempts=3, pause=1)
    assert owner == "600"
    assert fake.killed == []
    problems = deploy.verify_serving_process(None, RELEASE)
    assert any("owns port 8000" in p for p in problems), (
        "a lasting disagreement is still reported"
    )
