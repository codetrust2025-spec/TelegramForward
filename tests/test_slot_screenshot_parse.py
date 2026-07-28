from features.slot_screenshot_parse import _infer_year, parse_invite_text


def test_google_calendar_yearless_day_month_24h_range() -> None:
    parsed = parse_invite_text(
        "Mon, 27 Jul + 14:30 - 15:00\n"
        "#Personal# TCS Interview Invite-EP2026CN7386704\n"
        "Microsoft Teams Meeting"
    )

    expected_year = _infer_year(7, 27)
    assert parsed["date"] == f"{expected_year}-07-27"
    assert parsed["time"] == "14:30"
    assert parsed["time_end"] == "15:00"
    assert parsed["platform"] == "teams"


def test_combined_date_time_does_not_parse_date_as_time_range() -> None:
    parsed = parse_invite_text(
        "Interview Invite: Sakthivel | Candidate ID: 1010934472\n"
        "Tomorrow + 10:30AM ~ 11:15AM\n"
        "Meeting Date and Time: 25-07-2026 10:30 IST\n"
        "Microsoft Teams Meeting"
    )

    assert parsed["date"] == "2026-07-25"
    assert parsed["time"] == "10:30"
    assert parsed["time_end"] == "11:15"


def test_date_after_time_label_is_never_a_time_range() -> None:
    parsed = parse_invite_text(
        "Candidate ID: 1010934472\n"
        "Meeting Date and Time: 25-07-2026\n"
    )

    assert parsed["date"] == "2026-07-25"
    assert parsed["time"] == ""
    assert parsed["time_end"] == ""


def test_google_calendar_yearless_day_month_accepts_ordinal() -> None:
    parsed = parse_invite_text("Mon, 27th Jul • 14:30 - 15:00")

    assert parsed["date"].endswith("-07-27")
    assert parsed["time"] == "14:30"
    assert parsed["time_end"] == "15:00"
