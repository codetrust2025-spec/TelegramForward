#!/usr/bin/env python3
import socket, paramiko, sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PASSWORD = "8897870998s@SS"
sock = socket.create_connection(("187.127.169.159", 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(hostname="187.127.169.159", username="root", password=PASSWORD, sock=sock)

test = r'''
import asyncio, traceback, sys
sys.path.insert(0, "/opt/telegramforward.old")

async def main():
    slot = "account7"
    from core.telegram_client import get_client
    from features.health_check import check_account_health
    from core.groups_store import load_master_groups, groups_readonly_snapshot_for_slot, load_account_dead
    from core.message_rewrite import prepare_cycle_message
    from core.group_assignment import partition_summary
    from core.execution_policy import compute_execution_policy
    from core.unified_scheduler import build_scheduler_context
    
    try:
        client = await get_client(slot)
        print("1 client ok")
        health = await check_account_health(client, None)
        print("2 health", health)
        if isinstance(health, tuple):
            health = health[0]
        if health != "ok":
            print("STOP: health not ok")
            return
        me = await client.get_me()
        print("3 me", me.id)
        master = load_master_groups()
        snap = groups_readonly_snapshot_for_slot(slot)
        print("4 snap", len(snap))
        # mimic filter - read blocked from state file
        invalid, blocked = load_account_dead(slot)
        blocked_set = set(blocked or [])
        groups = [g for g in snap if g not in blocked_set]
        print("5 after blocked filter", len(groups))
        msg = prepare_cycle_message(slot, 1)
        print("6 msg", len(msg))
        pol = compute_execution_policy(slot, health_score=100, heavy_rate_limit=False, flood_streak=0, fleet_pressure=0, fleet_delay_multiplier=1.0, recently_flooded=False)
        print("7 policy", pol.fleet_pressure)
        ctx = build_scheduler_context(slot, health_score=100, success_rate=0.5, flood_streak=0, cycles_without_flood=0, fleet_pressure=0, unhealthy=False, heavy_rate_limit=False, speed_mode="normal")
        print("8 scheduler ok")
        part = partition_summary(slot, master)
        print("9 partition", part)
        print("SUCCESS all steps")
    except Exception:
        traceback.print_exc()

asyncio.run(main())
'''

_, stdout, stderr = c.exec_command(f"cd /opt/telegramforward.old && ./venv/bin/python3 - <<'PY'\n{test}\nPY", timeout=120)
print("OUT:", stdout.read().decode(errors="replace"))
print("ERR:", stderr.read().decode(errors="replace")[:4000])

# grep _filter_groups
_, stdout, _ = c.exec_command("grep -n 'def _filter_groups' /opt/telegramforward.old/workers/account_worker.py; sed -n '$(grep -n \"def _filter_groups\" /opt/telegramforward.old/workers/account_worker.py | head -1 | cut -d: -f1),+40p' /opt/telegramforward.old/workers/account_worker.py", timeout=30)
print("\n=== _filter_groups ===")
print(stdout.read().decode(errors="replace")[:3000])
c.close()
