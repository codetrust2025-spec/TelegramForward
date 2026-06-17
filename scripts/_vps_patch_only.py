import os, sys, paramiko
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REMOTE = "/opt/telegramforward"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", "root", password=os.environ.get("VPS_PASSWORD", ""), timeout=30)
sftp = c.open_sftp()
sftp.put(os.path.join(REPO, "scripts", "_patch_confirm.js"), f"{REMOTE}/scripts/_patch_confirm.js")
sftp.close()
_, o, e = c.exec_command(f"cd {REMOTE} && node scripts/_patch_confirm.js", timeout=60)
print(o.read().decode())
if e.read().strip():
    print("stderr:", e.read().decode()[:500])
c.close()
