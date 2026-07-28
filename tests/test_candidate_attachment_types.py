from pathlib import Path

import pytest

from features import candidate_store
from features.candidate_attachment_migration import migrate_payload


def _store(monkeypatch, tmp_path: Path):
    row = {
        **candidate_store._normalise(
            {
                "name": "Typed Candidate",
                "technology": "ETL",
                "phone": "9876543210",
            }
        ),
        "id": "candidate-1",
    }
    state = {"candidates": [row]}
    monkeypatch.setattr(candidate_store, "PROOFS_DIR", str(tmp_path))
    monkeypatch.setattr(candidate_store, "_load", lambda *args, **kwargs: state)
    monkeypatch.setattr(candidate_store, "_save", lambda updated: state.update(updated))
    return state


def test_missing_or_invalid_attachment_type_is_rejected(monkeypatch, tmp_path):
    _store(monkeypatch, tmp_path)
    kwargs = {
        "data": b"image",
        "original_name": "proof.jpg",
        "mime_type": "image/jpeg",
    }
    with pytest.raises(ValueError, match="attachment_type is required"):
        candidate_store.add_proof("candidate-1", **kwargs)
    with pytest.raises(ValueError, match="Invalid attachment_type"):
        candidate_store.add_proof(
            "candidate-1", attachment_type="generic_proof", **kwargs
        )


def test_slot_and_payment_attachments_never_mix(monkeypatch, tmp_path):
    state = _store(monkeypatch, tmp_path)
    payment = candidate_store.add_payment_proof(
        "candidate-1",
        data=b"payment",
        original_name="receipt.jpg",
        mime_type="image/jpeg",
        metadata={"payment_id": "pay-1"},
    )
    slot = candidate_store.add_slot_screenshot_proof(
        "candidate-1",
        data=b"slot",
        original_name="invite.jpg",
        mime_type="image/jpeg",
        metadata={"booking_id": "booking-1"},
    )

    raw = state["candidates"][0]
    assert [item["id"] for item in raw["payment_proofs"]] == [payment["id"]]
    assert [item["id"] for item in raw["slot_screenshot_proofs"]] == [slot["id"]]

    api_row = candidate_store._with_computed(raw)
    assert "proofs" not in api_row
    assert [item["attachment_type"] for item in api_row["payment_proofs"]] == [
        "payment_proof"
    ]
    assert [
        item["attachment_type"] for item in api_row["slot_screenshot_proofs"]
    ] == ["slot_screenshot_proof"]
    evidence = candidate_store._latest_slot_screenshot_proof(raw)
    assert evidence["id"] == slot["id"]
    assert evidence["id"] != payment["id"]


def test_profile_photo_is_separate(monkeypatch, tmp_path):
    state = _store(monkeypatch, tmp_path)
    photo = candidate_store.set_profile_photo(
        "candidate-1",
        data=b"photo",
        original_name="avatar.png",
        mime_type="image/png",
    )
    api_row = candidate_store._with_computed(state["candidates"][0])
    assert api_row["profile_photo"]["id"] == photo["id"]
    assert api_row["payment_proofs"] == []
    assert api_row["slot_screenshot_proofs"] == []


def test_legacy_migration_classifies_and_quarantines_without_deleting_metadata():
    payload = {
        "candidates": [
            {
                "id": "legacy",
                "proofs": [
                    {"id": "p1", "filename": "p1.jpg", "payment_id": "pay-1"},
                    {"id": "s1", "filename": "s1.jpg", "booking_id": "book-1"},
                    {"id": "u1", "filename": "u1.jpg", "note": "uploaded image"},
                ],
            }
        ]
    }
    migrated, stats = migrate_payload(payload)
    row = migrated["candidates"][0]
    assert "proofs" not in row
    assert [item["id"] for item in row["payment_proofs"]] == ["p1"]
    assert [item["id"] for item in row["slot_screenshot_proofs"]] == ["s1"]
    assert [item["id"] for item in row["attachment_review_queue"]] == ["u1"]
    assert all(item["legacy_storage"] for item in (
        row["payment_proofs"] + row["slot_screenshot_proofs"] + row["attachment_review_queue"]
    ))
    assert stats == {
        "candidates": 1,
        "payment": 1,
        "slot": 1,
        "profile": 0,
        "review": 1,
    }
