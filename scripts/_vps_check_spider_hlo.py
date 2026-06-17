import json
import os
import paramiko

P = os.environ["VPS_PASSWORD"]
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("187.127.169.159", username="root", password=P, timeout=30)
_, o, _ = ssh.exec_command(
    """python3 <<'PY'
import json
d = json.load(open("/opt/telegramforward.old/data/accounts/account7/dm_inbox.json"))
c = d["conversations"].get("8345253416")
if not c:
    print("no conv")
else:
    for m in c.get("messages") or []:
        t = (m.get("text") or "").lower()
        if "hlo" in t:
            print(m.get("id"), m.get("sent_by"), m.get("sender_name"), m.get("ai"), m.get("ai_stage"), repr(m.get("text")))
PY""",
    timeout=30,
)
print(o.read().decode())
ssh.close()
