"""Resume account workers and flush Karthik queue on VPS."""
import asyncio
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REMOTE = "/opt/telegramforward"
PY = f"{REMOTE}/venv/bin/python"


async def main() -> None:
    import paramiko
    from dotenv import load_dotenv

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("187.127.169.159", username="root", password=os.environ["VPS_PASSWORD"], timeout=30)

    script = f"""
import asyncio
import sys
sys.path.insert(0, "{REMOTE}")
from dotenv import load_dotenv
load_dotenv("{REMOTE}/.env")

async def run():
    from services.account_manager import manager
    from core.config import ACCOUNTS
    from core import ai_smart_reply
    from core.karthik_inbox_sweep import start, status
    start()
    resumed = await manager.resume_persisted_workers()
    print("resumed", resumed)
    for slot in ACCOUNTS:
        try:
            w = manager.get_worker(slot)
            if not w.state.running:
                await w.start()
                print("started", slot)
        except Exception as e:
            print("start_fail", slot, e)
    print("sweep", status())
    print("catch_up", await ai_smart_reply.catch_up_pending_replies(max_replies=10))

asyncio.run(run())
"""
    path = f"{REMOTE}/scripts/_wake_karthik_workers_once.py"
    sftp = ssh.open_sftp()
    with sftp.open(path, "w") as f:
        f.write(script)
    sftp.close()

    _, o, e = ssh.exec_command(f"cd {REMOTE} && PYTHONPATH={REMOTE} {PY} scripts/_wake_karthik_workers_once.py", timeout=300)
    print((o.read() + e.read()).decode())

    _, o, e = ssh.exec_command(
        "sleep 30 && pm2 logs telegram-backend --nostream --lines 40 2>/dev/null "
        "| grep -iE 'ai_smart_reply|karthik' | tail -12",
        timeout=60,
    )
    print((o.read() + e.read()).decode())
    ssh.close()


if __name__ == "__main__":
    asyncio.run(main())
