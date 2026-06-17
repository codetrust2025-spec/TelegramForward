"""Test POST /login/send-otp on VPS for account11."""
import json
import os
import sys

import paramiko

HOST = "187.127.169.159"
PWD = os.environ.get("VPS_PASSWORD", "")
SLOT = sys.argv[1] if len(sys.argv) > 1 else "account11"
PHONE = sys.argv[2] if len(sys.argv) > 2 else "+919908957244"


def main() -> None:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username="root", password=PWD, timeout=30)
    body = json.dumps({"phone": PHONE, "slot": SLOT})
    cmd = (
        "curl -s -m 55 -w '\\nhttp_code:%{http_code}' "
        "-X POST http://127.0.0.1:8000/login/send-otp "
        "-H 'Content-Type: application/json' "
        f"-d '{body}'"
    )
    _, o, e = c.exec_command(cmd, timeout=70)
    print(o.read().decode())
    err = e.read().decode().strip()
    if err:
        print("stderr:", err)
    c.close()


if __name__ == "__main__":
    main()
