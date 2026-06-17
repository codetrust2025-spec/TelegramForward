import os, paramiko
P = os.environ["VPS_PASSWORD"]
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("187.127.169.159", username="root", password=P, timeout=30)
cmds = [
    "file /opt/telegramforward.old/data/accounts/account7/dm_media_cache/8345253416_6335.bin",
    "wc -c /opt/telegramforward.old/data/accounts/account7/dm_media_cache/8345253416_6335.bin",
    "xxd /opt/telegramforward.old/data/accounts/account7/dm_media_cache/8345253416_6335.bin | head -2",
]
for c in cmds:
    _, o, _ = ssh.exec_command(c, timeout=30)
    print(o.read().decode())
ssh.close()
