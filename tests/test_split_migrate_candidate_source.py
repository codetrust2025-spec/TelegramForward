"""The monolith keeps candidates twice, and the two copies have drifted.

Measured on production: candidates_store holds 195 rows, candidates.json holds
102, and only 66 are in both. Of the 26 candidates that live recruitment mail
references, all 26 are in PostgreSQL and 7 are in the file.

Building the destination table from the file drops 129 live candidates and
resurrects 36 the product no longer has - and the resulting row count looks
plausible either way, which is what makes it worth a test.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "split_migrate",
    Path(__file__).resolve().parents[1] / "scripts" / "split_migrate.py",
)
sm = importlib.util.module_from_spec(_SPEC)
# Registered before exec because the module defines dataclasses, and their
# annotation resolution looks the module up by name.
sys.modules[_SPEC.name] = sm
_SPEC.loader.exec_module(sm)


def test_candidates_store_is_migrated_from_postgres():
    assert "candidates_store" in sm.OPERATIONS_TABLES


def test_the_json_mirror_does_not_build_the_table():
    store = next(s for s in sm.JSON_STORES if s.filename == "candidates.json")
    assert store.target_table is None, (
        "candidates.json is a stale mirror and must not build candidates_store")


def test_the_json_mirror_is_still_carried_across():
    """Not authoritative is not the same as discarded. The file still moves, so
    the 36 records only it has are preserved for an owner decision."""
    store = next(s for s in sm.JSON_STORES if s.filename == "candidates.json")
    assert store.owner == sm.OPERATIONS


def test_the_divergence_is_declared_so_it_gets_measured():
    assert sm._MIRRORED_TABLES.get("candidates.json") == "candidates_store"


def test_no_mirrored_store_also_targets_its_table():
    """A store that is both a mirror and a table source would silently pick a
    winner, which is the bug this whole file exists about."""
    for store in sm.JSON_STORES:
        if store.filename in sm._MIRRORED_TABLES:
            assert store.target_table is None, store.filename


def test_the_trees_that_actually_hold_the_evidence_are_migrated():
    """payment_evidence holds 6 files. The evidence the product writes lives in
    candidates_proofs (211), candidates_resumes (37), handler_expense_proofs
    (16) and pending_slot_payments (11). Migrating payment_evidence alone and
    calling it done leaves 275 files behind."""
    declared = {rel: owner for rel, owner, _ in sm.FILE_TREES}
    for tree in ("data/candidates_proofs", "data/candidates_resumes",
                 "data/handler_expense_proofs", "data/pending_slot_payments"):
        assert declared.get(tree) == sm.OPERATIONS, tree
    assert declared.get("data/crm") == sm.MARKETING


def test_trees_left_behind_are_named_rather_than_forgotten():
    """A tree nobody listed looks the same as a tree somebody decided against."""
    declared = {rel: owner for rel, owner, _ in sm.FILE_TREES}
    for tree in ("data/demo_tools", "data/migration_backups", "data/backups"):
        assert declared.get(tree) == sm.EXCLUDED, tree


def test_session_files_are_excluded_wherever_they_sit(tmp_path):
    """Production keeps six .session files inside data/accounts, which is a
    migrated tree. The exclusion list was only ever consulted when printing the
    plan, so the copy would have carried live Telegram secrets across."""
    account = tmp_path / "accounts" / "acct1"
    account.mkdir(parents=True)
    (account / "acct1.session").write_bytes(b"live secret")
    (account / "acct1.session-journal").write_bytes(b"live secret")
    (account / "state.json").write_bytes(b"{}")

    assert sm._is_excluded_file(account / "acct1.session")
    assert sm._is_excluded_file(account / "acct1.session-journal")
    assert not sm._is_excluded_file(account / "state.json")


def test_env_files_are_excluded():
    assert sm._is_excluded_file(Path("/anywhere/data/accounts/x/.env"))
