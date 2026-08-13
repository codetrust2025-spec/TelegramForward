"""A decorated but unambiguous timezone must not block booking.

Altimetrik message 5494b05a produced a correct INTERVIEW_CONFIRMED event, then
auto-booking blocked with INVALID_TIMEZONE because Ollama returned
"IST (Asia/Kolkata)" — a valid zone carrying an annotation the IANA parser
rejects. Decoration is not ambiguity; a genuinely unknown zone still blocks.
"""

import pytest
from zoneinfo import ZoneInfo

from services.interview_auto_booking import BookingValidationError, validate_timezone


@pytest.mark.parametrize("raw", [
    "Asia/Kolkata", "America/New_York", "Europe/London", "Asia/Tokyo", "UTC",
])
def test_valid_iana_zones_pass_through_unchanged(raw):
    assert validate_timezone(raw) == ZoneInfo(raw)


@pytest.mark.parametrize("raw", [
    "IST", "ist", " IST ",
    "Asia/Calcutta", "ASIA/CALCUTTA",          # older name for the same zone
    "IST (Asia/Kolkata)", "IST(Asia/Kolkata)", "IST ( Asia/Kolkata )",
    "Asia/Kolkata (IST)",                       # annotation the other way round
])
def test_ist_aliases_and_annotated_zones_resolve(raw):
    assert validate_timezone(raw) == ZoneInfo("Asia/Kolkata")


@pytest.mark.parametrize("raw", [
    "Not/AZone", "Mars/Olympus", "XYZ", "Kolkata", "GMT+5:30 maybe",
])
def test_unknown_timezones_are_never_guessed(raw):
    with pytest.raises(BookingValidationError) as err:
        validate_timezone(raw)
    assert err.value.args[0] == "INVALID_TIMEZONE"


@pytest.mark.parametrize("raw", ["", "   ", None])
def test_a_missing_timezone_is_reported_as_missing(raw):
    with pytest.raises(BookingValidationError) as err:
        validate_timezone(raw)
    assert err.value.args[0] == "MISSING_TIMEZONE"


def test_the_resolved_zone_carries_the_right_offset_for_rollover():
    """Rollover correctness depends on the real offset, not the label."""
    from datetime import datetime
    zone = validate_timezone("IST (Asia/Kolkata)")
    local = datetime(2026, 8, 14, 14, 0, tzinfo=zone)
    assert local.utcoffset().total_seconds() == 5.5 * 3600
    assert local.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M") == "2026-08-14 08:30"
    # a late-evening IST slot is the previous day in UTC
    late = datetime(2026, 8, 14, 0, 30, tzinfo=zone)
    assert late.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d") == "2026-08-13"
