import json
import os
import paramiko

P = os.environ["VPS_PASSWORD"]
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("187.127.169.159", username="root", password=P, timeout=30)
sftp = ssh.open_sftp()
sftp.put(os.path.join(root, "core", "dm_store.py"), "/opt/telegramforward.old/core/dm_store.py")
sftp.close()
_, o, _ = ssh.exec_command(
    """python3 <<'PY'
import json
p = "/opt/telegramforward.old/data/accounts/account7/dm_inbox.json"
d = json.load(open(p))
m = next(x for x in d["conversations"]["8345253416"]["messages"] if x["id"] == 6335)
m.pop("media", None)
m.pop("media_type", None)
json.dump(d, open(p, "w"), indent=2)
print("ok", m["text"][:60])
PY""",
    timeout=30,
)
print(o.read().decode())
ssh.exec_command("pm2 restart telegram-backend --update-env", timeout=30)
ssh.close()
