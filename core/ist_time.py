"""India Standard Time helpers — calendar-day boundaries for daily stats."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

APP_TIMEZONE = "Asia/Kolkata"

try:
    from zoneinfo import ZoneInfo

    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    # Fixed offset — India has no DST; safe when tzdata is unavailable (e.g. some Windows installs).
    IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def ist_now(now: float | None = None) -> datetime:
    return datetime.fromtimestamp(now or time.time(), tz=IST)


def ist_date_str(now: float | None = None) -> str:
    return ist_now(now).strftime("%Y-%m-%d")


def ist_day_start_ts(now: float | None = None) -> float:
    """Unix timestamp for 00:00:00 IST on the current IST calendar day."""
    dt = ist_now(now)
    start = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.timestamp()


def ist_day_start_iso(now: float | None = None) -> str:
    return ist_now(now).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
