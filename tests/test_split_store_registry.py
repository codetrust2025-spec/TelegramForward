"""An unregistered top-level JSON store must be loud, not invisible.

The registry's docstring always promised that adding a source without
classifying it would "surface as UNCLASSIFIED rather than being dropped". That
promise had nothing behind it: `build_plan` only walked the registry, so a file
no entry mentioned was never looked at. Six stores were left behind at the
2026-08-16 cutover that way, three of them financial, and the migration
reported success.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import split_migrate as sm  # noqa: E402


@pytest.fixture()
def data_dir(tmp_path):
    (tmp_path / "referrers.json").write_text(json.dumps({"referrers": []}), encoding="utf-8")
    return tmp_path


def test_the_accounting_stores_are_registered_to_operations():
    """The three stores whose absence overstated the August balances."""
    owners = {s.filename: s.owner for s in sm.JSON_STORES}
    for filename in ("handler_expenses.json", "handler_salaries.json"):
        assert owners.get(filename) == sm.OPERATIONS, f"{filename} is unowned"


def test_every_registry_entry_declares_an_owner():
    valid = {sm.MARKETING, sm.OPERATIONS, sm.AMBIGUOUS, sm.EXCLUDED}
    for store in sm.JSON_STORES:
        assert store.owner in valid, f"{store.filename} has owner {store.owner!r}"


def test_an_unregistered_store_is_reported_as_unclassified(data_dir):
    (data_dir / "invented_store.json").write_text(json.dumps({"rows": []}), encoding="utf-8")

    plan = sm.build_plan(data_dir, None)
    orphans = [i for i in plan.items if i.owner == sm.UNCLASSIFIED]

    assert [i.name for i in orphans] == ["invented_store.json"]
    assert any("not in JSON_STORES" in p for p in orphans[0].problems)


def test_a_registered_store_is_not_reported_as_unclassified(data_dir):
    plan = sm.build_plan(data_dir, None)
    assert [i for i in plan.items if i.owner == sm.UNCLASSIFIED] == []


def test_runtime_state_is_not_treated_as_an_orphan(data_dir):
    """Files the service rebuilds on start are deliberately not migrated."""
    (data_dir / "ollama_nodes_state.json").write_text("{}", encoding="utf-8")
    plan = sm.build_plan(data_dir, None)
    assert [i for i in plan.items if i.owner == sm.UNCLASSIFIED] == []


def test_execute_refuses_to_run_with_an_unregistered_store(data_dir, capsys):
    """The gate that would have stopped the cutover.

    Reporting an orphan is not enough on its own — a migration that prints a
    warning and then writes anyway still leaves the data behind.
    """
    (data_dir / "invented_store.json").write_text(json.dumps({"rows": []}), encoding="utf-8")

    exit_code = sm.main([
        "--execute", "--confirm-non-production",
        "--data-dir", str(data_dir),
        "--marketing-dsn", "postgresql://u@localhost/m_test",
        "--marketing-data-dir", str(data_dir / "m"),
        "--operations-dsn", "postgresql://u@localhost/o_test",
        "--operations-data-dir", str(data_dir / "o"),
    ])

    assert exit_code != 0
    assert "invented_store.json" in capsys.readouterr().out
