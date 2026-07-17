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
    ):
        try:
            raw = await file.read()
            # Validate the image looks like a payment screenshot
            try:
                from features.payment_proof_validator import validate_payment_proof
                # Get the due amount for this candidate
                due_amount = cs.merged_balance_due_for_name(name) if name else 0
                print(f"[PAYMENT-PROOF] Validating: name={name}, due={due_amount}, size={len(raw)}")
                is_valid, reason = validate_payment_proof(raw, file.content_type or "", expected_amount=due_amount)
                print(f"[PAYMENT-PROOF] Result: valid={is_valid}, reason={reason}")
                if not is_valid:
                    return _json_error(reason or "This doesn't look like a payment screenshot.")
            except ImportError as exc:
                print(f"[PAYMENT-PROOF] Import error: {exc}")
            except Exception as exc:
                print(f"[PAYMENT-PROOF] Validation exception: {exc}")
                import traceback; traceback.print_exc()
            result = cs.public_add_payment_proof_for_name(
                name,
                data=raw,
                original_name=file.filename or "payment.jpg",
                mime_type=file.content_type or "image/jpeg",
                note=note or "",
            )
            # AI extraction (non-blocking addition to response)
            ai_extraction = None
            try:
                from features.ollama_payment_extract import (
                    extract_payment_with_ollama,
                    verify_payment_against_due,
                    generate_payment_narrative,
                )
                ai_result = await asyncio.to_thread(extract_payment_with_ollama, raw, file.content_type or "image/jpeg")
                if ai_result and ai_result.get("is_payment_screenshot"):
                    due = cs.merged_balance_due_for_name(name) if name else 0
                    ai_extraction = verify_payment_against_due(ai_result, due)
                    # Generate plain-English narrative for the UI
                    try:
                        received = cs.merged_received_for_name(name) if name else 0
                    except Exception:
                        received = 0
                    ai_extraction["narrative"] = await asyncio.to_thread(
                        generate_payment_narrative,
                        ai_extraction,
                        candidate_name=name,
                        expected_amount=due,
                        received_amount=0,
                    )
            except Exception as ai_exc:
                logger.debug("AI payment extraction skipped: %s", ai_exc)
        except ValueError as e:
            return _json_error(str(e))
        resp = {"status": "ok", **result}
        if ai_extraction:
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
            from features.ollama_payment_extract import (
                extract_payment_with_ollama,
                verify_payment_against_due,
            )

            result = await asyncio.to_thread(extract_payment_with_ollama, raw, mime)

            # Auto-verify against candidate's due amount if name provided
            if candidate_name.strip() and result.get("is_payment_screenshot"):
                try:
                    amount_due = cs.merged_balance_due_for_name(candidate_name.strip())
                    result = verify_payment_against_due(result, amount_due)
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
        service_type: str = Form(default="round_wise"),
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
        if slot_image and (not day or not slot_time):
            try:
                from features.slot_screenshot_parse import parse_invite_screenshot

                parsed = await asyncio.to_thread(
                    parse_invite_screenshot, slot_image, slot_image_mime
                )
                day = day or parsed.get("date") or ""
                slot_time = slot_time or parsed.get("time") or ""
                slot_end = slot_end or parsed.get("time_end") or ""
                if not interview_round.strip() and parsed.get("interview_round"):
                    interview_round = parsed["interview_round"]
                if not technology.strip() and parsed.get("technology"):
                    technology = parsed["technology"]
            except ValueError as e:
                return _json_error(str(e))

        if not day or not slot_time:
            return _json_error("Upload a clear invite screenshot — date and time are read automatically.")

        try:
            row, action = cs.import_confirmed_interview_slot(
                name=name,
                date=day,
                time=slot_time,
                time_end=slot_end,
                interview_round=interview_round,
                technology=technology,
                service_type=service_type.strip() or "round_wise",
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
