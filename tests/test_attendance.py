"""Attendance capture: day boundaries, arrival states, office network, overrides.

The percentage these produce is intended to drive pay eventually, so the cases
that matter are the ones where being wrong is invisible: a day counted twice, a
day scored against a holiday, an arrival that lands in two states, or a record
that claims an office IP the client supplied itself.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from features import attendance, office_network
from features import attendance_config as cfg

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    config = {
        "working_weekdays": [0, 1, 2, 3, 4, 5],  # Mon-Sat
        "holidays": ["2026-08-15"],
        "shift_start": "09:30",
        "grace_minutes": 15,
        "early_threshold_minutes": 30,
        "credited_states": ["early", "on_time", "grace"],
        "office_ip_allowlist": ["203.0.113.0/24", "198.51.100.7"],
        "trusted_proxy_hops": 1,
    }
    config_file = tmp_path / "attendance_config.json"
    config_file.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setenv("ATTENDANCE_CONFIG_FILE", str(config_file))
    monkeypatch.setenv("ATTENDANCE_DIR", str(tmp_path / "attendance"))
    return config_file


class FakeHeaders(dict):
    def get(self, key, default=None):  # headers are case-insensitive
        return super().get(str(key).lower(), default)


class FakeRequest:
    # The default peer is loopback because that is what nginx connects from:
    # `proxy_pass http://127.0.0.1:8000`. A test that wants to simulate a
    # request which skipped the proxy passes a public peer explicitly.
    def __init__(self, *, forwarded=None, peer="127.0.0.1"):
        headers = {}
        if forwarded is not None:
            headers["x-forwarded-for"] = forwarded
        self.headers = FakeHeaders(headers)
        self.client = type("C", (), {"host": peer})()


def at(day: str, clock: str) -> datetime:
    hour, minute = (int(part) for part in clock.split(":"))
    return datetime.fromisoformat(f"{day}T00:00:00").replace(hour=hour, minute=minute, tzinfo=IST)


# ── arrival states ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "clock,expected",
    [
        ("08:30", "early"),    # 60 min before, past the 30 min early threshold
        ("09:00", "on_time"),  # exactly on the threshold edge, still on time
        ("09:29", "on_time"),
        ("09:30", "on_time"),  # the shift start minute itself is not late
        ("09:31", "grace"),
        ("09:45", "grace"),    # last grace minute
        ("09:46", "late"),
        ("11:00", "late"),
    ],
)
def test_arrival_states_are_contiguous_and_exclusive(clock, expected):
    state, _ = cfg.classify_arrival(at("2026-08-10", clock))
    assert state == expected


def test_every_minute_of_the_morning_lands_in_exactly_one_state():
    """No gaps and no overlaps — a gap would silently drop somebody's day."""
    seen = set()
    for minute in range(6 * 60, 12 * 60):
        moment = at("2026-08-10", f"{minute // 60:02d}:{minute % 60:02d}")
        state, _ = cfg.classify_arrival(moment)
        assert state in cfg.DEFAULT_STATES
        seen.add(state)
    assert seen == set(cfg.DEFAULT_STATES)


# ── daily idempotency ────────────────────────────────────────────────────────


def test_second_start_of_the_day_returns_the_first_record_unchanged():
    first, created_first = attendance.record_start(
        employee_id="EMP-0001", started_at=at("2026-08-10", "09:28")
    )
    second, created_second = attendance.record_start(
        employee_id="EMP-0001", started_at=at("2026-08-10", "17:45")
    )

    assert created_first is True
    assert created_second is False
    assert second["started_at"] == first["started_at"]
    assert second["state"] == "on_time"  # not overwritten by the later click
    assert len(attendance.records_for_month("2026-08", "EMP-0001")) == 1


def test_two_employees_on_the_same_day_are_separate_records():
    attendance.record_start(employee_id="EMP-0001", started_at=at("2026-08-10", "09:00"))
    _, created = attendance.record_start(employee_id="EMP-0002", started_at=at("2026-08-10", "09:00"))
    assert created is True
    assert len(attendance.records_for_month("2026-08")) == 2


# ── IST day rollover ─────────────────────────────────────────────────────────


def test_the_attendance_day_rolls_over_at_ist_midnight_not_utc():
    """23:00 IST is still 17:30 UTC on the same date — a UTC boundary would put
    an evening login on the previous working day."""
    late_evening = datetime(2026, 8, 10, 23, 0, tzinfo=IST)
    assert cfg.ist_date_str(late_evening) == "2026-08-10"
    assert cfg.ist_date_str(late_evening.astimezone(timezone.utc)) == "2026-08-10"


def test_a_new_ist_day_allows_a_new_record():
    attendance.record_start(employee_id="EMP-0001", started_at=at("2026-08-10", "09:00"))
    _, created = attendance.record_start(
        employee_id="EMP-0001", started_at=at("2026-08-11", "09:00")
    )
    assert created is True
    assert len(attendance.records_for_month("2026-08", "EMP-0001")) == 2


def test_just_after_ist_midnight_belongs_to_the_new_day():
    just_after = datetime(2026, 8, 11, 0, 5, tzinfo=IST)
    assert cfg.ist_date_str(just_after) == "2026-08-11"


# ── working days, holidays, denominator ──────────────────────────────────────


def test_sunday_is_not_a_working_day_under_a_six_day_week():
    assert cfg.is_working_day("2026-08-10") is True   # Monday
    assert cfg.is_working_day("2026-08-15") is False  # configured holiday
    assert cfg.is_working_day("2026-08-16") is False  # Sunday


def test_configured_holiday_is_excluded_from_the_denominator():
    days = cfg.scheduled_working_days("2026-08", through="2026-08-31")
    assert "2026-08-15" not in days
    assert "2026-08-16" not in days  # Sunday
    assert "2026-08-10" in days


def test_the_working_week_is_configuration_not_code(isolated):
    """Switching to Mon-Fri must move the denominator, with no code change."""
    six_day = len(cfg.scheduled_working_days("2026-08", through="2026-08-31"))

    isolated.write_text(
        json.dumps({"working_weekdays": [0, 1, 2, 3, 4], "holidays": []}), encoding="utf-8"
    )
    five_day = cfg.scheduled_working_days("2026-08", through="2026-08-31")

    assert len(five_day) == 21  # August 2026 has 21 weekdays
    assert six_day > len(five_day)
    assert "2026-08-01" not in five_day  # Saturday
    assert "2026-08-31" in five_day  # Monday


def test_nothing_is_scheduled_when_no_calendar_is_configured(isolated):
    isolated.write_text(json.dumps({}), encoding="utf-8")
    assert cfg.is_configured() is False
    assert cfg.scheduled_working_days("2026-08", through="2026-08-31") == []
    assert cfg.is_working_day("2026-08-10") is False


# ── percentage ───────────────────────────────────────────────────────────────


def test_percentage_is_credited_days_over_elapsed_scheduled_days():
    for day in ("2026-08-03", "2026-08-04", "2026-08-05"):
        attendance.record_start(employee_id="EMP-0001", started_at=at(day, "09:00"))

    summary = attendance.employee_month_summary("EMP-0001", "2026-08", through="2026-08-05")
    # Mon 3rd, Tue 4th, Wed 5th are all scheduled; Sat 1st is too, Sun 2nd is not.
    assert summary["scheduled_working_days"] == 4
    assert summary["days_credited"] == 3
    assert summary["days_absent"] == 1
    assert summary["attendance_percentage"] == 75.0


def test_an_in_progress_month_is_not_scored_against_days_that_have_not_happened(monkeypatch):
    """Nobody is absent for a day that has not arrived.

    On the 10th, the denominator must stop at the 10th. Counting the rest of the
    month would show a person at a fraction of their real attendance for most of
    every month, and that number is meant to inform pay.
    """
    for day in ("2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07",
                "2026-08-08", "2026-08-10"):
        attendance.record_start(employee_id="EMP-0001", started_at=at(day, "09:00"))

    # Pin "today" only for the summary; pinning it earlier would also pin the
    # day each record was written to, collapsing them all onto one date.
    monkeypatch.setattr(cfg, "ist_date_str", lambda moment=None: "2026-08-10")
    summary = attendance.employee_month_summary("EMP-0001", "2026-08")

    # Aug 1 (Sat) through Aug 10 (Mon), minus the two Sundays = 8 scheduled.
    assert summary["scheduled_working_days"] == 8
    assert summary["scheduled_through"] == "2026-08-10"
    assert summary["days_recorded"] == 7
    assert summary["days_absent"] == 1  # only Aug 1, not the rest of the month
    assert summary["attendance_percentage"] == 87.5


def test_a_completed_month_is_scored_against_its_whole_calendar(monkeypatch):
    """Once the month is over, the full configured calendar is the denominator."""
    monkeypatch.setattr(cfg, "ist_date_str", lambda moment=None: "2026-09-15")
    summary = attendance.employee_month_summary("EMP-0001", "2026-08")

    full_august = len(cfg.scheduled_working_days("2026-08", through="2026-08-31"))
    assert summary["scheduled_working_days"] == full_august
    assert summary["scheduled_working_days"] == 25  # 26 Mon-Sat days, less one holiday


def test_late_days_are_recorded_but_not_credited_by_default():
    attendance.record_start(employee_id="EMP-0001", started_at=at("2026-08-03", "11:00"))
    summary = attendance.employee_month_summary("EMP-0001", "2026-08", through="2026-08-03")
    assert summary["days_recorded"] == 1
    assert summary["days_credited"] == 0
    assert summary["by_state"]["late"] == 1
    assert summary["attendance_percentage"] == 0.0


def test_which_states_count_is_configuration_not_code(isolated):
    isolated.write_text(
        json.dumps(
            {
                "working_weekdays": [0, 1, 2, 3, 4, 5],
                "shift_start": "09:30",
                "credited_states": ["early", "on_time", "grace", "late"],
            }
        ),
        encoding="utf-8",
    )
    attendance.record_start(employee_id="EMP-0001", started_at=at("2026-08-03", "11:00"))
    summary = attendance.employee_month_summary("EMP-0001", "2026-08", through="2026-08-03")
    assert summary["days_credited"] == 1


def test_a_record_on_a_holiday_does_not_inflate_the_percentage():
    attendance.record_start(employee_id="EMP-0001", started_at=at("2026-08-15", "09:00"))
    summary = attendance.employee_month_summary("EMP-0001", "2026-08", through="2026-08-15")
    assert summary["off_schedule_records"] == 1
    assert summary["days_credited"] == 0


# ── office network ───────────────────────────────────────────────────────────


def test_office_ip_inside_the_allowlisted_range_is_verified():
    result = office_network.verify(FakeRequest(forwarded="203.0.113.44"))
    assert result["verified"] is True
    assert result["matched_rule"] == "203.0.113.0/24"


def test_ip_outside_the_allowlist_is_rejected():
    result = office_network.verify(FakeRequest(forwarded="8.8.8.8"))
    assert result["verified"] is False
    assert result["reason"] == office_network.NOT_ALLOWLISTED
    assert "office network" in office_network.failure_message(result)


def test_a_client_cannot_spoof_an_office_ip_through_x_forwarded_for():
    """With one proxy in front, only the rightmost hop was added by us.

    A client sending "203.0.113.5, 8.8.8.8" is claiming an office address it
    does not have; the entry nginx appended is the one that counts.
    """
    result = office_network.verify(FakeRequest(forwarded="203.0.113.5, 8.8.8.8"))
    assert result["verified"] is False
    assert result["ip"] == "8.8.8.8"


def test_a_request_that_skipped_the_proxy_cannot_forge_an_office_ip():
    """The app binds 0.0.0.0:8000 with no firewall, so it is reachable directly
    as well as through nginx.

    A request that skipped nginx carries whatever X-Forwarded-For its sender
    typed. Believing it would let anyone record attendance from anywhere with
    one curl flag, so the header is only honoured when the connection came from
    a trusted proxy.
    """
    direct = FakeRequest(forwarded="203.0.113.44", peer="8.8.8.8")
    result = office_network.verify(direct)
    assert result["verified"] is False
    assert result["ip"] == "8.8.8.8"  # the real peer, not the claimed office IP


def test_the_same_header_is_honoured_when_it_arrives_through_the_proxy():
    """The counterpart: identical header, trusted peer, and it works."""
    through_nginx = FakeRequest(forwarded="203.0.113.44", peer="127.0.0.1")
    assert office_network.verify(through_nginx)["verified"] is True


def test_only_configured_proxies_are_trusted(isolated):
    isolated.write_text(
        json.dumps(
            {
                "working_weekdays": [0],
                "office_ip_allowlist": ["203.0.113.0/24"],
                "trusted_proxy_ips": ["10.20.0.5"],
            }
        ),
        encoding="utf-8",
    )
    assert office_network.verify(FakeRequest(forwarded="203.0.113.44", peer="10.20.0.5"))["verified"] is True
    # loopback is no longer trusted once the list is overridden
    assert office_network.verify(FakeRequest(forwarded="203.0.113.44", peer="127.0.0.1"))["verified"] is False


def test_an_empty_allowlist_fails_closed_rather_than_open(isolated):
    isolated.write_text(
        json.dumps({"working_weekdays": [0], "office_ip_allowlist": []}), encoding="utf-8"
    )
    result = office_network.verify(FakeRequest(forwarded="203.0.113.44"))
    assert result["verified"] is False
    assert result["reason"] == office_network.NO_ALLOWLIST


def test_direct_peer_is_used_when_no_proxy_is_in_front(isolated):
    isolated.write_text(
        json.dumps(
            {
                "working_weekdays": [0],
                "office_ip_allowlist": ["198.51.100.7"],
                "trusted_proxy_hops": 0,
            }
        ),
        encoding="utf-8",
    )
    assert office_network.verify(FakeRequest(peer="198.51.100.7")).get("verified") is True
    # ...and the header is ignored entirely at zero hops.
    spoofed = FakeRequest(forwarded="198.51.100.7", peer="8.8.8.8")
    assert office_network.verify(spoofed)["verified"] is False


# ── admin override ───────────────────────────────────────────────────────────


def test_override_creates_a_credited_day_with_a_full_audit_trail():
    original = {"verified": False, "ip": "8.8.8.8", "reason": office_network.NOT_ALLOWLISTED}
    record, error = attendance.apply_override(
        employee_id="EMP-0001",
        day="2026-08-10",
        reason="Office ISP outage, worked from the office",
        approved_by="admin",
        approved_by_employee_id="EMP-0002",
        original_network=original,
    )

    assert error is None
    assert record["override"]["reason"].startswith("Office ISP outage")
    assert record["override"]["approved_by"] == "admin"
    assert record["override"]["approved_by_employee_id"] == "EMP-0002"
    assert record["override"]["approved_at"]
    assert record["override"]["original_network_result"] == original

    summary = attendance.employee_month_summary("EMP-0001", "2026-08", through="2026-08-10")
    assert summary["days_credited"] == 1
    assert summary["overrides"] == 1


def test_override_annotates_an_existing_record_instead_of_duplicating_the_day():
    attendance.record_start(employee_id="EMP-0001", started_at=at("2026-08-10", "11:00"))
    attendance.apply_override(
        employee_id="EMP-0001",
        day="2026-08-10",
        reason="Traffic, approved",
        approved_by="admin",
    )
    rows = attendance.records_for_month("2026-08", "EMP-0001")
    assert len(rows) == 1
    assert rows[0]["override"]["approved_by"] == "admin"
    # The arrival state is preserved: an override authorises the day, it does
    # not rewrite when the person actually arrived.
    assert rows[0]["state"] == "late"


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({"reason": ""}, "reason"),
        ({"approved_by": ""}, "administrator"),
        ({"day": "not-a-date"}, "date"),
        ({"employee_id": ""}, "employee id"),
    ],
)
def test_override_refuses_to_record_an_unattributable_exception(kwargs, expected):
    base = {
        "employee_id": "EMP-0001",
        "day": "2026-08-10",
        "reason": "ISP outage",
        "approved_by": "admin",
    }
    base.update(kwargs)
    record, error = attendance.apply_override(**base)
    assert record is None
    assert expected in error.lower()


# ── device metadata is a hint, not evidence ──────────────────────────────────


def test_device_metadata_is_captured_but_bounded():
    record, _ = attendance.record_start(
        employee_id="EMP-0001",
        started_at=at("2026-08-10", "09:00"),
        device={"user_agent": "x" * 900, "platform": "Win32", "secret": "dropped"},
    )
    assert record["device"]["platform"] == "Win32"
    assert len(record["device"]["user_agent"]) == 300
    assert "secret" not in record["device"]
