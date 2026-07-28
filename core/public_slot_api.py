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
        return JSONResponse(
            {"status": "ok", "candidates": rows, "count": len(rows)},
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.get("/public/slots/booked")
    async def public_slot_booked(days: int = 60):
        snap = cs.public_booked_interview_slots(days=days)
        return JSONResponse(
            {"status": "ok", **snap},
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @app.post("/public/slots/payment-proof")
    async def public_slot_payment_proof(
        name: str = Form(...),
        file: UploadFile = File(...),
        note: str = Form(default=""),
        service_type: str = Form(default=""),
        phone: str = Form(default=""),
        technology: str = Form(default=""),
        interview_round: str = Form(default=""),
    ):
        try:
            raw = await file.read()
            if service_type.strip() == "round_wise":
                payment_owner = cs.ensure_round_wise_payment_row(
                    name,
                    phone=phone,
                    technology=technology,
                    interview_round=interview_round,
                    # Tabs opened before the frontend deployment do not send
                    # these three new fields.  Keep them compatible: the final
                    # booking endpoint still requires and persists all fields.
                    allow_incomplete=True,
                )
                due_amount = max(
                    0,
                    cs.effective_expected_payment(payment_owner)
                    - int(payment_owner.get("payment") or 0),
                )
            else:
                due_amount = cs.merged_balance_due_for_name(name) if name else 0
                payment_owner = cs._best_row_for_slot_name(name)
            # Payee validation is security-critical and deliberately fails
            # closed. Never save or credit the receipt before this succeeds.
            try:
                from features.payment_verification_engine import verify_payment_screenshot
                from features.ollama_payment_extract import generate_payment_narrative

                ai_extraction = await asyncio.to_thread(
                    verify_payment_screenshot,
                    raw,
                    file.content_type or "image/jpeg",
                    source_module="public_slot_payment_proof",
                    expected_amount=due_amount,
                    entity_id=str((payment_owner or {}).get("id") or ""),
                    entity_name=name.strip(),
                    candidate_id=str((payment_owner or {}).get("id") or ""),
                    referrer_hint=str((payment_owner or {}).get("reference") or ""),
                    purpose="candidate_payment",
                    payment_scope=(
                        "ROUND" if service_type.strip() == "round_wise" else "PROFILE"
                    ),
                )
                ai_extraction["company_payment_reasons"] = list(
                    ai_extraction.get("deterministic_reasons") or []
                )
                if not ai_extraction.get("booking_eligible"):
                    verification_state = str(
                        ai_extraction.get("verification_state") or ""
                    )
                    if verification_state == "INCOMPLETE_PAYMENT_EVIDENCE":
                        message = (
                            "More Payment Details Required. Upload the complete "
                            "transaction-details screenshot showing the receiver "
                            "identifier and Transaction ID or UTR."
                        )
                    else:
                        message = (
                            " ".join(ai_extraction["company_payment_reasons"])
                            or "This receipt is not a verified payment to a registered company or referrer account."
                        )
                    return _json_error(
                        message,
                        ai_extraction=ai_extraction,
                    )
            except Exception as ai_exc:
                logger.exception("Company payment verification failed")
                return _json_error(
                    "Could not verify this payment against the company/referrer registry. "
                    "Upload a clear receipt showing the receiver UPI ID or payment phone number, amount, UTR, and successful status."
                )

            result = cs.public_add_payment_proof_for_name(
                name,
                data=raw,
                original_name=file.filename or "payment.jpg",
                mime_type=file.content_type or "image/jpeg",
                note=note or "",
                extraction=ai_extraction,
                service_type=service_type,
            )
            try:
                ai_extraction["narrative"] = await asyncio.to_thread(
                    generate_payment_narrative,
                    ai_extraction,
                    candidate_name=name,
                    expected_amount=due_amount,
                    received_amount=0,
                )
            except Exception as narrative_exc:
                logger.debug("Payment narrative generation skipped: %s", narrative_exc)
        except ValueError as e:
            return _json_error(str(e))
        resp = {"status": "ok", **result}
        resp["ai_extraction"] = ai_extraction
        return resp

    @app.post("/public/slots/parse-screenshot")
    async def public_slot_parse_screenshot(file: UploadFile = File(...)):
        raw = await file.read()
        mime = file.content_type or "image/jpeg"
        try:
            from features.slot_screenshot_parse import parse_invite_screenshot

            parsed = await asyncio.to_thread(parse_invite_screenshot, raw, mime)
        except ValueError as e:
            return _json_error(str(e))
        except Exception as exc:
            logger.exception("parse-screenshot failed")
            return _json_error(f"Could not read screenshot: {exc}", status=500)
        return {"status": "ok", "slot": parsed}

    @app.post("/public/slots/extract-invite-ai")
    async def public_slot_extract_invite_ai(file: UploadFile = File(...)):
        """AI-powered interview invite extraction using Ollama vision models."""
        raw = await file.read()
        mime = file.content_type or "image/jpeg"
        try:
            from features.ollama_invite_extract import extract_interview_invite_with_ollama

            result = await asyncio.to_thread(extract_interview_invite_with_ollama, raw, mime)
        except Exception as exc:
            logger.exception("AI invite extraction failed")
            # Return graceful fallback
            return {
                "status": "ok",
                "success": False,
                "extraction_source": "error",
                "data": {
                    "candidate_name": "",
                    "interview_date": "",
                    "start_time": "",
                    "end_time": "",
                    "interview_round": "",
                    "technology": "",
                    "meeting_platform": "",
                    "confidence_score": 0,
                    "missing_fields": ["interview_date", "start_time", "interview_round"],
                    "warnings": [f"AI extraction failed: {exc}. Use manual entry."],
                    "is_payment_screenshot": False,
                    "looks_like_interview_invite": True,
                    "manual_fields_required": True,
                },
            }
        
        is_success = bool(result and result.get("confidence_score", 0) > 0)
        return {
            "status": "ok",
            "success": is_success,
            "extraction_source": result.get("extraction_source", "unknown"),
            "primary_model": result.get("primary_model", ""),
            "backup_model": result.get("backup_model", ""),
            "data": result,
        }

    @app.post("/public/slots/extract-payment-ai")
    async def public_slot_extract_payment_ai(
        file: UploadFile = File(...),
        candidate_name: str = Form(default=""),
    ):
        """AI-powered payment proof extraction using Ollama vision models.

        Reads UPI/bank screenshots and extracts: amount, sender, UTR, date, status.
        If candidate_name is provided, auto-verifies against their balance due.
        """
        raw = await file.read()
        mime = file.content_type or "image/jpeg"
        try:
            from features.payment_verification_engine import verify_payment_screenshot

            amount_due = (
                cs.merged_balance_due_for_name(candidate_name.strip())
                if candidate_name.strip()
                else 0
            )
            result = await asyncio.to_thread(
                verify_payment_screenshot,
                raw,
                mime,
                source_module="public_slot_payment_extract",
                expected_amount=amount_due,
                entity_id=str(
                    (
                        cs._best_row_for_slot_name(candidate_name.strip())
                        if candidate_name.strip()
                        else {}
                    ).get("id")
                    or ""
                ),
                entity_name=candidate_name.strip(),
                candidate_id=str(
                    (
                        cs._best_row_for_slot_name(candidate_name.strip())
                        if candidate_name.strip()
                        else {}
                    ).get("id")
                    or ""
                ),
                referrer_hint=str(
                    (
                        cs._best_row_for_slot_name(candidate_name.strip())
                        if candidate_name.strip()
                        else {}
                    ).get("reference")
                    or ""
                ),
                purpose="candidate_payment",
                payment_scope="PROFILE",
            )

            if candidate_name.strip() and result.get("is_payment_screenshot"):
                try:
                    # Generate narrative
                    from features.ollama_payment_extract import generate_payment_narrative
                    result["narrative"] = await asyncio.to_thread(
                        generate_payment_narrative,
                        result,
                        candidate_name=candidate_name.strip(),
                        expected_amount=amount_due,
                        received_amount=0,
                    )
                except Exception as vex:
                    logger.warning("Payment verification failed: %s", vex)
                    result["warnings"] = list(result.get("warnings") or [])
                    result["warnings"].append(f"Auto-verify failed: {vex}")

        except Exception as exc:
            logger.exception("AI payment extraction failed")
            return {
                "status": "ok",
                "success": False,
                "extraction_source": "error",
                "data": {
                    "amount": 0,
                    "is_payment_screenshot": False,
                    "confidence_score": 0,
                    "warnings": [f"AI extraction failed: {exc}"],
                    "verified": False,
                    "verification_result": "Extraction failed",
                },
            }

        is_success = bool(
            result
            and result.get("is_payment_screenshot")
            and result.get("amount", 0) > 0
        )
        return {
            "status": "ok",
            "success": is_success,
            "extraction_source": result.get("extraction_source", "unknown"),
            "primary_model": result.get("primary_model", ""),
            "data": result,
        }

    @app.post("/public/slots/extract-resume-ai")
    async def public_slot_extract_resume_ai(file: UploadFile = File(...)):
        """AI-powered resume PDF extraction using Ollama.

        Reads PDF resumes and extracts: name, phone, email, technology,
        years of experience, skills, education, current company.
        """
        raw = await file.read()
        mime = file.content_type or "application/pdf"
        try:
            from features.ollama_resume_extract import extract_resume_with_ollama

            result = await asyncio.to_thread(extract_resume_with_ollama, raw, mime)
        except Exception as exc:
            logger.exception("AI resume extraction failed")
            return {
                "status": "ok",
                "success": False,
                "extraction_source": "error",
                "data": {
                    "candidate_name": "",
                    "technology": "",
                    "phone": "",
                    "confidence_score": 0,
                    "is_resume": False,
                    "error": str(exc),
                },
            }

        # Success if we have at least a name OR enough contact/skill signals.
        # Regex fallback (no Ollama) is still useful if it found phone/email/tech.
        has_name = bool(result.get("candidate_name"))
        has_contact = bool(result.get("phone") or result.get("email"))
        has_tech = bool(result.get("technology"))
        is_success = bool(
            result
            and result.get("is_resume")
            and (has_name or (has_contact and has_tech))
        )
        return {
            "status": "ok",
            "success": is_success,
            "extraction_source": result.get("extraction_source", "unknown"),
            "primary_model": result.get("primary_model", ""),
            "data": result,
        }

    @app.post("/public/slots/book")
    async def public_slot_book(
        name: str = Form(...),
        date: str = Form(default=""),
        time: str = Form(default=""),
        time_end: str = Form(default=""),
        interview_round: str = Form(default=""),
        technology: str = Form(default=""),
        phone: str = Form(default=""),
        service_type: str = Form(default="round_wise"),
        notes: str = Form(default=""),
        payment_proof_id: str = Form(default=""),
        file: UploadFile | None = File(default=None),
    ):
        normalized_service_type = service_type.strip() or "round_wise"
        normalized_technology = technology.strip()
        normalized_phone = phone.strip() if normalized_service_type == "round_wise" else ""
        if normalized_service_type == "round_wise" and not normalized_technology:
            return _json_error(
                "Technology is required for round-wise booking. "
                "Select the technology and try again."
            )
        if normalized_service_type == "round_wise" and not cs.candidate_phone_identity(normalized_phone):
            return _json_error(
                "A valid phone number is required for round-wise booking. "
                "Enter the candidate phone number and try again."
            )

        slot_image: bytes | None = None
        slot_image_name = ""
        slot_image_mime = ""
        if file and file.filename:
            slot_image = await file.read()
            slot_image_name = file.filename or "slot.jpg"
            slot_image_mime = file.content_type or "image/jpeg"
            # Validate: must look like an interview invite
            try:
                from features.payment_proof_validator import validate_interview_invite
                is_valid, reason = validate_interview_invite(slot_image, slot_image_mime)
                if not is_valid:
                    return _json_error(reason)
            except Exception:
                pass

        day = date.strip()
        slot_time = time.strip()
        slot_end = time_end.strip()
        if not day or not slot_time:
            return _json_error(
                "Interview date and start time are required. "
                "Automatic booking is allowed only after dual-source AI verification; "
                "otherwise enter them manually."
            )
        try:
            row, action = cs.import_confirmed_interview_slot(
                name=name,
                date=day,
                time=slot_time,
                time_end=slot_end,
                interview_round=interview_round,
                technology=normalized_technology,
                phone=normalized_phone,
                service_type=normalized_service_type,
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
