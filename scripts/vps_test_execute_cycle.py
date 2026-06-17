#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
REMOTE = r'''
import asyncio, traceback
from services.account_manager import manager
from core.groups_store import groups_readonly_snapshot_for_slot, load_master_groups
from core.message_store import load_message_for_account

async def test_cycle_init(slot):
    w = manager.get_worker(slot)
    if not w:
        return f"{slot}: no worker"
    st = w.state
    print(f"\n=== {slot} worker state ===")
    print(f"  running={st.running} campaign_running={st.campaign_running} status={st.campaign_status}")
    print(f"  message len={len(load_message_for_account(slot))}")
    print(f"  snapshot groups={len(groups_readonly_snapshot_for_slot(slot))}")
    print(f"  master={len(load_master_groups())}")
    try:
        # call internal cycle prep if exists
        from core.telegram_client import get_client, check_client_health, reconnect_client
        client = await get_client(slot)
        print(f"  client={client is not None}")
        if client:
            health = await check_client_health(client)
            print(f"  health={health}")
            me = await client.get_me()
            print(f"  get_me OK id={me.id}")
    except Exception as e:
        print(f"  client error: {type(e).__name__}: {e}")
        traceback.print_exc()
    try:
        async with w._cycle_lock:
            result = await w._execute_cycle()
            print(f"  _execute_cycle returned: {result}")
            print(f"  after: my_groups={len(st.my_groups or [])} success={st.success} cycle={st.cycle} status={st.status}")
    except Exception as e:
        print(f"  _execute_cycle EXCEPTION: {type(e).__name__}: {e}")
        traceback.print_exc()

async def main():
    # stop others first via manager
    for slot in [f"account{i}" for i in range(1,11)]:
        if slot != "account7":
            try:
                await manager.stop_account_async(slot)
            except Exception:
                pass
    await asyncio.sleep(3)
    if not manager.get_worker("account7") or not manager.get_worker("account7").state.campaign_running:
        await manager.start_account("account7", feature="campaign")
        await asyncio.sleep(5)
    await test_cycle_init("account7")

asyncio.run(main())
'''
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)
_, stdout, stderr = c.exec_command(
    f"cd /opt/telegramforward.old && set -a && . ./.env && set +a && PYTHONPATH=. ./venv/bin/python - <<'PY'\n{REMOTE}\nPY",
    timeout=180,
)
print(stdout.read().decode("utf-8", errors="replace"))
print(stderr.read().decode("utf-8", errors="replace")[-8000:])
c.close()
