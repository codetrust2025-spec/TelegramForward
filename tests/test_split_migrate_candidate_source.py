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
import json
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


def test_a_mirrored_store_declares_its_archive_only_records():
    """The exclusion is otherwise invisible: the file is copied, the table is
    migrated from PostgreSQL, both report success, and nothing says that some
    records in the file were carried as archive only. An operator reading the
    run cannot see the decision, and a change in the drift would go unnoticed."""
    assert hasattr(sm, "_write_quarantine_manifest")

    import inspect
    src = inspect.getsource(sm._write_quarantine_manifest)
    # the manifest has to carry the numbers a reviewer needs to re-check
    for field in ("records_in_file", "records_in_table", "archive_only_count",
                  "archive_only_ids", "treatment", "operator_action"):
        assert field in src, field


def test_the_quarantine_manifest_is_ledgered_so_a_rerun_does_not_duplicate():
    import inspect
    src = inspect.getsource(sm._write_quarantine_manifest)
    assert "_ledger_has" in src and "_ledger_put" in src


def test_the_broken_reference_check_reads_the_key_that_exists():
    """It read proof["path"] or proof["file"]. Real entries carry url, id,
    filename, mime_type, size, note, uploaded_at, original_name - neither key -
    so the check returned clean on every run since it was written, and
    reconcile() returns PASS partly on that emptiness."""
    import inspect
    src = inspect.getsource(sm._check_cross_references)
    assert '"url"' in src, "the key real proof entries actually carry"
    assert "candidates_proofs" in src, "the tree the evidence actually lives in"
    assert "candidates_resumes" in src
    assert "resumes" in src, "resumes are references too"


def test_a_mirrored_store_is_archived_off_the_application_read_path():
    """use_postgres() is a presence check on DATABASE_URL that fails open, and
    the candidate store falls back to DATA_DIR/candidates.json. Writing the
    superseded mirror to that path would let an unset variable promote 102
    stale records over 195 live ones."""
    import inspect
    src = inspect.getsource(sm.execute)
    assert "_archive" in src
    assert "_MIRRORED_TABLES" in src


def test_broken_reference_check_actually_fires_now(tmp_path):
    """Proof that the fix works rather than that the source string changed:
    build a data dir whose proof url points at nothing, and require the check
    to report it. Under the old key names this returned clean."""
    data = tmp_path / "data"
    (data / "candidates_proofs" / "cand1").mkdir(parents=True)
    (data / "candidates_proofs" / "cand1" / "present.jpg").write_bytes(b"x")
    (data / "candidates.json").write_text(json.dumps({"candidates": [
        {"id": "cand1", "proofs": [
            {"id": "p1", "url": "/candidates_proofs/cand1/present.jpg"},
            {"id": "p2", "url": "/candidates_proofs/cand1/vanished.jpg"},
        ]},
    ]}), encoding="utf-8")

    plan = sm.Plan()
    sm._check_cross_references(data, plan)

    assert len(plan.broken_refs) == 1, plan.broken_refs
    assert "vanished.jpg" in plan.broken_refs[0]
    assert "present.jpg" not in plan.broken_refs[0]


def test_broken_reference_check_covers_resumes_too(tmp_path):
    data = tmp_path / "data"
    (data / "candidates_resumes").mkdir(parents=True)
    (data / "candidates.json").write_text(json.dumps({"candidates": [
        {"id": "cand1", "resumes": [{"id": "r1", "url": "/x/cand1/cv.pdf"}]},
    ]}), encoding="utf-8")
    plan = sm.Plan()
    sm._check_cross_references(data, plan)
    assert any("cv.pdf" in r for r in plan.broken_refs), plan.broken_refs


def test_inherited_broken_references_are_reported_not_fatal(tmp_path):
    """Production carries 70 proof and resume entries whose file exists
    nowhere. The migration copies files wholesale, so it neither creates nor
    repairs them. Failing on them blocks a cutover on a pre-existing condition
    and pushes someone to silence the check again - which is how it came to be
    a no-op in the first place."""
    import inspect
    src = inspect.getsource(sm.reconcile)
    assert "inherited_broken_references" in src
    # the pass/fail condition must no longer hinge on them
    assert 'if (ok and not plan.duplicates)' in src or \
           'not plan.broken_refs' not in src.split('report["result"]')[1][:200]


def test_the_plan_does_not_count_files_the_copy_refuses(tmp_path):
    """Counting a session file in the plan and refusing to copy it in execute
    makes expected and migrated differ by exactly the number of secrets present,
    so reconcile fails on the safety feature working. Production keeps six
    .session files inside data/accounts, a migrated tree."""
    data = tmp_path / "data"
    acct = data / "accounts" / "a1"
    acct.mkdir(parents=True)
    (acct / "a1.session").write_bytes(b"secret")
    (acct / "a1.session-journal").write_bytes(b"secret")
    (acct / "state.json").write_bytes(b"{}")
    (data / "candidates.json").write_text('{"candidates": []}', encoding="utf-8")

    plan = sm.build_plan(data, None)
    tree = next(i for i in plan.items
                if i.kind == "file_tree" and i.name == "data/accounts")
    assert tree.count == 1, "only state.json should be planned"
    assert tree.units == 1


def test_the_quarantine_manifest_is_not_counted_as_a_migrated_record():
    """It describes the migration; it is not a record the migration moved.
    Counting it makes migrated exceed expected by one."""
    import inspect
    src = inspect.getsource(sm._write_quarantine_manifest)
    body = src.split("_ledger_put")[1]
    assert "written[owner] += 1" not in body, \
        "the manifest must not be counted as a migrated record"


def test_artefact_ledger_rows_do_not_count_as_migrated_units():
    """The manifest is ledgered so a re-run does not rewrite it, which puts a
    row in the same table the reconciliation counts. Resume checkpoints already
    had this problem and the same exclusion applies."""
    import inspect
    src = inspect.getsource(sm.reconcile)
    assert "_ARTEFACT_KIND_PREFIX" in src
    assert sm._ARTEFACT_KIND_PREFIX == "quarantine:"
    # the manifest's ledger kind must carry that prefix
    manifest = inspect.getsource(sm._write_quarantine_manifest)
    assert 'kind = f"quarantine:{store.filename}"' in manifest


def test_a_production_cutover_needs_its_own_flag_not_a_false_assertion():
    """The marker guard stops accidental production targets. Reaching production
    on purpose must not require asserting that production is disposable - if the
    only way to do an authorised cutover is to lie to the safety check, the
    safety check protects nothing."""
    import inspect
    src = inspect.getsource(sm.main)
    assert "--authorized-production-cutover" in src
    assert "mutually exclusive" in src.lower()
    # execute must accept either, and refuse with neither
    assert "args.confirm_non_production or args.authorized_production_cutover" in src


def test_the_marker_guard_still_fires_without_the_cutover_flag():
    import pytest
    with pytest.raises(sm.MigrationError):
        sm.assert_not_production("--marketing-dsn",
                                 "postgresql://u:p@h/marketing_prod")
    # and an ordinary disposable target passes
    sm.assert_not_production("--marketing-dsn", "postgresql://u:p@h/mkt_dest")


def test_suffixed_session_backups_are_excluded():
    """Production keeps timestamped backups beside the live session files.
    session_accountN.session.pre_migrate_<ts> is every bit as usable as the
    original, and *.session walked straight past it - one reached the Marketing
    volume during the cutover before this was caught."""
    from pathlib import Path as P
    for name in ("accounts/a3/corrupt_session_backup/"
                 "session_account3.session.pre_migrate_20260613_095312",
                 "accounts/a1/a1.session",
                 "accounts/a1/a1.session-journal",
                 "accounts/a1/inbox_snapshot.session",
                 "accounts/a1/a1.session.bak"):
        assert sm._is_excluded_file(P("/data") / name), name


def test_ordinary_account_files_are_still_copied():
    from pathlib import Path as P
    for name in ("accounts/a1/state.json", "accounts/a1/posting_mode.json",
                 "accounts/a1/join_state.json"):
        assert not sm._is_excluded_file(P("/data") / name), name


def test_string_sessions_are_excluded_too():
    """A Telethon StringSession has the same authority over the account as a
    .session file and none of the naming. Nine of these reached the Marketing
    volume during the cutover because every rule keyed on the ".session"
    substring."""
    from pathlib import Path as P
    for name in ("accounts/a1/inbox_string_session.txt",
                 "accounts/a2/string_session.dat",
                 "accounts/a3/my_string_session_backup"):
        assert sm._is_excluded_file(P("/data") / name), name


def test_data_room_content_is_not_mistaken_for_a_system_secret():
    """data_room/credentials.json is the Data Room's own vault - admin,
    handlers, service accounts - and is Operations business data that must
    migrate. Excluding it on the name would silently drop Data Room content."""
    from pathlib import Path as P
    assert not sm._is_excluded_file(P("/data/data_room/credentials.json"))


def test_a_second_pass_can_re_scan_finished_tables():
    """The ledger marks a finished table so a re-run skips it. In a phased
    cutover the second pass exists precisely to collect rows written since the
    first, and skipping leaves them behind - six rows in each of the two
    highest-churn tables, during the real cutover."""
    import inspect
    src = inspect.getsource(sm.execute)
    assert 'resync_tables' in src
    assert '_ledger_has(cur, "pg_table", table) and not resync_tables' in src
    assert "resync_tables" in inspect.signature(sm.execute).parameters
    main = inspect.getsource(sm.main)
    assert "--resync-tables" in main
    assert "resync_tables=args.resync_tables" in main
