#!/usr/bin/env python3
"""Validate a completed split migration against the source it came from.

The migration tool's own --reconcile answers "did I write what I planned to
write". This answers the different question a cutover actually depends on: is
what landed in the destinations internally consistent and complete.

  Row parity        every migrated table has the same number of rows it had in
                    the source. A silent truncation at scale looks exactly like
                    a successful run until someone counts.

  Foreign keys      every declared constraint holds. PostgreSQL enforces these
                    on insert, so a violation here does not mean a bad row - it
                    means a constraint that is not actually present in the
                    destination, which is the failure worth catching.

  Orphans           references that are NOT declared foreign keys. The monolith
                    carries plenty: a candidate_id in a text column pointing at
                    a row in a table the database was never told about.

  Duplicates        natural keys that should be unique and are not. Re-running a
                    migration is the classic way to create these, so this is
                    checked after the idempotent second run rather than before.

  File references   a row naming a file the destination tree does not contain.
                    Evidence and attachments migrate as files, and a reference
                    with nothing behind it is a broken record, not a missing
                    nicety.

Reports counts, table names and column names. Never prints a value.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2


def connect(dsn: str):
    conn = psycopg2.connect(dsn)
    conn.set_session(readonly=True)
    return conn


def tables(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_type='BASE TABLE'")
        return {r[0] for r in cur.fetchall()}


def count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f'SELECT COUNT(*) FROM "{table}"')
        return cur.fetchone()[0]


def check_row_parity(src, dests, failures) -> None:
    print("=" * 78)
    print("1. row parity: every migrated table keeps its row count")
    print("=" * 78)
    src_tables = tables(src)
    total_checked = total_rows = 0
    for label, conn in dests:
        shared = sorted(src_tables & tables(conn))
        mismatched = []
        for table in shared:
            a, b = count(src, table), count(conn, table)
            total_checked += 1
            total_rows += b
            if a != b:
                mismatched.append((table, a, b))
        print(f"   {label}: {len(shared)} shared tables, "
              f"{len(mismatched)} with a differing count")
        for table, a, b in mismatched:
            print(f"     MISMATCH {table}: source {a} -> {label} {b}")
            failures.append(f"row count mismatch in {label}.{table}")
    print(f"   tables compared: {total_checked}, rows in destinations: {total_rows}")


def check_foreign_keys(dests, failures) -> None:
    print()
    print("=" * 78)
    print("2. foreign keys: every declared constraint actually holds")
    print("=" * 78)
    for label, conn in dests:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT tc.constraint_name, tc.table_name, kcu.column_name,
                       ccu.table_name, ccu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_name = tc.constraint_name
                 AND kcu.table_schema = tc.table_schema
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_name = tc.constraint_name
                 AND ccu.table_schema = tc.table_schema
                WHERE tc.table_schema='public' AND tc.constraint_type='FOREIGN KEY'
                ORDER BY tc.table_name, tc.constraint_name""")
            fks = cur.fetchall()
        violations = []
        for name, child, child_col, parent, parent_col in fks:
            with conn.cursor() as cur:
                cur.execute(
                    f'SELECT COUNT(*) FROM "{child}" c '
                    f'WHERE c."{child_col}" IS NOT NULL AND NOT EXISTS ('
                    f'SELECT 1 FROM "{parent}" p WHERE p."{parent_col}" = c."{child_col}")')
                bad = cur.fetchone()[0]
            if bad:
                violations.append((name, f"{child}.{child_col}", bad))
        print(f"   {label}: {len(fks)} foreign keys, {len(violations)} violated")
        for name, where, bad in violations:
            print(f"     VIOLATION {where} ({name}): {bad} rows")
            failures.append(f"foreign key {name} violated in {label}")


def check_orphans(dests, pairs, failures) -> None:
    print()
    print("=" * 78)
    print("3. orphans: references the schema does not declare as foreign keys")
    print("=" * 78)
    for label, conn in dests:
        present = tables(conn)
        checked, orphaned = 0, []
        for child, child_col, parent, parent_col in pairs:
            if child not in present or parent not in present:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s AND column_name=%s",
                    (child, child_col))
                if not cur.fetchone()[0]:
                    continue
                cur.execute(
                    f'SELECT COUNT(*) FROM "{child}" c '
                    f'WHERE c."{child_col}" IS NOT NULL AND c."{child_col}" <> \'\' '
                    f'AND NOT EXISTS (SELECT 1 FROM "{parent}" p '
                    f'WHERE p."{parent_col}"::text = c."{child_col}"::text)')
                bad = cur.fetchone()[0]
            checked += 1
            if bad:
                orphaned.append((f"{child}.{child_col} -> {parent}.{parent_col}", bad))
        print(f"   {label}: {checked} undeclared references checked, "
              f"{len(orphaned)} with orphans")
        for where, bad in orphaned:
            print(f"     ORPHANS {where}: {bad} rows")
            failures.append(f"orphaned references in {label}.{where}")


def check_duplicates(dests, natural_keys, failures) -> None:
    print()
    print("=" * 78)
    print("4. duplicates on natural keys, after the idempotent second run")
    print("=" * 78)
    for label, conn in dests:
        present = tables(conn)
        checked, dupes = 0, []
        for table, cols in natural_keys:
            if table not in present:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s", (table,))
                have = {r[0] for r in cur.fetchall()}
                if not set(cols) <= have:
                    continue
                quoted = ", ".join(f'"{c}"' for c in cols)
                cur.execute(
                    f'SELECT COUNT(*) FROM (SELECT {quoted} FROM "{table}" '
                    f'GROUP BY {quoted} HAVING COUNT(*) > 1) d')
                n = cur.fetchone()[0]
            checked += 1
            if n:
                dupes.append((f"{table}({', '.join(cols)})", n))
        print(f"   {label}: {checked} natural keys checked, {len(dupes)} duplicated")
        for where, n in dupes:
            print(f"     DUPLICATES {where}: {n} repeated key(s)")
            failures.append(f"duplicate natural key in {label}.{where}")


def check_file_references(dests, data_dirs, columns, failures) -> None:
    print()
    print("=" * 78)
    print("5. file references: every named file exists in the destination tree")
    print("=" * 78)
    for (label, conn), root in zip(dests, data_dirs):
        if not root or not root.exists():
            print(f"   {label}: no data directory given, skipped")
            continue
        names = {p.name for p in root.rglob("*") if p.is_file()}
        present = tables(conn)
        checked, missing_total, missing_cols = 0, 0, []
        for table, col in columns:
            if table not in present:
                continue
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s AND column_name=%s",
                    (table, col))
                if not cur.fetchone()[0]:
                    continue
                cur.execute(f'SELECT "{col}" FROM "{table}" '
                            f"WHERE \"{col}\" IS NOT NULL AND \"{col}\" <> ''")
                referenced = [str(r[0]) for r in cur.fetchall()]
            checked += 1
            missing = [r for r in referenced if Path(r).name not in names]
            if missing:
                missing_total += len(missing)
                missing_cols.append((f"{table}.{col}", len(missing), len(referenced)))
        print(f"   {label}: {len(names)} files in tree, {checked} columns checked, "
              f"{missing_total} references with nothing behind them")
        for where, n, total in missing_cols:
            print(f"     MISSING {where}: {n} of {total}")
            failures.append(f"missing files referenced by {label}.{where}")


# References the monolith relies on that the schema never declared.
UNDECLARED_REFERENCES = [
    ("mail_outcome_audit_findings", "candidate_id", "candidates_store", "id"),
    ("mailbox_messages", "candidate_id", "candidates_store", "id"),
    ("mail_ai_analyses", "candidate_id", "candidates_store", "id"),
    ("interview_mail_analyses", "candidate_id", "candidates_store", "id"),
    ("recruitment_audit_log", "candidate_id", "candidates_store", "id"),
    ("mail_realtime_events", "candidate_id", "candidates_store", "id"),
    ("candidate_status_history", "candidate_id", "candidates_store", "id"),
    ("candidate_mailboxes", "candidate_id", "candidates_store", "id"),
    ("mail_ai_analyses", "mailbox_message_id", "mailbox_messages", "id"),
    ("mail_outcome_audit_findings", "mailbox_message_id", "mailbox_messages", "id"),
    ("mailbox_attachments", "mailbox_message_id", "mailbox_messages", "id"),
    ("mail_outcome_audit_cleanup_log", "finding_id", "mail_outcome_audit_findings", "id"),
    ("mail_outcome_audit_finding_history", "finding_id", "mail_outcome_audit_findings", "id"),
]

# Keys that must be unique. provider_message_id is deliberately NOT here: the
# rehearsal measured 1,066 repeats across 15,018 rows in the SOURCE and exactly
# 1,066 in the destination, so the same provider message legitimately appears
# more than once and the migration reproduced it faithfully. Asserting
# uniqueness there tests an assumption about the data rather than the migration.
NATURAL_KEYS = [
    ("mail_outcome_audit_findings", ["id"]),
    ("candidates_store", ["id"]),
    ("mail_ai_analyses", ["id"]),
    ("candidate_mailboxes", ["candidate_id", "email_address"]),
    ("recruitment_audit_log", ["id"]),
]

# mailbox_attachments.filename is deliberately absent. All 3,486 rows carry an
# extracted_text_reference and none of the 537 distinct filenames exist on disk
# anywhere in production: the monolith parsed these attachments and kept the
# text, never the bytes. They are extraction records, not file references, and
# checking them reports 3,486 missing files that were never there.
FILE_REFERENCE_COLUMNS = [
    ("candidates_store", "latest_resume"),
    ("payment_evidence", "filename"),
    ("payment_evidence", "original_name"),
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source-dsn", required=True)
    ap.add_argument("--marketing-dsn", required=True)
    ap.add_argument("--operations-dsn", required=True)
    ap.add_argument("--marketing-data-dir", type=Path)
    ap.add_argument("--operations-data-dir", type=Path)
    args = ap.parse_args(argv)

    src = connect(args.source_dsn)
    dests = [("marketing", connect(args.marketing_dsn)),
             ("operations", connect(args.operations_dsn))]
    data_dirs = [args.marketing_data_dir, args.operations_data_dir]
    failures: list[str] = []

    check_row_parity(src, dests, failures)
    check_foreign_keys(dests, failures)
    check_orphans(dests, UNDECLARED_REFERENCES, failures)
    check_duplicates(dests, NATURAL_KEYS, failures)
    check_file_references(dests, data_dirs, FILE_REFERENCE_COLUMNS, failures)

    src.close()
    for _, conn in dests:
        conn.close()

    print()
    if failures:
        print(f"RESULT: FAIL - {len(failures)} finding(s)")
        for f in failures:
            print(f"   {f}")
        return 1
    print("RESULT: PASS - counts match, constraints hold, no orphans, "
          "no duplicates, no dangling file references")
    return 0


if __name__ == "__main__":
    sys.exit(main())
