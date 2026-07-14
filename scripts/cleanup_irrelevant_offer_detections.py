"""Archive historical non-offer detections without deleting audit data."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.db.connection import get_connection
from core.recruitment_offer_visibility import cleanup_reason, qualified_event_sql


VERSION = "offer_review_cleanup_v1"


def run(*, apply: bool = False) -> dict[str, int | str]:
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT EXISTS(SELECT 1 FROM information_schema.columns
          WHERE table_name='ai_recruitment_events' AND column_name='visible_in_offer_review')""")
        has_visibility = bool(cur.fetchone()[0])
        visibility_clause = "AND COALESCE(e.visible_in_offer_review,true)=true" if has_visibility else ""
        cur.execute(f"""SELECT e.*,m.subject,m.sender_name,m.sender_email
          FROM ai_recruitment_events e LEFT JOIN mailbox_messages m ON m.id=e.mailbox_message_id
          WHERE e.review_status NOT IN('IGNORED','FALSE_POSITIVE','DUPLICATE') {visibility_clause}""")
        names = [column.name for column in cur.description]
        rows = [dict(zip(names, row)) for row in cur.fetchall()]
        candidates = [(row, cleanup_reason(row)) for row in rows]
        candidates = [(row, reason) for row, reason in candidates if reason]
        if apply:
            if not has_visibility:
                raise RuntimeError("Migration 004 must be applied before --apply")
            for row, reason in candidates:
                cur.execute("""UPDATE ai_recruitment_events SET
                  original_primary_status=COALESCE(original_primary_status,primary_status),
                  primary_status='IGNORED_NOT_OFFER_RELATED',review_status='IGNORED',
                  visible_in_offer_review=false,ignore_reason=%s,ignored_at=COALESCE(ignored_at,now()),
                  cleanup_version=%s,updated_at=now() WHERE id=%s""", (reason, VERSION, row["id"]))
                cur.execute("""UPDATE mailbox_messages SET processing_status='IGNORED_NOT_OFFER_RELATED',
                  ignore_reason=%s,ignored_at=COALESCE(ignored_at,now()),cleanup_version=%s,updated_at=now()
                  WHERE id=%s""", (reason, VERSION, row.get("mailbox_message_id")))
                cur.execute("UPDATE offer_verification_cases SET verification_status='IGNORED',updated_at=now() WHERE ai_recruitment_event_id=%s", (row["id"],))
                cur.execute("UPDATE recruitment_review_flags SET review_status='IGNORED' WHERE event_id=%s", (row["id"],))
                cur.execute("""INSERT INTO recruitment_audit_log(id,actor,role,action,candidate_id,source_id,previous_value,new_value,created_at)
                  VALUES(%s,'maintenance','system','OFFER_REVIEW_EVENT_IGNORED',%s,%s,%s::jsonb,%s::jsonb,now())""",
                  (str(uuid.uuid4()),row["candidate_id"],row["id"],json.dumps({"primary_status":row["primary_status"],"review_status":row["review_status"]}),json.dumps({"primary_status":"IGNORED_NOT_OFFER_RELATED","review_status":"IGNORED","reason":reason,"cleanup_version":VERSION})))
        predicate, predicate_params = qualified_event_sql("e")
        cur.execute("""SELECT count(*) FILTER(WHERE e.cleanup_version=%s),
          count(*) FILTER(WHERE e.cleanup_version=%s AND e.primary_status='IGNORED_NOT_OFFER_RELATED'
            AND e.review_status='IGNORED' AND e.visible_in_offer_review=false),
          count(*) FILTER(WHERE e.cleanup_version=%s AND lower(COALESCE(m.subject,'')) LIKE '%%job recommendations for you%%foundit%%')
          FROM ai_recruitment_events e LEFT JOIN mailbox_messages m ON m.id=e.mailbox_message_id""", (VERSION, VERSION, VERSION))
        cleanup_total, cleanup_valid, cleaned_foundit = cur.fetchone()
        cur.execute(f"""SELECT count(*) FROM ai_recruitment_events e
          LEFT JOIN mailbox_messages m ON m.id=e.mailbox_message_id
          WHERE {predicate} AND lower(COALESCE(m.subject,'')) LIKE '%%job recommendations for you%%foundit%%'""", predicate_params)
        visible_foundit = cur.fetchone()[0]
        return {
            "mode": "apply" if apply else "dry-run",
            "records_scanned": len(rows),
            "records_qualifying_for_cleanup": len(candidates),
            "records_marked_ignored": len(candidates) if apply else 0,
            "records_preserved": len(rows) - len(candidates),
            "database_cleanup_total": cleanup_total,
            "database_cleanup_state_valid": cleanup_valid,
            "cleaned_foundit_recommendations": cleaned_foundit,
            "visible_foundit_recommendations": visible_foundit,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(apply=args.apply), indent=2))
