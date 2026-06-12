#!/usr/bin/env python3
import os, socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = os.environ.get("VPS_PASSWORD", "")

def run(cmd):
    sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
    _, stdout, stderr = c.exec_command(cmd, timeout=120)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    c.close()
    return out + err

print(run("grep -rl 'smart.reply\\|smart_reply\\|Hi.*Karthik\\|greeting\\|first_name\\|lead_name' /opt/telegramforward.old/core /opt/telegramforward.old/*.py 2>/dev/null | head -30"))
print("---")
print(run("grep -rn 'What can I help\\|assistant_name\\|display_name\\|greet' /opt/telegramforward.old/core/ai* /opt/telegramforward.old/core/*smart* /opt/telegramforward.old/core/*inbox* 2>/dev/null | head -40"))
