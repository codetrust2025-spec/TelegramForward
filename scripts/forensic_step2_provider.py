"""FORENSIC - STEP 2: Identify VPS provider and check snapshot availability.
READ-ONLY. No production modifications."""
import socket, paramiko

sock = socket.create_connection(('187.127.169.159', 22), timeout=30)
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('187.127.169.159', username='root', password='REMOVED_VPS_PASSWORD', sock=sock)

print("="*70)
print("STEP 2: VPS PROVIDER IDENTIFICATION & SNAPSHOT CHECK")
print("="*70)

# Identify provider
print("\n[2.1] Detecting hosting provider...")
_, stdout, _ = c.exec_command("""
echo "--- System vendor ---"
cat /sys/class/dmi/id/sys_vendor 2>/dev/null || echo "unknown"

echo "--- Product name ---"
cat /sys/class/dmi/id/product_name 2>/dev/null || echo "unknown"

echo "--- Hostnamectl ---"
hostnamectl 2>/dev/null | grep -iE "static|chassis|vendor|virtualization"

echo "--- Cloud-init datasource ---"
grep -i datasource /etc/cloud/cloud.cfg 2>/dev/null | head -3
cat /run/cloud-init/ds-identify.log 2>/dev/null | grep -i "found\|selected" | head -5

echo "--- IP/hostname clues ---"
hostname -f 2>/dev/null
cat /etc/hostname

echo "--- Metadata endpoints ---"
curl -s --connect-timeout 2 http://169.254.169.254/metadata/v1/id 2>/dev/null && echo " [DigitalOcean]"
curl -s --connect-timeout 2 http://169.254.169.254/latest/meta-data/instance-id 2>/dev/null && echo " [AWS/EC2]"
curl -s --connect-timeout 2 -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/id 2>/dev/null && echo " [GCP]"
curl -s --connect-timeout 2 http://169.254.169.254/v1.json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('label',''), '[Vultr]')" 2>/dev/null
curl -s --connect-timeout 2 http://169.254.169.254/hetzner/v1/metadata 2>/dev/null && echo " [Hetzner]"
""", timeout=30)
print(stdout.read().decode())

# Check for provider CLI tools
print("\n[2.2] Checking for provider CLI tools...")
_, stdout2, _ = c.exec_command("""
echo "--- Installed CLIs ---"
which doctl aws gcloud vultr-cli hcloud linode-cli 2>/dev/null
ls ~/.config/doctl/config.yaml 2>/dev/null && echo "doctl configured"
ls ~/.aws/credentials 2>/dev/null && echo "AWS configured"
ls ~/.config/hcloud/cli.toml 2>/dev/null && echo "hcloud configured"
""", timeout=30)
print(stdout2.read().decode())

# PITR feasibility
print("\n" + "="*70)
print("STEP 3: POSTGRESQL PITR FEASIBILITY")
print("="*70)

_, stdout3, _ = c.exec_command("""
echo "--- PostgreSQL version ---"
/usr/lib/postgresql/16/bin/postgres --version 2>/dev/null || psql --version

echo ""
echo "--- Critical settings ---"
sudo -u postgres psql -t -c "SELECT name, setting FROM pg_settings WHERE name IN ('archive_mode','archive_command','wal_level','max_wal_senders','wal_keep_size','restore_command');" 2>/dev/null

echo ""
echo "--- Replication slots ---"
sudo -u postgres psql -c "SELECT slot_name, slot_type, active FROM pg_replication_slots;" 2>/dev/null

echo ""
echo "--- WAL files on disk ---"
ls -lth /var/lib/postgresql/16/main/pg_wal/*.* 2>/dev/null | head -10

echo ""
echo "--- pg_controldata (key fields) ---"
sudo -u postgres /usr/lib/postgresql/16/bin/pg_controldata /var/lib/postgresql/16/main 2>/dev/null | grep -E "checkpoint|Timeline|WAL|backup"

echo ""
echo "--- Base backup existence ---"
find / -maxdepth 4 -name 'backup_manifest' -o -name 'base.tar*' -o -name 'pg_basebackup*' 2>/dev/null | grep -v proc | head -5
ls /var/lib/postgresql/16/main/backup_label 2>/dev/null && cat /var/lib/postgresql/16/main/backup_label
""", timeout=30)
print(stdout3.read().decode())

# STEP 4: Identify what pg_save did
print("\n" + "="*70)
print("STEP 4: WHAT DID pg_save() DO?")
print("="*70)

_, stdout4, _ = c.exec_command("""
cat /opt/telegramforward/core/db/candidates_pg.py
""", timeout=30)
print(stdout4.read().decode())

# STEP 5: Check all database tables
print("\n" + "="*70)
print("STEP 5: DATABASE TABLES & ROW COUNTS")
print("="*70)

_, stdout5, _ = c.exec_command("""
sudo -u postgres psql teleautomation << 'SQL'
SELECT schemaname, tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;

SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY relname;
SQL
""", timeout=30)
print(stdout5.read().decode())

c.close()

print("\n" + "="*70)
print("FINDINGS & NEXT STEPS")
print("="*70)
