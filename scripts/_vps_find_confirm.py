import os, sys, paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REMOTE = "/opt/telegramforward"
path = f"{REMOTE}/dashboard/src/teleautomation-app.jsx"
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
cmds = [
    f"grep -n 'useConfirm must\\|ConfirmProvider\\|ConfirmContext\\|createContext(null)' {path} | head -40",
    f"grep -n 'function.*Confirm\\|confirm:' {path} | head -30",
    f"head -15 {path}",
    f"grep -n 'const k=W0\\|import.*react' {path} | head -20",
]
for cmd in cmds:
    print("===", cmd[:100])
    _, o, _ = c.exec_command(cmd, timeout=120)
    print(o.read().decode("utf-8", errors="replace")[:4000])
c.close()
