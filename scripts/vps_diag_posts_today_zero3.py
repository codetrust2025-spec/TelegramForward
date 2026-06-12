#!/usr/bin/env python3
import os, socket, sys
import paramiko

HOST, USER = "187.127.169.159", "root"
PWD = os.environ.get("VPS_PASSWORD", "")

def run(cmd):
    sock = socket.create_connection((HOST, 22), timeout=30)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, sock=sock)
    _, o, e = c.exec_command(cmd, timeout=90)
    return o.read().decode() + e.read().decode()

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(run("pm2 list"))
    print("--- account1 logs ---")
    print(run("pm2 logs account1 --lines 15 --nostream 2>&1"))
    print("--- curl daily stats ---")
    print(run("curl -s --max-time 10 http://127.0.0.1:8000/stats/daily | head -c 400"))
