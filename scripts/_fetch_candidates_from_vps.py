"""Download teleautomation-app.jsx and extract CandidatesPanel for local restore."""
from __future__ import annotations

import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import paramiko

HOST, USER = "187.127.169.159", "root"
REMOTE = "/opt/telegramforward"
PWD = os.environ.get("VPS_PASSWORD", "")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "scripts", "_vps_extract")
TA_PATH = f"{REMOTE}/dashboard/src/teleautomation-app.jsx"


def main() -> None:
    if not PWD:
        print("Set VPS_PASSWORD")
        sys.exit(1)

    os.makedirs(OUT_DIR, exist_ok=True)
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PWD, timeout=30)

    sftp = c.open_sftp()
    local_ta = os.path.join(OUT_DIR, "teleautomation-app.jsx")
    print("Downloading", TA_PATH)
    sftp.get(TA_PATH, local_ta)
    panel_remote = f"{REMOTE}/dashboard/src/components/CandidatesPanel.jsx"
    panel_local = os.path.join(REPO, "dashboard", "src", "components", "CandidatesPanel.jsx")
    print("Downloading panel to", panel_local)
    sftp.get(panel_remote, panel_local)
    print("Panel bytes", os.path.getsize(panel_local))

    for rel in ("features/candidate_store.py", "features/handler_expenses.py"):
        remote = f"{REMOTE}/{rel}"
        local = os.path.join(OUT_DIR, os.path.basename(rel))
        try:
            sftp.get(remote, local)
            print("Downloaded", rel)
        except OSError as e:
            print("Skip", rel, e)
    sftp.close()
    c.close()

    text = open(local_ta, encoding="utf-8", errors="replace").read()
    for pat in (
        r"function CandidatesPanel",
        r"CandidatesPanel\s*=",
        r"cand-page",
        r"/candidates",
    ):
        m = re.search(pat, text)
        print(pat, "->", m.start() if m else "not found")

    # Line numbers for cand-page
    lines = text.splitlines()
    hits = [i + 1 for i, ln in enumerate(lines) if "cand-page" in ln or "CandidatesPanel" in ln][:40]
    print("line hits (first 40):", hits[:40])

    # Try to find function CandidatesPanel block
    start = text.find("function CandidatesPanel")
    if start < 0:
        start = text.find("function CandidatesTracker")
    if start < 0:
        # search export
        for name in ("CandidatesPanel", "CandidatesView", "CandidatesTracker"):
            idx = text.find(f"function {name}")
            if idx >= 0:
                start = idx
                print("Found", name, "at", idx)
                break

    if start < 0:
        print("Could not locate Candidates component start")
        sys.exit(2)

    # Brace-match from function start
    i = text.find("{", start)
    depth = 0
    end = i
    for j in range(i, len(text)):
        ch = text[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = j + 1
                break

    chunk = text[start:end]
    out_panel = os.path.join(OUT_DIR, "CandidatesPanel.extracted.jsx")
    with open(out_panel, "w", encoding="utf-8") as f:
        f.write(chunk)
    print("Wrote", out_panel, "chars", len(chunk))


if __name__ == "__main__":
    main()
