#!/usr/bin/env python3
"""Check what's still showing as 'Needs Review' after cleanup."""
import paramiko

VPS_HOST = '187.127.169.159'
VPS_USER = 'root'
VPS_PASSWORD = '8897870998s@SS'
VPS_PATH = '/opt/telegramforward'

def main():
    print("=== Checking Remaining 'Needs Review' Events ===\n")
    
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)
    
    # Check what's still PENDING
    stdin, stdout, stderr = client.exec_command(f"""cd {VPS_PATH} && venv/bin/python3 -c "
from dotenv import load_dotenv
from pathlib import Path
load_dotenv()
from core.db.connection import get_connection

with get_connection() as conn, conn.cursor() as cur:
    cur.execute('''
        SELECT 
            e.id,
            e.primary_status,
            e.confidence,
            m.subject,
            e.created_at,
            e.review_status
        FROM ai_recruitment_events e
        JOIN mailbox_messages m ON m.id = e.mailbox_message_id
        WHERE e.review_status = 'PENDING'
        ORDER BY e.created_at DESC
        LIMIT 20
    ''')
    
    print('Currently PENDING events:')
    print('=' * 80)
    for row in cur.fetchall():
        event_id, status, conf, subject, created, review = row
        print(f'[{{status}}] {{conf:.0%}} - {{subject[:60]}}')
        print(f'  Created: {{created}} | Review: {{review}}')
        print()
"
""", timeout=60)
    
    stdout.channel.recv_exit_status()
    print(stdout.read().decode())
    
    # Now run cleanup again to catch any remaining
    print("\n=== Running Cleanup Again ===\n")
    
    stdin, stdout, stderr = client.exec_command(
        f"cd {VPS_PATH} && venv/bin/python3 scripts/cleanup_needs_review_noise.py",
        timeout=300
    )
    
    while True:
        line = stdout.readline()
        if not line:
            break
        print(line.rstrip())
    
    stdout.channel.recv_exit_status()
    
    client.close()

if __name__ == '__main__':
    main()
