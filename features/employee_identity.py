"""Immutable employee identity, independent of display name, login or role.

Until now a handler was only ``{username, reference, password}``, and money was
bucketed by the lowercased ``reference`` — that is, by a *name*. That is fine
for showing a row on a screen and wrong for scoping a payout rule: rename the
reference and the rule silently follows the name to whoever holds it next.

So an employee here has an ``employee_id`` that is assigned once, never derived
from anything a person can change, and never reused. Usernames and references
become *aliases* of that id. Renaming somebody adds an alias; it does not create
a new employee, and it does not move a rule.

Backward compatible by construction: nothing else in the app has to know about
this file. A handler with no registry entry simply has no employee id, and
callers are expected to treat that as "not enrolled" rather than an error.

The registry is operational data under ``DATA_DIR`` — like handler salaries, it
is managed on the host and never shipped in a release. See
``data/employee_ids.example.json`` for the shape.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone

from core.config import DATA_DIR

_FILE = os.path.join(DATA_DIR, "employee_ids.json")
_ID_RE = re.compile(r"^EMP-(\d{4,})$")


def _store_path() -> str:
    return os.environ.get("EMPLOYEE_IDS_FILE") or _FILE


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


def _load() -> dict:
    """Load the whole payload, not just the rows.

    The top level also carries ``sequence``, the high-water mark of assigned
    ids, so unrelated keys must survive a read/write cycle.
    """
    try:
        with open(_store_path(), encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"employees": []}
    if not isinstance(payload, dict):
        return {"employees": []}
    employees = payload.get("employees")
    payload["employees"] = [row for row in employees if isinstance(row, dict)] if isinstance(employees, list) else []
    return payload


def _save(payload: dict) -> None:
    """Write atomically so a crash cannot leave a half-written registry."""
    path = _store_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    directory = os.path.dirname(path) or "."
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp"
    )
    try:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.flush()
        os.fsync(handle.fileno())
        handle.close()
        os.replace(handle.name, path)
    finally:
        if os.path.exists(handle.name):
            os.unlink(handle.name)


def _aliases(record: dict, field: str) -> set[str]:
    raw = record.get(field)
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return set()
    return {_norm(item) for item in raw if _norm(item)}


def all_employees() -> list[dict]:
    """Every registered employee, newest id last."""
    rows = [row for row in _load()["employees"] if _ID_RE.fullmatch(str(row.get("employee_id") or ""))]
    rows.sort(key=lambda row: str(row.get("employee_id")))
    return rows


def employee_record(employee_id: str) -> dict | None:
    wanted = str(employee_id or "").strip().upper()
    for row in all_employees():
        if str(row.get("employee_id")).upper() == wanted:
            return row
    return None


def is_active(record: dict | None) -> bool:
    """Absent ``active`` means active — a registry written by hand should not
    have to opt every row in."""
    if not record:
        return False
    return record.get("active", True) is not False


def employee_id_for(username: object = None, reference: object = None) -> str | None:
    """Resolve an employee id from a login or an earnings reference.

    Username is checked first: it is what the person actually signed in as, and
    references are shared with legacy earnings rows where spellings drift.
    """
    user_key = _norm(username)
    ref_key = _norm(reference)
    rows = [row for row in all_employees() if is_active(row)]

    if user_key:
        for row in rows:
            if user_key in _aliases(row, "usernames"):
                return str(row["employee_id"])
    if ref_key:
        for row in rows:
            if ref_key in _aliases(row, "references"):
                return str(row["employee_id"])
    return None


def employee_id_for_profile(profile: dict | None) -> str | None:
    """Resolve from a dashboard auth profile."""
    if not isinstance(profile, dict):
        return None
    return employee_id_for(profile.get("username"), profile.get("reference"))


def _next_employee_id(payload: dict) -> str:
    """Monotonic, never reused — a retired id is not handed to a new joiner.

    Derived from a persisted high-water mark rather than from the rows that
    happen to be present, because a row can be removed. If it were derived from
    the rows, deleting an employee would release their id to the next joiner,
    and every attendance record or payout rule still holding that id would
    quietly start pointing at a different person.
    """
    highest = 0
    for row in payload.get("employees", []):
        match = _ID_RE.fullmatch(str(row.get("employee_id") or ""))
        if match:
            highest = max(highest, int(match.group(1)))
    try:
        highest = max(highest, int(payload.get("sequence") or 0))
    except (TypeError, ValueError):
        pass
    return f"EMP-{highest + 1:04d}"


def assign_employee_id(
    *,
    display_name: str,
    username: str | None = None,
    reference: str | None = None,
) -> tuple[str | None, str | None]:
    """Register a new employee. Returns ``(employee_id, error)``.

    Refuses to attach an alias that already belongs to somebody else, because
    two employees sharing a login or a reference would make every downstream
    attendance and payout figure ambiguous.
    """
    name = str(display_name or "").strip()
    if not name:
        return None, "Display name is required"
    user_key = _norm(username)
    ref_key = _norm(reference)
    if not user_key and not ref_key:
        return None, "A username or a reference is required to identify the employee"

    payload = _load()
    rows = payload["employees"]
    for row in rows:
        if user_key and user_key in _aliases(row, "usernames"):
            return None, f"Username '{username}' already belongs to {row.get('employee_id')}"
        if ref_key and ref_key in _aliases(row, "references"):
            return None, f"Reference '{reference}' already belongs to {row.get('employee_id')}"

    employee_id = _next_employee_id(payload)
    rows.append(
        {
            "employee_id": employee_id,
            "display_name": name,
            "usernames": [user_key] if user_key else [],
            "references": [ref_key] if ref_key else [],
            "assigned_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        }
    )
    # Bump the high-water mark so the id is spent even if the row is later removed.
    payload["sequence"] = int(_ID_RE.fullmatch(employee_id).group(1))
    _save(payload)
    return employee_id, None


def add_alias(employee_id: str, *, username: str | None = None, reference: str | None = None) -> str | None:
    """Attach a renamed login or reference to an existing employee.

    This is the rename path: the id stays, so any rule scoped to it keeps
    pointing at the same person.
    """
    payload = _load()
    rows = payload["employees"]
    wanted = str(employee_id or "").strip().upper()
    target = next((row for row in rows if str(row.get("employee_id", "")).upper() == wanted), None)
    if target is None:
        return "Unknown employee id"

    user_key = _norm(username)
    ref_key = _norm(reference)
    if not user_key and not ref_key:
        return "Nothing to add"

    for row in rows:
        if row is target:
            continue
        if user_key and user_key in _aliases(row, "usernames"):
            return f"Username '{username}' already belongs to {row.get('employee_id')}"
        if ref_key and ref_key in _aliases(row, "references"):
            return f"Reference '{reference}' already belongs to {row.get('employee_id')}"

    if user_key:
        target.setdefault("usernames", [])
        if user_key not in {_norm(u) for u in target["usernames"]}:
            target["usernames"].append(user_key)
    if ref_key:
        target.setdefault("references", [])
        if ref_key not in {_norm(r) for r in target["references"]}:
            target["references"].append(ref_key)
    _save(payload)
    return None
