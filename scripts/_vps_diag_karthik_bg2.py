import os, paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password=os.environ['VPS_PASSWORD'], timeout=30)
probe = r'''cd /opt/telegramforward && PYTHONPATH=/opt/telegramforward /opt/telegramforward/venv/bin/python <<'PY'
from dotenv import load_dotenv
load_dotenv('/opt/telegramforward/.env')
from core.dm_store import load_inbox
from messaging.account_queue import queue_manager
import asyncio

d = load_inbox('account9')
keys = list((d.get('conversations') or {}).keys())
print('conv_keys', keys)
bad = [k for k in keys if not str(k).lstrip('-').isdigit()]
print('non_numeric_keys', bad)

async def q():
    qm = queue_manager.get_queue('account9')
    depth = await qm.depth()
    pending = await qm.has_pending_ai_auto_reply_for_user(1234875138)
    print('queue_depth', depth, 'ai_pending_bg', pending)
asyncio.run(q())
PY'''
_, o, e = c.exec_command(probe, timeout=30)
print((o.read()+e.read()).decode())
_, o2, _ = c.exec_command('curl -s http://127.0.0.1:8000/state | python3 -c "import sys,json; d=json.load(sys.stdin); a=[x for x in d.get(\"accounts\",[]) if x.get(\"slot\")==\"account9\"]; print(a[0] if a else \"missing\")" 2>/dev/null | head -c 500', timeout=20)
print('account9:', o2.read().decode())
c.close()
