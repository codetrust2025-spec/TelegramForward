#!/usr/bin/env python3
import os, socket, sys, subprocess
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

def run(cmd, t=60):
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    _, o, e = c.exec_command(cmd, timeout=t)
    return o.read().decode() + e.read().decode()

ACTIVE = ["account1","account2","account3","account4","account5","account6","account7","account8","account9","account10"]

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=== Session files ===")
    for a in ACTIVE:
        print(run(f"ls -la /opt/telegramforward.old/data/accounts/{a}/session*.session 2>/dev/null | head -3").strip() or f"{a}: no session file")

    print("\n=== Wrong session errors per account (last 500 log lines) ===")
    log = run("pm2 logs telegram-backend --lines 500 --nostream 2>&1", t=30)
    for a in ACTIVE:
        hits = sum(1 for line in log.splitlines() if a in line.lower() and "wrong session" in line.lower())
        conn = sum(1 for line in log.splitlines() if a in line.lower() and "connection failed" in line.lower())
        started = sum(1 for line in log.splitlines() if a in line.lower() and "worker started" in line.lower())
        fwd = sum(1 for line in log.splitlines() if a in line.lower() and ("forward" in line.lower() or "tick" in line.lower()))
        if hits or conn or started:
            print(f"{a}: wrong_session={hits} conn_fail={conn} worker_started={started} fwd_lines={fwd}")

    print("\n=== Last 8 lines per forward account in log ===")
    for a in ["account1","account2","account4","account6","account9"]:
        lines = [l for l in log.splitlines() if a.replace("account","") in l or a in l.lower()]
        print(f"--- {a} ---")
        for l in lines[-8:]:
            print(l[:200])
