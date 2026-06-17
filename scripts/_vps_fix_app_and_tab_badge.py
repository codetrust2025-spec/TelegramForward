"""Upload tab badge patch script and run on VPS."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    if not PWD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1
    local = os.path.join(REPO, "scripts", "_remote_tab_badge_patch.py")
    remote = f"{REMOTE}/scripts/_remote_tab_badge_patch.py"

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()
    sftp.put(local, remote)
    sftp.close()
    cmd = f"TA_REMOTE={REMOTE} python3 {remote}"
    print(">>>", cmd)
    _, o, e = c.exec_command(cmd, timeout=120)
    print(o.read().decode())
    err = e.read().decode()
    if err.strip():
        print("stderr:", err)
    code = o.channel.recv_exit_status()
    c.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
