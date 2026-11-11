"""Attendance capture and the HR attendance view.

Deliberately contains no payout logic. Attendance percentages are reported here
and consumed by humans; wiring them to commission waits on the commission
source-of-truth decision.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request

from core import dashboard_auth_vps as dashboard_auth
from features import attendance, employee_identity, office_network
from features import attendance_config as cfg
from server import _require_fleet_admin

router = APIRouter()


def _profile(request: Request) -> dict:
    profile = dashboard_auth.operator_profile_from_cookies(dict(request.cookies))
    if not isinstance(profile, dict) or not profile.get("username"):
        raise HTTPException(401, "Authentication required")
    return profile


def _display_name(profile: dict, record: dict | None) -> str:
    if record and record.get("display_name"):
        return str(record["display_name"])
    return str(profile.get("reference") or profile.get("username") or "there")


@router.get("/api/attendance/today")
async def attendance_today(request: Request):
    """Everything the dashboard needs to decide whether to prompt.

    The prompt is a function of server state only — configuration, enrolment,
    the IST day, whether a record already exists — so a page reload or a second
    tab cannot resurrect a prompt the employee has already answered.
    """
    profile = _profile(request)
    config = cfg.load_config()
    employee_id = employee_identity.employee_id_for_profile(profile)
    record = employee_identity.employee_record(employee_id) if employee_id else None
    day = cfg.ist_date_str()
    is_working_day = cfg.is_working_day(day, config)
    today_record = attendance.get_record(employee_id, day) if employee_id else None
    network = office_network.verify(request, config=config)

    return {
        "status": "ok",
        "configured": config["configured"],
        "enrolled": bool(employee_id),
        "employee_id": employee_id,
        "display_name": _display_name(profile, record),
        "date": day,
        "is_working_day": is_working_day,
        "already_recorded": bool(today_record),
        "record": today_record,
        "shift_start": config["shift_start"],
        "network": {
            "verified": network["verified"],
            "reason": network["reason"],
            "message": None if network["verified"] else office_network.failure_message(network),
        },
        "can_start": bool(
            config["configured"]
            and employee_id
            and is_working_day
            and not today_record
            and network["verified"]
        ),
        "prompt": bool(
            config["configured"] and employee_id and is_working_day and not today_record
        ),
    }


@router.post("/api/attendance/start")
async def attendance_start(request: Request, payload: dict = Body(default={})):
    """Record the start of the working day.

    Network verification is re-run here rather than trusted from the client:
    the earlier GET only decided whether to enable a button, and a button is not
    an authorisation.
    """
    profile = _profile(request)
    config = cfg.load_config()
    if not config["configured"]:
        raise HTTPException(409, "Attendance is not configured yet. Ask an administrator to set the working calendar.")

    employee_id = employee_identity.employee_id_for_profile(profile)
    if not employee_id:
        raise HTTPException(403, "This login is not enrolled for attendance. Ask an administrator to assign an employee id.")

    day = cfg.ist_date_str()
    if not cfg.is_working_day(day, config):
        raise HTTPException(409, "Today is not a scheduled working day.")

    network = office_network.verify(request, config=config)
    if not network["verified"]:
        raise HTTPException(403, office_network.failure_message(network))

    record, created = attendance.record_start(
        employee_id=employee_id,
        device=payload.get("device"),
        network=network,
    )
    return {"status": "ok", "created": created, "record": record}


@router.get("/api/attendance/config", dependencies=[Depends(_require_fleet_admin)])
async def attendance_get_config():
    return {"status": "ok", "config": cfg.load_config()}


@router.put("/api/attendance/config", dependencies=[Depends(_require_fleet_admin)])
async def attendance_put_config(payload: dict = Body(default={})):
    return {"status": "ok", "config": cfg.save_config(payload)}


@router.get("/api/attendance/employees", dependencies=[Depends(_require_fleet_admin)])
async def attendance_employees():
    return {"status": "ok", "employees": employee_identity.all_employees()}


@router.post("/api/attendance/employees", dependencies=[Depends(_require_fleet_admin)])
async def attendance_assign_employee(payload: dict = Body(default={})):
    employee_id, error = employee_identity.assign_employee_id(
        display_name=str(payload.get("display_name") or ""),
        username=payload.get("username"),
        reference=payload.get("reference"),
    )
    if error:
        raise HTTPException(400, error)
    return {"status": "ok", "employee_id": employee_id}


@router.post("/api/attendance/employees/{employee_id}/aliases", dependencies=[Depends(_require_fleet_admin)])
async def attendance_add_alias(employee_id: str, payload: dict = Body(default={})):
    error = employee_identity.add_alias(
        employee_id,
        username=payload.get("username"),
        reference=payload.get("reference"),
    )
    if error:
        raise HTTPException(400, error)
    return {"status": "ok"}


@router.get("/api/attendance/records", dependencies=[Depends(_require_fleet_admin)])
async def attendance_records(
    month: str = Query(...),
    employee_id: str | None = Query(default=None),
):
    return {
        "status": "ok",
        "month": month,
        "records": attendance.records_for_month(month, employee_id),
    }


@router.get("/api/attendance/summary", dependencies=[Depends(_require_fleet_admin)])
async def attendance_summary(month: str = Query(...)):
    """Attendance percentages for the HR view.

    Percentages only. No salary and no commission is read or written here.
    """
    employees = employee_identity.all_employees()
    summary = attendance.month_summary(month, [row["employee_id"] for row in employees])
    names = {row["employee_id"]: row.get("display_name") for row in employees}
    for entry in summary["employees"]:
        entry["display_name"] = names.get(entry["employee_id"])
    return {"status": "ok", "summary": summary}


@router.post("/api/attendance/override", dependencies=[Depends(_require_fleet_admin)])
async def attendance_override(request: Request, payload: dict = Body(default={})):
    """Authorise a day the office-network check could not pass.

    Recorded with who approved it, why, and what the network check said — an
    override has to be legible as an exception months later.
    """
    approver = dashboard_auth.operator_profile_from_cookies(dict(request.cookies)) or {}
    approver_name = str(approver.get("username") or "").strip()
    if not approver_name:
        raise HTTPException(401, "Authentication required")

    record, error = attendance.apply_override(
        employee_id=str(payload.get("employee_id") or ""),
        day=str(payload.get("date") or ""),
        reason=str(payload.get("reason") or ""),
        approved_by=approver_name,
        approved_by_employee_id=employee_identity.employee_id_for_profile(approver),
        original_network=payload.get("original_network_result") or office_network.verify(request),
    )
    if error:
        raise HTTPException(400, error)
    return {"status": "ok", "record": record}
