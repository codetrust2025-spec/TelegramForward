from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.public_slot_api import install_public_slot_routes
from features import candidate_store as cs
from features import pending_slot_payment as pending


def _verified_payment() -> dict:
    return {
        "verification_engine": "central_payment_verification_v2",
        "booking_eligible": True,
        "company_payment_verified": True,
        "verification_state": "VERIFIED_COMPANY_PAYMENT",
        "is_payment_screenshot": True,
        "status": "success",
        "amount": 5000,
        "amount_sufficient": True,
        "confidence_score": 99,
        "utr_number": "123456789012",
        "receiver_type": "company",
        "receiver_upi_id": "company@ybl",
        "deterministic_reasons": [],
    }


def _client(monkeypatch, tmp_path) -> TestClient:
    monkeypatch.setattr(cs, "_FILE", str(tmp_path / "candidates.json"))
    monkeypatch.setattr(cs, "PROOFS_DIR", str(tmp_path / "candidate-proofs"))
    monkeypatch.setattr(cs, "_load_cache", None)
    monkeypatch.setattr(cs, "_load_cache_at", 0.0)
    monkeypatch.setattr(pending, "PENDING_PAYMENT_DIR", str(tmp_path / "pending"))
    monkeypatch.setattr(pending, "PENDING_PAYMENT_INDEX", str(tmp_path / "pending" / "index.json"))
    monkeypatch.setattr("core.db.connection.use_postgres", lambda: False)
    monkeypatch.setattr("features.payment_verification_engine.verify_payment_screenshot", lambda *_args, **_kwargs: _verified_payment())
    monkeypatch.setattr("features.ollama_payment_extract.generate_payment_narrative", lambda *_args, **_kwargs: "Verified payment")
    monkeypatch.setattr("features.payment_proof_validator.validate_interview_invite", lambda *_args, **_kwargs: (True, ""))
    app = FastAPI()
    install_public_slot_routes(app)
    return TestClient(app)


def _upload(client: TestClient) -> str:
    response = client.post(
        "/public/slots/payment-proof",
        data={"name": "Raju", "service_type": "round_wise", "phone": "9876543210", "technology": "ETL", "interview_round": "L1"},
        files={"file": ("payment.jpg", b"verified-payment", "image/jpeg")},
    )
    assert response.status_code == 200
    return response.json()["proof_id"]


def _booking(proof_id: str) -> dict:
    return {
        "name": "Raju", "service_type": "round_wise", "phone": "9876543210",
        "technology": "ETL", "interview_round": "L1", "date": "2026-08-01",
        "time": "02:00 PM", "time_end": "03:00 PM", "payment_proof_id": proof_id,
        "idempotency_key": "raju-booking-2026-08-01-1400",
    }


def test_upload_creates_nothing_and_confirm_is_idempotent(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    proof_id = _upload(client)
    assert cs.list_candidates(stage="all", month="all") == []
    booking = _booking(proof_id)
    first = client.post("/bookings/confirm", data=booking, files={"file": ("invite.jpg", b"invite", "image/jpeg")})
    second = client.post("/bookings/confirm", data=booking, files={"file": ("invite.jpg", b"invite", "image/jpeg")})
    assert first.status_code == second.status_code == 200
    rows = cs.list_candidates(stage="all", month="all")
    assert len(rows) == 1
    assert rows[0]["payment"] == 5000
    assert len(rows[0]["payment_proofs"]) == 1


def test_failed_invite_extraction_creates_no_candidate(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "features.ollama_invite_extract.extract_interview_invite_with_ollama",
        lambda *_args, **_kwargs: {
            "confidence_score": 0,
            "auto_booking_safe": False,
            "manual_fields_required": True,
            "failure_stage": "vision",
            "failure_reason": "Vision model returned no parseable JSON.",
            "missing_fields": ["interview_date", "start_time"],
            "warnings": ["Enter the date and time manually."],
        },
    )
    client = _client(monkeypatch, tmp_path)

    response = client.post(
        "/public/slots/extract-invite-ai",
        files={"file": ("invite.jpg", b"invalid-image", "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json()["data"]["manual_fields_required"] is True
    assert cs.list_candidates(stage="all", month="all") == []


def test_missing_payment_blocks_confirmation_without_records(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.post(
        "/bookings/confirm",
        data={**_booking(""), "payment_proof_id": ""},
        files={"file": ("invite.jpg", b"invite", "image/jpeg")},
    )
    assert response.status_code == 400
    assert response.json()["message"] == "Upload and verify the payment screenshot to continue."
    assert cs.list_candidates(stage="all", month="all") == []


def test_failed_confirmation_rolls_back_new_candidate(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    booking = _booking(_upload(client))
    original = cs.finalize_public_booking_payment

    def fail_after_creation(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("simulated finalization failure")

    monkeypatch.setattr(cs, "finalize_public_booking_payment", fail_after_creation)
    response = client.post("/bookings/confirm", data=booking, files={"file": ("invite.jpg", b"invite", "image/jpeg")})
    assert response.status_code == 500
    assert cs.list_candidates(stage="all", month="all") == []


def test_legacy_booking_endpoint_cannot_create(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = client.post("/public/slots/book")
    assert response.status_code == 410
    assert cs.list_candidates(stage="all", month="all") == []
