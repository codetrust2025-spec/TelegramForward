#!/usr/bin/env python3
"""Delete old backup directories safely. Do NOT touch .old or current app."""
import paramiko

VPS_HOST = "187.127.169.159"
VPS_USER = "root"
VPS_PASSWORD = "REMOVED_VPS_PASSWORD"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print("Connecting to VPS...")
ssh.connect(VPS_HOST, username=VPS_USER, password=VPS_PASSWORD, timeout=30)

def run(cmd, label=""):
    if label:
        print(f"\n{'─'*50}\n  {label}\n{'─'*50}")
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    if out:
        print(out)
    if err:
        print(f"  STDERR: {err}")
    return out

# Pre-deletion safety checks
run("pwd", "Current directory")
run("pm2 list --no-color | grep -E 'telegram|advocate'", "PM2 processes")
run("df -h /", "Disk BEFORE deletion")
run("du -sh /opt/telegramforward_old_* 2>/dev/null | wc -l", "Count of _old_ dirs")
run("du -sh /opt/telegramforward_backup_* 2>/dev/null | wc -l", "Count of _backup_ dirs")

print("\n" + "="*50)
print("  DELETING OLD BACKUP DIRECTORIES...")
print("="*50)

# Delete old snapshot directories
run("rm -rf /opt/telegramforward_old_*", "Deleting /opt/telegramforward_old_*")
run("rm -rf /opt/telegramforward_backup_*", "Deleting /opt/telegramforward_backup_*")

print("\n" + "="*50)
print("  POST-DELETION VERIFICATION")
print("="*50)

# Verify after deletion
run("df -h /", "Disk AFTER deletion")
run("du -sh /opt/telegramforward/", "Current app size")
run("pm2 list --no-color | grep -E 'telegram|advocate'", "PM2 still running")
run("systemctl is-active nginx", "Nginx status")
run("curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/public/slots/candidates", "App API check")
run("du -sh /opt/telegramforward_old_* 2>/dev/null | head -3 || echo 'All _old_ dirs deleted'", "Verify _old_ gone")
run("du -sh /opt/telegramforward_backup_* 2>/dev/null | head -3 || echo 'All _backup_ dirs deleted'", "Verify _backup_ gone")

# Check .old directory nature
print("\n" + "="*50)
print("  INVESTIGATING /opt/telegramforward.old/")
print("="*50)

run("ls -ld /opt/telegramforward /opt/telegramforward.old", "Directory listing")
run("stat /opt/telegramforward /opt/telegramforward.old 2>&1 | grep -E 'File:|Inode:|Device:'", "Stat (inode check)")
run("findmnt | grep telegramforward || echo 'No mounts found'", "Mount check")
run("mount | grep telegramforward || echo 'No mounts'", "Mount grep")
run("readlink -f /opt/telegramforward", "Resolved path: current")
run("readlink -f /opt/telegramforward.old", "Resolved path: .old")

ssh.close()
print("\n\n✓ Cleanup complete.")
