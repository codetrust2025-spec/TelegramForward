#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "REMOVED_VPS_PASSWORD"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

test = r'''
import asyncio, traceback, sys
sys.path.insert(0, "/opt/telegramforward.old")

async def main():
    slot = "account7"
    try:
        from core.telegram_client import get_client, check_account_health
        from core.groups_store import load_master_groups, groups_readonly_snapshot_for_slot, load_account_dead
        from core.message_store import prepare_cycle_message
        from core.group_partition import partition_summary
        
        client = await get_client(slot)
        print("client ok")
        health = await check_account_health(client, None)
        print("health", health)
        me = await client.get_me()
        print("me", me.id)
        master = load_master_groups()
        print("master groups", len(master))
        disk_invalid, disk_blocked = load_account_dead(slot)
        print("dead", len(disk_invalid), len(disk_blocked))
        from workers.account_worker import AccountWorker
        # can't easily instantiate - inline filter
        from core.groups_store import groups_readonly_snapshot_for_slot
        snap = groups_readonly_snapshot_for_slot(slot)
        print("snapshot", len(snap))
        msg = prepare_cycle_message(slot, 1)
        print("msg len", len(msg))
        part = partition_summary(slot, master)
        print("partition", part)
        from core.execution_policy import compute_execution_policy
        from core.unified_scheduler import build_scheduler_context
        pol = compute_execution_policy(slot, health_score=100)
        print("policy ok", pol.fleet_pressure)
        ctx = build_scheduler_context(slot, health_score=100, success_rate=0.5, flood_streak=0, cycles_without_flood=0, fleet_pressure=0, unhealthy=False, heavy_rate_limit=False, speed_mode="normal")
        print("scheduler ok")
    except Exception as e:
        traceback.print_exc()

asyncio.run(main())
'''

_, stdout, stderr = c.exec_command(f"cd /opt/telegramforward.old && ./venv/bin/python3 - <<'PY'\n{test}\nPY", timeout=120)
print("OUT:", stdout.read().decode(errors="replace"))
print("ERR:", stderr.read().decode(errors="replace")[:5000])
c.close()
