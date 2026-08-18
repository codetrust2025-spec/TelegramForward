"""Stable employee identity, and scoping a rule to a person rather than a name.

The point of this module is a payout rule that survives a rename. These tests
pin the properties that make that true, using the concrete case the identity was
introduced for: a rule that must apply to one person and to nobody else, not by
display name, not by reference, not by username, and not by role.
"""
from __future__ import annotations

import json

import pytest

from features import employee_identity as identity


@pytest.fixture(autouse=True)
def registry(monkeypatch, tmp_path):
    path = tmp_path / "employee_ids.json"
    path.write_text(json.dumps({"employees": []}), encoding="utf-8")
    monkeypatch.setenv("EMPLOYEE_IDS_FILE", str(path))
    return path


def _seed():
    thrilok, _ = identity.assign_employee_id(
        display_name="Thrilok", username="thrilok", reference="thrilok"
    )
    other, _ = identity.assign_employee_id(
        display_name="Pavan Kalyan", username="pavan", reference="pavan kalyan"
    )
    return thrilok, other


def test_ids_are_sequential_and_not_derived_from_any_name():
    thrilok, other = _seed()
    assert thrilok == "EMP-0001"
    assert other == "EMP-0002"
    assert "thrilok" not in thrilok.lower()


def test_resolution_works_from_either_a_login_or_an_earnings_reference():
    thrilok, _ = _seed()
    assert identity.employee_id_for(username="thrilok") == thrilok
    assert identity.employee_id_for(reference="Thrilok") == thrilok
    assert identity.employee_id_for(username="THRILOK") == thrilok


def test_an_unknown_login_is_simply_not_enrolled():
    _seed()
    assert identity.employee_id_for(username="stranger") is None
    assert identity.employee_id_for_profile({"username": "stranger"}) is None
    assert identity.employee_id_for_profile(None) is None


def test_a_rule_scoped_to_the_id_survives_a_rename():
    """The whole reason the id exists.

    Rename the person's reference and login; the id does not move, so a rule
    written against it still selects the same human being.
    """
    thrilok, _ = _seed()
    rule_target = thrilok  # what an attendance-linked payout rule would store

    assert identity.add_alias(thrilok, username="thrilok.k", reference="thrilok kumar") is None

    assert identity.employee_id_for(username="thrilok.k") == rule_target
    assert identity.employee_id_for(reference="thrilok kumar") == rule_target
    # the old spellings keep resolving too, so historical rows still match
    assert identity.employee_id_for(username="thrilok") == rule_target


def test_a_rule_scoped_to_the_id_does_not_follow_the_name_to_someone_else():
    """The failure mode that name-scoping has.

    If the rule had been written as reference == "thrilok", handing that
    reference to a different employee would hand them the rule. Ids cannot be
    reassigned, so the registry refuses the collision outright.
    """
    thrilok, _ = _seed()
    new_id, error = identity.assign_employee_id(
        display_name="Different Person", username="newjoiner", reference="thrilok"
    )
    assert new_id is None
    assert "already belongs to" in error
    assert identity.employee_id_for(reference="thrilok") == thrilok


def test_a_retired_id_is_never_handed_to_a_new_joiner():
    thrilok, other = _seed()
    payload = json.loads(identity._store_path() and open(identity._store_path(), encoding="utf-8").read())
    payload["employees"] = [row for row in payload["employees"] if row["employee_id"] != other]
    with open(identity._store_path(), "w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    third, _ = identity.assign_employee_id(display_name="Third", username="third")
    assert third == "EMP-0003"
    assert third != other


def test_a_deactivated_employee_stops_resolving():
    thrilok, _ = _seed()
    with open(identity._store_path(), encoding="utf-8") as handle:
        payload = json.load(handle)
    for row in payload["employees"]:
        if row["employee_id"] == thrilok:
            row["active"] = False
    with open(identity._store_path(), "w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    assert identity.employee_id_for(username="thrilok") is None


def test_registry_absent_means_nobody_is_enrolled_rather_than_an_error(monkeypatch, tmp_path):
    monkeypatch.setenv("EMPLOYEE_IDS_FILE", str(tmp_path / "missing.json"))
    assert identity.all_employees() == []
    assert identity.employee_id_for(username="thrilok") is None


def test_assignment_requires_something_to_identify_the_person_by():
    employee_id, error = identity.assign_employee_id(display_name="Nameless Login")
    assert employee_id is None
    assert "username or a reference" in error


def test_role_is_never_part_of_identity():
    """Scoping by role was explicitly rejected: a second admin would inherit the
    rule. Nothing in a stored employee record mentions a role at all."""
    _seed()
    for row in identity.all_employees():
        assert "role" not in row
        assert "admin" not in json.dumps(row).lower()
