#!/usr/bin/env python3
import json
import os
import socket
import paramiko

HOST = "187.127.169.159"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

sock = socket.create_connection((HOST, 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, username="root", password=PASSWORD, sock=sock)

for port in (8080, 8000, 5000, 3000):
    _, out, _ = c.exec_command(f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}/state")
    code = out.read().decode().strip()
    if code == "200":
        _, out2, _ = c.exec_command(f"curl -s http://127.0.0.1:{port}/state")
        raw = out2.read().decode()
        st = json.loads(raw)
        info = st.get("account_info") or {}
        states = st.get("account_states") or {}
        logged = [s for s in info if info[s]]
        running = [s for s in logged if states.get(s, {}).get("running")]
        idle = [s for s in logged if not states.get(s, {}).get("running")]
        print(f"port {port}: logged_in={len(logged)} running={len(running)} idle={len(idle)}")
        print(f"  idle slots: {idle}")
        print(f"  running slots: {running}")
        break
else:
    _, out, _ = c.exec_command("curl -s https://teleautomation.online/state | head -c 500")
    print("via nginx:", out.read().decode()[:500])

c.close()
