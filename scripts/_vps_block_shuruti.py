"""Block SHURUTI SEN spam chat on production."""
import json
import os
import sys

import paramiko

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
PASSWORD = os.environ.get("VPS_PASSWORD", "")


def run(cmd: str) -> str:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username="root", password=PASSWORD, timeout=30)
    _, stdout, _ = client.exec_command(cmd, timeout=120)
    out = stdout.read().decode(errors="replace")
    client.close()
    return out


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1
    print("Scan all...")
    scan = run(
        "curl -s -X POST http://127.0.0.1:8000/crm/karthik/block-spam-chats "
        "-H 'Content-Type: application/json' -d '{}'"
    )
    try:
        data = json.loads(scan)
        print(f"scanned={data.get('scanned')} blocked={data.get('blocked_count')}")
        for row in data.get("blocked") or []:
            print(f"  {row.get('slot')}:{row.get('user_id')} {row.get('name','')[:50]}")
    except json.JSONDecodeError:
        print(scan[:500])

    print("Block account9 SHURUTI...")
    block = run(
        "curl -s -X POST http://127.0.0.1:8000/inbox/account9/karthik/block-spam/6246102335"
    )
    try:
        data = json.loads(block)
        print("status", data.get("status"), "lead", (data.get("lead") or {}).get("status"))
    except json.JSONDecodeError:
        print(block[:500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
