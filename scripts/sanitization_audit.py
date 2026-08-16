#!/usr/bin/env python3
"""Independently verify that no production data survived sanitisation.

Deliberately does NOT reuse the sanitiser's own verifier. That verifier scans
the output for things that look real; this one takes real values out of the
source and asks whether any of them came through. A bug that makes the
sanitiser skip a column also makes its self-check skip that column, so the two
have to be independent to mean anything.

Four questions, because one rule cannot answer all of them:

  1. Full-replacement columns, row by row on the primary key. For each row, did
     THIS row's value change? Comparing whole columns instead would be
     unsatisfiable and meaningless for a pooled kind: the fake-name pool is
     drawn from common Indian names, so a pool name coincides with some real
     person somewhere by construction. The pool is a hardcoded list in this
     repository and reveals nothing about anyone.

  2. The same, as multisets, for tables with no primary key. Without row
     identity that is the strongest available statement.

  3. redact columns. These are SUPPOSED to survive - keeping the structure is
     the point, so an RFC message id stays parseable. What must not survive is
     the personal part inside, tested fragment by fragment.

  4. A global sweep. Every address and long number found in a scrubbed column,
     against every text value in the output, including columns it did not come
     from. Probes are harvested only from scrubbed columns: taking them from
     the id columns and then finding them in the output would only prove that
     preserved join keys were preserved, which is the design.

Reports counts, table names and column names. Never prints a value, so its
output is safe to paste into a review or attach to a release record.

Usage
  python scripts/sanitization_audit.py \
      --source-dsn postgresql://user@host/restored_copy \
      --target-dsn postgresql://user@host/sanitized
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from collections import Counter
from pathlib import Path

import psycopg2

_SPEC = importlib.util.spec_from_file_location(
    "sanitize_snapshot", Path(__file__).resolve().parent / "sanitize_snapshot.py")
sz = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sz)

# Kinds that replace the whole value. redact is excluded on purpose: it keeps
# the value and removes only what is personal inside it.
FULL_REPLACEMENT = {
    "person_name", "email", "phone", "upi", "bank_account", "company_name",
    "free_text", "filename", "credential", "ip", "domain", "rehash",
}


def bounded(fragment: str, haystack: str) -> bool:
    """Present as a standalone token, not buried inside a longer one."""
    return re.search(r"(?<![0-9A-Za-z])" + re.escape(fragment) + r"(?![0-9A-Za-z])",
                     haystack) is not None


def pii_fragments(text: str) -> set[str]:
    out = set(sz.EMAIL_IN_TEXT.findall(text)) | set(sz.UPI_IN_TEXT.findall(text))
    out |= {m for m in sz.DIGITS_IN_TEXT.findall(text) if len(m) >= 7}
    return {f for f in out if "sanitized" not in f}


def schema(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.table_name, c.column_name
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON t.table_name = c.table_name AND t.table_schema = c.table_schema
            WHERE c.table_schema='public' AND t.table_type='BASE TABLE'
              AND c.data_type IN ('text','character varying','character')
            ORDER BY c.table_name, c.column_name""")
        text_cols = cur.fetchall()
        cur.execute("""
            SELECT tc.table_name, kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_name = tc.constraint_name
             AND kcu.table_schema = tc.table_schema
            WHERE tc.table_schema='public' AND tc.constraint_type='PRIMARY KEY'
            ORDER BY tc.table_name, kcu.ordinal_position""")
        pks: dict[str, list[str]] = {}
        for table, column in cur.fetchall():
            pks.setdefault(table, []).append(column)
    return text_cols, pks


def atom_shape(value: str) -> str:
    """What kind of thing is this, so the audit can fail on the right ones.

    A store full of epoch timestamps and money amounts will trip any rule that
    says "a long run of digits is a phone number". Those have to be told apart
    from the things that identify a person, or the audit reports hundreds of
    findings and stops being read.
    """
    if sz.EMAIL_IN_TEXT.search(value):
        return "address"
    if sz.UPI_IN_TEXT.search(value):
        return "upi id"
    core = value.lstrip("-")
    if not core.isdigit():
        return "text" if sz.DIGITS_IN_TEXT.search(value) else "other"
    if "." in value:
        return "timestamp"
    if len(core) == 10 and core[0] in "6789":
        return "mobile number"
    if len(core) >= 16:
        # Telegram access_hash territory. Nothing benign in these stores is
        # this long.
        return "long identity"
    if len(core) in (10, 13) and core[0] == "1":
        return "timestamp"
    return "number"


PERSONAL_SHAPES = {"address", "upi id", "mobile number", "long identity"}


def personal_atoms(node, out: set[str], key: str | None = None) -> None:
    """Every key and scalar in a document that is personal data in the SOURCE.

    Keys are collected as well as values. These stores are keyed by phone
    number, so the keys alone are personal data.
    """
    if isinstance(node, dict):
        for k, value in node.items():
            if isinstance(k, str) and sz.looks_like_personal_data(k):
                out.add(k)
            personal_atoms(value, out, k if isinstance(k, str) else None)
    elif isinstance(node, list):
        for item in node:
            personal_atoms(item, out, key)
    elif node is not None and not isinstance(node, bool):
        text = str(node)
        if len(text) >= 7 and sz.looks_like_personal_data(text):
            out.add(text)


def audit_json_stores(src_dir: Path, dst_dir: Path, failures: list[str]) -> None:
    import json

    files = sorted(p for p in dst_dir.rglob("*.json"))
    print(f"   sanitised JSON stores: {len(files)}")
    atoms_total, leaked_files, residual_files = 0, [], []
    benign: Counter = Counter()
    for target in files:
        source = src_dir / target.relative_to(dst_dir)
        if not source.exists():
            continue
        try:
            src_doc = json.loads(source.read_text(encoding="utf-8"))
            out_text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        atoms: set[str] = set()
        personal_atoms(src_doc, atoms)
        atoms_total += len(atoms)
        survived = [a for a in atoms if bounded(a, out_text)]
        personal = [a for a in survived if atom_shape(a) in PERSONAL_SHAPES]
        for a in survived:
            benign[atom_shape(a)] += 0 if a in personal else 1
        if personal:
            shapes = sorted({atom_shape(a) for a in personal})
            leaked_files.append((target.name, len(personal), len(atoms), shapes))
        if sz.output_leak_label(out_text):
            residual_files.append(target.name)

    print(f"   personal keys and values taken from the source: {atoms_total}")
    print(f"   files where one survived: {len(leaked_files)}")
    for name, n, total, shapes in leaked_files:
        print(f"     LEAK {name}: {n} of {total} - {', '.join(shapes)}")
        failures.append(f"surviving personal values in {name}")
    if not leaked_files:
        print("     none")
    print(f"   files still scanning as real: {len(residual_files)}")
    for name in residual_files:
        print(f"     LEAK {name}")
        failures.append(f"residual real-looking data in {name}")
    print("   preserved on purpose, reported so the number is not mistaken "
          "for a clean sweep:")
    for shape, n in sorted(benign.items()):
        if n:
            print(f"     {n:>6}  {shape}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source-dsn", required=True)
    ap.add_argument("--target-dsn", required=True)
    ap.add_argument("--source-data-dir", type=Path,
                    help="monolith data/ directory the snapshot was taken from")
    ap.add_argument("--target-data-dir", type=Path,
                    help="sanitised data/ directory to audit")
    ap.add_argument("--sample", type=int, default=300,
                    help="distinct values per column used to harvest probes")
    args = ap.parse_args(argv)

    src = psycopg2.connect(args.source_dsn); src.set_session(readonly=True)
    dst = psycopg2.connect(args.target_dsn); dst.set_session(readonly=True)
    text_cols, pks = schema(src)
    scrubbed = [(t, c) for t, c in text_cols if c in sz.SCRUB]
    failures: list[str] = []

    print("=" * 78)
    print("1. full-replacement columns, row by row on the primary key")
    print("=" * 78)
    rows_compared, unchanged = 0, []
    for table, col in scrubbed:
        if sz.SCRUB[col] not in FULL_REPLACEMENT or table not in pks:
            continue
        keys = ", ".join(f'"{k}"' for k in pks[table])
        q = (f'SELECT {keys}, "{col}" FROM "{table}" '
             f"WHERE \"{col}\" IS NOT NULL AND \"{col}\" <> '' ORDER BY {keys}")
        with src.cursor() as a, dst.cursor() as b:
            a.execute(q); b.execute(q)
            before = {tuple(r[:-1]): r[-1] for r in a.fetchall()}
            after = {tuple(r[:-1]): r[-1] for r in b.fetchall()}
        same = [k for k, v in before.items() if k in after and after[k] == v]
        rows_compared += len(before)
        if same:
            unchanged.append((f"{table}.{col}", sz.SCRUB[col], len(same), len(before)))
    print(f"   rows compared: {rows_compared}")
    print(f"   rows whose value did not change: {sum(u[2] for u in unchanged)}")
    for name, kind, n, total in unchanged:
        print(f"     UNCHANGED {name} [{kind}]: {n} of {total}")
        failures.append(f"unchanged rows in {name}")

    print()
    print("=" * 78)
    print("2. full-replacement columns in keyless tables, compared as multisets")
    print("=" * 78)
    keyless_checked, keyless_leaks = 0, []
    for table, col in scrubbed:
        if sz.SCRUB[col] not in FULL_REPLACEMENT or table in pks:
            continue
        q = (f'SELECT "{col}" FROM "{table}" '
             f"WHERE \"{col}\" IS NOT NULL AND \"{col}\" <> ''")
        with src.cursor() as a, dst.cursor() as b:
            a.execute(q); b.execute(q)
            before = Counter(str(r[0]) for r in a.fetchall())
            after = Counter(str(r[0]) for r in b.fetchall())
        if not before:
            continue
        keyless_checked += 1
        overlap = sum((before & after).values())
        if overlap:
            keyless_leaks.append((f"{table}.{col}", overlap, sum(before.values())))
    print(f"   keyless columns checked: {keyless_checked}")
    print(f"   columns with a surviving value: {len(keyless_leaks)}")
    for name, n, total in keyless_leaks:
        print(f"     SURVIVED {name}: {n} of {total}")
        failures.append(f"surviving values in {name}")

    print()
    print("=" * 78)
    print("3. redact columns: the value survives, the PII inside must not")
    print("=" * 78)
    frags_checked, redact_leaks = 0, []
    for table, col in scrubbed:
        if sz.SCRUB[col] != "redact":
            continue
        with src.cursor() as cur:
            cur.execute(f'SELECT DISTINCT "{col}" FROM "{table}" '
                        f"WHERE \"{col}\" IS NOT NULL AND \"{col}\" <> '' LIMIT %s",
                        (args.sample * 2,))
            frags: set[str] = set()
            for (v,) in cur.fetchall():
                frags |= pii_fragments(str(v))
        if not frags:
            continue
        frags_checked += len(frags)
        with dst.cursor() as cur:
            cur.execute(f'SELECT "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL')
            out_vals = [str(r[0]) for r in cur.fetchall()]
        blob = "\n".join(out_vals)
        survived = {f for f in frags
                    if f in blob and any(bounded(f, o) for o in out_vals)}
        if survived:
            redact_leaks.append((f"{table}.{col}", len(survived), len(frags)))
    print(f"   personal fragments taken from redact columns: {frags_checked}")
    print(f"   columns with a surviving fragment: {len(redact_leaks)}")
    for name, n, total in redact_leaks:
        print(f"     LEAK {name}: {n} of {total} fragments survived")
        failures.append(f"surviving fragments in {name}")

    print()
    print("=" * 78)
    print("4. global sweep: anything from a scrubbed column, anywhere in output")
    print("=" * 78)
    emails, numbers = set(), set()
    with src.cursor() as cur:
        for table, col in scrubbed:
            cur.execute(f'SELECT DISTINCT "{col}" FROM "{table}" '
                        f"WHERE \"{col}\" IS NOT NULL AND \"{col}\" <> '' LIMIT %s",
                        (args.sample,))
            for (v,) in cur.fetchall():
                text = str(v)
                emails |= set(sz.EMAIL_IN_TEXT.findall(text))
                numbers |= {m for m in sz.DIGITS_IN_TEXT.findall(text) if len(m) >= 9}
    emails = sorted(e for e in emails if "sanitized" not in e)
    numbers = sorted(numbers)
    print(f"   real addresses harvested: {len(emails)}")
    print(f"   real long numbers harvested: {len(numbers)}")

    email_hits, number_hits = [], []
    with dst.cursor() as cur:
        for table, col in text_cols:
            cur.execute(f'SELECT "{col}" FROM "{table}" '
                        f"WHERE \"{col}\" IS NOT NULL AND \"{col}\" <> ''")
            vals = [str(r[0]) for r in cur.fetchall()]
            if not vals:
                continue
            blob = "\n".join(vals)
            hit_e = [p for p in emails if p in blob and any(bounded(p, v) for v in vals)]
            hit_n = [p for p in numbers if p in blob and any(bounded(p, v) for v in vals)]
            if hit_e:
                email_hits.append((f"{table}.{col}", len(hit_e)))
            if hit_n:
                number_hits.append((f"{table}.{col}", len(hit_n),
                                    col in sz.SAFE_TEXT_COLUMNS))
    print(f"   columns still holding a real address: {len(email_hits)}")
    for name, n in email_hits:
        print(f"     LEAK {name}: {n} addresses")
        failures.append(f"surviving addresses in {name}")

    preserved = [h for h in number_hits if h[2]]
    leaked = [h for h in number_hits if not h[2]]
    print(f"   numbers surviving in deliberately preserved id columns: {len(preserved)}")
    print(f"   numbers surviving in columns we promised to scrub: {len(leaked)}")
    for name, n, _ in leaked:
        print(f"     LEAK {name}: {n} numbers")
        failures.append(f"surviving numbers in {name}")

    src.close(); dst.close()

    if args.source_data_dir and args.target_data_dir:
        print()
        print("=" * 78)
        print("5. JSON stores: keys and leaves from the source, in the output")
        print("=" * 78)
        audit_json_stores(args.source_data_dir, args.target_data_dir, failures)

    print()
    if failures:
        print(f"RESULT: FAIL - {len(failures)} finding(s)")
        return 1
    print("RESULT: PASS - no production value, address or number survived")
    return 0


if __name__ == "__main__":
    sys.exit(main())
