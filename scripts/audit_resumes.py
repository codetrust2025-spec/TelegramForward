"""Report the health of every stored resume. Read-only.

A resume record and the file it names are two separate things, and either can
outlive the other: metadata whose file has gone leaves the preview endpoint
answering "Resume not found", and a file nobody references is invisible but
still occupying disk.

    python scripts/audit_resumes.py
    python scripts/audit_resumes.py --json

Nothing is modified. Repair is a separate, deliberate step so the findings can
be read before anything moves.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features import candidate_store  # noqa: E402


def _digest(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return ""


def audit() -> dict:
    rows = candidate_store._load(force=True).get("candidates") or []
    by_id = {str(r.get("id")): r for r in rows if r.get("id")}

    records: list[dict] = []
    seen_rid: dict[str, list[str]] = defaultdict(list)
    referenced: set[str] = set()

    for row in rows:
        cid = str(row.get("id") or "")
        for entry in (row.get("resumes") or []):
            rid = str(entry.get("id") or "")
            storage_cid = candidate_store._resume_storage_candidate_id(cid, entry)
            filename = str(entry.get("filename") or "")
            path = os.path.join(candidate_store._resume_dir(storage_cid), filename)
            exists = bool(filename) and os.path.exists(path)
            referenced.add(os.path.abspath(path))
            seen_rid[rid].append(cid)

            problems = []
            if not rid:
                problems.append("missing_resume_id")
            if not filename:
                problems.append("missing_stored_filename")
            if not exists:
                problems.append("file_missing")
            if storage_cid != cid and storage_cid not in by_id:
                problems.append("storage_candidate_unknown")

            records.append({
                "candidate_id": cid,
                "candidate_name": row.get("name"),
                "resume_id": rid,
                "original_name": entry.get("original_name"),
                "stored_filename": filename,
                "storage_candidate_id": storage_cid,
                "path": path,
                "exists": exists,
                "size_on_disk": os.path.getsize(path) if exists else None,
                "size_recorded": entry.get("size"),
                "mime_type": entry.get("mime_type"),
                "sha256_recorded": entry.get("sha256") or "",
                "sha256_on_disk": _digest(path) if exists else "",
                "uploaded_at": entry.get("uploaded_at"),
                "url": entry.get("url"),
                "problems": problems,
            })

    # Files on disk that no record points at.
    orphans: list[dict] = []
    root = candidate_store.RESUMES_DIR
    if os.path.isdir(root):
        for folder, _dirs, files in os.walk(root):
            for name in files:
                full = os.path.abspath(os.path.join(folder, name))
                if full in referenced or name.endswith(".tmp"):
                    continue
                orphans.append({
                    "path": full,
                    "folder_candidate_id": os.path.basename(folder),
                    "size": os.path.getsize(full),
                    "sha256": _digest(full),
                    "folder_is_a_known_candidate":
                        os.path.basename(folder) in by_id,
                })

    duplicates = {rid: cids for rid, cids in seen_rid.items() if len(cids) > 1}
    missing = [r for r in records if "file_missing" in r["problems"]]
    mismatched = [
        r for r in records
        if r["exists"] and r["sha256_recorded"]
        and r["sha256_recorded"] != r["sha256_on_disk"]
    ]
    return {
        "resumes_dir": root,
        "total_records": len(records),
        "valid": len([r for r in records if not r["problems"]]),
        "missing_file": missing,
        "checksum_mismatch": mismatched,
        "unknown_storage_candidate": [
            r for r in records if "storage_candidate_unknown" in r["problems"]
        ],
        "duplicate_resume_ids": duplicates,
        "orphan_files": orphans,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the raw findings")
    args = parser.parse_args()
    report = audit()

    if args.json:
        print(json.dumps(report, indent=2, default=str))
        return 1 if report["missing_file"] else 0

    print("=" * 72)
    print("RESUME AUDIT - READ ONLY, NOTHING CHANGED")
    print("=" * 72)
    print(f"storage root      : {report['resumes_dir']}")
    print(f"resume records    : {report['total_records']}")
    print(f"  intact          : {report['valid']}")
    print(f"  file missing    : {len(report['missing_file'])}")
    print(f"  checksum differs: {len(report['checksum_mismatch'])}")
    print(f"  unknown storage : {len(report['unknown_storage_candidate'])}")
    print(f"duplicate ids     : {len(report['duplicate_resume_ids'])}")
    print(f"orphan files      : {len(report['orphan_files'])}")

    if report["missing_file"]:
        print("\n--- metadata whose file is gone ---")
        for r in report["missing_file"]:
            print(f"  {r['candidate_id']}/{r['resume_id']}  {r['original_name']}")
            print(f"      expected at {r['path']}")
            print(f"      uploaded {r['uploaded_at']}  recorded size {r['size_recorded']}")

    if report["orphan_files"]:
        print("\n--- files nothing points at ---")
        for o in report["orphan_files"]:
            print(f"  {o['path']}  {o['size']} bytes  sha {o['sha256'][:16]}"
                  f"  known_candidate={o['folder_is_a_known_candidate']}")

    if report["duplicate_resume_ids"]:
        print("\n--- resume ids used by more than one candidate row ---")
        for rid, cids in report["duplicate_resume_ids"].items():
            print(f"  {rid}: {cids}")

    return 1 if report["missing_file"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
