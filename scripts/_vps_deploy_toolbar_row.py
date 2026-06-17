"""Deploy single-row CRM inbox toolbar CSS."""
from __future__ import annotations

import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER, REMOTE = "187.127.169.159", "root", "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CSS_BLOCK = """
/* CRM Inbox: one toolbar row; when a chat is open, use the chat header only */
.inbox-root:not(.inbox-root--chat-open) .crm-inbox-toolbar {
  flex-direction: row;
  align-items: center;
  flex-wrap: nowrap;
  gap: 8px;
  padding: 4px 8px 6px;
}

.inbox-root:not(.inbox-root--chat-open) .crm-stats-bar {
  margin-bottom: 0;
  flex-wrap: nowrap;
  padding: 4px 8px;
}

.inbox-root:not(.inbox-root--chat-open) .call-analytics {
  display: none;
}

.crm-inbox-toolbar {
  flex-direction: row;
  align-items: center;
  flex-wrap: nowrap;
}

.crm-inbox-toolbar--chat-open,
.inbox-root--chat-open .crm-inbox-toolbar {
  display: none !important;
}

.call-analytics {
  flex-direction: row;
  align-items: center;
  gap: 10px;
  padding: 0;
  min-width: 0;
}

.call-analytics-title {
  margin: 0;
  white-space: nowrap;
  font-size: 10px;
}

.call-analytics-grid {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
}

.call-analytics-stat {
  min-width: auto;
}

.inbox-root--chat-open .wa-chat-header-actions .ai-toolbar-btn,
.inbox-root--chat-open .inbox-chat-header-actions .ai-toolbar-btn,
.inbox-root--chat-open .wa-chat-header-actions .crm-buzzer-toggle,
.inbox-root--chat-open .inbox-chat-header-actions .crm-buzzer-toggle {
  display: none !important;
}
"""

MARKER = "/* CRM Inbox: one toolbar row"


def main() -> int:
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)
    sftp = c.open_sftp()

    local_css = os.path.join(REPO, "dashboard", "src", "index.css")
    sftp.put(local_css, f"{REMOTE}/dashboard/src/index.css")
    print("uploaded index.css")

    for rel in ("dashboard/src/teleautomation.css",):
        path = f"{REMOTE}/{rel}"
        try:
            with sftp.open(path, "r") as f:
                content = f.read().decode("utf-8", errors="replace")
        except FileNotFoundError:
            continue
        if MARKER not in content:
            content = content.rstrip() + "\n" + CSS_BLOCK + "\n"
            with sftp.open(path, "w") as f:
                f.write(content.encode("utf-8"))
            print("appended to", rel)
        else:
            print("marker already in", rel)

    sftp.close()

    cmds = [
        f"cd {REMOTE}/dashboard && npm run build 2>&1 | tail -8",
        f"cd {REMOTE} && node scripts/_patch_confirm.js 2>&1",
    ]
    for cmd in cmds:
        print(">>>", cmd[:90])
        _, o, _ = c.exec_command(cmd, timeout=300000)
        print(o.read().decode("utf-8", errors="replace")[-1500:])
    c.close()
    print("Done — hard refresh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
