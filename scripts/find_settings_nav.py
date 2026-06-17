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
    c.close()
    return out

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(ssh_run("grep -rn 'Settings' /opt/telegramforward.old/dashboard/src 2>/dev/null | grep -v AISmart | grep -v printer | grep -v ai-settings | grep -v OpenAi"))
    print(ssh_run("grep -rn 'id: \"settings\"\\|id:\"settings\"\\|settings.*label' /opt/telegramforward.old/dashboard 2>/dev/null | head -20"))
    print(ssh_run("head -30 /opt/telegramforward.old/dashboard/index.html"))
