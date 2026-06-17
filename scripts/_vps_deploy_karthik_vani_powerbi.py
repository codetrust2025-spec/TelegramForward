"""Deploy Karthik→Vani data routing + Power BI campaign message to VPS."""
from __future__ import annotations

import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOST = "187.127.169.159"
USER = "root"
REMOTE = "/opt/telegramforward"
PASSWORD = os.environ.get("VPS_PASSWORD", "")

FILES = [
    "core/config.py",
    "core/ai_smart_reply.py",
    "core/ai_smart_reply_store.py",
    "data/ai_smart_reply.json",
]

VANI_PHONE = "+91 90323 88581"
VANI_WA = "https://wa.me/919032388581"


def _patch_business_prompt(text: str) -> str:
    if not text:
        return text
    out = text
    replacements = [
        ("Satya garu (most senior in data", "Vani garu (senior data analyst"),
        ("Satya garu (most senior — data", "Vani garu (senior data analyst"),
        ("Data/analytics → Satya", "Data/analytics/Power BI → Vani"),
        ("Data/analytics roles → Satya", "Data/analytics/Power BI → Vani"),
        ("→ Satya 📞 +91 78934 12359", f"→ Vani 📞 {VANI_PHONE}"),
        ("Satya 📞 +91 78934 12359", f"Vani 📞 {VANI_PHONE}"),
        ("+91 78934 12359", VANI_PHONE),
        ("https://wa.me/917893412359", VANI_WA),
        ("Satya explains and closes data", "Vani explains and closes data"),
        ("hand off to Satya", "hand off to Vani"),
        ("Handed off to senior for convincing (Satya /", "Handed off to senior for convincing (Vani /"),
        ("Satya / Kalyan", "Vani / Kalyan"),
        ("(Satya, Kalyan", "(Vani, Kalyan"),
    ]
    for old, new in replacements:
        out = out.replace(old, new)
    if "Karthik on data/Power BI" not in out:
        marker = "Data Analyst & Analytics roles"
        if marker in out:
            insert = (
                "\n\nKARTHIK + VANI — POWER BI / DATA ANALYST (STRICT)\n"
                "- Karthik (inbox): greet, confirm tech stack (Power BI, SQL, Tableau, DAX, etc.), "
                "interview date/time, round type — first-level filter only.\n"
                "- Karthik must NEVER quote ₹ amounts, payment, UPI, or slot fees on data/BI leads.\n"
                "- When tech is Power BI / data / analytics related OR user asks price/payment/process → "
                f"hand off to Vani (senior data analyst) with contacts: 📞 {VANI_PHONE} 📲 {VANI_WA}\n"
            )
            out = out.replace(marker, insert + marker, 1)
    return out


def main() -> None:
    try:
        import paramiko
    except ImportError:
        print("pip install paramiko", file=sys.stderr)
        sys.exit(1)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not PASSWORD:
        print("Set VPS_PASSWORD", file=sys.stderr)
        sys.exit(1)

    json_path = os.path.join(root, "data", "ai_smart_reply.json")
    if os.path.isfile(json_path):
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        bp = (data.get("config") or {}).get("business_prompt") or ""
        patched = _patch_business_prompt(bp)
        if patched != bp:
            data["config"]["business_prompt"] = patched
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("Patched local data/ai_smart_reply.json business_prompt")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = ssh.open_sftp()

    for rel in FILES:
        local = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(local):
            print(f"skip missing {rel}")
            continue
        remote = f"{REMOTE}/{rel}"
        remote_dir = os.path.dirname(remote).replace("\\", "/")
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            parts = remote_dir.split("/")
            acc = ""
            for p in parts:
                if not p:
                    continue
                acc = f"{acc}/{p}" if acc else f"/{p}"
                try:
                    sftp.mkdir(acc)
                except OSError:
                    pass
        sftp.put(local, remote)
        print(f"uploaded {rel}")

    msg_path = os.path.join(root, "data", "custom_message.txt")
    if os.path.isfile(msg_path):
        with open(msg_path, encoding="utf-8") as f:
            msg = f.read()
        for target in (
            f"{REMOTE}/data/custom_message.txt",
            f"{REMOTE}/data/message.txt",
        ):
            with sftp.open(target, "w") as rf:
                rf.write(msg)
            print(f"uploaded campaign text -> {target}")

    cmd = (
        f"cd {REMOTE} && "
        "PYTHONPATH=/opt/telegramforward pm2 restart telegram-backend --update-env"
    )
    _, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode("utf-8", errors="replace"))
    err = stderr.read().decode("utf-8", errors="replace")
    if err.strip():
        print(err, file=sys.stderr)
    sftp.close()
    ssh.close()
    print("Done — hard refresh dashboard (Ctrl+Shift+R)")


if __name__ == "__main__":
    main()
