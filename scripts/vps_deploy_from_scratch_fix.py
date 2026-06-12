#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASSWORD = os.environ.get("VPS_PASSWORD", "")
LOCAL = r"C:\Users\codet\OneDrive\Desktop\Automation\scripts\ai_smart_reply_vps.py"
REMOTE = "/opt/telegramforward.old/core/ai_smart_reply.py"
REMOTE_LIVE = "/opt/telegramforward/core/ai_smart_reply.py"

sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
sftp = c.open_sftp()

for remote in [REMOTE, REMOTE_LIVE]:
    try:
        backup = remote + ".bak_from_scratch"
        with sftp.open(remote, "rb") as rf, sftp.open(backup, "wb") as wf:
            wf.write(rf.read())
        sftp.put(LOCAL, remote)
        print(f"Uploaded -> {remote}")
    except Exception as e:
        print(f"Skip {remote}: {e}")

sftp.close()

test_cmd = """cd /opt/telegramforward.old && python3 - <<'PY'
import sys
sys.path.insert(0, "/opt/telegramforward.old")
from core.ai_smart_reply import (
    _job_seeker_reply,
    _user_wants_full_placement_from_scratch,
)

history = [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hi 👍 I'm Karthik. What can I help you with?"},
    {"role": "user", "content": "I need job"},
]
r1 = _job_seeker_reply("I need job", history=history, lang="english", lead={"name": "Unknown"})
assert "scheduled round" not in r1.lower(), r1
print("need job OK:", r1[:80])

history2 = history + [
    {"role": "assistant", "content": r1},
    {"role": "user", "content": "Everything should be done by scratch"},
]
assert _user_wants_full_placement_from_scratch("Everything should be done by scratch", history2)
r2 = _job_seeker_reply("Everything should be done by scratch", history=history2, lang="english", lead={"name": "Unknown"})
assert "experience" in r2.lower() or "fresher" in r2.lower(), r2
assert "scheduled round" not in r2.lower(), r2
print("from scratch OK:", r2[:100])
print("ALL TESTS PASSED")
PY
"""
_, stdout, stderr = c.exec_command(test_cmd, timeout=60)
out = stdout.read().decode()
err = stderr.read().decode()
print(out)
if err:
    print("STDERR:", err)
if "ALL TESTS PASSED" not in out:
    raise SystemExit("Deploy test failed")

_, stdout, stderr = c.exec_command("pm2 restart telegram-backend --update-env", timeout=60)
print(stdout.read().decode())
print(stderr.read().decode())
c.close()
print("Done")
