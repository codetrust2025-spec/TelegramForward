from __future__ import annotations

import pytest

from scripts import git_deploy_gate as gate


def _status(**overrides):
    commit = "a" * 40
    status = {
        "dirty": False,
        "head": commit,
        "branch": "main",
        "upstream": "origin/main",
        "origin_head": commit,
        "ahead": 0,
        "behind": 0,
        "ok": True,
    }
    status.update(overrides)
    return status


def test_accepts_only_clean_main_at_exact_origin_commit(monkeypatch):
    monkeypatch.setattr(gate, "_fetch_origin", lambda branch: None)
    monkeypatch.setattr(gate, "git_deploy_status", lambda branch="main": _status())

    assert gate.require_git_pushed("main") == "a" * 40


@pytest.mark.parametrize(
    "overrides",
    [
        {"branch": "feature/payment-fix", "ok": False},
        {"dirty": True, "ok": False},
        {"ahead": 1, "head": "b" * 40, "ok": False},
        {"behind": 1, "origin_head": "b" * 40, "ok": False},
        {"origin_head": "", "ok": False},
        {"origin_head": "b" * 40, "ok": False},
    ],
)
def test_rejects_any_state_other_than_exact_merged_main(monkeypatch, overrides):
    monkeypatch.setattr(gate, "_fetch_origin", lambda branch: None)
    monkeypatch.setattr(
        gate,
        "git_deploy_status",
        lambda branch="main": _status(**overrides),
    )

    with pytest.raises(SystemExit):
        gate.require_git_pushed("main")


def test_rejects_when_origin_cannot_be_refreshed(monkeypatch):
    def fail_fetch(branch):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(gate, "_fetch_origin", fail_fetch)

    with pytest.raises(SystemExit):
        gate.require_git_pushed("main")
