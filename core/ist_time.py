"""Display timestamps in India Standard Time (IST) for UI and exports."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def _to_ist(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)


def format_ist_datetime(
    value: datetime | float | int | str | None,
    *,
    with_seconds: bool = False,
    with_year: bool = True,
) -> str:
    """Human-readable IST, e.g. 03 Jun 2026, 01:12 pm."""
    if value is None:
        return "—"
    if isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
    elif isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith(" UTC"):
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        elif text.endswith(" IST"):
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M IST").replace(tzinfo=IST)
        else:
            s = text.replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
    ist = _to_ist(dt)
    fmt = "%d %b"
    if with_year:
        fmt += " %Y"
    fmt += ", %I:%M:%S %p" if with_seconds else ", %I:%M %p"
    return ist.strftime(fmt).lstrip("0").replace(" 0", " ", 1)


def format_ist_storage_label(value: datetime | float | None = None) -> str:
    """Legacy storage label: YYYY-MM-DD HH:MM IST."""
    if value is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
    else:
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return _to_ist(dt).strftime("%Y-%m-%d %H:%M IST")


def format_ist_iso(value: datetime | float | None = None) -> str:
    """ISO with IST offset for API fields shown in UI."""
    if value is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
    else:
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return _to_ist(dt).isoformat(timespec="seconds")
