import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
sftp = c.open_sftp()
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sftp.get(
    "/opt/telegramforward.old/services/whatsapp_send_service.py",
    os.path.join(repo, "services", "whatsapp_send_service.py"),
)
print("downloaded whatsapp_send_service.py")
for path in [
    "/opt/telegramforward.old/core/whatsapp_api.py",
    "/opt/telegramforward.old/core/web_whatsapp_api.py",
    "/opt/telegramforward.old/features/whatsapp.py",
]:
    try:
        sftp.stat(path)
        local = os.path.join(repo, path.split("/opt/telegramforward.old/")[1].replace("/", os.sep))
        os.makedirs(os.path.dirname(local), exist_ok=True)
        sftp.get(path, local)
        print("downloaded", path)
    except OSError:
        pass
cmds = [
    "grep -rn whatsapp /opt/telegramforward.old/server.py /opt/telegramforward.old/core/*.py 2>/dev/null | head -60",
    "grep -rn link.phone /opt/telegramforward.old 2>/dev/null | head -20",
    "grep -rn webhooks/whatsapp /opt/telegramforward.old 2>/dev/null | head -20",
]
for cmd in cmds:
    print("===", cmd[:70])
    _, o, _ = c.exec_command(cmd, timeout=60)
    print(o.read().decode()[:6000])
sftp.close()
c.close()
