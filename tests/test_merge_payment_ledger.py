"""The historical-ledger merge imports what is missing and nothing else.

The Operations service came out of the split with its own ledger holding
post-cutover activity, while the pre-split monolith held the only copy of the
historical entries. Overwriting either direction loses money, so the merge has
to be additive, identity-checked and safe to run twice.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "merge_payment_ledger.py"
sys.path.insert(0, str(SCRIPT.parent))

from merge_payment_ledger import MergeRefused, merge  # noqa: E402


def _ledger(**collections) -> dict:
    doc = {"schema_version": 2, "entries": [], "payments": [],
           "evidence": [], "entitlements": []}
    doc.update(collections)
    return doc


def _entry(key: str, **over) -> dict:
    row = {"id": key, "idempotency_key": f"pay_{key}:X", "action": "referrer_recovery",
           "amount": 5_000, "payment_date": "2026-07-22", "referrer": "LUKKA PAVAN KALYAN"}
    row.update(over)
    return row


def test_imports_only_the_rows_the_target_lacks():
    source = _ledger(entries=[_entry("a"), _entry("b")])
    target = _ledger(entries=[_entry("b")])

    merged, report = merge(source, target)

    assert report["collections"]["entries"]["imported"] == 1
    assert report["collections"]["entries"]["collided_kept_target"] == 1
    assert [e["id"] for e in merged["entries"]] == ["b", "a"]


def test_post_cutover_rows_survive_and_stay_first():
    """The live service's own rows are authoritative and keep their order."""
    source = _ledger(payments=[{"payment_id": "pay_old"}])
    target = _ledger(payments=[{"payment_id": "pay_new_1"}, {"payment_id": "pay_new_2"}])

    merged, _ = merge(source, target)

    assert [p["payment_id"] for p in merged["payments"]] == [
        "pay_new_1", "pay_new_2", "pay_old",
    ]


def test_a_colliding_row_never_overwrites_the_live_one():
    source = _ledger(entries=[_entry("a", amount=999)])
    target = _ledger(entries=[_entry("a", amount=5_000)])

    merged, report = merge(source, target)

    assert len(merged["entries"]) == 1
    assert merged["entries"][0]["amount"] == 5_000
    assert report["total_imported"] == 0


def test_merging_twice_imports_nothing_the_second_time():
    """Idempotency: a retried correction must not duplicate money."""
    source = _ledger(entries=[_entry("a"), _entry("b")])
    target = _ledger(entries=[])

    once, _ = merge(source, target)
    twice, report = merge(source, once)

    assert report["total_imported"] == 0
    assert json.dumps(once, sort_keys=True) == json.dumps(twice, sort_keys=True)


def test_refuses_a_collection_whose_identity_key_is_not_unique():
    """`payments.idempotency_key` really is duplicated in production data.

    Keying on it would silently collapse two distinct payments into one, so the
    tool must refuse rather than guess.
    """
    source = _ledger(payments=[{"payment_id": "p1", "idempotency_key": "same"},
                               {"payment_id": "p1", "idempotency_key": "same"}])
    with pytest.raises(MergeRefused, match="more than once"):
        merge(source, _ledger())


def test_refuses_a_row_with_no_identity_field():
    source = _ledger(evidence=[{"created_at": "2026-07-28"}])
    with pytest.raises(MergeRefused, match="cannot deduplicate"):
        merge(source, _ledger())


def test_refuses_a_schema_version_mismatch():
    source = _ledger()
    target = _ledger()
    target["schema_version"] = 3
    with pytest.raises(MergeRefused, match="schema_version"):
        merge(source, target)


def test_updated_at_is_deterministic_not_wall_clock():
    """A second run must reproduce the same bytes, so the stamp cannot be `now`."""
    source = _ledger(entries=[_entry("a")])
    source["updated_at"] = "2026-08-11T09:32:15+00:00"
    target = _ledger()
    target["updated_at"] = "2026-08-17T13:11:47+00:00"

    merged, _ = merge(source, target)
    assert merged["updated_at"] == "2026-08-17T13:11:47+00:00"


def test_dry_run_writes_nothing(tmp_path):
    src = tmp_path / "source.json"
    tgt = tmp_path / "target.json"
    src.write_text(json.dumps(_ledger(entries=[_entry("a")])), encoding="utf-8")
    tgt.write_text(json.dumps(_ledger()), encoding="utf-8")
    before = tgt.read_bytes()

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--source", str(src), "--target", str(tgt)],
        capture_output=True, text=True, check=True,
    )

    assert "DRY RUN" in result.stdout
    assert tgt.read_bytes() == before


def test_apply_then_reapply_leaves_the_file_byte_identical(tmp_path):
    src = tmp_path / "source.json"
    tgt = tmp_path / "target.json"
    src.write_text(json.dumps(_ledger(entries=[_entry("a"), _entry("b")])), encoding="utf-8")
    tgt.write_text(json.dumps(_ledger()), encoding="utf-8")

    for _ in range(2):
        subprocess.run(
            [sys.executable, str(SCRIPT), "--source", str(src),
             "--target", str(tgt), "--apply"],
            capture_output=True, text=True, check=True,
        )
        if not locals().get("first"):
            first = tgt.read_bytes()

    assert tgt.read_bytes() == first
    assert len(json.loads(tgt.read_text(encoding="utf-8"))["entries"]) == 2
