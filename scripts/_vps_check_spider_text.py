import json, paramiko, os
P = os.environ["VPS_PASSWORD"]
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("187.127.169.159", username="root", password=P, timeout=30)
_, o, _ = ssh.exec_command(
    """python3 -c "
import json
d=json.load(open('/opt/telegramforward.old/data/accounts/account7/dm_inbox.json'))
c=d['conversations']['8345253416']
for mid in (6322,6333,6335):
  m=next(x for x in c['messages'] if x['id']==mid)
  print(mid, m.get('media_type'), repr((m.get('text') or '')[:120]))
" """,
    timeout=30,
)
print(o.read().decode())
ssh.close()
