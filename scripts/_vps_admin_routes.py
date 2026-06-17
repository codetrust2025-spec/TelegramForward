import os, sys, paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REMOTE = "/opt/telegramforward.old"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
cmds = [
    f"grep -rn '@app\\.' {REMOTE}/server.py | grep -i admin | head -40",
    f"grep -rn 'admin' {REMOTE}/core/admin_dashboard.py 2>/dev/null | head -30",
    f"test -f {REMOTE}/core/admin_dashboard.py && wc -l {REMOTE}/core/admin_dashboard.py || echo no admin_dashboard",
    f"grep -rn 'install.*admin\\|admin_dashboard' {REMOTE}/server.py | head -20",
    "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/admin/overview",
    "curl -s http://127.0.0.1:8000/admin/overview | head -c 200",
    "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/admin/metrics/overview",
    "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/metrics/overview",
]
for cmd in cmds:
    print("===", cmd[:100])
    _, o, e = c.exec_command(cmd, timeout=60)
    print(o.read().decode("utf-8", errors="replace")[:2000])
    err = e.read().decode().strip()
    if err:
        print("stderr:", err[:200])
c.close()
