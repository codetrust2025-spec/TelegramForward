import os, paramiko
P = os.environ["VPS_PASSWORD"]
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("187.127.169.159", username="root", password=P, timeout=30)
cmds = [
    "wc -c /opt/telegramforward.old/data/accounts/account7/dm_media_cache/7282523499_6299.webp",
    "xxd /opt/telegramforward.old/data/accounts/account7/dm_media_cache/7282523499_6299.webp | head -3",
    "ls -la /opt/telegramforward.old/static/assets/app-*.js | tail -2",
    "grep -l 'Sticker could not load' /opt/telegramforward.old/static/assets/*.js 2>/dev/null | tail -1",
    "grep -l 'Sticker could not load' /opt/telegramforward/static/assets/*.js 2>/dev/null | tail -1",
]
for c in cmds:
    print("===", c)
    _, o, _ = ssh.exec_command(c, timeout=30)
    print(o.read().decode() or "(empty)")
ssh.close()
