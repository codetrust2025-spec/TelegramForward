"""Consolidate redundant profile rows while preserving interview-slot history."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from core.config import DATA_DIR
from features import candidate_store as cs


def identity(row: dict) -> str:
    phone = cs.candidate_phone_identity(row.get("phone"))
    if phone:
        return f"phone:{phone}"
    name = cs._normalise_candidate_name_key(cs.canonical_candidate_name(row.get("name") or ""))
    return f"name:{name}" if name else ""


def is_profile(row: dict) -> bool:
    return cs._normalise_service_type(row.get("service_type"), row) != "round_wise"


def is_interview_row(row: dict) -> bool:
    return bool(row.get("slot_confirmed") or str(row.get("time") or "").strip())


def score(row: dict) -> tuple:
    return (
        bool(row.get("proofs")), len(row.get("proofs") or []),
        bool(row.get("resumes")), len(row.get("resumes") or []),
        bool(row.get("slot_confirmed")), int(row.get("payment") or 0),
        bool(str(row.get("phone") or "").strip()),
        str(row.get("updated_at") or ""),
    )


def merge_items(rows: list[dict], key: str) -> list[dict]:
    found = {}
    for row in rows:
        for item in row.get(key) or []:
            item_id = item.get("id") or f"{item.get('filename')}:{item.get('uploaded_at')}"
            if item_id not in found:
                found[item_id] = item
    return list(found.values())


def main(apply: bool) -> None:
    data = cs._load(force=True)
    rows = list(data.get("candidates") or [])
    groups = {}
    for row in rows:
        key = identity(row)
        if key and is_profile(row):
            groups.setdefault(key, []).append(row)

    delete_ids = set()
    report = []
    for key, group in groups.items():
        if len(group) < 2:
            continue
        interview_rows = [row for row in group if is_interview_row(row)]
        base_rows = [row for row in group if not is_interview_row(row)]
        if len(base_rows) <= 1:
            continue
        keeper = max(group, key=score)
        redundant = [row for row in base_rows if row.get("id") != keeper.get("id")]
        if keeper not in base_rows:
            redundant = base_rows
        if not redundant:
            continue

        keeper["proofs"] = merge_items(group, "proofs")
        keeper["resumes"] = merge_items(group, "resumes")
        keeper["payment"] = max(int(row.get("payment") or 0) for row in group)
        keeper["expected_payment"] = max(cs.effective_expected_payment(row) for row in group)
        for field in ("phone", "reference", "follow_up", "technology", "notes", "logged_date"):
            if not str(keeper.get(field) or "").strip():
                value = next((row.get(field) for row in group if str(row.get(field) or "").strip()), "")
                keeper[field] = value
        keeper["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Keep commercial fields consistent on retained interview rows.
        for retained in interview_rows:
            retained["payment"] = keeper["payment"]
            retained["expected_payment"] = keeper["expected_payment"]
            retained["phone"] = keeper.get("phone") or retained.get("phone")
            retained["reference"] = keeper.get("reference") or retained.get("reference")
            retained["follow_up"] = keeper.get("follow_up") or retained.get("follow_up")

        delete_ids.update(row.get("id") for row in redundant)
        report.append({
            "identity": key, "name": keeper.get("name"), "keeper": keeper.get("id"),
            "deleted": [row.get("id") for row in redundant],
            "retained_interview_rows": [row.get("id") for row in interview_rows if row.get("id") != keeper.get("id")],
        })

    print(json.dumps({"groups": len(report), "delete_count": len(delete_ids), "report": report}, indent=2))
    if not apply or not delete_ids:
        return
    backup_dir = Path(DATA_DIR) / "migration_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backup_dir / f"candidates_before_dedupe_{stamp}.json"
    backup.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    data["candidates"] = [row for row in rows if row.get("id") not in delete_ids]
    cs._save(data)
    print(f"APPLIED backup={backup} remaining={len(data['candidates'])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    main(args.apply)
