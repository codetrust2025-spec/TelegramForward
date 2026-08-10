"""Attendance calendar and shift policy — configuration, never code.

Working weekdays and holidays are deliberately *not* hard-coded. A six-day week
is as plausible as a five-day one here, holidays differ by state and by year,
and a wrong denominator silently changes every attendance percentage. So the
calendar lives in operational configuration and this module refuses to invent
one: with no configuration, ``is_configured()`` is False and callers must say so
rather than guess.

Shipped shape: ``data/attendance_config.example.json``.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, time, timedelta, timezone

from core.config import DATA_DIR

_FILE = os.path.join(DATA_DIR, "attendance_config.json")
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# India Standard Time has no daylight saving, so a fixed offset is exact rather
# than an approximation. Used when the host has no tz database (Windows).
_IST = timezone(timedelta(hours=5, minutes=30), "IST")

DEFAULT_STATES = ("early", "on_time", "grace", "late")


def _config_path() -> str:
    return os.environ.get("ATTENDANCE_CONFIG_FILE") or _FILE


def ist_timezone():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("Asia/Kolkata")
    except Exception:  # pragma: no cover - depends on host tzdata
        return _IST


def now_ist() -> datetime:
    return datetime.now(timezone.utc).astimezone(ist_timezone())


def ist_date_str(moment: datetime | None = None) -> str:
    """The IST calendar day. This is the attendance day boundary.

    Using UTC here would roll the day over at 05:30 IST — in the middle of the
    morning that this feature exists to record.
    """
    return (moment or now_ist()).astimezone(ist_timezone()).strftime("%Y-%m-%d")


def _read() -> dict:
    try:
        with open(_config_path(), encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _weekdays(raw: object) -> list[int]:
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw:
        try:
            day = int(item)
        except (TypeError, ValueError):
            continue
        if 0 <= day <= 6 and day not in out:
            out.append(day)
    return sorted(out)


def _holidays(raw: object) -> set[str]:
    if not isinstance(raw, list):
        return set()
    return {str(item).strip() for item in raw if _DATE_RE.fullmatch(str(item).strip())}


def _clock(raw: object, fallback: str) -> str:
    value = str(raw or "").strip()
    return value if _TIME_RE.fullmatch(value) else fallback


def _positive_int(raw: object, fallback: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return fallback
    return value if value >= 0 else fallback


def load_config() -> dict:
    """Effective configuration, with ``configured`` telling callers whether a
    calendar actually exists."""
    raw = _read()
    weekdays = _weekdays(raw.get("working_weekdays"))
    credited = [
        state
        for state in (raw.get("credited_states") or ["early", "on_time", "grace"])
        if state in DEFAULT_STATES
    ]
    return {
        "configured": bool(weekdays),
        "working_weekdays": weekdays,
        "holidays": sorted(_holidays(raw.get("holidays"))),
        "shift_start": _clock(raw.get("shift_start"), "09:30"),
        "grace_minutes": _positive_int(raw.get("grace_minutes"), 15),
        "early_threshold_minutes": _positive_int(raw.get("early_threshold_minutes"), 30),
        "credited_states": credited or ["early", "on_time", "grace"],
        "office_ip_allowlist": [
            str(item).strip()
            for item in (raw.get("office_ip_allowlist") or [])
            if str(item).strip()
        ],
        "trusted_proxy_hops": _positive_int(raw.get("trusted_proxy_hops"), 1),
        # Which immediate peers are allowed to have their X-Forwarded-For
        # believed. Defaults to loopback because that is where nginx connects
        # from; a request arriving from anywhere else did not come through the
        # proxy and its forwarding headers are self-reported.
        "trusted_proxy_ips": [
            str(item).strip()
            for item in (raw.get("trusted_proxy_ips") or ["127.0.0.1", "::1"])
            if str(item).strip()
        ],
    }


def is_configured() -> bool:
    return load_config()["configured"]


def save_config(patch: dict) -> dict:
    """Merge an admin edit over the stored configuration and persist it."""
    current = _read()
    if not isinstance(patch, dict):
        return load_config()
    allowed = {
        "working_weekdays",
        "holidays",
        "shift_start",
        "grace_minutes",
        "early_threshold_minutes",
        "credited_states",
        "office_ip_allowlist",
        "trusted_proxy_hops",
        "trusted_proxy_ips",
    }
    for key, value in patch.items():
        if key in allowed:
            current[key] = value

    path = _config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(current, handle, indent=2, ensure_ascii=False)
    return load_config()


def shift_start_time(config: dict | None = None) -> time:
    cfg = config or load_config()
    hour, minute = cfg["shift_start"].split(":")
    return time(int(hour), int(minute))


def is_working_day(day: str, config: dict | None = None) -> bool:
    """A configured weekday that is not a configured holiday."""
    cfg = config or load_config()
    if not cfg["configured"]:
        return False
    if not _DATE_RE.fullmatch(str(day)):
        return False
    if str(day) in set(cfg["holidays"]):
        return False
    return date.fromisoformat(str(day)).weekday() in cfg["working_weekdays"]


def scheduled_working_days(month: str, *, through: str | None = None, config: dict | None = None) -> list[str]:
    """Every scheduled working day in ``YYYY-MM``, up to and including ``through``.

    Percentages are always measured against days that have actually elapsed, so
    a month in progress is not scored against days nobody has worked yet.
    """
    cfg = config or load_config()
    if not cfg["configured"] or not re.fullmatch(r"\d{4}-\d{2}", str(month or "")):
        return []

    year, month_number = (int(part) for part in str(month).split("-"))
    if not 1 <= month_number <= 12:
        return []

    cursor = date(year, month_number, 1)
    limit = date(year + (month_number == 12), (month_number % 12) + 1, 1) - timedelta(days=1)
    if through and _DATE_RE.fullmatch(str(through)):
        limit = min(limit, date.fromisoformat(str(through)))

    days = []
    while cursor <= limit:
        iso = cursor.isoformat()
        if is_working_day(iso, cfg):
            days.append(iso)
        cursor += timedelta(days=1)
    return days


def classify_arrival(started_at: datetime, config: dict | None = None) -> tuple[str, int]:
    """Bucket an arrival into early / on_time / grace / late.

    Returns the state and minutes relative to shift start (negative = before).
    The four bands are contiguous and non-overlapping, so every arrival lands in
    exactly one.
    """
    cfg = config or load_config()
    local = started_at.astimezone(ist_timezone())
    start = shift_start_time(cfg)
    reference = local.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
    delta_minutes = int((local - reference).total_seconds() // 60)

    if delta_minutes < -cfg["early_threshold_minutes"]:
        return "early", delta_minutes
    if delta_minutes <= 0:
        return "on_time", delta_minutes
    if delta_minutes <= cfg["grace_minutes"]:
        return "grace", delta_minutes
    return "late", delta_minutes
