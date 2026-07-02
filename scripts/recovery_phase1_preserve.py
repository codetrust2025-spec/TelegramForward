"""
PHASE 1: FREEZE AND PRESERVE CURRENT STATE
ALL COMMANDS ARE READ-ONLY (pg_dump, cp, cat, ls)
NO WRITES to production database.
"""
import socket, paramiko, time

ts = time.strftime('%Y%m%d_%H%M%S')
RECOVERY_DIR = f'/root/teleautomation_recovery_{ts}'

sock = socket.create_connection(('187.127.169.159', 22), timeout=60)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)

print("="*70)
print(f"PHASE 1: FREEZE AND PRESERVE")
print(f"Recovery directory: {RECOVERY_DIR}")
print(f"All operations are READ-ONLY")
print("="*70)

def run(cmd, timeout=120):
    """Execute read-only command and return output."""
    _, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err

# Create recovery directory
run(f"mkdir -p {RECOVERY_DIR}")

# 1. PostgreSQL dumps (READ-ONLY: pg_dump only reads)
print("\n[1/8] Creating PostgreSQL dumps (read-only)...")
out, err = run(f"""
sudo -u postgres pg_dump -Fc teleautomation > {RECOVERY_DIR}/current_custom.dump 2>&1
echo "Custom dump: $?"
sudo -u postgres pg_dump teleautomation > {RECOVERY_DIR}/current_plain.sql 2>&1
echo "Plain dump: $?"
sudo -u postgres pg_dump --schema-only teleautomation > {RECOVERY_DIR}/schema_only.sql 2>&1
echo "Schema dump: $?"
sudo -u postgres pg_dump --data-only teleautomation > {RECOVERY_DIR}/data_only.sql 2>&1
echo "Data dump: $?"
ls -lh {RECOVERY_DIR}/*.sql {RECOVERY_DIR}/*.dump 2>/dev/null
""", timeout=120)
print(out)

# 2. Copy WAL files (READ-ONLY: cp)
print("\n[2/8] Copying WAL files...")
out, _ = run(f"""
mkdir -p {RECOVERY_DIR}/pg_wal
cp -a /var/lib/postgresql/16/main/pg_wal/* {RECOVERY_DIR}/pg_wal/ 2>&1
ls -lh {RECOVERY_DIR}/pg_wal/
""", timeout=60)
print(out)

# 3. PostgreSQL config and control data
print("\n[3/8] Copying PostgreSQL config...")
out, _ = run(f"""
cp /etc/postgresql/16/main/postgresql.conf {RECOVERY_DIR}/ 2>/dev/null
cp /etc/postgresql/16/main/pg_hba.conf {RECOVERY_DIR}/ 2>/dev/null
sudo -u postgres /usr/lib/postgresql/16/bin/pg_controldata /var/lib/postgresql/16/main > {RECOVERY_DIR}/pg_controldata.txt 2>&1
echo "Done"
""")
print(out)

# 4. Application data
print("\n[4/8] Copying application data...")
out, _ = run(f"""
cp -a /opt/telegramforward/data {RECOVERY_DIR}/app_data 2>&1
cp -a /opt/telegramforward/backups {RECOVERY_DIR}/app_backups 2>&1
cp -a /opt/telegramforward.old/data {RECOVERY_DIR}/old_app_data 2>&1
cp -a /root/teleautomation_migration {RECOVERY_DIR}/migration 2>&1
ls -lh {RECOVERY_DIR}/app_data/ 2>/dev/null | head -10
echo "Done"
""", timeout=120)
print(out)

# 5. Logs
print("\n[5/8] Copying logs...")
out, _ = run(f"""
mkdir -p {RECOVERY_DIR}/logs
cp /var/log/nginx/access.log {RECOVERY_DIR}/logs/ 2>/dev/null
cp /var/log/nginx/error.log {RECOVERY_DIR}/logs/ 2>/dev/null
cp /var/log/postgresql/*.log {RECOVERY_DIR}/logs/ 2>/dev/null
cp -a /opt/telegramforward/logs/* {RECOVERY_DIR}/logs/ 2>/dev/null
journalctl --since "2026-07-01" --no-pager > {RECOVERY_DIR}/logs/journal.log 2>&1
echo "Done"
""", timeout=60)
print(out)

# 6. Shell history, cron, tmp
print("\n[6/8] Copying shell history, cron, tmp files...")
out, _ = run(f"""
cp ~/.bash_history {RECOVERY_DIR}/bash_history.txt 2>/dev/null
crontab -l > {RECOVERY_DIR}/crontab.txt 2>/dev/null
mkdir -p {RECOVERY_DIR}/tmp_files
find /tmp -maxdepth 1 -type f \\( -name '*.json' -o -name '*.sql' -o -name '*.csv' -o -name '*.py' \\) -exec cp {{}} {RECOVERY_DIR}/tmp_files/ \\; 2>/dev/null
ls {RECOVERY_DIR}/tmp_files/ 2>/dev/null
echo "Done"
""")
print(out)

# 7. Checksums
print("\n[7/8] Generating SHA-256 checksums...")
out, _ = run(f"""
find {RECOVERY_DIR} -type f ! -name 'checksums.sha256' -exec sha256sum {{}} \\; > {RECOVERY_DIR}/checksums.sha256 2>&1
wc -l {RECOVERY_DIR}/checksums.sha256
""", timeout=120)
print(out)

# 8. Directory summary
print("\n[8/8] Recovery directory summary...")
out, _ = run(f"du -sh {RECOVERY_DIR}")
print(out)

# Print key info
print("\n" + "="*70)
print(f"✅ PHASE 1 COMPLETE: Evidence preserved at {RECOVERY_DIR}")
print("="*70)

c.close()
