from features.candidate_store import (
    referrer_commission_amount,
    referrer_commission_basis,
)


def test_below_tariff_agreed_payment_keeps_full_referral_percentage():
    krishna = {
        "name": "Krishna",
        "reference": "Thrilok",
        "service_type": "round_wise",
        "interview_scope": "internal",
        "expected_payment": 8_000,
        "payment": 8_000,
    }

    assert referrer_commission_basis(krishna) == 8_000
    assert referrer_commission_amount(krishna) == 4_000


def test_partial_payment_earns_half_of_cash_received():
    row = {
        "service_type": "round_wise",
        "interview_scope": "internal",
        "expected_payment": 9_000,
        "payment": 5_000,
    }

    assert referrer_commission_basis(row) == 5_000
    assert referrer_commission_amount(row) == 2_500


def test_commission_remains_capped_at_agreed_client_charge():
    row = {
        "service_type": "round_wise",
        "interview_scope": "external",
        "expected_payment": 5_000,
        "payment": 8_000,
    }

    assert referrer_commission_basis(row) == 5_000
    assert referrer_commission_amount(row) == 2_500


def test_bgv_pass_through_remains_non_commissionable():
    row = {
        "service_type": "profile_service",
        "bgv_certificates": True,
        "expected_payment": 50_000,
        "payment": 50_000,
    }

    assert referrer_commission_basis(row) == 20_000
    assert referrer_commission_amount(row) == 10_000
