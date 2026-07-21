#!/usr/bin/env python3
"""Hide timeout-only review events while preserving their source mail retry state."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from core.db.connection import get_connection  # noqa: E402


VERSION = "timeout_relevance_gate_v1"


def run(*, apply: bool = False) -> dict[str, object]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT e.id,e.candidate_id,e.mailbox_message_id,m.subject
          FROM ai_recruitment_events e
          LEFT JOIN mailbox_messages m ON m.id=e.mailbox_message_id
          WHERE e.primary_status='MANUAL_REVIEW_REQUIRED'
            AND COALESCE(e.validation_status,e.structured_result->>'validation_status')='RETRY_PENDING'
            AND e.review_status='PENDING'
            AND COALESCE(e.visible_in_offer_review,true)=true
            AND e.confidence<0.8
            AND jsonb_array_length(COALESCE(e.structured_result->'evidence','[]'::jsonb))=0
          ORDER BY e.created_at""")
        names = [column.name for column in cur.description]
        rows = [dict(zip(names, row)) for row in cur.fetchall()]
        if apply and rows:
            ids = [row["id"] for row in rows]
            cur.execute("""UPDATE ai_recruitment_events SET
              visible_in_offer_review=false,review_status='IGNORED',requires_manual_review=false,
              ignore_reason='AI_TIMEOUT_WITHOUT_LIFECYCLE_EVIDENCE',ignored_at=now(),
              cleanup_version=%s,updated_at=now()
              WHERE id=ANY(%s)""", (VERSION, ids))
            cur.execute("""INSERT INTO recruitment_audit_log(
              id,actor,role,action,new_value,created_at)
              VALUES(%s,'maintenance','system','TIMEOUT_REVIEW_NOISE_HIDDEN',%s::jsonb,now())""",
              (str(uuid.uuid4()), json.dumps({
                  "cleanup_version": VERSION,
                  "event_count": len(rows),
                  "event_ids": [str(item) for item in ids],
                  "source_mail_preserved_for_retry": True,
              })))
        return {
            "mode": "apply" if apply else "dry-run",
            "records_qualifying": len(rows),
            "records_hidden": len(rows) if apply else 0,
            "source_mail_retry_state_preserved": True,
            "sample_subjects": [str(row.get("subject") or "(no subject)")[:100] for row in rows[:10]],
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(apply=args.apply), indent=2))
