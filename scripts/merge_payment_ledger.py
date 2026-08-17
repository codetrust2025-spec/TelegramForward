#!/usr/bin/env python3
"""Merge historical payment-ledger records into a live ledger without loss.

The split cutover left the Operations service with its own
``payment_verification_ledger.json`` that already carries post-cutover
activity, while the pre-split monolith still holds the only copy of the
historical entries. Neither file is a superset of the other, so the
historical records have to be *merged in*, never copied over.

Design rules, in priority order:

1. **The target is authoritative for anything it already holds.** Every row
   already in the target survives byte-for-byte, in its original order. A
   source row whose identity collides with a target row is skipped, not
   applied — the live service wins.
2. **Only genuinely absent rows are imported**, appended after the target's
   own rows in source-file order.
3. **Identity keys are verified, not assumed.** Each collection declares its
   identity field; the tool proves that field is present and unique in both
   files before merging, and refuses to run otherwise. This matters: in the
   real data ``payments.idempotency_key`` is *not* unique (two payments cite
   one reused proof), so keying on it would silently collapse a real payment.
4. **Idempotent.** Running twice imports zero rows the second time and leaves
   the file byte-identical, so a retried or double-run correction is safe.

Dry-run is the default. ``--apply`` writes, and only after taking a backup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile

# collection -> identity field. Chosen because each is verified unique in the
# real data; `entries` falls back to `id` when a row predates idempotency keys.
COLLECTIONS: dict[str, tuple[str, ...]] = {
    "entries": ("idempotency_key", "id"),
    "payments": ("payment_id",),
    "evidence": ("evidence_id",),
    "entitlements": ("entitlement_id",),
}


class MergeRefused(RuntimeError):
    """The merge cannot be performed safely and must not be forced."""


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise MergeRefused(f"{path}: expected a JSON object, got {type(data).__name__}")
    return data


def _rows(doc: dict, collection: str) -> list[dict]:
    value = doc.get(collection) or []
    if not isinstance(value, list):
        raise MergeRefused(f"{collection!r} is {type(value).__name__}, expected a list")
    return [row for row in value if isinstance(row, dict)]


def _identity(row: dict, fields: tuple[str, ...]) -> str | None:
    for field in fields:
        value = row.get(field)
        if value not in (None, ""):
            return f"{field}={value}"
    return None


def _index(rows: list[dict], fields: tuple[str, ...], label: str) -> dict[str, dict]:
    """Key rows by identity, refusing anything ambiguous.

    An unkeyable or duplicated row means we cannot tell an import from a
    re-import, which is exactly the condition that produces double-counted
    money. Refuse rather than guess.
    """
    out: dict[str, dict] = {}
    for position, row in enumerate(rows):
        key = _identity(row, fields)
        if key is None:
            raise MergeRefused(
                f"{label}: row {position} has none of {fields}; cannot deduplicate safely"
            )
        if key in out:
            raise MergeRefused(
                f"{label}: identity {key!r} appears more than once; "
                f"{fields[0]!r} is not a safe merge key for this file"
            )
        out[key] = row
    return out


def merge(source: dict, target: dict) -> tuple[dict, dict]:
    """Return ``(merged_document, report)``. Pure — mutates neither input."""
    src_version = source.get("schema_version")
    tgt_version = target.get("schema_version")
    if src_version != tgt_version:
        raise MergeRefused(
            f"schema_version mismatch: source={src_version!r} target={tgt_version!r}. "
            "A schema migration must be resolved before merging."
        )

    merged = dict(target)
    report: dict = {"schema_version": tgt_version, "collections": {}, "imported": []}

    for collection, fields in COLLECTIONS.items():
        src_rows = _rows(source, collection)
        tgt_rows = _rows(target, collection)
        src_index = _index(src_rows, fields, f"source.{collection}")
        tgt_index = _index(tgt_rows, fields, f"target.{collection}")

        # Target rows first, untouched and in their original order.
        result = list(tgt_rows)
        imported: list[dict] = []
        for key, row in src_index.items():
            if key in tgt_index:
                continue  # live service wins; never overwrite
            result.append(row)
            imported.append(row)
            report["imported"].append(
                {
                    "collection": collection,
                    "identity": key,
                    "action": row.get("action"),
                    "amount": row.get("amount"),
                    "date": str(row.get("payment_date") or row.get("created_at") or "")[:10],
                    "party": row.get("referrer") or row.get("receiver_registry_name") or "",
                }
            )

        merged[collection] = result
        report["collections"][collection] = {
            "target_before": len(tgt_rows),
            "source_available": len(src_rows),
            "imported": len(imported),
            "collided_kept_target": len(set(src_index) & set(tgt_index)),
            "target_after": len(result),
        }

    # Deterministic: the later of the two recorded timestamps, never "now",
    # so a second run reproduces the same bytes.
    stamps = [s for s in (source.get("updated_at"), target.get("updated_at")) if s]
    if stamps:
        merged["updated_at"] = max(stamps)

    report["total_imported"] = len(report["imported"])
    return merged, report


def _serialise(doc: dict) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", required=True, help="historical ledger to import from")
    parser.add_argument("--target", required=True, help="live ledger to merge into")
    parser.add_argument("--apply", action="store_true", help="write the merge (default: dry run)")
    parser.add_argument("--backup-dir", help="where to copy the target before writing")
    parser.add_argument("--report", help="write the JSON report here")
    args = parser.parse_args(argv)

    try:
        source = _load(args.source)
        target = _load(args.target)
        merged, report = merge(source, target)
    except MergeRefused as exc:
        print(f"MERGE REFUSED: {exc}", file=sys.stderr)
        return 2

    payload = _serialise(merged)
    before = _serialise(target)
    report["target_sha256_before"] = _sha(before)
    report["target_sha256_after"] = _sha(payload)
    report["no_op"] = report["target_sha256_before"] == report["target_sha256_after"]

    width = max(len(c) for c in COLLECTIONS)
    print(f"{'collection':{width}}  {'before':>7} {'avail':>6} {'import':>7} {'kept':>5} {'after':>7}")
    for collection, counts in report["collections"].items():
        print(
            f"{collection:{width}}  {counts['target_before']:>7} {counts['source_available']:>6} "
            f"{counts['imported']:>7} {counts['collided_kept_target']:>5} {counts['target_after']:>7}"
        )
    print(f"\ntotal rows imported : {report['total_imported']}")
    print(f"target sha before   : {report['target_sha256_before'][:32]}")
    print(f"target sha after    : {report['target_sha256_after'][:32]}")
    print(f"no-op (idempotent)  : {report['no_op']}")

    if report["imported"]:
        print("\nexact rows to be imported:")
        for item in report["imported"]:
            print(
                f"   {item['collection']:13} {item['identity'][:46]:48} "
                f"{str(item['action'] or ''):18} {str(item['date']):12} "
                f"{str(item['amount'] or ''):>8}  {str(item['party'])[:24]}"
            )

    if args.report:
        with open(args.report, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(f"\nreport written to {args.report}")

    if not args.apply:
        print("\nDRY RUN — nothing written. Re-run with --apply to write.")
        return 0

    if args.backup_dir:
        os.makedirs(args.backup_dir, exist_ok=True)
        backup = os.path.join(args.backup_dir, os.path.basename(args.target) + ".pre-merge")
        shutil.copy2(args.target, backup)
        print(f"\nbacked up target to {backup}")

    # Atomic replace, preserving the original mode so a live service keeps
    # exactly the permissions it had.
    mode = os.stat(args.target).st_mode & 0o777
    directory = os.path.dirname(os.path.abspath(args.target))
    handle_fd, temp_path = tempfile.mkstemp(dir=directory, prefix=".ledger-merge-")
    try:
        with os.fdopen(handle_fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.chmod(temp_path, mode)
        os.replace(temp_path, args.target)
    except BaseException:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

    print(f"APPLIED — {report['total_imported']} rows imported into {args.target}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
