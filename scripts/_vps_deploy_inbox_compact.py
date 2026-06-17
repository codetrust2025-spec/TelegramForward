"""Deploy compact Telegram-style inbox layout to production."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = [
    "dashboard/src/main.jsx",
    "dashboard/src/context/AuthContext.jsx",
    "dashboard/src/components/AuthGate.jsx",
    "dashboard/src/components/LoginScreen.jsx",
    "dashboard/src/inbox/outgoingCall.css",
    "dashboard/src/inbox/OutgoingCallOverlay.jsx",
    "dashboard/src/inbox/CallStatusBar.jsx",
    "dashboard/src/utils/calls.js",
    "dashboard/src/utils/voiceCallApi.js",
    "dashboard/src/inbox/useTelegramVoiceCall.js",
    "dashboard/src/inbox/voiceCallEvents.js",
    "dashboard/src/App.jsx",
    "dashboard/src/utils/statsResetConfirm.js",
    "dashboard/src/utils/fleetReachHelp.js",
    "dashboard/src/components/ui/MetricBlock.jsx",
    "dashboard/src/components/ConfirmDialog.jsx",
    "dashboard/src/context/ConfirmContext.jsx",
    "dashboard/src/components/ModesSetupPanel.jsx",
    "dashboard/src/components/AccountModeSwitcher.jsx",
    "dashboard/src/components/AccountPrimaryActions.jsx",
    "dashboard/src/components/SetupAccountPicker.jsx",
    "dashboard/src/components/GlobalWorkspaceMode.jsx",
    "dashboard/src/utils/workspaceMode.js",
    "dashboard/src/components/PostingModePanel.jsx",
    "dashboard/src/components/MessageEditor.jsx",
    "dashboard/src/components/ProgressHubPanel.jsx",
    "features/interval_forward.py",
    "core/config.py",
    "core/fleet_defaults.py",
    "core/posting_mode.py",
    "services/fleet_setup_service.py",
    "dashboard/src/components/FleetDefaultsPanel.jsx",
    "core/account_features.py",
    "core/message_store.py",
    "dashboard/src/utils/forwardAccountUtils.js",
    "workers/account_worker.py",
    "services/forward_message_service.py",
    "dashboard/src/components/ForwardMessagePanel.jsx",
    "server.py",
    "core/dashboard_auth.py",
    "core/dashboard_auth_vps.py",
    "core/dashboard_auth_api.py",
    "core/dm_media.py",
    "core/dm_store.py",
    "core/call_store.py",
    "services/dm_inbox_service.py",
    "services/spam_guard_service.py",
    "core/spam_detector.py",
    "core/account_info_store.py",
    "dashboard/src/components/AccountNameEditor.jsx",
    "dashboard/src/components/AccountCard.jsx",
    "services/account_manager.py",
    "core/voice_call_api.py",
    "core/voice_call_store.py",
    "core/voice_signaling.py",
    "services/voice_call_service.py",
    "services/telegram_call_service.py",
    "services/tgcalls_service.py",
    "dashboard/src/index.css",
    "dashboard/src/components/DailyStatsPanel.jsx",
    "dashboard/src/components/AccountPanel.jsx",
    "dashboard/src/components/AccountCard.jsx",
    "dashboard/src/components/ShutdownListPanel.jsx",
    "dashboard/src/utils/accountUi.js",
    "dashboard/src/responsive.css",
    "dashboard/src/inbox/inboxLayout.css",
    "dashboard/src/inbox/InboxSidebarTools.jsx",
    "dashboard/src/inbox/VirtualList.jsx",
    "dashboard/src/inbox/VirtualConversationList.jsx",
    "dashboard/src/inbox/VirtualList.jsx",
    "dashboard/src/inbox/ConversationListItem.jsx",
    "dashboard/src/inbox/MessageBubble.jsx",
    "dashboard/src/inbox/MessageBubbleText.jsx",
    "dashboard/src/inbox/InboxMediaImage.jsx",
    "dashboard/src/inbox/InboxMediaAttachment.jsx",
    "dashboard/src/inbox/inboxUiUtils.js",
    "dashboard/src/inbox/MessageTimeline.jsx",
    "dashboard/src/inbox/ChatHeader.jsx",
    "dashboard/src/inbox/InboxMarketingMessageModal.jsx",
    "dashboard/src/utils/messagePreviewHtml.js",
    "dashboard/src/inbox/ChatComposer.jsx",
    "dashboard/src/inbox/inboxUiUtils.js",
    "dashboard/src/utils/inboxDrafts.js",
    "dashboard/src/utils/inboxScrollCache.js",
    "dashboard/src/utils/inboxMessageUtils.js",
    "dashboard/src/components/InboxPanel.jsx",
    "dashboard/src/components/crm/CRMInboxList.jsx",
    "dashboard/src/components/crm/ChatWindow.jsx",
    "dashboard/src/App.jsx",
    "dashboard/src/components/crm/DeleteChatModal.jsx",
    "dashboard/src/components/crm/LeadDetailsPanel.jsx",
    "dashboard/src/utils/deleteChat.js",
    "dashboard/src/utils/karthikSpam.js",
    "dashboard/src/utils/crm.js",
]

REMOTE_CMDS = [
    f"cd {REMOTE}/dashboard && npm run build",
    "pm2 restart telegram-backend --update-env",
    f"grep -l tg-inbox-shell $(ls -t {REMOTE}/static/assets/*.css 2>/dev/null | head -1)",
    f"grep -l tg-sidebar-head $(ls -t {REMOTE}/static/assets/*.css 2>/dev/null | head -1)",
    f"grep -l voice/calls/start $(ls -t {REMOTE}/static/assets/*.js 2>/dev/null | head -1)",
    'curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:8000/voice/calls/start -H "Content-Type: application/json" -d "{}" || true',
]


def main() -> int:
    if not PASSWORD:
        print("VPS_PASSWORD not set", file=sys.stderr)
        return 1

    import paramiko

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {USER}@{HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()

    for rel in FILES:
        local = os.path.join(repo, rel.replace("/", os.sep))
        remote = f"{REMOTE}/{rel}"
        remote_dir = os.path.dirname(remote).replace("\\", "/")
        parts = remote_dir.split("/")
        path = ""
        for p in parts:
            if not p:
                continue
            path += f"/{p}"
            try:
                sftp.stat(path)
            except OSError:
                try:
                    sftp.mkdir(path)
                except OSError:
                    pass
        print(f"  upload {rel}")
        sftp.put(local, remote)

    sftp.close()

    for cmd in REMOTE_CMDS:
        print(f"\n>>> {cmd}")
        _, stdout, stderr = client.exec_command(cmd, get_pty=True, timeout=600)
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        code = stdout.channel.recv_exit_status()
        if out:
            print(out[-4000:])
        if err.strip():
            print(err[-1500:], file=sys.stderr)
        if code != 0:
            client.close()
            return code

    _, o, _ = client.exec_command(
        f"ls -t {REMOTE}/static/assets/*.css {REMOTE}/static/assets/*.js 2>/dev/null | head -2",
        timeout=30,
    )
    print("\nAssets:", o.read().decode().strip())
    client.close()
    print("\nDeploy OK — hard refresh: Ctrl+Shift+R on https://teleautomation.online")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
