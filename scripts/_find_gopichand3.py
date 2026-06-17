import os
import paramiko

PWD = os.environ["VPS_PASSWORD"]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
cmd = (
    "python3 <<'PY'\n"
    "import json\n"
    "for p in ['/opt/telegramforward/data/candidates.json','/opt/telegramforward/data/interview_support_tally.json']:\n"
    "  try:\n"
    "    t=open(p,encoding='utf-8').read()\n"
    "    if '7a6a68d247' in t or 'Gopichand' in t:\n"
    "      print('HIT', p)\n"
    "      if p.endswith('candidates.json'):\n"
    "        d=json.loads(t)\n"
    "        for r in d.get('candidates',[]):\n"
    "          if 'gopichand' in (r.get('name') or '').lower() or r.get('id')=='7a6a68d247':\n"
    "            print(r)\n"
    "  except Exception as e:\n"
    "    print(p, e)\n"
    "PY"
)
_, o, _ = c.exec_command(cmd)
print(o.read().decode("utf-8", errors="replace"))
c.close()
