import asyncio
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REMOTE = "/opt/telegramforward"
PY = f"{REMOTE}/venv/bin/python"


def main() -> None:
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("187.127.169.159", username="root", password=os.environ["VPS_PASSWORD"], timeout=30)
    sftp = ssh.open_sftp()
    sftp.put(os.path.join(root, "server.py"), f"{REMOTE}/server.py")
    sftp.close()

    def run(cmd: str) -> str:
        _, o, e = ssh.exec_command(cmd, timeout=180)
        return (o.read() + e.read()).decode()

    print(run(f"cd {REMOTE} && PYTHONPATH={REMOTE} pm2 restart telegram-backend --update-env"))
    print(run("sleep 12"))

    verify = os.path.join(root, "scripts", "_vps_verify_karthik_once.py")
    with open(verify, "w", encoding="utf-8") as f:
        f.write(
            "import asyncio\n"
            "from dotenv import load_dotenv\n"
            f'load_dotenv("{REMOTE}/.env")\n'
            "from core.karthik_inbox_sweep import status\n"
            "from core import ai_smart_reply\n"
            'print("sweep", status())\n'
            'print("health", ai_smart_reply.health())\n'
            'print("catch_up", asyncio.run(ai_smart_reply.catch_up_pending_replies(max_replies=8)))\n'
        )
    sftp = ssh.open_sftp()
    sftp.put(verify, f"{REMOTE}/scripts/_vps_verify_karthik_once.py")
    sftp.close()
    print(run(f"cd {REMOTE} && PYTHONPATH={REMOTE} {PY} scripts/_vps_verify_karthik_once.py"))
    ssh.close()


if __name__ == "__main__":
    main()
