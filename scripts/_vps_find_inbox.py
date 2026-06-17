import os, sys
import paramiko

PASSWORD = os.environ.get("VPS_PASSWORD", "")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("187.127.169.159", username="root", password=PASSWORD, timeout=30)
cmds = [
    "find /opt/telegramforward.old/data -name 'dm_inbox.json' 2>/dev/null | head -5",
    "find /opt/telegramforward/data -name 'dm_inbox.json' 2>/dev/null | head -5",
    "grep -l '7282523499' /opt/telegramforward.old/data/accounts/*/dm_inbox.json 2>/dev/null | head -3",
    "ls -la /opt/telegramforward.old/data/accounts/account7/dm_media_cache/ 2>/dev/null | tail -8",
    "pm2 describe telegram-backend 2>/dev/null | grep -E 'cwd|script path'",
]
for c in cmds:
    print("===", c)
    _, o, _ = ssh.exec_command(c, timeout=60)
    print(o.read().decode())
ssh.close()
