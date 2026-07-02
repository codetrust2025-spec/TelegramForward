"""FORENSIC PRESERVATION - READ ONLY - DO NOT MODIFY PRODUCTION.

Step 1: Copy all evidence to /root/teleautomation_forensic_20260702/
Step 2: Check VPS provider for snapshots
Step 3: Gather PITR feasibility data

ALL COMMANDS ARE READ-ONLY (cp, cat, ls, pg_controldata, etc.)
NO WRITES to production database or application data.
"""
import socket, paramiko, time

ts = time.strftime('%Y%m%d_%H%M%S')
FORENSIC_DIR = f'/root/teleautomation_forensic_{ts}'

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)

print("="*70)
print(f"FORENSIC EVIDENCE PRESERVATION")
print(f"Target: {FORENSIC_DIR}")
print(f"Mode: READ-ONLY — no production modifications")
print("="*70)

# ─── STEP 1: Create forensic evidence directory ───────────────────────────

print("\n[STEP 1] Creating forensic evidence directory...")
_, stdout, _ = c.exec_command(f"mkdir -p {FORENSIC_DIR}", timeout=30)
stdout.read()

# 1a. Copy PostgreSQL data directory (includes WAL)
print("  Copying PostgreSQL data directory...")
_, stdout, _ = c.exec_command(f"""
cp -a /var/lib/postgresql/16/main {FORENSIC_DIR}/pg_data_main 2>&1 | tail -3
cp /etc/postgresql/16/main/postgresql.conf {FORENSIC_DIR}/ 2>/dev/null
cp /etc/postgresql/16/main/pg_hba.conf {FORENSIC_DIR}/ 2>/dev/null
sudo -u postgres /usr/lib/postgresql/16/bin/pg_controldata /var/lib/postgresql/16/main > {FORENSIC_DIR}/pg_controldata.txt 2>&1
echo "DONE: pg_data"
""", timeout=120)
print(f"  {stdout.read().decode().strip()}")

# 1b. Copy application directories
print("  Copying application data...")
_, stdout, _ = c.exec_command(f"""
cp -a /opt/telegramforward/data {FORENSIC_DIR}/app_data 2>&1 | tail -1
cp -a /opt/telegramforward/backups {FORENSIC_DIR}/app_backups 2>&1 | tail -1
cp -a /opt/telegramforward/logs {FORENSIC_DIR}/app_logs 2>&1 | tail -1
cp -a /opt/telegramforward.old/data {FORENSIC_DIR}/app_old_data 2>&1 | tail -1
cp -a /root/teleautomation_migration {FORENSIC_DIR}/migration_dump 2>&1 | tail -1
echo "DONE: app_data"
""", timeout=120)
print(f"  {stdout.read().decode().strip()}")

# 1c. Copy logs
print("  Copying logs...")
_, stdout, _ = c.exec_command(f"""
cp /var/log/nginx/access.log {FORENSIC_DIR}/nginx_access.log 2>/dev/null
cp /var/log/nginx/error.log {FORENSIC_DIR}/nginx_error.log 2>/dev/null
journalctl --since "2026-07-01" --no-pager > {FORENSIC_DIR}/journal_jul.log 2>&1
cp /var/log/postgresql/postgresql-16-main.log {FORENSIC_DIR}/ 2>/dev/null
echo "DONE: logs"
""", timeout=60)
print(f"  {stdout.read().decode().strip()}")

# 1d. Copy shell history, cron, tmp files
print("  Copying shell history, cron, tmp...")
_, stdout, _ = c.exec_command(f"""
cp ~/.bash_history {FORENSIC_DIR}/bash_history.txt 2>/dev/null
crontab -l > {FORENSIC_DIR}/crontab.txt 2>/dev/null
find /tmp -maxdepth 1 -type f -name '*.json' -o -name '*.sql' -o -name '*.csv' -o -name '*.py' 2>/dev/null | xargs -I{{}} cp {{}} {FORENSIC_DIR}/ 2>/dev/null
echo "DONE: misc"
""", timeout=30)
print(f"  {stdout.read().decode().strip()}")

# 1e. Generate checksums
print("  Generating SHA-256 checksums...")
_, stdout, _ = c.exec_command(f"""
find {FORENSIC_DIR} -type f -exec sha256sum {{}} \\; > {FORENSIC_DIR}/checksums.sha256 2>&1
wc -l {FORENSIC_DIR}/checksums.sha256
echo "DONE: checksums"
""", timeout=120)
print(f"  {stdout.read().decode().strip()}")

# 1f. Show forensic directory size
_, stdout, _ = c.exec_command(f"du -sh {FORENSIC_DIR}", timeout=30)
print(f"\n  📦 Forensic directory: {stdout.read().decode().strip()}")


# ─── STEP 2: CHECK VPS PROVIDER FOR SNAPSHOTS ────────────────────────────

print("\n" + "="*70)
print("[STEP 2] Checking VPS provider for snapshots")
print("="*70)

# Determine hosting provider
print("\n  Detecting hosting provider...")
_, stdout, _ = c.exec_command("""
# Check for provider metadata endpoints (read-only HTTP queries)
curl -s --connect-timeout 3 http://169.254.169.254/metadata/v1/ 2>/dev/null && echo "DIGITALOCEAN" || true
curl -s --connect-timeout 3 http://169.254.169.254/latest/meta-data/ 2>/dev/null && echo "AWS" || true
curl -s --connect-timeout 3 http://metadata.google.internal/computeMetadata/v1/ -H "Metadata-Flavor: Google" 2>/dev/null && echo "GCP" || true
curl -s --connect-timeout 3 http://169.254.169.254/openstack/latest/ 2>/dev/null && echo "OPENSTACK" || true
curl -s --connect-timeout 3 http://169.254.169.254/v1.json 2>/dev/null | head -5 && echo "VULTR" || true

# Check /etc for provider hints
cat /etc/cloud/cloud.cfg 2>/dev/null | grep -i "datasource\\|provider" | head -5
cat /sys/class/dmi/id/sys_vendor 2>/dev/null
cat /sys/class/dmi/id/product_name 2>/dev/null
hostnamectl 2>/dev/null | grep -i "vendor\\|chassis\\|virtual"
""", timeout=30)
provider_info = stdout.read().decode()
print(f"  {provider_info}")

# Check if any CLI tools are installed for snapshot management
print("\n  Checking for provider CLI tools...")
_, stdout2, _ = c.exec_command("""
which doctl 2>/dev/null && echo "DigitalOcean CLI found"
which aws 2>/dev/null && echo "AWS CLI found"
which gcloud 2>/dev/null && echo "GCloud CLI found"
which vultr-cli 2>/dev/null && echo "Vultr CLI found"
which hcloud 2>/dev/null && echo "Hetzner CLI found"
which linode-cli 2>/dev/null && echo "Linode CLI found"
ls /root/.config/doctl 2>/dev/null && echo "doctl config exists"
ls ~/.aws/credentials 2>/dev/null && echo "AWS creds exist"
""", timeout=30)
print(f"  {stdout2.read().decode()}")


# ─── STEP 3: POSTGRESQL PITR FEASIBILITY ─────────────────────────────────

print("\n" + "="*70)
print("[STEP 3] PostgreSQL PITR feasibility assessment")
print("="*70)

_, stdout3, _ = c.exec_command(f"""
echo "=== pg_controldata ==="
cat {FORENSIC_DIR}/pg_controldata.txt

echo ""
echo "=== PostgreSQL version ==="
/usr/lib/postgresql/16/bin/postgres --version

echo ""
echo "=== archive_mode and wal_level ==="
sudo -u postgres psql -c "SHOW archive_mode; SHOW wal_level; SHOW archive_command;" 2>/dev/null

echo ""
echo "=== Replication slots ==="
sudo -u postgres psql -c "SELECT * FROM pg_replication_slots;" 2>/dev/null

echo ""
echo "=== WAL files available ==="
ls -lth /var/lib/postgresql/16/main/pg_wal/ 2>/dev/null

echo ""
echo "=== Base backups ==="
ls -lth /var/lib/postgresql/16/main/pg_wal/archive_status/ 2>/dev/null
find / -name 'base.tar*' -o -name 'backup_manifest' 2>/dev/null | head -5

echo ""
echo "=== Timeline history ==="
ls /var/lib/postgresql/16/main/pg_wal/*.history 2>/dev/null || echo "No timeline history files"
""", timeout=60)
pitr_info = stdout3.read().decode()
print(pitr_info)


# ─── STEP 4: IDENTIFY AFFECTED TABLES ────────────────────────────────────

print("\n" + "="*70)
print("[STEP 4] Identifying affected tables (from pg_save code)")
print("="*70)

_, stdout4, _ = c.exec_command("""
# Read the pg_save function to understand what it did
cat /opt/telegramforward/core/db/candidates_pg.py
""", timeout=30)
pg_save_code = stdout4.read().decode()
print(pg_save_code)


# ─── STEP 5: SEARCH FOR SECONDARY COPIES ─────────────────────────────────

print("\n" + "="*70)
print("[STEP 5] Searching for secondary copies on VPS")
print("="*70)

_, stdout5, _ = c.exec_command("""
echo "=== nginx access log: recent /candidates API calls ==="
grep 'GET /candidates' /var/log/nginx/access.log 2>/dev/null | tail -20

echo ""
echo "=== Any exported CSV/Excel files ==="
find / -maxdepth 4 -name '*.csv' -o -name '*.xlsx' 2>/dev/null | grep -v proc | grep -v sys | head -10

echo ""
echo "=== Checking if there's a Redis cache ==="
redis-cli ping 2>/dev/null && redis-cli keys '*candidate*' 2>/dev/null | head -5 || echo "No Redis"

echo ""
echo "=== Checking for audit/history tables ==="
sudo -u postgres psql teleautomation -c "\\dt" 2>/dev/null
""", timeout=60)
print(stdout5.read().decode())

c.close()

print("\n" + "="*70)
print("FORENSIC PRESERVATION COMPLETE")
print("="*70)
print(f"""
Evidence preserved at: {FORENSIC_DIR}

CRITICAL NEXT STEPS FOR YOU:

1. DETERMINE YOUR VPS HOSTING PROVIDER
   Based on the output above, identify your provider.

2. CHECK FOR PROVIDER SNAPSHOTS
   Log into your VPS provider's control panel and check:
   - Automatic backups / snapshots
   - Any snapshot from BEFORE today 13:38 UTC (Jul 2, 2026)
   - Disk/volume backups

3. IF A SNAPSHOT EXISTS:
   - Do NOT restore it over the current VPS
   - Clone it to a NEW separate VPS
   - We can then extract the database from the clone

4. IF NO SNAPSHOT EXISTS:
   - We have limited recovery options
   - The June 17th dump is the most complete backup available
   - Partial reconstruction from logs/screenshots is possible

Please tell me:
- What is your VPS hosting provider? (DigitalOcean, Vultr, Hetzner, etc.)
- Can you log into the provider control panel to check for snapshots?
""")
