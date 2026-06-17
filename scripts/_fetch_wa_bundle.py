import os
import paramiko

PWD = os.environ.get("VPS_PASSWORD", "")
REMOTE_BASE = "/opt/telegramforward.old"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FILES = [
    "services/whatsapp_send_service.py",
    "services/whatsapp_bsp.py",
    "services/whatsapp_inbox_service.py",
    "services/whatsapp_gupshup.py",
    "services/whatsapp_interakt.py",
    "services/whatsapp_media_service.py",
    "core/contact_link_store.py",
    "core/phone_utils.py",
    "core/whatsapp_templates.py",
    "core/whatsapp_identity.py",
    "core/lead_graph.py",
    "docs/WHATSAPP_INTEGRATION.md",
    "config/whatsapp_templates.yaml",
    "scripts/_deploy_whatsapp_once.py",
    "core/whatsapp_api.py",
    "core/wa_media_store.py",
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("187.127.169.159", username="root", password=PWD, timeout=30)
sftp = c.open_sftp()
for rel in FILES:
    remote = f"{REMOTE_BASE}/{rel}"
    try:
        sftp.stat(remote)
    except OSError:
        print("MISSING", rel)
        continue
    local = os.path.join(REPO, rel.replace("/", os.sep))
    os.makedirs(os.path.dirname(local), exist_ok=True)
    sftp.get(remote, local)
    print("OK", rel)
sftp.close()
_, o, _ = c.exec_command(
    "grep -rn install_whatsapp /opt/telegramforward.old --include='*.py' 2>/dev/null | head -20; "
    "grep -rn 'def install' /opt/telegramforward.old/core/*whatsapp* 2>/dev/null; "
    "ls /opt/telegramforward.old/core/*whatsapp* 2>/dev/null; "
    "ls /opt/telegramforward.old/services/*whatsapp* 2>/dev/null",
    timeout=60,
)
print(o.read().decode())
c.close()
