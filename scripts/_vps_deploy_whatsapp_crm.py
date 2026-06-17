"""Deploy WhatsApp Business CRM (backend routes + dashboard + contact links)."""
from __future__ import annotations

import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTES = ["/opt/telegramforward", "/opt/telegramforward.old"]
PASSWORD = os.environ.get("VPS_PASSWORD", "")
BUILD_STAMP = "2026-06-05-whatsapp-full"


def ensure_remote_dir(sftp, remote_dir: str) -> None:
    parts = remote_dir.strip("/").split("/")
    path = ""
    for p in parts:
        path += f"/{p}"
        try:
            sftp.stat(path)
        except OSError:
            try:
                sftp.mkdir(path)
            except OSError:
                pass


def put_tree(sftp, local_dir: str, remote_dir: str) -> None:
    for name in os.listdir(local_dir):
        lp = os.path.join(local_dir, name)
        rp = f"{remote_dir}/{name}"
        if os.path.isdir(lp):
            try:
                sftp.stat(rp)
            except OSError:
                try:
                    sftp.mkdir(rp)
                except OSError:
                    pass
            put_tree(sftp, lp, rp)
        else:
            sftp.put(lp, rp)


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dash = os.path.join(repo, "dashboard")
    static = os.path.join(repo, "static")

    print(">>> npm run build (local)")
    r = subprocess.run(
        ["npm", "run", "build"],
        cwd=dash,
        shell=os.name == "nt",
        check=False,
    )
    if r.returncode != 0:
        return r.returncode

    source_files = [
        "server.py",
        "core/config.py",
        "core/contact_link_store.py",
        "core/dm_store.py",
        "core/phone_utils.py",
        "core/whatsapp_api.py",
        "core/wa_media_store.py",
        "core/whatsapp_channel.py",
        "core/whatsapp_identity.py",
        "core/whatsapp_templates.py",
        "core/lead_graph.py",
        "services/whatsapp_send_service.py",
        "services/whatsapp_bsp.py",
        "services/whatsapp_inbox_service.py",
        "services/whatsapp_gupshup.py",
        "services/whatsapp_interakt.py",
        "services/whatsapp_media_service.py",
        "services/whatsapp_dispatch.py",
        "services/crm_service.py",
        "config/whatsapp_templates.yaml",
        "docs/WHATSAPP_INTEGRATION.md",
        "dashboard/src/config.js",
        "dashboard/src/utils/whatsapp.js",
        "dashboard/src/inbox/inboxUiUtils.js",
        "dashboard/src/inbox/inboxLayout.css",
        "dashboard/src/inbox/ChatComposer.jsx",
        "dashboard/src/inbox/MessageBubble.jsx",
        "dashboard/src/inbox/InboxMediaAttachment.jsx",
        "dashboard/src/inbox/MessageTimeline.jsx",
        "dashboard/src/inbox/ConversationListItem.jsx",
        "dashboard/src/components/InboxPanel.jsx",
        "dashboard/src/components/crm/LeadDetailsPanel.jsx",
        "dashboard/src/components/crm/ChatWindow.jsx",
    ]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    for remote in REMOTES:
        print(f"\n=== {remote} ===")
        for rel in source_files:
            local = os.path.join(repo, rel.replace("/", os.sep))
            remote_path = f"{remote}/{rel}".replace("\\", "/")
            ensure_remote_dir(sftp, os.path.dirname(remote_path).replace("\\", "/"))
            sftp.put(local, remote_path)
            print(f"  uploaded {rel}")
        put_tree(sftp, static, f"{remote}/static")
        print("  uploaded static/")

    sftp.close()

    _, o, _ = client.exec_command(
        f"grep -o '{BUILD_STAMP}' /opt/telegramforward/static/assets/app-*.js | head -1; "
        "grep -c install_whatsapp_routes /opt/telegramforward/server.py; "
        "curl -s http://127.0.0.1:8000/whatsapp/status | head -c 120",
        timeout=30,
    )
    print("Verify:", o.read().decode().strip())

    _, o3, _ = client.exec_command(
        "rsync -a --delete /opt/telegramforward.old/static/ /opt/telegramforward/static/",
        timeout=120,
    )
    print("nginx static sync:", o3.read().decode().strip()[-120:])

    _, o2, _ = client.exec_command(
        "pm2 restart telegram-backend --update-env 2>/dev/null || true",
        timeout=45,
    )
    print("pm2:", o2.read().decode().strip()[-280:])

    # Ensure WHATSAPP_ENABLED in .env (preserve existing API keys)
    env_patch = (
        "ENV=/opt/telegramforward/.env; "
        "touch \"$ENV\"; "
        "grep -q '^WHATSAPP_ENABLED=' \"$ENV\" || echo 'WHATSAPP_ENABLED=1' >> \"$ENV\"; "
        "grep -q '^WHATSAPP_DEFAULT_SLOT=' \"$ENV\" || echo 'WHATSAPP_DEFAULT_SLOT=account1' >> \"$ENV\"; "
        "grep -q '^WHATSAPP_BSP=' \"$ENV\" || echo 'WHATSAPP_BSP=interakt' >> \"$ENV\"; "
        "grep -q '^WHATSAPP_WEBHOOK_VERIFY_TOKEN=' \"$ENV\" || "
        "echo 'WHATSAPP_WEBHOOK_VERIFY_TOKEN=ta_whatsapp_verify_2026' >> \"$ENV\"; "
        "grep WHATSAPP_ \"$ENV\" | sed 's/API_KEY=.*/API_KEY=***/' | sed 's/TOKEN=.*/TOKEN=***/'"
    )
    _, o_env, _ = client.exec_command(env_patch, timeout=20)
    print("WhatsApp .env:", o_env.read().decode().strip())

    _, o4, _ = client.exec_command(
        "pm2 restart telegram-backend --update-env 2>/dev/null; "
        "sleep 3; curl -s http://127.0.0.1:8000/whatsapp/status",
        timeout=45,
    )
    print("Post-restart /whatsapp/status:", o4.read().decode().strip())

    webhook_test = (
        f"cd /opt/telegramforward && PYTHONPATH=/opt/telegramforward "
        "/opt/telegramforward/venv/bin/python -c \""
        "from dotenv import load_dotenv; load_dotenv('/opt/telegramforward/.env'); "
        "import asyncio, json; "
        "from services.whatsapp_inbox_service import process_webhook_payload; "
        "p={'type':'message_received','data':{'customer':{'phone_number':'919876543210',"
        "'name':'WA Deploy Test'},'message':{'id':'deploy_test_1','message_type':'text',"
        "'text':'Hello from deploy verification'}}}; "
        "print(json.dumps(asyncio.run(process_webhook_payload(p))))\""
    )
    _, o5, _ = client.exec_command(webhook_test, timeout=30)
    print("Webhook inject:", o5.read().decode().strip()[:240])

    _, o6, _ = client.exec_command(
        "curl -s https://teleautomation.online/whatsapp/status | head -c 200",
        timeout=20,
    )
    print("Public /whatsapp/status:", o6.read().decode().strip())

    client.close()
    print(f"\nDone — hard refresh Ctrl+Shift+R (stamp {BUILD_STAMP})")
    print("https://teleautomation.online — Inbox → account1 → look for WA Deploy Test thread")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
