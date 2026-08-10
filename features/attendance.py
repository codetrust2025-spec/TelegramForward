"""Daily attendance records and monthly attendance percentages.

One record per employee per IST calendar day. Recording is idempotent: the
second Start Work of the day returns the first record untouched, because the
first click is the one that says when the person actually arrived.

This module computes attendance percentages and nothing else. It does not touch
salary, commission or any payout — attendance-linked pay is a separate, still
undecided policy, and the commission source-of-truth discrepancy has to be
settled before a percentage is allowed anywhere near money.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone

from core.config import DATA_DIR
from features import attendance_config as cfg

_DIR = os.path.join(DATA_DIR, "attendance")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def _dir() -> str:
    return os.environ.get("ATTENDANCE_DIR") or _DIR


def _month_of(day: str) -> str:
    return str(day)[:7]


def _path(month: str) -> str:
    return os.path.join(_dir(), f"{month}.json")


def _load_month(month: str) -> list[dict]:
    if not _MONTH_RE.fullmatch(str(month or "")):
        return []
    try:
        with open(_path(month), encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return []
    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list):
        return []
    return [row for row in records if isinstance(row, dict)]


def _save_month(month: str, records: list[dict]) -> None:
    directory = _dir()
    os.makedirs(directory, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp"
    )
    try:
        json.dump({"month": month, "records": records}, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(handle.name, _path(month))
    finally:
        if os.path.exists(handle.name):
            os.unlink(handle.name)


def _sanitise_device(device: object) -> dict:
    """Keep a small, fixed set of self-reported fields.

    Device metadata is a hint about which machine was used, never evidence of
    where it was: everything here is written by the page and therefore by the
    person sitting at it. The office check is the server-side IP one.
    """
    if not isinstance(device, dict):
        return {}
    keys = ("user_agent", "platform", "language", "timezone", "screen")
    return {key: str(device.get(key) or "")[:300] for key in keys if device.get(key)}


def get_record(employee_id: str, day: str) -> dict | None:
    wanted = str(employee_id or "").strip().upper()
    for row in _load_month(_month_of(day)):
        if str(row.get("employee_id", "")).upper() == wanted and row.get("date") == day:
            return row
    return None


def records_for_month(month: str, employee_id: str | None = None) -> list[dict]:
    rows = _load_month(month)
    if employee_id:
        wanted = str(employee_id).strip().upper()
        rows = [r for r in rows if str(r.get("employee_id", "")).upper() == wanted]
    return sorted(rows, key=lambda r: (str(r.get("date")), str(r.get("employee_id"))))


def record_start(
    *,
    employee_id: str,
    device: object = None,
    network: dict | None = None,
    started_at: datetime | None = None,
) -> tuple[dict, bool]:
    """Record the start of a working day. Returns ``(record, created)``.

    ``created`` is False when the day already had a record — the caller should
    treat that as success and stop showing the prompt, not as an error.
    """
    moment = (started_at or cfg.now_ist()).astimezone(cfg.ist_timezone())
    day = cfg.ist_date_str(moment)
    existing = get_record(employee_id, day)
    if existing:
        return existing, False

    config = cfg.load_config()
    state, offset = cfg.classify_arrival(moment, config)
    record = {
        "employee_id": str(employee_id).strip().upper(),
        "date": day,
        "started_at": moment.isoformat(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "state": state,
        "minutes_from_shift_start": offset,
        "shift_start": config["shift_start"],
        "device": _sanitise_device(device),
        "network": network or {},
        "override": None,
    }
    month = _month_of(day)
    rows = _load_month(month)
    rows.append(record)
    _save_month(month, rows)
    return record, True


def apply_override(
    *,
    employee_id: str,
    day: str,
    reason: str,
    approved_by: str,
    approved_by_employee_id: str | None = None,
    original_network: dict | None = None,
    started_at: datetime | None = None,
) -> tuple[dict | None, str | None]:
    """Admin-authorised attendance for a day the network check could not pass.

    The audit trail is the point: who approved it, why, when, and what the
    network check actually said at the time. An override that only flipped a
    boolean would be indistinguishable from a normal day a month later.
    """
    if not _DATE_RE.fullmatch(str(day or "")):
        return None, "A valid date (YYYY-MM-DD) is required"
    if not str(reason or "").strip():
        return None, "A reason is required"
    if not str(approved_by or "").strip():
        return None, "An approving administrator is required"
    if not str(employee_id or "").strip():
        return None, "An employee id is required"

    config = cfg.load_config()
    if started_at is not None:
        moment = started_at.astimezone(cfg.ist_timezone())
    else:
        start = cfg.shift_start_time(config)
        moment = datetime.fromisoformat(f"{day}T{start.strftime('%H:%M')}:00").replace(
            tzinfo=cfg.ist_timezone()
        )

    audit = {
        "reason": str(reason).strip()[:500],
        "approved_by": str(approved_by).strip(),
        "approved_by_employee_id": (str(approved_by_employee_id).strip().upper() if approved_by_employee_id else None),
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "original_network_result": original_network or {},
    }

    month = _month_of(day)
    rows = _load_month(month)
    wanted = str(employee_id).strip().upper()
    for row in rows:
        if str(row.get("employee_id", "")).upper() == wanted and row.get("date") == day:
            row["override"] = audit
            _save_month(month, rows)
            return row, None

    state, offset = cfg.classify_arrival(moment, config)
    record = {
        "employee_id": wanted,
        "date": day,
        "started_at": moment.isoformat(),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "state": state,
        "minutes_from_shift_start": offset,
        "shift_start": config["shift_start"],
        "device": {},
        "network": original_network or {},
        "override": audit,
    }
    rows.append(record)
    _save_month(month, rows)
    return record, None


def is_credited(record: dict, config: dict | None = None) -> bool:
    """Whether a record counts toward the attendance percentage."""
    configuration = config or cfg.load_config()
    return str(record.get("state")) in set(configuration["credited_states"])


def employee_month_summary(
    employee_id: str,
    month: str,
    *,
    through: str | None = None,
    config: dict | None = None,
) -> dict:
    """Attendance for one employee in one month, with the working shown.

    ``percentage`` is credited days over *elapsed* scheduled working days, so a
    month in progress is not scored against days that have not happened.
    """
    configuration = config or cfg.load_config()
    limit = through or cfg.ist_date_str()
    scheduled = cfg.scheduled_working_days(month, through=limit, config=configuration)
    scheduled_set = set(scheduled)

    rows = records_for_month(month, employee_id)
    on_scheduled = [r for r in rows if r.get("date") in scheduled_set]
    credited = [r for r in on_scheduled if is_credited(r, configuration)]

    by_state = {state: 0 for state in cfg.DEFAULT_STATES}
    for row in on_scheduled:
        state = str(row.get("state"))
        if state in by_state:
            by_state[state] += 1

    scheduled_count = len(scheduled)
    percentage = round(len(credited) * 100.0 / scheduled_count, 2) if scheduled_count else 0.0

    return {
        "employee_id": str(employee_id).strip().upper(),
        "month": month,
        "configured": configuration["configured"],
        "scheduled_working_days": scheduled_count,
        "scheduled_through": limit,
        "days_recorded": len(on_scheduled),
        "days_credited": len(credited),
        "days_absent": max(0, scheduled_count - len(on_scheduled)),
        "by_state": by_state,
        "credited_states": list(configuration["credited_states"]),
        "overrides": sum(1 for r in on_scheduled if r.get("override")),
        "off_schedule_records": len(rows) - len(on_scheduled),
        "attendance_percentage": percentage,
    }


def month_summary(month: str, employee_ids: list[str], *, through: str | None = None) -> dict:
    """Per-employee attendance for the HR view."""
    configuration = cfg.load_config()
    limit = through or cfg.ist_date_str()
    return {
        "month": month,
        "configured": configuration["configured"],
        "scheduled_through": limit,
        "scheduled_working_days": len(
            cfg.scheduled_working_days(month, through=limit, config=configuration)
        ),
        "employees": [
            employee_month_summary(employee_id, month, through=limit, config=configuration)
            for employee_id in employee_ids
        ],
    }
