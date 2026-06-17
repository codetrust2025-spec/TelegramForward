"""Deploy backdoor-job / layoff reply routing fix."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def main() -> None:
    import paramiko

    if not PASSWORD:
        print("Set VPS_PASSWORD")
        sys.exit(1)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rel = "core/ai_smart_reply.py"
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()
    sftp.put(os.path.join(root, rel), f"{REMOTE}/{rel}")
    print(f"uploaded {rel}")
    sftp.close()
    py = f"{REMOTE}/venv/bin/python"
    for cmd in [
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} -m py_compile core/ai_smart_reply.py",
        f"cd {REMOTE} && PYTHONPATH={REMOTE} pm2 restart telegram-backend --update-env",
    ]:
        _, o, e = ssh.exec_command(cmd, timeout=120)
        print(o.read().decode())
        err = e.read().decode()
        if err.strip():
            print(err, file=sys.stderr)
    ssh.close()
    print("Done — backdoor/layoff threads get correct replies now.")


if __name__ == "__main__":
    main()
