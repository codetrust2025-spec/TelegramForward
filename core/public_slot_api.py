"""Public interview slot booking API (no dashboard login required)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import File, Form, UploadFile
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def _json_error(message: str, status: int = 400, **extra: Any) -> JSONResponse:
    payload: dict[str, Any] = {"status": "error", "message": message}
    payload.update(extra)
    return JSONResponse(payload, status_code=status)


def install_public_slot_routes(app) -> None:
    from features import candidate_store as cs

    @app.get("/public/slots/candidates")
    async def public_slot_candidates(channel: str | None = None):
        rows = cs.interview_slot_picker_rows(channel=channel or "profile")
        return {"status": "ok", "candidates": rows, "count": len(rows)}

    @app.get("/public/slots/booked")
    async def public_slot_booked(days: int = 60):
        snap = cs.public_booked_interview_slots(days=days)
        return {"status": "ok", **snap}

    @app.post("/public/slots/payment-proof")
    async def public_slot_payment_proof(
        name: str = Form(...),
        file: UploadFile = File(...),
        note: str = Form(default=""),
    ):
        try:
            raw = await file.read()
            result = cs.public_add_payment_proof_for_name(
                name,
                data=raw,
                original_name=file.filename or "payment.jpg",
                mime_type=file.content_type or "image/jpeg",
                note=note or "",
            )
        except ValueError as e:
            return _json_error(str(e))
        return {"status": "ok", **result}

    @app.post("/public/slots/book")
    async def public_slot_book(
        name: str = Form(...),
        date: str = Form(...),
        time: str = Form(...),
        time_end: str = Form(default=""),
        interview_round: str = Form(default=""),
        technology: str = Form(default=""),
        notes: str = Form(default=""),
        payment_proof_id: str = Form(default=""),
        file: UploadFile | None = File(default=None),
    ):
        slot_image: bytes | None = None
        slot_image_name = ""
        slot_image_mime = ""
        if file and file.filename:
            slot_image = await file.read()
            slot_image_name = file.filename or "slot.jpg"
            slot_image_mime = file.content_type or "image/jpeg"
        try:
            row, action = cs.import_confirmed_interview_slot(
                name=name,
                date=date,
                time=time,
                time_end=time_end,
                interview_round=interview_round,
                technology=technology,
                notes=notes,
                source="submit-slot form",
                payment_proof_id=payment_proof_id.strip() or None,
                slot_image=slot_image,
                slot_image_name=slot_image_name,
                slot_image_mime=slot_image_mime,
            )
        except cs.PaymentDueError as e:
            return _json_error(
                str(e),
                payment_due=True,
                balance_due=e.balance_due,
                name=e.name,
            )
        except cs.SlotBookedError as e:
            return _json_error(str(e), slot_conflict=True, conflicts=e.conflicts)
        except ValueError as e:
            return _json_error(str(e))

        async def _notify() -> None:
            try:
                from services.slot_booking_notify import notify_slot_booked

                await notify_slot_booked(row, action=action)
            except Exception as exc:
                logger.debug("slot booking notify failed: %s", exc)

        asyncio.create_task(_notify())
        return {"status": "ok", "action": action, "candidate": row}

    @app.post("/public/slots/session-complete")
    async def public_slot_session_complete(
        name: str = Form(...),
        date: str = Form(default=""),
        time: str = Form(default=""),
        file: UploadFile = File(...),
    ):
        try:
            raw = await file.read()
            row, action = cs.mark_session_complete_by_name(
                name,
                date=date,
                time=time,
                source="submit-slot",
                slot_image=raw,
                slot_image_name=file.filename or "session-complete.jpg",
                slot_image_mime=file.content_type or "image/jpeg",
            )
        except ValueError as e:
            return _json_error(str(e))
        return {"status": "ok", "action": action, "candidate": row}
