import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
for start, end, label in [(121, 180, "start"), (340, 415, "finish/outcome")]:
    _, o, _ = c.exec_command(
        f"sed -n '{start},{end}p' /opt/telegramforward.old/services/voice_call_service.py",
        timeout=30,
    )
    print(f"=== {label} ===")
    print(o.read().decode("utf-8", errors="replace"))
c.close()
