import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REMOTE = "/opt/telegramforward.old"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

REMOTE_PY = r'''
import os
os.chdir("/opt/telegramforward.old")
# Same import path as uvicorn worker
import server  # noqa: F401 — loads dotenv
from core import ai_smart_reply
print("cwd", os.getcwd())
print("env_key_len", len(os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""))
print("is_enabled", ai_smart_reply.is_enabled())
print("api_key_present", ai_smart_reply.health().get("api_key_present"))
'''

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)

path = f"{REMOTE}/scripts/_check_server_ai_once.py"
sftp = client.open_sftp()
with sftp.open(path, "w") as f:
    f.write(REMOTE_PY)
sftp.close()

stdin, stdout, stderr = client.exec_command(
    f"cd {REMOTE} && PYTHONPATH={REMOTE} ./venv/bin/python scripts/_check_server_ai_once.py",
    timeout=60,
)
print(stdout.read().decode("utf-8", errors="replace"))
print(stderr.read().decode("utf-8", errors="replace"))

client.close()
