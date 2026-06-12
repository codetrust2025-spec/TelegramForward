#!/usr/bin/env python3
import os, sys
from pathlib import Path
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
ROOT = Path(__file__).resolve().parent.parent

def fetch(remote: str, local: Path):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", "root", PWD, timeout=30)
    sftp = c.open_sftp()
    local.parent.mkdir(parents=True, exist_ok=True)
    sftp.get(remote, str(local))
    sftp.close()
    c.close()

def run(cmd):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect("187.127.169.159", "root", PWD, timeout=30)
    _, o, _ = c.exec_command(cmd, timeout=120)
    out = o.read().decode("utf-8", errors="replace")
    c.close()
    return out

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(run("find /opt/telegramforward.old/features /opt/telegramforward.old/dashboard -iname '*candidate*' -o -iname '*handler*' -o -iname '*demo*' 2>/dev/null | head -40"))
    print(run("grep -n 'def.*candidate\\|/candidates\\|demo-tools\\|handler-expenses' /opt/telegramforward.old/server.py | head -30"))
    js = ROOT / "prod_bundle.js"
    fetch("/opt/telegramforward.old/static/assets/index-r6ZovQOX.js", js)
    tail = js.read_text(encoding="utf-8", errors="replace")[-500:]
    print("JS tail:", "sourceMappingURL" in tail, "len", js.stat().st_size)
