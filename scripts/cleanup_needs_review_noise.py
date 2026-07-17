#!/usr/bin/env python3
"""Clean up 'Needs Review' noise - mark non-actionable events as IGNORED."""
import os
import sys
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.db.connection import get_connection
from core.recruitment_offer_visibility import cleanup_reason

def main():
    print("=== Cleaning Up 'Needs Review' Noise ===\n")
    
    with get_connection() as conn, conn.cursor() as cur:
        # Get all PENDING events
        cur.execute("""
            SELECT 
                e.id,
                e.candidate_id,
                e.primary_status,
                e.confidence,
                e.subject,
                e.sender_name,
                e.sender_email,
                e.summary,
                e.structured_result,
                e.review_status,
                e.visible_in_offer_review
            FROM ai_recruitment_events e
            WHERE e.review_status = 'PENDING'
            ORDER BY e.created_at DESC
        """)
        
        events = []
        for row in cur.fetchall():
            events.append({
                'id': row[0],
                'candidate_id': row[1],
                'primary_status': row[2],
                'confidence': row[3],
                'subject': row[4],
                'sender_name': row[5],
                'sender_email': row[6],
                'summary': row[7],
                'structured_result': row[8],
                'review_status': row[9],
                'visible_in_offer_review': row[10],
            })
        
        print(f"Found {len(events)} PENDING review events\n")
        
        to_ignore = []
        to_keep = []
        
        for event in events:
            reason = cleanup_reason(event)
            if reason:
                to_ignore.append((event['id'], reason, event['subject'][:60]))
            else:
                to_keep.append((event['primary_status'], event['subject'][:60]))
        
        print(f"Events to IGNORE (noise): {len(to_ignore)}")
        print(f"Events to KEEP (actionable): {len(to_keep)}\n")
        
        if to_ignore:
            print("Sample events being marked as IGNORED:")
            for event_id, reason, subject in to_ignore[:10]:
                print(f"  • {subject} → {reason}")
            print()
        
        if to_keep:
            print("Sample events being kept for review:")
            for status, subject in to_keep[:10]:
                print(f"  • [{status}] {subject}")
            print()
        
        # Mark noise events as IGNORED
        if to_ignore:
            event_ids = [item[0] for item in to_ignore]
            cur.execute("""
                UPDATE ai_recruitment_events
                SET review_status = 'IGNORED',
                    ignore_reason = 'CLEANUP: Not actionable - profile views, recommendations, generic updates',
                    ignored_at = now(),
                    visible_in_offer_review = false,
                    updated_at = now()
                WHERE id = ANY(%s)
            """, (event_ids,))
            
            print(f"\n✓ Marked {len(to_ignore)} events as IGNORED")
        
        # Add audit log
        cur.execute("""
            INSERT INTO recruitment_audit_log(id, actor, role, action, new_value, created_at)
            VALUES(gen_random_uuid(), 'system', 'system', 'BULK_NOISE_CLEANUP', %s::jsonb, now())
        """, (__import__('json').dumps({'ignored_count': len(to_ignore), 'kept_count': len(to_keep)}),))
    
    print("\n=== Cleanup Complete ===")
    print(f"Total events processed: {len(events)}")
    print(f"Marked as IGNORED: {len(to_ignore)}")
    print(f"Kept for review: {len(to_keep)}")

if __name__ == '__main__':
    main()
