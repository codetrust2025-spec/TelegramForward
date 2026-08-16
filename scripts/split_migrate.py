#!/usr/bin/env python3
"""Split monolith data into the Marketing and Operations stores.

Reads a monolith snapshot (PostgreSQL + JSON-backed stores + file trees),
classifies every source by owning project, writes each owned record into the
correct destination store, and produces a reconciliation report.

Modes
  --dry-run     (default) read-only. Reports source counts, per-destination
                counts, ignored/legacy sources, ambiguous sources and broken
                references. Writes nothing anywhere.
  --execute     apply the plan. Refuses to run without --confirm-non-production.
  --reconcile   compare source against both destinations after an execute.

Safety
  Production is never a valid target. Any DSN or path carrying a production
  marker aborts the run before a connection is opened. Telegram session files
  and credential material are never copied: sessions are live secrets, and a
  copy is a second place for them to leak from.

  Execution is idempotent. Every migrated record is recorded in a ledger keyed
  by (source_kind, source_id), so a re-run after a mid-way failure resumes
  instead of duplicating. A failed run leaves the ledger and the partial
  destination intact as evidence rather than rolling back silently.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

MARKETING = "marketing"
OPERATIONS = "operations"
AMBIGUOUS = "ambiguous"
EXCLUDED = "excluded"

# Any of these appearing in a target DSN or data directory aborts the run.
PRODUCTION_MARKERS = (
    "teleautomation.online",
    "prod",
    "production",
)

# Rows read and inserted per round trip. Large enough that a production table
# is not one round trip per row, small enough that a batch stays in memory and
# an interruption loses little work.
COPY_BATCH_ROWS = 5000

# How often progress is reported for a long table.
PROGRESS_EVERY_ROWS = 50_000

LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS split_migration_ledger (
    source_kind TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    target      TEXT NOT NULL,
    checksum    TEXT NOT NULL,
    migrated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_kind, source_id)
);
"""


class MigrationError(RuntimeError):
    """Fatal, reported with context rather than a traceback."""


# ---------------------------------------------------------------------------
# Ownership registry
# ---------------------------------------------------------------------------
# The single auditable statement of who owns what. Adding a source without
# adding it here makes it surface as UNCLASSIFIED rather than being dropped.

@dataclass(frozen=True)
class JsonStore:
    filename: str
    owner: str
    container: str | None      # key holding the records, None => whole document
    id_field: str | None       # record identity, None => positional
    target_table: str | None   # None => copied as a JSON file, not a table
    note: str = ""


JSON_STORES: tuple[JsonStore, ...] = (
    # Legacy mirror, deliberately NOT the source for candidates_store.
    #
    # Measured on production: this file holds 102 candidates and the
    # candidates_store table holds 195, with only 66 in common. Of the 26
    # candidates that live recruitment mail actually references, all 26 are in
    # PostgreSQL and 7 are in this file. PostgreSQL is what the product writes
    # to; this file has fallen behind.
    #
    # Building the destination table from it would have dropped 129 live
    # candidates and resurrected 36 the product no longer has, with row counts
    # that look plausible either way. Copied verbatim so nothing is destroyed,
    # but the table is built from PostgreSQL.
    JsonStore("candidates.json", OPERATIONS, "candidates", "id", None,
              "legacy mirror; candidates_store is migrated from PostgreSQL"),
    JsonStore("payment_receiver_accounts.json", OPERATIONS, "accounts", "id", None,
              "receiver registry; typed columns are rebuilt by Operations on import"),
    JsonStore("referrers.json", OPERATIONS, "referrers", "id", None),
    JsonStore("payment_recalculation_audit.json", OPERATIONS, None, None, None,
              "audit evidence; copied verbatim"),
    JsonStore("groups_list.json", MARKETING, None, None, None,
              "Telegram group master list"),
    JsonStore("accounts_config.json", MARKETING, None, None, None,
              "messaging account configuration"),
    # Ownership resolved 2026-08-15. Marketing owns web push outright: it holds
    # the whole implementation (core/web_push_api.py, the VAPID key endpoint and
    # both subscribe routes), while Operations has no push implementation and no
    # subscription UI. Operations already reaches users through Marketing's
    # POST /internal/v1/notifications contract (services/messaging_client.py),
    # so subscriptions are not duplicated and no split of this file is needed.
    JsonStore("web_push_subscriptions.json", MARKETING, "subscriptions", None, None,
              "browser push endpoints; Operations notifies via the cross-project "
              "notification contract rather than holding its own subscriptions"),
    JsonStore("postgres_backup_before_sync.json", EXCLUDED, None, None, None,
              "historical backup artefact, not live state"),
    JsonStore("vapid_keys.json", EXCLUDED, None, None, None,
              "push signing keys; regenerate per environment, never copy"),
)

# PostgreSQL tables. Everything in the monolith schema is Operations-owned;
# Marketing's only table is created by its own baseline, not migrated.
OPERATIONS_TABLES: tuple[str, ...] = (
    # candidates_store is sourced from PostgreSQL, NOT from candidates.json.
    # The two have diverged in production - see the JsonStore entry below - and
    # PostgreSQL is the live one.
    "candidates_store",
    "candidate_identity_links", "candidate_job_status", "candidate_mailboxes",
    "candidate_status_history", "ai_recruitment_events",
    "gmail_message_ingestion_queue", "gmail_pubsub_deliveries",
    "interview_auto_booking_audit", "interview_mail_analyses", "mail_ai_analyses",
    "mail_audit_ai_log", "mail_audit_ai_queue", "mail_audit_ai_results",
    "mail_monitoring_notifications", "mail_outcome_audit_approvals",
    "mail_outcome_audit_candidates", "mail_outcome_audit_cleanup_log",
    "mail_outcome_audit_finding_history", "mail_outcome_audit_findings",
    "mail_outcome_audit_gaps", "mail_outcome_audit_runs", "mail_realtime_events",
    "mail_review_evaluations", "mailbox_attachment_cache", "mailbox_attachments",
    "mailbox_messages", "mailbox_sync_jobs", "offer_verification_cases",
    "payment_entitlements", "payment_evidence", "payment_ledger_entries",
    "payment_receiver_accounts", "payment_verifications", "recruitment_audit_log",
    "recruitment_review_flags",
)

MARKETING_TABLES: tuple[str, ...] = ("ai_smart_reply_store",)

# Relative file trees. Sessions are deliberately absent -> never copied.
FILE_TREES: tuple[tuple[str, str, str], ...] = (
    ("data/payment_evidence", OPERATIONS, "payment proof images and metadata"),
    ("data/data_room", OPERATIONS, "Data Room documents"),
    ("data/accounts", MARKETING, "per-account messaging state"),
    # Found by the rehearsal. payment_evidence holds 6 files; the evidence the
    # product actually writes lives in these, 275 files of it. Migrating
    # payment_evidence alone and calling it done would have left every
    # candidate proof and resume behind.
    ("data/candidates_proofs", OPERATIONS,
     "payment proof images, one directory per candidate"),
    ("data/candidates_resumes", OPERATIONS,
     "candidate resumes, one directory per candidate"),
    ("data/handler_expense_proofs", OPERATIONS, "handler expense evidence"),
    ("data/pending_slot_payments", OPERATIONS, "slot payment screenshots"),
    ("data/crm", MARKETING, "CRM stores: leads, calls, block list, voice calls"),
    # Present and deliberately not migrated. Named rather than ignored, so they
    # appear in the plan as a decision rather than as an oversight.
    ("data/demo_tools", EXCLUDED,
     "third-party installer binaries, 474 MB, not business data"),
    ("data/migration_backups", EXCLUDED, "historical backup artefacts"),
    ("data/backups", EXCLUDED, "historical backup artefacts"),
)

EXCLUDED_GLOBS: tuple[tuple[str, str], ...] = (
    ("*.session", "live Telegram session secret"),
    ("*.session-journal", "live Telegram session secret"),
    (".env", "credential material"),
)


# ---------------------------------------------------------------------------
# Plan model
# ---------------------------------------------------------------------------

@dataclass
class Item:
    kind: str           # json_store | pg_table | file_tree
    name: str
    owner: str
    count: int = 0      # source records, for human reporting
    units: int = 0      # ledger entries this item produces, for reconciliation
    checksum: str = ""
    note: str = ""
    problems: list[str] = field(default_factory=list)


@dataclass
class Plan:
    items: list[Item] = field(default_factory=list)
    broken_refs: list[str] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)
    divergences: list[str] = field(default_factory=list)

    def owned(self, owner: str) -> list[Item]:
        return [i for i in self.items if i.owner == owner]

    def total(self, owner: str) -> int:
        return sum(i.count for i in self.owned(owner))

    def total_units(self, owner: str) -> int:
        """Ledger entries expected for this owner.

        Distinct from total(): a store copied verbatim as one file holds many
        records but produces a single ledger entry, so reconciling record
        counts against ledger rows would compare different units.
        """
        return sum(i.units for i in self.owned(owner))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _records(doc: Any, store: JsonStore) -> list[Any]:
    body = doc if store.container is None else doc.get(store.container, [])
    if isinstance(body, dict):
        return list(body.values())
    if isinstance(body, list):
        return body
    return [body]


def _record_id(rec: Any, store: JsonStore, index: int) -> str:
    if isinstance(rec, dict) and store.id_field and rec.get(store.id_field) is not None:
        return str(rec[store.id_field])
    return f"{store.filename}#{index}"


# ---------------------------------------------------------------------------
# Source inspection
# ---------------------------------------------------------------------------

def build_plan(data_dir: Path, source_dsn: str | None) -> Plan:
    plan = Plan()

    for store in JSON_STORES:
        path = data_dir / store.filename
        item = Item("json_store", store.filename, store.owner, note=store.note)
        if not path.exists():
            item.note = (item.note + "; " if item.note else "") + "absent from snapshot"
            plan.items.append(item)
            continue
        raw = path.read_bytes()
        item.checksum = _sha256_bytes(raw)
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            item.problems.append(f"unreadable JSON: {exc}")
            plan.items.append(item)
            continue
        if store.owner in (EXCLUDED, AMBIGUOUS):
            # Still counted so the report shows what is being withheld.
            item.count = len(_records(doc, store))
            plan.items.append(item)
            continue
        recs = _records(doc, store)
        item.count = len(recs)
        # A table-backed store migrates row by row; a verbatim store is one file.
        item.units = len(recs) if store.target_table else 1
        seen: set[str] = set()
        for idx, rec in enumerate(recs):
            rid = _record_id(rec, store, idx)
            if rid in seen:
                plan.duplicates.append(f"{store.filename}:{rid}")
            seen.add(rid)
        plan.items.append(item)

    _check_cross_references(data_dir, plan)
    _check_store_divergence(data_dir, source_dsn, plan)

    for rel, owner, note in FILE_TREES:
        root = data_dir.parent / rel if not (data_dir / Path(rel).name).exists() else data_dir / Path(rel).name
        item = Item("file_tree", rel, owner, note=note)
        if root.exists() and root.is_dir():
            files = [p for p in root.rglob("*") if p.is_file()]
            item.count = len(files)
            item.units = len(files)
            digest = hashlib.sha256()
            for p in sorted(files):
                digest.update(p.relative_to(root).as_posix().encode())
                digest.update(_sha256_file(p).encode())
            item.checksum = digest.hexdigest()
        else:
            item.note += "; absent from snapshot"
        plan.items.append(item)

    for pattern, why in EXCLUDED_GLOBS:
        # Recursive: the session files are inside data/accounts/<name>/, not at
        # the top level, so a non-recursive glob reported zero of them.
        hits = list(data_dir.parent.rglob(pattern)) + list(data_dir.rglob(pattern))
        if hits:
            plan.items.append(Item("excluded", pattern, EXCLUDED, len(hits), note=why))

    if source_dsn:
        _inspect_tables(source_dsn, plan)
    else:
        for table in OPERATIONS_TABLES:
            plan.items.append(Item("pg_table", table, OPERATIONS, note="not counted: no --source-dsn"))
        for table in MARKETING_TABLES:
            plan.items.append(Item("pg_table", table, MARKETING, note="not counted: no --source-dsn"))

    return plan


def _check_cross_references(data_dir: Path, plan: Plan) -> None:
    """Candidate payment proofs must point at files that exist."""
    path = data_dir / "candidates.json"
    if not path.exists():
        return
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return
    evidence_root = data_dir / "payment_evidence"
    for rec in doc.get("candidates", []) or []:
        if not isinstance(rec, dict):
            continue
        cid = rec.get("id", "?")
        for proof in rec.get("proofs", []) or []:
            ref = proof.get("path") or proof.get("file") if isinstance(proof, dict) else None
            if ref and not (evidence_root / str(ref).lstrip("/\\")).exists():
                plan.broken_refs.append(f"candidate {cid} -> missing proof {ref}")


def _check_store_divergence(data_dir: Path, dsn: str | None, plan: Plan) -> None:
    """Compare a JSON store against the table that holds the same records.

    The monolith keeps some stores twice, as a file and as a table, and they
    drift. Whichever one a migration reads becomes the truth, and the row count
    looks reasonable either way, so the drift is invisible unless it is measured.
    This measures it and reports it instead of picking a winner quietly.
    """
    if not dsn:
        return
    for store in JSON_STORES:
        mirror = _MIRRORED_TABLES.get(store.filename)
        if not mirror:
            continue
        path = data_dir / store.filename
        if not path.exists():
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        file_ids = {str(_record_id(rec, store, i))
                    for i, rec in enumerate(_records(doc, store))
                    if isinstance(rec, dict)}
        with _connect(dsn) as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass(%s)", (mirror,))
            if cur.fetchone()[0] is None:
                continue
            cur.execute(f'SELECT id FROM "{mirror}"')
            table_ids = {str(r[0]) for r in cur.fetchall()}
        only_file = file_ids - table_ids
        only_table = table_ids - file_ids
        if not (only_file or only_table):
            continue
        plan.divergences.append(
            f"{store.filename} and {mirror} disagree: "
            f"{len(file_ids)} in the file, {len(table_ids)} in the table, "
            f"{len(file_ids & table_ids)} in both, "
            f"{len(only_table)} only in the table, {len(only_file)} only in the file. "
            f"{mirror} is migrated from PostgreSQL; the {len(only_file)} "
            f"file-only record(s) are NOT migrated and need an owner decision")


# JSON stores the monolith also keeps as a table. Kept explicit rather than
# guessed, because being wrong here means migrating the stale copy.
_MIRRORED_TABLES = {"candidates.json": "candidates_store"}


def _is_excluded_file(path: Path) -> bool:
    """Session and credential files are never copied, wherever they sit."""
    return any(path.match(pattern) for pattern, _ in EXCLUDED_GLOBS)


def _connect(dsn: str):
    try:
        import psycopg2
    except ImportError as exc:  # pragma: no cover - environment guard
        raise MigrationError(
            "psycopg2 is required for PostgreSQL work. Install psycopg2-binary."
        ) from exc
    return psycopg2.connect(dsn)


def _inspect_tables(dsn: str, plan: Plan) -> None:
    with _connect(dsn) as conn, conn.cursor() as cur:
        for owner, tables in ((OPERATIONS, OPERATIONS_TABLES), (MARKETING, MARKETING_TABLES)):
            for table in tables:
                item = Item("pg_table", table, owner)
                cur.execute("SELECT to_regclass(%s)", (table,))
                if cur.fetchone()[0] is None:
                    item.note = "absent from source schema"
                else:
                    cur.execute(f'SELECT count(*) FROM "{table}"')
                    item.count = int(cur.fetchone()[0])
                    # One ledger entry per table; row-level idempotency comes
                    # from ON CONFLICT DO NOTHING on the primary key.
                    item.units = 1 if item.count else 0
                plan.items.append(item)


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

def assert_not_production(label: str, value: str | None) -> None:
    if not value:
        return
    low = value.lower()
    for marker in PRODUCTION_MARKERS:
        if marker in low:
            raise MigrationError(
                f"refusing to run: {label} contains the production marker "
                f"{marker!r}. This tool must never target production."
            )


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _ledger_has(cur, kind: str, sid: str) -> bool:
    cur.execute(
        "SELECT 1 FROM split_migration_ledger WHERE source_kind=%s AND source_id=%s",
        (kind, sid),
    )
    return cur.fetchone() is not None


def _ledger_put(cur, kind: str, sid: str, target: str, checksum: str) -> None:
    cur.execute(
        "INSERT INTO split_migration_ledger (source_kind, source_id, target, checksum) "
        "VALUES (%s,%s,%s,%s) ON CONFLICT (source_kind, source_id) DO NOTHING",
        (kind, sid, target, checksum),
    )


# Resume checkpoints live in the ledger under their own source_kind, so a table
# interrupted part-way records the last key it committed. The completed-table
# marker stays "pg_table"; a checkpoint is cleared once its table finishes.
_CHECKPOINT_KIND = "pg_checkpoint"


def _checkpoint_get(cur, table: str) -> str | None:
    cur.execute(
        "SELECT checksum FROM split_migration_ledger WHERE source_kind=%s AND source_id=%s",
        (_CHECKPOINT_KIND, table),
    )
    row = cur.fetchone()
    return row[0] if row and row[0] else None


def _checkpoint_put(cur, table: str, target: str, last_key: str) -> None:
    cur.execute(
        "INSERT INTO split_migration_ledger (source_kind, source_id, target, checksum) "
        "VALUES (%s,%s,%s,%s) "
        "ON CONFLICT (source_kind, source_id) DO UPDATE SET checksum = EXCLUDED.checksum",
        (_CHECKPOINT_KIND, table, target, last_key),
    )


def _checkpoint_clear(cur, table: str) -> None:
    cur.execute(
        "DELETE FROM split_migration_ledger WHERE source_kind=%s AND source_id=%s",
        (_CHECKPOINT_KIND, table),
    )


def _progress_reporter(dst_conn, table: str, owner: str):
    """Report progress on long tables without spamming short ones."""
    state = {"next": PROGRESS_EVERY_ROWS}

    def report(_table: str, done: int) -> None:
        if done >= state["next"]:
            print(f"  {table}: {done:,} rows copied…", flush=True)
            state["next"] += PROGRESS_EVERY_ROWS

    return report


def _fk_order(conn, tables: Iterable[str]) -> list[str]:
    """Order tables so a foreign key is always inserted after its parent.

    The declared registry order is alphabetical, which is not a valid insertion
    order: interview_mail_analyses references mailbox_messages, so copying in
    registry order fails the foreign key. Ordering is derived from the live
    schema rather than maintained by hand, so a new constraint cannot silently
    reintroduce the problem.
    """
    wanted = list(tables)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tc.table_name, ccu.table_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON tc.constraint_name = ccu.constraint_name "
            "WHERE tc.constraint_type='FOREIGN KEY' AND tc.table_schema='public'"
        )
        deps: dict[str, set[str]] = {t: set() for t in wanted}
        for child, parent in cur.fetchall():
            if child in deps and parent in deps and child != parent:
                deps[child].add(parent)

    ordered: list[str] = []
    done: set[str] = set()

    def visit(t: str, stack: tuple[str, ...] = ()) -> None:
        if t in done or t in stack:      # cycles fall back to registry order
            return
        for parent in sorted(deps.get(t, ())):
            visit(parent, stack + (t,))
        done.add(t)
        ordered.append(t)

    for t in wanted:
        visit(t)
    return ordered


def _single_column_pk(conn, table: str) -> str | None:
    """The primary key column, when it is a single column.

    Keyset resumption needs one orderable column. Composite keys fall back to a
    full re-stream, which stays correct because insertion is ON CONFLICT DO
    NOTHING; it is only slower.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT a.attname FROM pg_index i "
            "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey) "
            "WHERE i.indrelid = %s::regclass AND i.indisprimary",
            (table,),
        )
        cols = [r[0] for r in cur.fetchall()]
    return cols[0] if len(cols) == 1 else None


def _copy_table(src_conn, dst_conn, table: str, *, batch: int = COPY_BATCH_ROWS,
                resume_after: str | None = None, on_progress=None,
                on_checkpoint=None) -> tuple[int, str, str | None]:
    """Copy one table across on the intersection of both column sets.

    Returns (rows_copied, checksum, last_key).

    Rows are streamed and inserted in batches rather than materialised: a
    production-sized table must not be pulled into memory by fetchall(), and one
    round trip per row does not finish in a maintenance window. Where the table
    has a single-column primary key the read is keyset-paginated, so an
    interrupted run resumes from the last committed key instead of re-reading
    from the start. Insertion is ON CONFLICT DO NOTHING throughout, so a resumed
    or repeated run can never duplicate.
    """
    from psycopg2.extras import execute_values

    with src_conn.cursor() as s, dst_conn.cursor() as d:
        s.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,))
        src_cols = [r[0] for r in s.fetchall()]
        d.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position", (table,))
        dst_cols = {r[0] for r in d.fetchall()}
    cols = [c for c in src_cols if c in dst_cols]
    if not cols:
        raise MigrationError(f"table {table}: source and destination share no columns")

    quoted = ", ".join(f'"{c}"' for c in cols)
    insert = f'INSERT INTO "{table}" ({quoted}) VALUES %s ON CONFLICT DO NOTHING'
    digest = hashlib.sha256()
    total = 0
    pk = _single_column_pk(src_conn, table)
    last_key = resume_after

    def flush(rows):
        nonlocal total
        if not rows:
            return
        with dst_conn.cursor() as d:
            execute_values(d, insert, rows, page_size=len(rows))
        total += len(rows)
        if on_progress:
            on_progress(table, total)

    if pk:
        key_index = cols.index(pk) if pk in cols else None
        if key_index is None:
            cols = cols + [pk]
            quoted = ", ".join(f'"{c}"' for c in cols)
            insert = f'INSERT INTO "{table}" ({quoted}) VALUES %s ON CONFLICT DO NOTHING'
            key_index = len(cols) - 1
        while True:
            with src_conn.cursor() as s:
                if last_key is None:
                    s.execute(f'SELECT {quoted} FROM "{table}" ORDER BY "{pk}" LIMIT %s', (batch,))
                else:
                    s.execute(
                        f'SELECT {quoted} FROM "{table}" WHERE "{pk}" > %s ORDER BY "{pk}" LIMIT %s',
                        (last_key, batch))
                rows = s.fetchall()
            if not rows:
                break
            for row in rows:
                digest.update(repr(row).encode())
            flush(rows)
            last_key = rows[-1][key_index]
            # The checkpoint is written inside the same transaction as its batch
            # and committed with it, so a recorded key can never be ahead of
            # committed rows. An interruption loses at most one batch.
            if on_checkpoint:
                on_checkpoint(str(last_key))
            dst_conn.commit()
            if len(rows) < batch:
                break
    else:
        # Server-side cursor: the result set stays on the server and arrives in
        # itersize chunks instead of all at once.
        name = f"split_migrate_{table}"
        with src_conn.cursor(name=name) as s:
            s.itersize = batch
            s.execute(f'SELECT {quoted} FROM "{table}"')
            buffer: list = []
            for row in s:
                digest.update(repr(row).encode())
                buffer.append(row)
                if len(buffer) >= batch:
                    flush(buffer)
                    dst_conn.commit()
                    buffer = []
            flush(buffer)
            dst_conn.commit()

    return total, digest.hexdigest(), (str(last_key) if last_key is not None else None)


def execute(data_dir: Path, targets: dict[str, dict[str, str]], plan: Plan,
            source_dsn: str | None = None) -> dict[str, int]:
    """Apply the plan. Idempotent: re-running migrates only what the ledger lacks."""
    written = {MARKETING: 0, OPERATIONS: 0}

    if source_dsn:
        src = _connect(source_dsn)
        # Keep json/jsonb as raw text on the way out. Decoded to dict/list,
        # psycopg2 cannot adapt the value back on insert ("can't adapt type
        # 'dict'"), and text round-trips into jsonb losslessly.
        import psycopg2.extras
        psycopg2.extras.register_default_json(conn_or_curs=src, loads=lambda s: s)
        psycopg2.extras.register_default_jsonb(conn_or_curs=src, loads=lambda s: s)
        try:
            for owner, cfg in targets.items():
                declared = OPERATIONS_TABLES if owner == OPERATIONS else MARKETING_TABLES
                tables = _fk_order(src, declared)
                with _connect(cfg["dsn"]) as dst:
                    with dst.cursor() as cur:
                        cur.execute(LEDGER_DDL)
                    dst.commit()
                    for table in tables:
                        with src.cursor() as s:
                            s.execute("SELECT to_regclass(%s)", (table,))
                            if s.fetchone()[0] is None:
                                continue
                        with dst.cursor() as cur:
                            if _ledger_has(cur, "pg_table", table):
                                continue
                            # A checkpoint from an interrupted run lets this
                            # table resume after its last committed key instead
                            # of re-reading from the start.
                            resume_after = _checkpoint_get(cur, table)
                        if resume_after:
                            print(f"  {table}: resuming after key {resume_after}")
                        try:
                            def _checkpoint(key: str, _t=table, _o=owner, _d=dst) -> None:
                                with _d.cursor() as c:
                                    _checkpoint_put(c, _t, _o, key)

                            n, checksum, last_key = _copy_table(
                                src, dst, table,
                                resume_after=resume_after,
                                on_progress=_progress_reporter(dst, table, owner),
                                on_checkpoint=_checkpoint,
                            )
                        except Exception as exc:
                            dst.rollback()
                            raise MigrationError(
                                f"table {table} failed to migrate: {exc}. The ledger, the "
                                f"resume checkpoint and already-migrated tables are left "
                                f"intact; re-run to resume."
                            ) from exc
                        if n:
                            with dst.cursor() as cur:
                                _ledger_put(cur, "pg_table", table, owner, checksum)
                                _checkpoint_clear(cur, table)
                            written[owner] += 1
                            print(f"  {table}: {n} rows")
                        dst.commit()
        finally:
            src.close()

    for owner, cfg in targets.items():
        dsn, out_dir = cfg["dsn"], Path(cfg["data_dir"])
        out_dir.mkdir(parents=True, exist_ok=True)
        with _connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(LEDGER_DDL)
            conn.commit()

            for store in JSON_STORES:
                if store.owner != owner:
                    continue
                path = data_dir / store.filename
                if not path.exists():
                    continue
                raw = path.read_bytes()
                doc = json.loads(raw.decode("utf-8"))

                if store.target_table:
                    recs = _records(doc, store)
                    with conn.cursor() as cur:
                        for idx, rec in enumerate(recs):
                            rid = _record_id(rec, store, idx)
                            kind = f"json:{store.filename}"
                            if _ledger_has(cur, kind, rid):
                                continue
                            cur.execute(
                                f'INSERT INTO "{store.target_table}" (id, payload) '
                                "VALUES (%s, %s) ON CONFLICT (id) DO NOTHING",
                                (rid, json.dumps(rec)),
                            )
                            _ledger_put(cur, kind, rid, owner,
                                        _sha256_bytes(json.dumps(rec, sort_keys=True).encode()))
                            written[owner] += 1
                    conn.commit()
                else:
                    # Copied verbatim as a file the destination service reads.
                    dest = out_dir / store.filename
                    kind = f"file:{store.filename}"
                    checksum = _sha256_bytes(raw)
                    with conn.cursor() as cur:
                        if not _ledger_has(cur, kind, store.filename):
                            dest.write_bytes(raw)
                            _ledger_put(cur, kind, store.filename, owner, checksum)
                            written[owner] += 1
                    conn.commit()

            for rel, tree_owner, _note in FILE_TREES:
                if tree_owner != owner:
                    continue
                root = data_dir / Path(rel).name
                if not root.is_dir():
                    continue
                for src in sorted(p for p in root.rglob("*") if p.is_file()):
                    # Enforced here, not only reported in the plan. Production
                    # keeps six .session files inside data/accounts, which is a
                    # migrated tree, so without this the run copies live
                    # Telegram session secrets into the destination - the exact
                    # thing this module's docstring promises never happens.
                    if _is_excluded_file(src):
                        continue
                    relpath = src.relative_to(root).as_posix()
                    kind = f"tree:{rel}"
                    with conn.cursor() as cur:
                        if _ledger_has(cur, kind, relpath):
                            continue
                        dest = out_dir / Path(rel).name / relpath
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(src.read_bytes())
                        _ledger_put(cur, kind, relpath, owner, _sha256_file(src))
                        written[owner] += 1
                    conn.commit()

    return written


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

def reconcile(data_dir: Path, targets: dict[str, dict[str, str]], plan: Plan) -> dict[str, Any]:
    report: dict[str, Any] = {"generated_at": datetime.now(timezone.utc).isoformat(), "checks": []}
    ok = True

    for owner, cfg in targets.items():
        expected = plan.total_units(owner)
        with _connect(cfg["dsn"]) as conn, conn.cursor() as cur:
            cur.execute(LEDGER_DDL)
            # Resume checkpoints share the ledger table but are bookkeeping, not
            # migrated units, so they must not count toward the reconciliation.
            cur.execute(
                "SELECT count(*) FROM split_migration_ledger "
                "WHERE target=%s AND source_kind <> %s", (owner, _CHECKPOINT_KIND))
            migrated = int(cur.fetchone()[0])
            cur.execute(
                "SELECT count(*) FROM (SELECT source_kind, source_id FROM split_migration_ledger "
                "WHERE target=%s AND source_kind <> %s GROUP BY 1,2 HAVING count(*) > 1) d",
                (owner, _CHECKPOINT_KIND))
            dupes = int(cur.fetchone()[0])

        passed = migrated == expected and dupes == 0
        ok = ok and passed
        report["checks"].append({
            "target": owner,
            "expected_records": expected,
            "migrated_records": migrated,
            "duplicate_ledger_keys": dupes,
            "result": "PASS" if passed else "FAIL",
        })

    # Ownership isolation: nothing owned by one side may exist in the other.
    for owner, cfg in targets.items():
        foreign = OPERATIONS_TABLES if owner == MARKETING else MARKETING_TABLES
        leaked = []
        with _connect(cfg["dsn"]) as conn, conn.cursor() as cur:
            for table in foreign:
                cur.execute("SELECT to_regclass(%s)", (table,))
                if cur.fetchone()[0] is not None:
                    cur.execute(f'SELECT count(*) FROM "{table}"')
                    if int(cur.fetchone()[0]) > 0:
                        leaked.append(table)
        ok = ok and not leaked
        report["checks"].append({
            "target": owner,
            "check": "ownership_isolation",
            "foreign_tables_with_rows": leaked,
            "result": "PASS" if not leaked else "FAIL",
        })

    report["broken_references"] = plan.broken_refs
    report["store_divergences"] = plan.divergences
    report["duplicate_source_ids"] = plan.duplicates
    report["result"] = "PASS" if (ok and not plan.broken_refs and not plan.duplicates) else "FAIL"
    return report


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_plan(plan: Plan) -> None:
    print("\n=== SOURCE INVENTORY ===")
    for owner, label in ((MARKETING, "MARKETING"), (OPERATIONS, "OPERATIONS"),
                         (AMBIGUOUS, "AMBIGUOUS - needs a decision"),
                         (EXCLUDED, "EXCLUDED - never migrated")):
        items = plan.owned(owner)
        if not items:
            continue
        print(f"\n-- {label} --")
        for i in sorted(items, key=lambda x: (x.kind, x.name)):
            note = f"  ({i.note})" if i.note else ""
            flag = "  !! " + "; ".join(i.problems) if i.problems else ""
            print(f"  {i.kind:<10} {i.name:<42} {i.count:>7}{note}{flag}")

    unclassified = [i for i in plan.items
                    if i.owner not in (MARKETING, OPERATIONS, AMBIGUOUS, EXCLUDED)]
    if unclassified:
        print("\n-- UNCLASSIFIED --")
        for i in unclassified:
            print(f"  {i.kind:<10} {i.name}")

    print("\n=== DESTINATION TOTALS ===")
    print(f"  Marketing records:  {plan.total(MARKETING):>6}   (ledger units {plan.total_units(MARKETING)})")
    print(f"  Operations records: {plan.total(OPERATIONS):>6}   (ledger units {plan.total_units(OPERATIONS)})")
    print(f"  Ambiguous (held):   {plan.total(AMBIGUOUS):>6}")
    print(f"  Excluded (held):    {plan.total(EXCLUDED):>6}")

    if plan.broken_refs:
        print(f"\n=== BROKEN REFERENCES ({len(plan.broken_refs)}) ===")
        for r in plan.broken_refs[:20]:
            print(f"  {r}")
    if plan.duplicates:
        print(f"\n=== DUPLICATE SOURCE IDS ({len(plan.duplicates)}) ===")
        for d in plan.duplicates[:20]:
            print(f"  {d}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--reconcile", action="store_true")
    ap.add_argument("--data-dir", required=True, type=Path,
                    help="monolith snapshot data/ directory")
    ap.add_argument("--source-dsn", help="monolith PostgreSQL DSN (read-only)")
    ap.add_argument("--marketing-dsn")
    ap.add_argument("--marketing-data-dir")
    ap.add_argument("--operations-dsn")
    ap.add_argument("--operations-data-dir")
    ap.add_argument("--report", type=Path, help="write the JSON report here")
    ap.add_argument("--confirm-non-production", action="store_true",
                    help="required for --execute; asserts targets are disposable")
    args = ap.parse_args(argv)

    try:
        for label, value in (("--source-dsn", args.source_dsn),
                             ("--marketing-dsn", args.marketing_dsn),
                             ("--operations-dsn", args.operations_dsn),
                             ("--marketing-data-dir", args.marketing_data_dir),
                             ("--operations-data-dir", args.operations_data_dir)):
            assert_not_production(label, value)

        if not args.data_dir.is_dir():
            raise MigrationError(f"--data-dir does not exist: {args.data_dir}")

        plan = build_plan(args.data_dir, args.source_dsn)
        print_plan(plan)

        if args.execute or args.reconcile:
            missing = [n for n, v in (("--marketing-dsn", args.marketing_dsn),
                                      ("--marketing-data-dir", args.marketing_data_dir),
                                      ("--operations-dsn", args.operations_dsn),
                                      ("--operations-data-dir", args.operations_data_dir))
                       if not v]
            if missing:
                raise MigrationError("missing required arguments: " + ", ".join(missing))
            targets = {
                MARKETING: {"dsn": args.marketing_dsn, "data_dir": args.marketing_data_dir},
                OPERATIONS: {"dsn": args.operations_dsn, "data_dir": args.operations_data_dir},
            }

        if args.execute:
            if not args.confirm_non_production:
                raise MigrationError(
                    "--execute requires --confirm-non-production. Refusing to write "
                    "without an explicit assertion that the targets are disposable."
                )
            written = execute(args.data_dir, targets, plan, args.source_dsn)
            print("\n=== EXECUTION ===")
            for owner, n in written.items():
                print(f"  {owner}: {n} records written this run")
            print("  (a second run writes 0: the ledger suppresses re-migration)")

        if args.reconcile:
            report = reconcile(args.data_dir, targets, plan)
            print("\n=== RECONCILIATION ===")
            for c in report["checks"]:
                print(f"  {json.dumps(c)}")
            print(f"\n  RESULT: {report['result']}")
            if args.report:
                args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
                print(f"  report written to {args.report}")
            return 0 if report["result"] == "PASS" else 1

        if args.report and not args.reconcile:
            args.report.write_text(json.dumps({
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "mode": "execute" if args.execute else "dry-run",
                "marketing_records": plan.total(MARKETING),
                "operations_records": plan.total(OPERATIONS),
                "ambiguous_records": plan.total(AMBIGUOUS),
                "excluded_records": plan.total(EXCLUDED),
                "broken_references": plan.broken_refs,
                "store_divergences": plan.divergences,
                "duplicate_source_ids": plan.duplicates,
                "items": [vars(i) for i in plan.items],
            }, indent=2), encoding="utf-8")
            print(f"\nreport written to {args.report}")
        return 0

    except MigrationError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
