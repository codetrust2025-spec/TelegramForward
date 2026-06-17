import os
import paramiko

HOST = "187.127.169.159"
USER = "root"
PASSWORD = os.environ.get("VPS_PASSWORD", "")
PATHS = [
    "/opt/telegramforward.old/static/index.html",
    "/opt/telegramforward/static/index.html",
]


def main():
    if not PASSWORD:
        print("VPS_PASSWORD not set")
        return 1
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    for path in PATHS:
        cmd = f"head -15 {path} 2>/dev/null; echo '---'; ls -lt $(dirname {path})/assets/*.js 2>/dev/null | head -5"
        _, o, e = c.exec_command(cmd, timeout=30)
        print(f"=== {path} ===")
        print(o.read().decode())
        err = e.read().decode().strip()
        if err:
            print("err:", err)
    c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
