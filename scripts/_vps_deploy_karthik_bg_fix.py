"""Deploy list_pending_inbound_targets fix + wake BG lead on VPS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = ["core/ai_smart_reply.py"]


def main() -> int:
    import paramiko

    if not PASSWORD:
        print("Set VPS_PASSWORD", file=sys.stderr)
        return 1

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()

    for rel in FILES:
        local = os.path.join(root, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        sftp.put(local, remote)
        print(f"uploaded {rel}")

    sftp.close()

    py = f"{REMOTE}/venv/bin/python"
    cmds = [
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} -m py_compile core/ai_smart_reply.py",
        f"cd {REMOTE} && PYTHONPATH={REMOTE} pm2 restart telegram-backend --update-env",
        "sleep 12",
        f"cd {REMOTE} && PYTHONPATH={REMOTE} {py} <<'PYEOF'\n"
        "import json, time, urllib.request\n"
        "from dotenv import load_dotenv\n"
        "load_dotenv('/opt/telegramforward/.env')\n"
        "from core import ai_smart_reply\n"
        "from core.dm_store import load_inbox\n"
        "print('health pending', ai_smart_reply.health().get('pending_inbound'))\n"
        "req = urllib.request.Request(\n"
        "    'http://127.0.0.1:8000/ai/smart-reply/catch-up',\n"
        "    data=json.dumps({'slot': 'account9', 'max_replies': 5, 'force': True}).encode(),\n"
        "    headers={'Content-Type': 'application/json'},\n"
        "    method='POST',\n"
        ")\n"
        "with urllib.request.urlopen(req, timeout=120) as resp:\n"
        "    print('catch_up_api', resp.read().decode())\n"
        "time.sleep(30)\n"
        "conv = (load_inbox('account9').get('conversations') or {}).get('1234875138') or {}\n"
        "for m in (conv.get('messages') or [])[-5:]:\n"
        "    print('MSG', m.get('direction'), repr((m.get('text') or '')[:80]), m.get('sent_by'))\n"
        "PYEOF",
    ]
    for cmd in cmds:
        print(f"\n$ {cmd[:90]}...")
        _, stdout, stderr = ssh.exec_command(cmd, timeout=180)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        if out.strip():
            print(out)
        if err.strip():
            print(err, file=sys.stderr)

    ssh.close()
    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
