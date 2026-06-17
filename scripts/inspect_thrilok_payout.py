#!/usr/bin/env python3
import os, socket, sys
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

def ssh_run(cmd: str) -> str:
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname=HOST, username=USER, password=PWD, sock=sock)
    _, o, e = c.exec_command(cmd, timeout=120)
    out = o.read().decode("utf-8", errors="replace")
    err = e.read().decode("utf-8", errors="replace")
    c.close()
    return out + ("\n" + err if err.strip() else "")

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for backup in [
        "/opt/telegramforward.old/backups/pre_prune_20260605_093708/handler_expenses.json",
        "/opt/telegramforward.old/backups/pre_prune_20260605_093754/handler_expenses.json",
        "/opt/telegramforward.old/backups/pre_prune_20260605_093849/handler_expenses.json",
        "/opt/telegramforward.old/backups/pre_keerthana_delete_20260605_095113/handler_expenses.json",
    ]:
        print(f"=== {backup} ===")
        print(ssh_run(f"cat {backup} 2>/dev/null || echo MISSING"))
