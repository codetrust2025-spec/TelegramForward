#!/usr/bin/env python3
"""Inspect VPS backup folders safely — do not delete anything."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "8897870998s@SS"

commands = [
    ("Step 1A: Size of telegramforward.old", "du -sh /opt/telegramforward.old/"),
    ("Step 1B: Contents of telegramforward.old (top)", "ls -lah /opt/telegramforward.old/ | head -50"),
    ("Step 1C: Size of current telegramforward", "du -sh /opt/telegramforward/"),
    ("Step 1D: Contents of current telegramforward (top)", "ls -lah /opt/telegramforward/ | head -50"),
    ("Step 2A: All old backup dirs", "du -sh /opt/telegramforward_old_* 2>/dev/null; du -sh /opt/telegramforward_backup_* 2>/dev/null"),
    ("Step 2B: Disk free", "df -h /"),
    ("Step 3A: Data/uploads in .old", "ls -lah /opt/telegramforward.old/data/ 2>/dev/null | head -20"),
    ("Step 3B: Data/uploads in current", "ls -lah /opt/telegramforward/data/ 2>/dev/null | head -20"),
    ("Step 3C: .env in .old", "cat /opt/telegramforward.old/.env 2>/dev/null | head -5 || echo 'No .env'"),
    ("Step 3D: .env in current", "cat /opt/telegramforward/.env 2>/dev/null | head -5 || echo 'No .env'"),
    ("Step 3E: Proofs in .old", "du -sh /opt/telegramforward.old/data/candidates_proofs 2>/dev/null || echo 'No proofs dir'"),
    ("Step 3F: Proofs in current", "du -sh /opt/telegramforward/data/candidates_proofs 2>/dev/null || echo 'No proofs dir'"),
    ("Step 4A: PM2 process details", "pm2 describe telegram-backend 2>/dev/null | grep -E 'script path|cwd|exec_interpreter|pid|status'"),
    ("Step 4B: Python processes", "ps aux | grep -i python | grep -v grep"),
    ("Step 4C: Nginx status", "systemctl is-active nginx"),
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to VPS...")
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

for name, cmd in commands:
    print(f"\n{'─'*60}")
    print(f"  {name}")
    print(f"{'─'*60}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(out or err or "(no output)")

ssh.close()
print("\n\n✓ Inspection complete. No files deleted.")
