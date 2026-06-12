#!/usr/bin/env python3
"""Fetch recent inbox messages for R.B. Madhu / account9 from Postgres."""
import os, socket, json, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")

REMOTE = r'''
import json, os, sys
sys.path.insert(0, "/opt/telegramforward.old")
os.chdir("/opt/telegramforward.old")
from dotenv import load_dotenv
load_dotenv(".env")

from core.db import get_connection

queries = [
    ("tables", "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'inbox%' ORDER BY 1"),
    ("search madhu", """
        SELECT slot, user_id, name, username, last_message, last_message_at, unread_count, crm_status
        FROM inbox_conversations
        WHERE lower(name) LIKE '%madhu%' OR lower(name) LIKE '%r.b%'
        ORDER BY last_message_at DESC NULLS LAST
        LIMIT 20
    """),
    ("account9 recent convs", """
        SELECT slot, user_id, name, username, last_message, last_message_at, unread_count
        FROM inbox_conversations
        WHERE slot = 'account9'
        ORDER BY last_message_at DESC NULLS LAST
        LIMIT 10
    """),
]

with get_connection() as conn:
    with conn.cursor() as cur:
        for label, q in queries:
            print(f"\n=== {label} ===")
            try:
                cur.execute(q)
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = cur.fetchall()
                print(f"rows: {len(rows)}")
                for row in rows[:15]:
                    print(dict(zip(cols, row)))
            except Exception as e:
                print("ERR:", e)
                conn.rollback()

        # messages for first madhu match
        print("\n=== messages for R.B./Madhu lead ===")
        try:
            cur.execute("""
                SELECT c.slot, c.user_id, c.name
                FROM inbox_conversations c
                WHERE lower(c.name) LIKE '%madhu%' OR lower(c.name) LIKE '%r.b%'
                ORDER BY c.last_message_at DESC NULLS LAST
                LIMIT 1
            """)
            row = cur.fetchone()
            if not row:
                print("No matching conversation")
            else:
                slot, uid, name = row
                print(f"Lead: {name} slot={slot} user_id={uid}")
                cur.execute("""
                    SELECT direction, text, sent_at, is_ai, status
                    FROM inbox_messages
                    WHERE slot = %s AND user_id = %s
                    ORDER BY sent_at DESC
                    LIMIT 30
                """, (slot, uid))
                cols = [d[0] for d in cur.description]
                msgs = cur.fetchall()
                for m in reversed(msgs):
                    print(dict(zip(cols, m)))
        except Exception as e:
            print("ERR:", e)
'''

script = f"cd /opt/telegramforward.old && ./venv/bin/python3 - <<'PY'\n{REMOTE}\nPY 2>&1"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
stdin, stdout, stderr = c.exec_command(script, timeout=120)
out = stdout.read().decode("utf-8", "replace")
err = stderr.read().decode("utf-8", "replace")
code = stdout.channel.recv_exit_status()
c.close()
path = os.path.join(os.environ.get("TEMP", "."), "inbox_chat_read.txt")
open(path, "w", encoding="utf-8").write(out + "\n" + err)
print(out or err or f"exit {code}")
print("saved", path)
