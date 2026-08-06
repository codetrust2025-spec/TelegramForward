"""Referral commission follows the money actually received."""
import pytest

from features import candidate_store as cs
from features import payment_receipts


def row(**changes):
    value = {
        "id": "c1", "name": "alluraiah", "reference": "Pavan Kalyan",
        "service_type": "round_wise", "interview_scope": "external",
        "expected_payment": 5000, "payment": 6000, "bgv_certificates": False,
    }
    value.update(changes)
    return value


@pytest.mark.parametrize(("received", "expected_commission"), [
    (5000, 2500),
    (6000, 3000),
    (7000, 3500),
    (12000, 6000),
])
def test_commission_is_half_of_what_was_received(received, expected_commission):
    assert cs.referrer_commission_amount(row(payment=received)) == expected_commission


def test_paying_above_the_minimum_is_commissionable():
    """The production case: ₹6,000 received against a ₹5,000 minimum used to
    earn commission on ₹5,000 because the basis was capped at the agreed
    amount."""
    value = row(payment=6000, expected_payment=5000)
    assert cs.referrer_commission_basis(value) == 6000
    assert cs.referrer_commission_amount(value) == 3000


def test_removing_a_proof_reduces_the_commission():
    assert cs.referrer_commission_amount(row(payment=12000)) == 6000
    assert cs.referrer_commission_amount(row(payment=5000)) == 2500


def test_no_payment_earns_no_commission():
    assert cs.referrer_commission_amount(row(payment=0)) == 0


def test_bgv_pass_through_is_still_excluded():
    """A third party bills the ₹30k BGV charge, so it never becomes company
    revenue and is not commissionable — even though it is 'received'."""
    value = row(service_type="profile_service", interview_scope="",
                expected_payment=50000, payment=50000, bgv_certificates=True)
    assert cs.referrer_commission_basis(value) == 20000
    assert cs.referrer_commission_amount(value) == 10000


def test_complimentary_stays_separate_from_the_payment_commission(monkeypatch):
    value = row(payment=6000)
    monkeypatch.setattr(cs, "referrer_complimentary_amount", lambda _r: 5000)
    allocations = cs.handler_earning_allocations(value)
    key = cs._reference_key("Pavan Kalyan")
    assert allocations[key] == 8000, "payment commission plus closure bonus"
    assert cs.referrer_commission_amount(value) == 3000, "commission alone is unchanged"


def test_computed_row_exposes_the_referral_figures():
    enriched = cs._with_computed(row(payment=6000))
    assert enriched["referral_commission"] == 3000
    assert enriched["referral_percentage"] == cs.HANDLER_COMMISSION_PCT
    assert enriched["referral_basis"] == 6000
    assert enriched["base_handler_commission"] == 3000


def test_api_summary_carries_the_referral_share():
    enriched = cs._with_computed(row(payment=6000))
    summary = payment_receipts.api_summary(enriched)
    assert summary["received_total"] == 6000
    assert summary["referral_percentage"] == 50
    assert summary["referral_commission"] == 3000
    assert summary["referrer"] == "Pavan Kalyan"
    assert summary["referrer_complimentary_amount"] == 0


def test_recalculation_is_idempotent():
    """Commission is derived from the row on every read, so re-deriving it can
    never produce a second allocation."""
    value = row(payment=6000)
    key = cs._reference_key("Pavan Kalyan")
    first = cs.handler_earning_allocations(value)
    second = cs.handler_earning_allocations(value)
    assert first == second == {key: 3000}
    assert len(first) == 1


def test_duplicate_proofs_do_not_inflate_commission():
    """Deduplication happens in the received total, so a re-uploaded receipt
    cannot raise the commission."""
    duplicate_pair = [
        {"id": "a", "verified_amount": 6000, "utr_number": "U1",
         "verification_state": "VERIFIED_COMPANY_PAYMENT"},
        {"id": "b", "verified_amount": 6000, "utr_number": "U1",
         "verification_state": "VERIFIED_COMPANY_PAYMENT"},
    ]
    total = payment_receipts.verified_proof_total(duplicate_pair)
    assert total == 6000
    assert cs.referrer_commission_amount(row(payment=total)) == 3000


def test_bgv_is_excluded_on_every_row_of_a_bgv_profile():
    """BGV is a profile attribute, but it is stored per row. The candidate list
    collapses clone rows and can pick one whose flag was never set, which is how
    a BGV pass-through leaked into commission for sakthivek: the collapsed row
    read bgv_certificates False and made the whole Rs 50,000 commissionable."""
    bgv_row = row(service_type="profile_service", interview_scope="",
                  expected_payment=50000, payment=50000, bgv_certificates=True)
    clone = dict(bgv_row, id="c2", bgv_certificates=False)

    assert cs.referrer_commission_amount(bgv_row) == 10000
    assert cs.referrer_commission_amount(clone) == 25000, (
        "a clone missing the flag over-pays by half the pass-through"
    )
    # Once the flag is carried across the profile, every row agrees.
    repaired = dict(clone, bgv_certificates=True)
    assert cs.referrer_commission_amount(repaired) == 10000
