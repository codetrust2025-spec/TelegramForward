import os
import urllib.request

import paramiko

PWD = os.environ["VPS_PASSWORD"]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
_, o, _ = c.exec_command("wc -l /opt/telegramforward/features/candidate_store.py")
print("lines:", o.read().decode())
test = (
    "cd /opt/telegramforward && PYTHONPATH=/opt/telegramforward "
    "./venv/bin/python -c \"from features import candidate_store as cs; "
    "print('upcoming', hasattr(cs, 'interview_upcoming')); "
    "print('global', hasattr(cs, 'interview_global_summary'))\""
)
_, o, e = c.exec_command(test)
print(o.read().decode())
err = e.read().decode()
if err:
    print("stderr:", err[:800])
c.close()

html = urllib.request.urlopen("https://teleautomation.online/", timeout=20).read().decode()
print("dashboard.bundle.js:", "dashboard.bundle.js" in html)
print("Daily ops in bundle:", "Daily ops" in urllib.request.urlopen(
    "https://teleautomation.online/assets/dashboard.bundle.js", timeout=120
).read().decode("utf-8", errors="replace")[:500000])
