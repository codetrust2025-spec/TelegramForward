"""Deterministic duplicate and risk checks for candidate payment proofs."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Any


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def assess_payment_proof(
    raw: bytes,
    extraction: dict[str, Any] | None,
    *,
    candidate_id: str = "",
    candidate_name: str = "",
) -> dict[str, Any]:
    from features import candidate_store

    digest = hashlib.sha256(raw).hexdigest()
    extracted = extraction or {}
    utr = _norm(extracted.get("utr_number") or extracted.get("transaction_id") or extracted.get("reference_number"))
    status = str(extracted.get("status") or "").strip().lower()
    matches = []
    reasons = []
    for row in candidate_store._load().get("candidates") or []:
        for proof in candidate_store.list_attachments(
            str(row.get("id") or ""), "payment_proof"
        ) or []:
            stored_digest = proof.get("sha256") or ""
            if not stored_digest and row.get("id") and proof.get("filename"):
                try:
                    hit = candidate_store.get_attachment(
                        str(row["id"]), str(proof.get("id") or ""), "payment_proof"
                    )
                    path = hit[0] if hit else ""
                    with open(path, "rb") as handle:
                        stored_digest = hashlib.sha256(handle.read()).hexdigest()
                except OSError:
                    stored_digest = ""
            if stored_digest == digest:
                matches.append({"candidate_id": row.get("id"), "candidate_name": row.get("name"), "proof_id": proof.get("id"), "match": "image"})
            stored_utr = _norm(proof.get("utr_number") or proof.get("transaction_id"))
            if utr and stored_utr and utr == stored_utr:
                matches.append({"candidate_id": row.get("id"), "candidate_name": row.get("name"), "proof_id": proof.get("id"), "match": "utr"})
    if any(m["match"] == "image" for m in matches):
        reasons.append("This payment screenshot has already been uploaded.")
    if any(m["match"] == "utr" for m in matches):
        reasons.append("This UTR or transaction number is already attached to another payment proof.")
    if status in {"failed", "failure", "declined", "reversed"}:
        reasons.append(f"The transaction status is {status}.")
    warnings = list(extracted.get("warnings") or [])
    if status in {"pending", "processing"}:
        warnings.append(f"Transaction status is {status}; manual confirmation is required.")
    confidence = int(extracted.get("confidence_score") or 0)
    if extracted and confidence < 55:
        warnings.append("Payment details have low extraction confidence.")
    decision = "rejected" if reasons else ("needs_review" if warnings else "verified")
    return {
        "decision": decision,
        "verified": decision == "verified",
        "reasons": reasons,
        "warnings": list(dict.fromkeys(warnings)),
        "duplicate_matches": matches,
        "sha256": digest,
        "utr_number": utr,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
    }
