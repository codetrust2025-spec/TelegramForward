"""Deploy server.py with resume routes."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD required", file=sys.stderr)
        return 1
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)
    sftp = c.open_sftp()
    sftp.put(os.path.join(REPO, "server.py"), "/opt/telegramforward/server.py")
    sftp.close()
    _, o, _ = c.exec_command(
        "grep -c 'resumes/{rid}/preview' /opt/telegramforward/server.py && "
        "curl -s -o /dev/null -w '%{http_code}' "
        "'http://127.0.0.1:8000/candidates/7a6a68d247/resumes/d32096422770/preview' && "
        "cd /opt/telegramforward && pm2 restart telegram-backend --update-env 2>&1 | tail -1"
    )
    print(o.read().decode("utf-8", errors="replace"))
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
