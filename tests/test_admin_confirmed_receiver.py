"""Releasing a false duplicate, and confirming a receiver the app redacted.

Both are administrator actions on a single proof. Neither may become a general
rule: a real double-spend must still refuse, and a confirmation must not teach
the receiver registry anything about future uploads.
"""

import json
import pathlib

import pytest

from features import candidate_store as cs


@pytest.fixture(autouse=True)
def _isolated_store(monkeypatch, tmp_path):
    store = tmp_path / "candidates.json"
    store.write_text(json.dumps({"candidates": []}), encoding="utf-8")
    # `_FILE` is resolved once at import from DATA_DIR, so it is the only name
    # that redirects the store. Patching anything else leaves _save() merging
    # test rows into the real data file.
    monkeypatch.setattr(cs, "_FILE", str(store))
    monkeypatch.setenv(
        "PAYMENT_VERIFICATION_LEDGER_FILE", str(tmp_path / "ledger.json")
    )
    cs._load_cache = None
    yield
    cs._load_cache = None


def _seed(proof_state, *, amount=10000, expected=20000, payments=None, tmp_path=None):
    cs._load_cache = None
    # _save() merges rows into whatever is already on disk, so a re-seed inside
    # one test would otherwise keep the previous proof state.
    pathlib.Path(cs._FILE).write_text(json.dumps({"candidates": []}), encoding="utf-8")
    data = {
        "candidates": [
            {
                "id": "cand-1",
                "name": "Poojitha",
                "payment": 0,
                "expected_payment": expected,
                "reference": "Ravinder",
                "payment_proofs": [
                    {
                        "id": "proof-1",
                        "verified_amount": amount,
                        "verification_state": proof_state,
                        "utr_number": "757988842904",
                        "transaction_id": "T2608071210007608760634",
                        "receiver_name": "JOLLU RAVINDER",
                        "receiver_upi_id": "XXXXXX4573@ybl",
                    }
                ],
            }
        ]
    }
    cs._save(data)
    if tmp_path is not None:
        (tmp_path / "ledger.json").write_text(
            json.dumps({"payments": payments or [], "evidence": []}), encoding="utf-8"
        )
    return data


def _proof():
    cs._load_cache = None
    row = next(r for r in cs._load()["candidates"] if r["id"] == "cand-1")
    return row["payment_proofs"][0]


# --- clearing a duplicate that was never real ---


def test_false_duplicate_is_released_when_nothing_else_was_credited(tmp_path):
    _seed("DUPLICATE_PAYMENT", tmp_path=tmp_path, payments=[
        {
            "payment_id": "pay_rejected",
            "source_entity_id": "junk-profile",
            "verification_state": "REJECTED",
            "amount_minor": 0,
            "transaction_references": {"transaction_id": "t2608071210007608760634"},
        }
    ])

    cs.clear_false_duplicate(
        "cand-1", "proof-1", reason="uploaded to the wrong profile first",
        reviewer="admin",
    )

    proof = _proof()
    assert proof["verification_state"] == "INCOMPLETE_PAYMENT_EVIDENCE"
    assert proof["duplicate_releases"][0]["reviewer"] == "admin"
    assert proof["verified_amount"] == 10000


def test_a_real_duplicate_still_refuses_to_be_released(tmp_path):
    _seed("DUPLICATE_PAYMENT", tmp_path=tmp_path, payments=[
        {
            "payment_id": "pay_real",
            "source_entity_id": "another-candidate",
            "verification_state": "VERIFIED_COMPANY_PAYMENT",
            "amount_minor": 1000000,
            "transaction_references": {"utr_number": "757988842904"},
        }
    ])

    with pytest.raises(ValueError, match="really is a duplicate"):
        cs.clear_false_duplicate(
            "cand-1", "proof-1", reason="looks wrong to me", reviewer="admin"
        )

    assert _proof()["verification_state"] == "DUPLICATE_PAYMENT"


def test_releasing_twice_is_a_no_op(tmp_path):
    _seed("DUPLICATE_PAYMENT", tmp_path=tmp_path)
    cs.clear_false_duplicate("cand-1", "proof-1", reason="r", reviewer="admin")
    cs.clear_false_duplicate("cand-1", "proof-1", reason="r", reviewer="admin")
    assert len(_proof()["duplicate_releases"]) == 1


# --- confirming who was paid ---


def test_confirming_the_company_receiver_credits_the_proof(tmp_path):
    _seed("INCOMPLETE_PAYMENT_EVIDENCE", tmp_path=tmp_path)

    cs.confirm_proof_receiver(
        "cand-1", "proof-1",
        receiver_type="company",
        receiver_name="J Ravinder",
        reason="account owner confirmed the handle ending 4573 is a company account",
        reviewer="admin",
    )

    proof = _proof()
    assert proof["verification_state"] == "VERIFIED_COMPANY_PAYMENT"
    assert proof["company_payment_verified"] is True
    assert proof["receiver_confirmations"][0]["is_original_system_capture"] is False
    # It answers who, never how much.
    assert proof["verified_amount"] == 10000


def test_a_confirmed_proof_drives_the_received_total(tmp_path):
    _seed("INCOMPLETE_PAYMENT_EVIDENCE", tmp_path=tmp_path)
    cs.confirm_proof_receiver(
        "cand-1", "proof-1", receiver_type="company",
        receiver_name="J Ravinder", reason="confirmed", reviewer="admin",
    )

    cs.recalculate_received_total(
        "cand-1", trigger="receiver_confirmation", reason="confirmed", reviewer="admin"
    )

    view = cs.get_candidate("cand-1")
    assert view["payment"] == 10000
    assert view["verified_received"] == 10000
    assert view["balance_due"] == 10000
    assert view["referral_commission"] == 5000


def test_a_rejected_or_duplicate_proof_cannot_be_confirmed_away(tmp_path):
    for blocked in ("REJECTED", "DUPLICATE_PAYMENT", "FAILED_PAYMENT"):
        _seed(blocked, tmp_path=tmp_path)
        with pytest.raises(ValueError, match="not a receiver question"):
            cs.confirm_proof_receiver(
                "cand-1", "proof-1", receiver_type="company",
                receiver_name="J Ravinder", reason="r", reviewer="admin",
            )
        assert _proof()["verification_state"] == blocked


def test_confirmation_needs_a_reviewer_and_a_reason(tmp_path):
    _seed("INCOMPLETE_PAYMENT_EVIDENCE", tmp_path=tmp_path)
    with pytest.raises(ValueError, match="reviewer and a reason"):
        cs.confirm_proof_receiver(
            "cand-1", "proof-1", receiver_type="company",
            receiver_name="J Ravinder", reason="", reviewer="admin",
        )
    with pytest.raises(ValueError, match="reviewer and a reason"):
        cs.confirm_proof_receiver(
            "cand-1", "proof-1", receiver_type="company",
            receiver_name="J Ravinder", reason="r", reviewer="",
        )


def test_confirming_twice_is_a_no_op(tmp_path):
    _seed("INCOMPLETE_PAYMENT_EVIDENCE", tmp_path=tmp_path)
    for _ in range(2):
        cs.confirm_proof_receiver(
            "cand-1", "proof-1", receiver_type="company",
            receiver_name="J Ravinder", reason="r", reviewer="admin",
        )
    assert len(_proof()["receiver_confirmations"]) == 1


def test_confirmation_does_not_touch_the_receiver_registry(tmp_path):
    """The whole point of scoping this to one proof: a masked handle must not
    start verifying by itself on the next upload."""
    from features import payment_verification_engine as engine

    _seed("INCOMPLETE_PAYMENT_EVIDENCE", tmp_path=tmp_path)
    def identifiers():
        # Timestamps churn between calls; what must not move is who the
        # registry will match and on what.
        return [
            (r["id"], r["upi_ids"], r["phones"], r["accounts"], r["aliases"])
            for r in engine.receiver_registry()
        ]

    before = identifiers()

    cs.confirm_proof_receiver(
        "cand-1", "proof-1", receiver_type="company",
        receiver_name="J Ravinder", reason="r", reviewer="admin",
    )

    assert identifiers() == before
    still_blocked = engine.classify_receiver(
        {"receiver_name": "JOLLU RAVINDER", "receiver_upi_id": "XXXXXX4573@ybl"}
    )
    assert still_blocked["receiver_match"] != "upi"
