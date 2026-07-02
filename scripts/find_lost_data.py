#!/usr/bin/env python3
"""Find lost interview slot data from backups made today."""
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST, USER, PWD = "187.127.169.159", "root", "REMOVED_VPS_PASSWORD"

sock = socket.create_connection((HOST, 22), 30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username=USER, password=PWD, sock=sock)

script = r"""
echo "=== FILES MODIFIED TODAY AFTER 6PM (18:00) ==="
find /opt/telegramforward.old -name "*.backup*" -newer /opt/telegramforward.old/data/candidates.json -mtime -1 2>/dev/null | head -20
echo ""
echo "=== CANDIDATE STORE BACKUPS ==="
find /opt/telegramforward.old -name "*candidate*backup*" -o -name "*candidate*.bak" 2>/dev/null
find /opt/telegramforward.old -name "*.py.backup*" 2>/dev/null | grep candidate
echo ""
echo "=== CHECK candidates.json MODIFICATION TIME ==="
stat /opt/telegramforward.old/data/candidates.json | grep -i modify
echo ""
echo "=== CHECK FOR DEPLOY SCRIPTS RUN TODAY ==="
ls -lt /opt/telegramforward.old/features/candidate_store.py* 2>/dev/null
echo ""
echo "=== CHECK PM2 LOGS FOR ERRORS AROUND 6PM ==="
grep -n "DELETE\|candidates_store\|pg_save\|error\|Traceback" /root/.pm2/logs/telegram-backend-out.log 2>/dev/null | tail -20
grep -n "DELETE\|candidates_store\|pg_save\|error\|Traceback" /root/.pm2/logs/telegram-backend-error.log 2>/dev/null | tail -20
echo ""
echo "=== CHECK CRON BACKUP (daily at 2:15AM) ==="
ls -lt /opt/telegramforward.old/backups/daily/ 2>/dev/null | head -5
find /opt/telegramforward.old/backups -name "*20260702*" 2>/dev/null
echo ""
echo "=== STATIC BACKUP DIRS FROM TODAY ==="
find /opt/telegramforward.old/static.backup* -maxdepth 0 2>/dev/null
ls -lt /opt/telegramforward.old/static.backup* 2>/dev/null | head -5
echo ""
echo "=== JSON CANDIDATES HISTORY - check if older copies exist ==="
find /opt/telegramforward.old/data -name "candidates*" -ls 2>/dev/null
find /opt/telegramforward.old -name "candidates.json.bak" -o -name "candidates_backup*" 2>/dev/null
"""

_, stdout, stderr = c.exec_command(script, timeout=30)
print(stdout.read().decode("utf-8", "replace"))
err = stderr.read().decode("utf-8", "replace")
if err:
    print("STDERR:", err[:800])
c.close()
