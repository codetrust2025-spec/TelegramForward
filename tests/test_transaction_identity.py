"""One real-world transaction must affect the balance exactly once."""
from __future__ import annotations

import pytest

from features import transaction_identity as ti


def _tx(**over):
    base = {
        "record_id": "r1",
        "kind": "expense",
        "source_module": "handler_expenses",
        "amount": 5000,
        "date": "2026-07-22",
        "payer": "TADEPALLI SRI RAMUDU",
        "receiver": "lukka pavan kalyan",
        "created_at": "2026-07-23T10:00:00+00:00",
    }
    base.update(over)
    return base


# ── identity ────────────────────────────────────────────────────────────────

def test_upi_reference_identifies_a_transaction_across_formatting():
    assert ti.normalize_external_id("484653160050") == ti.normalize_external_id(
        "4846 5316 0050"
    )
    assert ti.normalize_external_id("utr-abc123") == "UTRABC123"


def test_short_reference_is_not_treated_as_identifying():
    # "12345" could be an invoice line, a slot number, anything.
    assert ti.normalize_external_id("12345") == ""


def test_upi_handle_identifies_a_party_more_precisely_than_the_name():
    assert ti.normalize_party("Lukka Pavan Kalyan pavankalyan42761@okaxis") == (
        "pavankalyan42761@okaxis"
    )
    assert ti.normalize_party("+91 90109 69470") == "9010969470"


def test_the_recording_module_is_not_part_of_the_fingerprint():
    # The whole point is matching the same money across different modules.
    expense = ti.fingerprint(_tx(source_module="handler_expenses"))
    recovery = ti.fingerprint(_tx(source_module="public_slot_booking", kind="recovery"))
    assert expense == recovery != ""


def test_a_transaction_without_an_amount_or_date_has_no_fingerprint():
    assert ti.fingerprint(_tx(amount=0)) == ""
    assert ti.fingerprint(_tx(date="")) == ""


def test_the_upi_reference_outranks_the_fingerprint():
    identity = ti.identity_of(_tx(upi_transaction_id="484653160050"))
    assert identity["identity"] == "484653160050"
    assert identity["fingerprint"].startswith("fp:")


# ── detection ───────────────────────────────────────────────────────────────

def test_a_recovery_refiled_as_an_expense_is_reported_as_one_transaction():
    groups = ti.find_duplicates(
        [
            _tx(record_id="rec1", kind="recovery", source_module="public_slot_booking"),
            _tx(record_id="exp1", kind="expense"),
        ]
    )
    assert len(groups) == 1
    # The automatic entry is kept; the hand-filed one is the duplicate.
    assert groups[0]["canonical"]["record_id"] == "rec1"
    assert [d["record_id"] for d in groups[0]["duplicates"]] == ["exp1"]
    assert groups[0]["financial_impact"] == 5000


def test_a_candidate_payment_and_the_recovery_it_causes_are_not_a_duplicate():
    # Both describe the same money on purpose: the recovery exists because the
    # candidate paid into the referrer's account.
    groups = ti.find_duplicates(
        [
            _tx(record_id="p1", kind="candidate_payment"),
            _tx(record_id="r1", kind="recovery"),
        ]
    )
    assert groups == []


def test_two_genuine_payments_of_the_same_amount_on_different_days_are_distinct():
    groups = ti.find_duplicates(
        [
            _tx(record_id="e1", date="2026-07-22"),
            _tx(record_id="e2", date="2026-07-29"),
        ]
    )
    assert groups == []


def test_the_same_amount_to_different_handlers_is_not_a_duplicate():
    groups = ti.find_duplicates(
        [
            _tx(record_id="e1", receiver="lukka pavan kalyan"),
            _tx(record_id="e2", receiver="venugopal"),
        ]
    )
    assert groups == []


def test_an_already_voided_record_no_longer_counts_as_a_duplicate():
    groups = ti.find_duplicates(
        [
            _tx(record_id="rec1", kind="recovery"),
            _tx(record_id="exp1", kind="expense", voided=True),
        ]
    )
    assert groups == []


def test_the_same_screenshot_in_two_modules_is_surfaced():
    groups = ti.find_duplicates(
        [
            _tx(record_id="rec1", kind="recovery", date="2026-07-22", screenshot_hash="abc"),
            # Different date typed in by hand, so only the image ties them.
            _tx(record_id="exp1", kind="expense", date="2026-07-25", screenshot_hash="abc"),
        ]
    )
    assert len(groups) == 1
    assert groups[0]["basis"] == "screenshot_hash"


def test_a_duplicate_is_reported_once_even_when_several_signals_agree():
    rows = [
        _tx(record_id="rec1", kind="recovery", upi_transaction_id="484653160050",
            screenshot_hash="abc"),
        _tx(record_id="exp1", kind="expense", upi_transaction_id="484653160050",
            screenshot_hash="abc"),
    ]
    assert len(ti.find_duplicates(rows)) == 1


def test_non_money_records_are_ignored():
    groups = ti.find_duplicates(
        [_tx(record_id="a", kind="note"), _tx(record_id="b", kind="note")]
    )
    assert groups == []


# ── prevention ──────────────────────────────────────────────────────────────

def test_an_incoming_expense_that_repeats_a_recovery_is_identified():
    existing = [_tx(record_id="rec1", kind="recovery")]
    clash = ti.duplicate_of(_tx(record_id="new", kind="expense"), existing)
    assert clash is not None and clash["record_id"] == "rec1"


def test_an_unrelated_expense_is_allowed_through():
    existing = [_tx(record_id="rec1", kind="recovery")]
    assert ti.duplicate_of(_tx(record_id="new", amount=1200, date="2026-08-01"), existing) is None


def test_a_transaction_with_no_usable_identity_is_never_blocked():
    # Blocking on amount alone would stop legitimate repeat expenses.
    existing = [_tx(record_id="rec1", kind="recovery")]
    assert ti.duplicate_of(_tx(record_id="new", date=""), existing) is None


def test_the_operator_is_told_what_the_money_is_already_recorded_as():
    message = ti.duplicate_message(_tx(kind="recovery"))
    assert "already recorded as a candidate-payment recovery" in message
    assert "2026-07-22" in message


# ── engine-assigned payment identity ────────────────────────────────────────

def test_the_engine_payment_outranks_every_other_signal():
    # The verification engine reuses one payment record when a second
    # screenshot of the same transfer is uploaded, so it is the ground truth.
    identity = ti.identity_of(_tx(payment_id="pay_36b6", upi_transaction_id="484653160050"))
    assert identity["identity"] == "pay:pay_36b6"


def test_a_refiled_expense_is_caught_even_when_the_typed_date_is_wrong():
    # The operator typed the day they filed it, not the day on the receipt, so
    # the fingerprint cannot match. The shared payment still does.
    groups = ti.find_duplicates(
        [
            _tx(record_id="rec1", kind="recovery", date="2026-07-22",
                payment_id="pay_36b6", source_module="public_slot_payment_proof"),
            _tx(record_id="exp1", kind="expense", date="2026-07-28",
                payment_id="pay_36b6"),
        ]
    )
    assert len(groups) == 1
    assert groups[0]["basis"] == "payment_id"
    assert groups[0]["confidence"] == "high"
    assert groups[0]["canonical"]["record_id"] == "rec1"


def test_a_ledger_mirror_is_never_the_duplicate_of_the_expense_it_mirrors():
    # Filing an expense also writes a COMMISSION_PAYOUT against the same
    # payment. Only the expense store feeds the balance.
    groups = ti.find_duplicates(
        [
            _tx(record_id="mirror", kind="ledger_mirror", payment_id="pay_71d7"),
            _tx(record_id="exp1", kind="expense", payment_id="pay_71d7"),
        ]
    )
    assert groups == []


def test_a_fingerprint_only_match_is_never_auto_correctable():
    groups = ti.find_duplicates(
        [
            _tx(record_id="rec1", kind="recovery"),
            _tx(record_id="exp1", kind="expense"),
        ]
    )
    assert groups[0]["basis"] == "fingerprint"
    assert groups[0]["confidence"] == "review"


def test_one_screenshot_on_two_records_of_different_amounts_needs_review():
    # Usually a proof attached to the wrong record, not money moved twice.
    groups = ti.find_duplicates(
        [
            _tx(record_id="exp1", kind="expense", amount=1500, date="2026-06-22",
                screenshot_hash="4e9c"),
            _tx(record_id="pay1", kind="candidate_payment", amount=2000,
                date="2026-06-11", screenshot_hash="4e9c"),
        ]
    )
    assert len(groups) == 1
    assert groups[0]["confidence"] == "review"


def test_a_shared_payment_with_disagreeing_amounts_is_not_auto_correctable():
    groups = ti.find_duplicates(
        [
            _tx(record_id="rec1", kind="recovery", amount=5000, payment_id="pay_1"),
            _tx(record_id="exp1", kind="expense", amount=2500, payment_id="pay_1"),
        ]
    )
    assert groups[0]["confidence"] == "review"


def test_a_mirror_sharing_the_payment_is_not_listed_as_a_duplicate():
    # Listing the audit copy alongside the expense would double the reported
    # financial impact of the finding.
    groups = ti.find_duplicates(
        [
            _tx(record_id="rec1", kind="recovery", payment_id="pay_1",
                source_module="public_slot_payment_proof"),
            _tx(record_id="mirror", kind="ledger_mirror", payment_id="pay_1"),
            _tx(record_id="exp1", kind="expense", payment_id="pay_1", date="2026-07-28"),
        ]
    )
    assert len(groups) == 1
    assert [d["record_id"] for d in groups[0]["duplicates"]] == ["exp1"]
    assert groups[0]["financial_impact"] == 5000
